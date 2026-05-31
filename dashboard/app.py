"""
dashboard/app.py — KDP Pipeline Dashboard

Web UI for managing book generation, cleaning, and assembly.
Streams real-time output for long-running pipeline commands.

Usage:
    python3 dashboard/app.py
    # Open http://localhost:8000
"""

import asyncio
import io
import importlib.util
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Optional

# Ensure the root directory is in sys.path so we can import from pipeline
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from pipeline.config_io import read_config, write_config
from pipeline.prompt import STYLE_TAGS, POSE_TAGS, ELEMENT_TAGS, THEME_TAGS, GROUP_DYNAMICS

from storyforge.templates import list_templates as _sf_list_templates, load_template as _sf_load_template
from storyforge.identity import build_hero as _sf_build_hero, save_sheet as _sf_save_sheet, load_sheet as _sf_load_sheet
from storyforge.engine import resolve as _sf_resolve
from storyforge.generator import generate_page as _sf_generate_page
from storyforge.builder import build_book as _sf_build_book
from storyforge.i18n import translate_pages as _sf_translate_pages
from storyforge.expand import expand_narrative as _sf_expand_narrative
from storyforge.cover import generate_cover as _sf_generate_cover

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _resolve_gemini_api_key() -> str:
    """Resolve Gemini key from runtime env first, then dashboard settings files."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key

    settings_file = ROOT / "settings.json"
    if settings_file.exists():
        try:
            data = json.loads(settings_file.read_text())
            key = str(data.get("gemini_api_key", "")).strip()
            if key:
                return key
        except Exception:
            pass

    env_local = ROOT / ".env.local"
    if env_local.exists():
        try:
            content = env_local.read_text()
            m = re.search(r'^\s*GEMINI_API_KEY\s*=\s*"?([^"\n]+)"?\s*$', content, re.MULTILINE)
            if m:
                return m.group(1).strip()
        except Exception:
            pass

    return ""

app = FastAPI(title="KDP Dashboard")
templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent / "templates"))

from fastapi.staticfiles import StaticFiles as _StaticFiles
_ASSETS_DIR = ROOT / "assets"
_ASSETS_DIR.mkdir(exist_ok=True)
app.mount("/assets", _StaticFiles(directory=str(_ASSETS_DIR)), name="assets")


# ── Pydantic models ─────────────────────────────────────────────────────────────

class SettingsModel(BaseModel):
    gemini_api_key: str
    text_model: str
    image_model: str
    target_languages: str
    concurrency_limit: int
    default_width: float
    default_height: float
    global_prompt_suffix: str

class CharacterModel(BaseModel):
    id: str
    name: str
    series: str
    prompt: str
    source_type: str = ""
    source_title: str = ""
    source_character_name: str = ""


class PageEntryModel(BaseModel):
    file: str
    label: str

class RewritePageModel(BaseModel):
    remark: str
    text_fr: str
    moral: str


class BookConfigModel(BaseModel):
    intro_text: dict | str = ""
    values_learned: dict | str = ""
    category: str = "coloring"
    story_format: str = "colored"
    story_layout: str = "top_bottom"
    languages: list[str] = ["fr"]
    story_base_prompt: str = ""
    pages: list[dict] = []
    title: str
    subtitle: str
    author: str
    testpen: str = ""
    images_folder: str = ""
    characters: list[CharacterModel] = []
    page_sequence: Optional[list[PageEntryModel]] = None
    kdp_metadata: dict = {}


class NewBookModel(BaseModel):
    slug: str
    category: str = "coloring"
    story_format: str = "colored"
    title: str
    subtitle: str
    author: str
    characters: list[CharacterModel] = []
    # For Story mode
    story_script: str = ""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_config(book_name: str):
    config_path = ROOT / "books" / book_name / "config.py"
    if not config_path.exists():
        return None
    spec   = importlib.util.spec_from_file_location(f"books.{book_name}.config", config_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _book_status(book_name: str) -> dict:
    cfg        = _load_config(book_name)
    if not cfg:
        return {"name": book_name, "error": "config.py not found"}

    images_dir = pathlib.Path(cfg.IMAGES_DIR)
    sequence   = getattr(cfg, "PAGE_SEQUENCE", [])
    characters = getattr(cfg, "CHARACTERS", [])

    # Image stats
    images_present = []
    images_missing = []
    images_black   = []   # heuristic: very small file size may indicate solid black

    for filename, label in sequence:
        path = images_dir / filename
        if path.exists():
            size_kb = path.stat().st_size / 1024
            images_present.append({"file": filename, "label": label, "size_kb": round(size_kb, 1)})
            if size_kb < 150:   # heuristic: suspiciously small = possible black fill
                images_black.append(filename)
        else:
            images_missing.append(filename)

    # Also list generated images not yet in PAGE_SEQUENCE
    all_images   = sorted(images_dir.glob("book*.png")) if images_dir.exists() else []
    in_sequence  = {f for f, _ in sequence}
    extra_images = [p.name for p in all_images if p.name not in in_sequence]

    # PDF status
    pdf_path = ROOT / "output" / f"{book_name}_interior_FINAL.pdf"
    pdf_info = None
    if pdf_path.exists():
        size_mb = pdf_path.stat().st_size / 1024 / 1024
        pdf_info = {"path": str(pdf_path), "size_mb": round(size_mb, 1)}

    return {
        "category":       getattr(cfg, "CATEGORY", "coloring"),
        "story_format":   getattr(cfg, "STORY_FORMAT", "colored"),
        "name":           book_name,
        "title":          getattr(cfg, "TITLE", book_name),
        "author":         getattr(cfg, "AUTHOR", ""),
        "total_chars":    len(characters),
        "in_sequence":    len(sequence),
        "present":        len(images_present),
        "missing":        images_missing,
        "suspicious":     images_black,
        "extra_images":   extra_images,
        "images_detail":  images_present,
        "pdf":            pdf_info,
    }


def _list_books() -> list[str]:
    books_dir = ROOT / "books"
    return sorted(
        d.name for d in books_dir.iterdir()
        if d.is_dir() and (d / "config.py").exists()
    )


# ── Routes ─────────────────────────────────────────────────────────────────────


# ========================================================
# SETTINGS ROUTES
# ========================================================
import json
import os

@app.get("/settings")
def view_settings(request: Request):
    settings_file = ROOT / "settings.json"
    settings_data = {}
    if settings_file.exists():
        with open(settings_file, "r") as f:
            settings_data = json.load(f)
    
    if not settings_data.get("gemini_api_key"):
        settings_data["gemini_api_key"] = os.environ.get("GEMINI_API_KEY", "")
        
    return templates.TemplateResponse(request=request, name="settings.html", context={"settings": settings_data})

@app.post("/api/settings")
def update_settings(data: SettingsModel):
    settings_file = ROOT / "settings.json"
    with open(settings_file, "w") as f:
        json.dump(data.model_dump(), f, indent=4)
        
    env_file = ROOT / ".env.local"
    if env_file.exists():
        env_content = env_file.read_text()
        if data.gemini_api_key:
            if "GEMINI_API_KEY=" in env_content:
                env_content = re.sub(r'GEMINI_API_KEY=.*', f'GEMINI_API_KEY="{data.gemini_api_key}"', env_content)
            else:
                env_content += f'\nGEMINI_API_KEY="{data.gemini_api_key}"'
            env_file.write_text(env_content)
    return {"status": "ok"}

# ========================================================
# BOOK DELETION
# ========================================================
import shutil

@app.delete("/api/book/{book_name}")
def delete_book(book_name: str):
    import re
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', book_name):
        raise HTTPException(status_code=400, detail="Nom invalide")
        
    book_dir = ROOT / "books" / book_name
    images_dir = ROOT / "images" / book_name
    
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail="Livre introuvable")
        
    # Delete configs
    shutil.rmtree(book_dir, ignore_errors=True)
    # Delete images if they exist
    shutil.rmtree(images_dir, ignore_errors=True)
    
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    books = [_book_status(b) for b in _list_books()]
    return templates.TemplateResponse(request=request, name="index.html", context={"books": books})


@app.get("/book/{book_name}", response_class=HTMLResponse)
async def book_detail(request: Request, book_name: str):
    status = _book_status(book_name)
    if status.get("category") == "story":
        return templates.TemplateResponse(request=request, name="story.html", context={"book": status, "book_name": book_name})
    return templates.TemplateResponse(request=request, name="book.html", context={"book": status, "book_name": book_name})


@app.get("/api/books")
async def api_books():
    return [_book_status(b) for b in _list_books()]


@app.get("/api/book/{book_name}")
async def api_book(book_name: str):
    return _book_status(book_name)


@app.get("/stream/generate/{book_name}")
async def stream_generate(request: Request, book_name: str, char_id: str = "", force: bool = False):
    """Stream real-time output of pipeline/generate.py"""
    api_key = _resolve_gemini_api_key()
    cmd = [sys.executable, str(ROOT / "pipeline" / "generate.py"), "--book", book_name, "--auto-clean"]
    if char_id:
        cmd += ["--id", char_id]
    if force:
        cmd += ["--force"]

    env = os.environ.copy()
    if api_key:
        env["GEMINI_API_KEY"] = api_key

    async def event_stream():
        process = None
        try:
            if not api_key:
                yield "data: ERROR: GEMINI_API_KEY not set in server environment.\n\n"
                yield "data: Set it in Settings page or export GEMINI_API_KEY, then restart dashboard if needed.\n\n"
                return
            process = await asyncio.create_subprocess_exec(
                *cmd, env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            while True:
                if await request.is_disconnected():
                    if process.returncode is None:
                        process.terminate()
                    break
                try:
                    line = await asyncio.wait_for(process.stdout.readline(), timeout=10.0)
                    if not line:
                        break
                    yield f"data: {line.decode(errors='replace').rstrip()}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"  # SSE comment — keeps connection alive, ignored by browser
            if process.returncode is None:
                await process.wait()
        except asyncio.CancelledError:
            if process and process.returncode is None:
                process.terminate()
            raise
        except Exception as e:
            yield f"data: ERROR: {e}\n\n"
        finally:
            try:
                yield "data: [DONE]\n\n"
            except Exception:
                # Client connection may already be closed; suppress trailing write errors.
                pass

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/stream/clean/{book_name}")
async def stream_clean(book_name: str, filename: str = ""):
    """Stream real-time output of pipeline/clean.py --auto for a file or all files"""
    cfg = _load_config(book_name)
    if not cfg:
        return {"error": "book not found"}

    images_dir = pathlib.Path(cfg.IMAGES_DIR)

    async def event_stream():
        try:
            targets = [images_dir / filename] if filename else sorted(images_dir.glob("book*.png"))
            for img_path in targets:
                if not img_path.exists():
                    yield f"data: SKIP (not found): {img_path.name}\n\n"
                    continue
                proc_cmd = [sys.executable, str(ROOT / "pipeline" / "clean.py"),
                            str(img_path), "--lineart", "--crop-portrait", "--auto"]
                process = await asyncio.create_subprocess_exec(
                    *proc_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                async for line in process.stdout:
                    yield f"data: {line.decode().rstrip()}\n\n"
                await process.wait()
        except Exception as e:
            yield f"data: ERROR: {e}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/stream/cleanup/{book_name}")
async def stream_cleanup(book_name: str, char_id: str = "", mode: str = "auto"):
    """
    Stream cleanup of a single image.  Saves a raw backup the first time,
    then always restores from raw before applying the chosen mode — so the
    user can compare modes without losing the original.

    mode: lineart | auto | crop | all
    """
    cfg = _load_config(book_name)
    if not cfg:
        return {"error": "book not found"}

    images_dir = pathlib.Path(cfg.IMAGES_DIR)
    prefix     = book_name.split("-")[0]
    img_path   = images_dir / f"{prefix}_{char_id}.png"
    raw_path   = images_dir / f"{prefix}_{char_id}_raw.png"

    async def event_stream():
        try:
            if not img_path.exists():
                yield f"data: ERROR: Image introuvable — {img_path.name}\n\n"
                return

            # Save raw backup on first cleanup (preserves the original generation)
            if not raw_path.exists():
                shutil.copy2(str(img_path), str(raw_path))
                yield f"data: Backup créé : {raw_path.name}\n\n"

            # Always restore from raw before applying — allows re-running any mode
            shutil.copy2(str(raw_path), str(img_path))
            yield f"data: Restauré depuis backup brut\n\n"

            # Build clean.py command
            cmd = [sys.executable, str(ROOT / "pipeline" / "clean.py"), str(img_path)]
            if mode == "lineart":
                cmd += ["--lineart", "--crop-portrait"]
            elif mode == "crop":
                cmd += ["--crop-portrait"]
            elif mode == "all":
                cmd += ["--lineart", "--crop-portrait", "--auto"]
            else:  # "auto" (default)
                cmd += ["--crop-portrait", "--auto"]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for line in process.stdout:
                yield f"data: {line.decode().rstrip()}\n\n"
            await process.wait()
        except Exception as e:
            yield f"data: ERROR: {e}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/stream/cover/{book_name}")
async def stream_cover(book_name: str, custom_prompt: str | None = None):
    """Stream real-time output of pipeline/cover.py"""
    import subprocess
    import asyncio
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', book_name):
        raise HTTPException(status_code=400, detail="Invalid book name")
    cmd = [sys.executable, str(ROOT / "pipeline" / "cover.py"), "--book", book_name]
    if custom_prompt:
        cmd += ["--prompt-override", custom_prompt]

    async def event_stream():
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(ROOT),
                env=os.environ.copy()
            )
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_str = line.decode('utf-8', errors='replace').rstrip()
                yield f"data: {line_str}\n\n"

            await process.wait()
            yield f"data: [DONE]\n\n"
        except Exception as e:
            yield f"data: ERROR: {str(e)}\n\n"
            yield f"data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/stream/assemble/{book_name}")
async def stream_assemble(book_name: str, output: str | None = None):
    """Stream real-time output of pipeline/assemble.py"""
    cmd = [sys.executable, str(ROOT / "pipeline" / "assemble.py"), "--book", book_name]
    if output:
        cmd += ["--output", output]

    async def event_stream():
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for line in process.stdout:
                yield f"data: {line.decode().rstrip()}\n\n"
            await process.wait()
        except Exception as e:
            yield f"data: ERROR: {e}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Config API routes ──────────────────────────────────────────────────────────

@app.post("/api/rewrite_page")
async def api_rewrite_page(data: RewritePageModel):
    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY non configuré.")
        
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(ROOT / "pipeline" / "rewrite_page.py"),
        "--remark", data.remark,
        "--text", data.text_fr,
        "--moral", data.moral,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=os.environ.copy()
    )
    stdout, _ = await process.communicate()
    
    if process.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Script failed: {stdout.decode()}")
        
    import json
    out_text = stdout.decode().strip()
    try:
        parsed = json.loads(out_text)
        if "error" in parsed:
            raise HTTPException(status_code=500, detail=parsed["error"])
        return parsed
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Bad JSON from Gemini: {out_text}")

class GlobalReplaceModel(BaseModel):
    search: str
    replace: str


class FeedbackModel(BaseModel):
    feedback: str
    current_prompt: str
    page_ref: str  # character id (coloring) or str(page_number) (story)

@app.post("/api/books/{book_name}/global-replace")
async def api_global_replace(book_name: str, data: GlobalReplaceModel):
    cfg_module = _load_config(book_name)
    pages = getattr(cfg_module, "PAGES", [])
    intro = getattr(cfg_module, "INTRO_TEXT", {})
    values = getattr(cfg_module, "VALUES_LEARNED", {})
    lang_list = getattr(cfg_module, "LANGUAGES", ["fr"])
    
    # helper for string/dict replacement
    def _replace(obj):
        if isinstance(obj, str):
            return obj.replace(data.search, data.replace)
        elif isinstance(obj, dict):
            return {k: v.replace(data.search, data.replace) for k,v in obj.items()}
        return obj

    intro = _replace(intro)
    values = _replace(values)

    for p in pages:
        if "text" in p:
            p["text"] = _replace(p["text"])
        if "prompt" in p:
            p["prompt"] = p["prompt"].replace(data.search, data.replace)

    from pipeline.config_io import save_config
    kwargs = {}
    for attr in dir(cfg_module):
        if not attr.startswith("_") and attr.isupper():
            kwargs[attr.lower()] = getattr(cfg_module, attr)
    kwargs["pages"] = pages
    kwargs["intro_text"] = intro
    kwargs["values_learned"] = values

    save_config(ROOT / "books" / book_name / "config.py", **kwargs)
    return {"status": "ok"}

@app.get("/api/book/{book_name}/config")
async def api_get_book_config(book_name: str):
    try:
        return read_config(book_name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Livre {book_name!r} introuvable")


@app.get("/api/book/{book_name}/cover-prompt")
async def api_get_cover_prompt(book_name: str):
    """Return the auto-generated cover prompt for the given book."""
    from pipeline.cover import _build_cover_prompt
    from pipeline.assemble import load_config as _lc
    try:
        cfg = _lc(book_name)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Livre {book_name!r} introuvable")
    prompt = _build_cover_prompt(cfg)
    return {"prompt": prompt}


@app.put("/api/book/{book_name}/config")
async def api_put_book_config(book_name: str, data: BookConfigModel):
    book_dir = ROOT / "books" / book_name
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail=f"Livre {book_name!r} introuvable")
    write_config(book_name, data.model_dump())
    return {"status": "ok"}


@app.post("/api/books/new")
async def api_new_book(data: NewBookModel):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', data.slug):
        raise HTTPException(status_code=400, detail="Slug invalide (alphanumérique + tirets)")
    book_dir = ROOT / "books" / data.slug
    if book_dir.exists():
        raise HTTPException(status_code=409, detail=f"Le livre {data.slug!r} existe déjà")
    
    # Si c'est un livre de conte avec script brut
    story_base_prompt = ""
    pages = []
    if data.category == "story" and data.story_script:
        # Appel du script Gemini
        import subprocess
        import json
        tmp_script = ROOT / f"tmp_script_{data.slug}.txt"
        tmp_script.write_text(data.story_script, encoding="utf-8")
        
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(ROOT / "pipeline" / "story_gen.py"),
                "--script", str(tmp_script),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy()
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise HTTPException(status_code=500, detail=f"Erreur génération script: {stderr.decode()}")
            
            stdout_text = stdout.decode().strip()
            try:
                parsed_story = json.loads(stdout_text)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Erreur Parse JSON de Gemini: {str(e)} | Sortie: {stdout_text[:500]}")
            
            story_base_prompt = parsed_story.get("story_base_prompt", "")
            intro_text = parsed_story.get("intro_text", "")
            values_learned = parsed_story.get("values_learned", "")
            pages = parsed_story.get("pages", [])
            
            # Auto-generate page_sequence for story based on pages
            page_sequence = [
                {"file": f"{data.slug}_page_{p['page_number']}.png", "label": f"Page {p['page_number']}"}
                for p in pages
            ]
        finally:
            if tmp_script.exists():
                tmp_script.unlink()
    else:
        intro_text = ""
        values_learned = ""
        # Auto-generate page_sequence for coloring based on characters
        page_sequence = [] # will be handled by config_io if empty
        
    book_dir.mkdir(parents=True)
    (ROOT / "images" / data.slug).mkdir(parents=True, exist_ok=True)
    
    write_config(data.slug, {
        "category":      data.category,
        "story_format":  data.story_format,
        "title":         data.title,
        "subtitle":      data.subtitle,
        "author":        data.author,
        "intro_text":    intro_text,
        "values_learned": values_learned,
        "images_folder": data.slug,
        "characters":    [c.model_dump() for c in data.characters],
        "page_sequence": page_sequence if data.category == "story" else [],
        "story_base_prompt": story_base_prompt,
        "pages":         pages
    })
    return {"status": "ok", "slug": data.slug}

@app.get("/api/prompt/tags")
async def api_prompt_tags():
    def _examples(category: str, tags: list[str]) -> dict[str, str]:
        slug = lambda t: t.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
        return {slug(t): f"/assets/tag_examples/{category}/{slug(t)}.png" for t in tags}

    return {
        "style":             STYLE_TAGS,
        "style_examples":    _examples("style",    STYLE_TAGS),
        "pose":              POSE_TAGS,
        "pose_examples":     _examples("pose",     POSE_TAGS),
        "elements":          ELEMENT_TAGS,
        "elements_examples": _examples("elements", ELEMENT_TAGS),
        "theme":             THEME_TAGS,
        "theme_examples":    _examples("theme",    THEME_TAGS),
        "group_dynamics":    GROUP_DYNAMICS,
    }


@app.post("/api/feedback/{book_name}")
async def api_feedback(book_name: str, data: FeedbackModel):
    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY non configuré.")

    process = await asyncio.create_subprocess_exec(
        sys.executable, str(ROOT / "pipeline" / "refine_prompt.py"),
        "--prompt",   data.current_prompt,
        "--feedback", data.feedback,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=os.environ.copy(),
    )
    stdout, _ = await process.communicate()

    if process.returncode != 0:
        raise HTTPException(status_code=500,
                            detail=f"Script failed: {stdout.decode()}")

    out_text = stdout.decode().strip()
    try:
        parsed = json.loads(out_text)
        if "error" in parsed:
            raise HTTPException(status_code=500, detail=parsed["error"])
        return parsed
    except json.JSONDecodeError:
        raise HTTPException(status_code=500,
                            detail=f"Bad JSON from Gemini: {out_text[:300]}")


@app.get("/images/{book_name}/{filename}")
async def serve_image(book_name: str, filename: str):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', book_name):
        raise HTTPException(status_code=400, detail="Invalid book name")
    cfg = _load_config(book_name)
    if not cfg:
        raise HTTPException(status_code=404, detail="Book not found")
    images_dir = pathlib.Path(cfg.IMAGES_DIR).resolve()
    image_path = (images_dir / filename).resolve()
    if not image_path.is_relative_to(images_dir):
        raise HTTPException(status_code=403, detail="Access denied")
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(
        str(image_path),
        media_type="image/png",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/api/choose-folder")
async def api_choose_folder():
    """Open a native macOS folder picker dialog and return the chosen path."""
    import platform
    import asyncio
    system = platform.system()
    if system != "Darwin":
        raise HTTPException(status_code=400, detail="Native folder picker only supported on macOS")
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e",
            'POSIX path of (choose folder with prompt "Choisir le dossier de destination pour le PDF")',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode != 0:
            # User cancelled (return code 1) or error
            return {"path": None, "cancelled": True}
        path = stdout.decode().strip().rstrip("/")
        return {"path": path, "cancelled": False}
    except asyncio.TimeoutError:
        return {"path": None, "cancelled": True}


@app.get("/api/book/{book_name}/open-pdf")
async def api_open_pdf(book_name: str):
    """Open the assembled PDF with the OS default viewer."""
    import platform
    pdf_path = ROOT / "output" / f"{book_name}_interior_FINAL.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF introuvable — lance d'abord 'Build PDF'")
    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", str(pdf_path)])
    elif system == "Linux":
        subprocess.Popen(["xdg-open", str(pdf_path)])
    else:
        subprocess.Popen(["start", "", str(pdf_path)], shell=True)
    return {"status": "ok"}


@app.get("/api/book/{book_name}/open-image")
async def api_open_image(book_name: str, filename: str):
    """Reveal the image file in the OS file manager (macOS Finder / Linux / Windows)."""
    import platform
    cfg = _load_config(book_name)
    if not cfg:
        raise HTTPException(status_code=404, detail="Book not found")
    images_dir = pathlib.Path(cfg.IMAGES_DIR).resolve()
    image_path = (images_dir / filename).resolve()
    if not image_path.is_relative_to(images_dir):
        raise HTTPException(status_code=403, detail="Access denied")
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", "-R", str(image_path)])
    elif system == "Linux":
        subprocess.Popen(["xdg-open", str(image_path.parent)])
    else:
        subprocess.Popen(["explorer", f"/select,{image_path}"])
    return {"status": "ok"}


@app.get("/new-book", response_class=HTMLResponse)
async def new_book_page(request: Request):
    return templates.TemplateResponse(request=request, name="new_book.html", context={})


@app.get("/niche", response_class=HTMLResponse)
async def niche_research_page(request: Request):
    """Render the Niche Research page. Matches Module A Steps 1-2."""
    return templates.TemplateResponse(request=request, name="niche.html", context={})


@app.post("/api/niche-research")
async def api_niche_research(niche: str = Form(...), csv_file: UploadFile = File(...)):
    """Module A: Brainstorming Engine. Process BookBolt CSV and ask Gemini for sub-niches."""
    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY non configuré sur le serveur.")

    tmp_path = ROOT / f"tmp_{csv_file.filename}"
    try:
        content = await csv_file.read()
        tmp_path.write_bytes(content)

        process = await asyncio.create_subprocess_exec(
            sys.executable, str(ROOT / "pipeline" / "niche_research.py"),
            "--csv", str(tmp_path),
            "--niche", niche,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy()
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Script failed: {stderr.decode()}")
            
        import json
        out_text = stdout.decode().strip()
        try:
            return json.loads(out_text)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail=f"Invalid JSON from Gemini: {out_text}")
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


# ── Entry point ────────────────────────────────────────────────────────────────

class TranslateRequest(BaseModel):
    text: str
    langs: list[str]

@app.post("/api/translate")
async def api_translate(req: TranslateRequest):
    import importlib.util
    import traceback
    try:
        spec = importlib.util.spec_from_file_location("translate", str(ROOT / "dashboard" / "translate.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.translate_text(req.text, req.langs)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")


class AddImageRequest(BaseModel):
    source_book: str
    filename: str

@app.get("/api/images/all")
async def api_all_images():
    images_dir = ROOT / "images"
    res = {}
    if images_dir.exists():
        for d in images_dir.iterdir():
            if d.is_dir():
                imgs = [img.name for img in d.glob("*.png")]
                if imgs:
                    res[d.name] = sorted(imgs)
    return res

@app.post("/api/book/{book_name}/add-image")
async def api_add_imported_image(book_name: str, req: AddImageRequest):
    import shutil
    src = ROOT / "images" / req.source_book / req.filename
    dest_dir = ROOT / "images" / book_name
    dest_dir.mkdir(parents=True, exist_ok=True)
    prefix = book_name.split('-')[0]
    
    # Try to extract the core name
    core = req.filename
    if "_" in core: core = core.split("_", 1)[1]
    if core.endswith(".png"): core = core[:-4]
    
    new_filename = f"{prefix}_{core}.png"
    dest = dest_dir / new_filename
    
    # avoid overwrite
    counter = 1
    while dest.exists():
        new_filename = f"{prefix}_{core}_{counter}.png"
        dest = dest_dir / new_filename
        counter += 1
        
    shutil.copy2(src, dest)
    new_id = new_filename.replace(f"{prefix}_", "").replace(".png", "")
    return {"status": "ok", "new_filename": new_filename, "new_id": new_id}


class GenerateMetaRequest(BaseModel):
    mode: str
    pages: list[dict]

@app.post("/api/generate_meta")
async def api_generate_meta(req: GenerateMetaRequest):
    import base64
    import os
    import json
    from google import genai
    from google.genai import types

    text_pages = []
    for p in req.pages:
        fr = ""
        if "text" in p and isinstance(p["text"], dict):
            fr = p["text"].get("fr", "")
        if fr:
            text_pages.append(f"Page {p.get('page_number', '?')}: {fr}")

    full_story = "\n".join(text_pages)
    if not full_story.strip():
        raise HTTPException(status_code=400, detail="Pas de texte FR trouvé dans les pages pour générer le contenu.")

    if req.mode == "intro":
        prompt = f"Voici l'histoire complète d'un livre pour enfant:\n\n{full_story}\n\nDonne-moi UNIQUEMENT un court texte d'introduction accrocheur (2-3 phrases max) qui sera mis à la page de garde pour introduire le livre. En français. Pas de formatage markdown, juste le texte."
    else:
        # values
        prompt = f"Voici l'histoire complète d'un livre pour enfant:\n\n{full_story}\n\nDonne-moi UNIQUEMENT une liste ou un court paragraphe (2-3 phrases max) résumant la morale ou les valeurs apprises dans cette histoire, à placer en fin de livre. En français. Pas de formatage markdown, juste le texte."

    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY")) if os.environ.get("GEMINI_API_KEY") else genai.Client()
        models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
        last_exc = None
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return {"result": response.text.strip()}
            except Exception as model_exc:
                err_str = str(model_exc)
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    last_exc = model_exc
                    continue
                raise
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(last_exc))
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ========================================================
# STORYFORGE — Personalized hero storybooks
# ========================================================

def _backend_provider():
    """Return a real Gemini image backend. Overridden in tests with a fake."""
    from storyforge.gemini_backend import GeminiBackend
    return GeminiBackend(api_key=_resolve_gemini_api_key())


def _analyze_provider(photos):
    """Analyze photos into a hero descriptor. Overridden in tests with a fake."""
    from storyforge.gemini_backend import analyze_photos
    return analyze_photos(photos, api_key=_resolve_gemini_api_key())


def _translate_provider(text, target_langs):
    """Translate text into target languages. Overridden in tests with a fake."""
    spec = importlib.util.spec_from_file_location(
        "sf_translate", str(ROOT / "dashboard" / "translate.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.translate_text(text, target_langs)


def _expand_provider(prompt, page_count):
    """Expand a base narrative into page_count pages. Overridden in tests with a fake."""
    from storyforge.gemini_backend import expand_story
    return expand_story(prompt, page_count, api_key=_resolve_gemini_api_key())


def _load_pricing_settings() -> dict:
    """Load pricing config from settings.json, falling back to library defaults."""
    from pipeline.pricing import default_pricing_settings
    settings_file = ROOT / "settings.json"
    if settings_file.exists():
        try:
            data = json.loads(settings_file.read_text())
            pricing = data.get("pricing")
            if isinstance(pricing, dict) and pricing:
                return pricing
        except (json.JSONDecodeError, OSError):
            pass
    return default_pricing_settings()



def _normalize_photo_to_png(data: bytes) -> bytes:
    """Decode an uploaded image and re-encode as PNG bytes for consistent Gemini refs."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGB")
            out = io.BytesIO()
            im.save(out, format="PNG")
            return out.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Unsupported or corrupted image file.") from exc


@app.get("/storybook", response_class=HTMLResponse)
def storybook_page(request: Request):
    return templates.TemplateResponse(request=request, name="storybook.html", context={})


@app.get("/api/storyforge/templates")
def storyforge_templates():
    out = []
    for t in _sf_list_templates():
        out.append({
            "slug": t.slug,
            "name": t.name,
            "mode": t.mode,
            "art_style": t.art_style,
            "variables": [
                {"key": v.key, "label": v.label, "type": v.type, "options": v.options}
                for v in t.variables
            ],
            "pages": len(t.pages),
        })
    return out


@app.post("/api/storyforge/{name}/photos")
async def storyforge_photos(name: str, photos: list[UploadFile] = File(...)):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', name):
        raise HTTPException(status_code=400, detail="Invalid book name")
    if not photos:
        raise HTTPException(status_code=400, detail="No photos uploaded.")
    if len(photos) > 3:
        raise HTTPException(status_code=400, detail="At most 3 photos.")
    hero_dir = ROOT / "books" / name / "hero"
    hero_dir.mkdir(parents=True, exist_ok=True)
    for old in hero_dir.glob("source_*.png"):
        old.unlink()
    for i, photo in enumerate(photos):
        data = await photo.read()
        if not data:
            raise HTTPException(status_code=400, detail="Empty photo.")
        if len(data) > 12 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Photo too large (max 12 MB).")
        png_data = _normalize_photo_to_png(data)
        (hero_dir / f"source_{i}.png").write_bytes(png_data)
    return {"saved": len(photos)}


@app.get("/api/storyforge/{name}/portrait")
def storyforge_portrait(name: str):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', name):
        raise HTTPException(status_code=400, detail="Invalid book name")
    path = ROOT / "books" / name / "hero" / "canonical_portrait.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No portrait yet.")
    return FileResponse(
        str(path),
        media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/stream/storyforge/{name}/hero")
def storyforge_hero(name: str, slug: str):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', name):
        raise HTTPException(status_code=400, detail="Invalid book name")

    def stream():
        try:
            tpl = _sf_load_template(slug)
            hero_dir = ROOT / "books" / name / "hero"
            photos = [p.read_bytes() for p in sorted(hero_dir.glob("source_*.png"))]
            yield "data: Building hero from photos...\n\n"
            sheet = _sf_build_hero(photos, tpl.art_style, _backend_provider(), _analyze_provider)
            _sf_save_sheet(ROOT / "books" / name, sheet)
            yield "data: Hero ready.\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: ERROR: {exc}\n\n"

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/pricing")
def api_pricing(page_count: int, color: bool = True, paper_quality: str = "standard",
                has_cover: bool = True):
    from pipeline.pricing import compute_price
    settings = _load_pricing_settings()
    try:
        return compute_price(page_count, color, paper_quality, has_cover, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/stream/storyforge/{name}/generate")
def storyforge_generate(name: str, request: Request, slug: str, title: str,
                        author: str = "", languages: str = "fr", page_count: int = 0):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', name):
        raise HTTPException(status_code=400, detail="Invalid book name")
    lang_list = [l.strip() for l in languages.split(",") if l.strip()] or ["fr"]
    reserved = ("slug", "title", "author", "languages", "page_count")
    variables = {
        k: v for k, v in request.query_params.items() if k not in reserved
    }

    def stream():
        try:
            tpl = _sf_load_template(slug)
            hero = _sf_load_sheet(ROOT / "books" / name)
            if page_count and page_count != len(tpl.pages):
                yield f"data: Shaping a {page_count}-page story...\n\n"
                specs = _sf_expand_narrative(tpl, variables, hero, page_count, _expand_provider)
            else:
                specs = _sf_resolve(tpl, variables, hero)
            gen = _backend_provider()
            page_pngs = []
            for spec in specs:
                yield f"data: Generating page {spec.page_number}/{len(specs)}...\n\n"
                page_pngs.append(_sf_generate_page(spec, hero, gen))

            source_lang = tpl.language_default
            yield "data: Translating pages...\n\n"
            page_texts = _sf_translate_pages(specs, source_lang, lang_list, _translate_provider)

            _sf_build_book(name, title, author, tpl.mode, specs, page_pngs, hero,
                           languages=lang_list, page_texts=page_texts)

            yield "data: Generating cover...\n\n"
            cover_png = _sf_generate_cover(title, hero, gen)
            (ROOT / "books" / name / "hero" / "cover.png").write_bytes(cover_png)

            yield "data: Book ready.\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: ERROR: {exc}\n\n"

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/storyforge/{name}/cover")
def storyforge_cover(name: str):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', name):
        raise HTTPException(status_code=400, detail="Invalid book name")
    path = ROOT / "books" / name / "hero" / "cover.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No cover yet.")
    return FileResponse(
        str(path),
        media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )



if __name__ == "__main__":
    import uvicorn
    print("\nKDP Dashboard running at http://localhost:8000\n")
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=8000, reload=True, app_dir=str(ROOT))



