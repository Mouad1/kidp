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
import secrets
import shutil
import subprocess
import sys
from typing import Optional

# Ensure the root directory is in sys.path so we can import from pipeline
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from pipeline.config_io import read_config, write_config
from pipeline.prompt import STYLE_TAGS, POSE_TAGS, ELEMENT_TAGS, THEME_TAGS, GROUP_DYNAMICS

from storyforge.templates import list_templates as _sf_list_templates, load_template as _sf_load_template
from storyforge.errors import TemplateError as _SfTemplateError
from storyforge.identity import build_hero as _sf_build_hero, save_sheet as _sf_save_sheet, load_sheet as _sf_load_sheet
from storyforge.engine import resolve as _sf_resolve
from storyforge.generator import generate_page as _sf_generate_page
from storyforge.builder import build_book as _sf_build_book
from storyforge.i18n import translate_pages as _sf_translate_pages
from storyforge.expand import expand_narrative as _sf_expand_narrative
from storyforge.cover import generate_cover as _sf_generate_cover

from storefront.auth import (
    request_code as _sf_request_code, verify_code as _sf_verify_code,
    AuthStore as _SfAuthStore, SqliteAuthStore as _SfSqliteAuthStore,
    FakeCodeSender as _SfFakeCodeSender, SmtpCodeSender as _SfSmtpCodeSender,
    ResendCodeSender as _SfResendCodeSender,
)
from storefront.session import sign as _sf_sign_session, verify as _sf_verify_session
from storefront.catalog import list_catalog as _sf_list_catalog
from storefront.payment import get_payment_provider as _sf_get_payment_provider
from storefront.db import (
    Database as _SfDatabase, new_reference as _sf_new_reference,
    create_order as _sf_create_order, get_order as _sf_get_order,
    set_order_status as _sf_set_order_status, list_orders as _sf_list_orders,
    set_order_notes as _sf_set_order_notes, get_stats as _sf_get_stats,
)
from storefront.admin import seed_admins as _sf_seed_admins, is_admin as _sf_is_admin

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
        "published":      getattr(cfg, "PUBLISHED", False),
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
    if _require_admin(request) is None:
        return RedirectResponse(url="/admin/login", status_code=303)
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
    if _require_admin(request) is None:
        return RedirectResponse(url="/admin/login", status_code=303)
    books = [_book_status(b) for b in _list_books()]
    return templates.TemplateResponse(request=request, name="index.html", context={"books": books})


@app.get("/book/{book_name}", response_class=HTMLResponse)
async def book_detail(request: Request, book_name: str):
    if _require_admin(request) is None:
        return RedirectResponse(url="/admin/login", status_code=303)
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


_CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}


def _store_price_quote(page_count: int) -> dict:
    """Storefront retail quote for a book (color, standard paper, with cover).

    Single source of truth for the price shown on the catalog, product page,
    and used when creating the order, so they can never drift apart.
    """
    from pipeline.pricing import compute_price
    quote = compute_price(page_count, color=True, paper_quality="standard",
                          has_cover=True, settings=_load_pricing_settings())
    currency = quote["currency"]
    symbol = _CURRENCY_SYMBOLS.get(currency, "")
    display = f"{symbol}{quote['price']:.2f}" if symbol else f"{quote['price']:.2f} {currency}"
    return {"price": quote["price"], "currency": currency, "display": display}



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
    if _require_admin(request) is None:
        return RedirectResponse(url="/admin/login", status_code=303)
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



# ========================================================
# STOREFRONT (customer-facing) ROUTES
# ========================================================
import datetime as _dt

_SF_SESSION_MAX_AGE = 86400  # 24h
_SF_ADMIN_MAX_AGE = 86400  # 24h
_SF_DB_HOLDER: dict = {}
_SF_SECRET_CACHE: str | None = None


def _load_storefront_settings() -> dict:
    settings_file = ROOT / "settings.json"
    if settings_file.exists():
        try:
            data = json.loads(settings_file.read_text())
            sf = data.get("storefront")
            if isinstance(sf, dict):
                return sf
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _store_db() -> _SfDatabase:
    """Lazily open and cache the SQLite database; seed admins from settings."""
    db = _SF_DB_HOLDER.get("db")
    if db is None:
        db = _SfDatabase(ROOT / ".storefront" / "storefront.db")
        admin_cfg = (_load_storefront_settings().get("admin") or {})
        emails = admin_cfg.get("emails") or []
        _sf_seed_admins(db, emails, now=_dt.datetime.utcnow())
        _SF_DB_HOLDER["db"] = db
    return db


def _store_https() -> bool:
    return bool(_load_storefront_settings().get("https", False))


def _admin_enabled() -> bool:
    return bool((_load_storefront_settings().get("admin") or {}).get("enabled", False))


def _store_session_secret() -> str:
    global _SF_SECRET_CACHE
    if _SF_SECRET_CACHE:
        return _SF_SECRET_CACHE

    secret = (_load_storefront_settings().get("session_secret") or "").strip()
    if not secret:
        secret = os.environ.get("STOREFRONT_SESSION_SECRET", "").strip()
    if not secret:
        secret = os.environ.get("SESSION_SECRET", "").strip()

    secret_file = ROOT / ".storefront" / "session_secret.txt"
    if not secret and secret_file.exists():
        try:
            secret = secret_file.read_text(encoding="utf-8").strip()
        except OSError:
            secret = ""

    if not secret:
        secret = secrets.token_urlsafe(48)
        try:
            secret_file.parent.mkdir(parents=True, exist_ok=True)
            secret_file.write_text(secret, encoding="utf-8")
        except OSError:
            # Keep running even if we cannot persist in this environment.
            pass

    _SF_SECRET_CACHE = secret
    return secret


def _store_auth_store():
    return _SfSqliteAuthStore(_store_db())


def _store_code_sender():
    sf = _load_storefront_settings()
    smtp = sf.get("smtp") or {}
    resend_api_key = os.environ.get("RESEND_API_KEY", "").strip()
    resend_from_addr = (
        smtp.get("from_addr")
        or os.environ.get("STOREFRONT_SMTP_FROM_ADDR", "")
        or os.environ.get("RESEND_FROM", "")
    ).strip()
    resend_endpoint = os.environ.get("RESEND_API_BASE", "https://api.resend.com").rstrip("/") + "/emails"
    if resend_api_key and resend_from_addr:
        return _SfResendCodeSender(
            api_key=resend_api_key,
            from_addr=resend_from_addr,
            endpoint=resend_endpoint,
        )

    host = (smtp.get("host") or os.environ.get("STOREFRONT_SMTP_HOST", "")).strip()
    if host:
        username = (smtp.get("username") or os.environ.get("STOREFRONT_SMTP_USERNAME", "")).strip()
        password = (
            smtp.get("password")
            or os.environ.get("STOREFRONT_SMTP_PASSWORD", "")
            or os.environ.get("SMTP_PASSWORD", "")
        )
        from_addr = (
            smtp.get("from_addr")
            or os.environ.get("STOREFRONT_SMTP_FROM_ADDR", "no-reply@example.com")
        )
        return _SfSmtpCodeSender(
            host=host, port=int(smtp.get("port", os.environ.get("STOREFRONT_SMTP_PORT", 587))),
            username=username, password=password,
            from_addr=from_addr,
            use_tls=bool(smtp.get("use_tls", True)),
        )
    return _SfFakeCodeSender()


def _store_catalog_names() -> list[str]:
    available = {tpl.slug for tpl in _sf_list_templates()}
    return [name for name in _list_books() if name in available]


def _store_read_config(name: str) -> dict:
    return read_config(name)


def _require_session(request: Request) -> dict | None:
    token = request.cookies.get("sf_session")
    if not token:
        return None
    return _sf_verify_session(token, _store_session_secret(),
                              max_age=_SF_SESSION_MAX_AGE, now=_dt.datetime.utcnow())


@app.get("/store", response_class=HTMLResponse)
def store_catalog(request: Request):
    entries = _sf_list_catalog(_store_catalog_names(), _store_read_config)
    view = []
    for e in entries:
        quote = _store_price_quote(e.page_count)
        view.append({
            "slug": e.slug,
            "title": e.title,
            "page_count": e.page_count,
            "category": e.category,
            "price_display": quote["display"],
        })
    return templates.TemplateResponse(
        request=request, name="store_catalog.html",
        context={"entries": view},
    )


@app.post("/store/auth/request")
async def store_auth_request(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="Invalid email address.")
    try:
        _sf_request_code(email, now=_dt.datetime.utcnow(),
                         code_sender=_store_code_sender(), store=_store_auth_store())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to send email code: {exc}")
    return JSONResponse({"sent": True})


@app.post("/store/auth/verify")
async def store_auth_verify(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    code = (body.get("code") or "").strip()
    ok = _sf_verify_code(email, code, now=_dt.datetime.utcnow(), store=_store_auth_store())
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid or expired code.")
    token = _sf_sign_session({"email": email}, _store_session_secret(),
                             now=_dt.datetime.utcnow())
    resp = JSONResponse({"authenticated": True})
    resp.set_cookie("sf_session", token, httponly=True, samesite="lax",
                    secure=_store_https(), max_age=_SF_SESSION_MAX_AGE)
    return resp


@app.post("/store/{slug}/preview")
async def store_preview(slug: str,
                        child_name: str = Form(...),
                        photo: UploadFile = File(...),
                        photo2: UploadFile | None = File(default=None)):
    """Free-trial face-swap preview: generates ONLY the cover + page 1.

    No order is created. Photos are never persisted. The response contains
    cover and page-1 PNGs as base64 data-URIs for immediate display.
    Strictly 3 Gemini image calls: 1 portrait + 1 cover + 1 page-1.
    """
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', slug):
        raise HTTPException(status_code=400, detail="Invalid book name")
    child = (child_name or "").strip()
    if not child:
        raise HTTPException(status_code=400, detail="Child name is required.")
    try:
        cfg = _store_read_config(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Book not found.")
    if not cfg.get("published"):
        raise HTTPException(status_code=404, detail="Book not found.")

    photos: list[bytes] = []
    raw = await photo.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty photo.")
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Photo too large (max 12 MB).")
    photos.append(_normalize_photo_to_png(raw))
    if photo2 is not None:
        raw2 = await photo2.read()
        if raw2:
            if len(raw2) > 12 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="Photo 2 too large (max 12 MB).")
            photos.append(_normalize_photo_to_png(raw2))

    try:
        tpl = _sf_load_template(slug)
    except _SfTemplateError:
        raise HTTPException(status_code=404, detail="Book template not found.")

    import asyncio
    import base64

    def _run_preview() -> dict:
        gen = _backend_provider()
        # 1 image call: build hero portrait from customer photos
        sheet = _sf_build_hero(photos, tpl.art_style, gen, _analyze_provider)
        # Resolve template page specs with child name substituted
        variables: dict[str, str] = {k: child for k in ("HERO_NAME", "NAME", "CHILD_NAME")}
        safe_vars = {k: v for k, v in variables.items() if k != "HERO_NAME"}
        specs = _sf_resolve(tpl, safe_vars, sheet)
        # 1 image call: page 1 only
        page1_png: bytes | None = _sf_generate_page(specs[0], sheet, gen) if specs else None
        # 1 image call: cover
        cover_png = _sf_generate_cover(child, sheet, gen)

        def b64(data: bytes) -> str:
            return "data:image/png;base64," + base64.b64encode(data).decode()

        return {
            "cover": b64(cover_png),
            "page1": b64(page1_png) if page1_png else None,
            "page_count": len(tpl.pages),
        }

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _run_preview)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Preview generation failed: {exc}")

    return JSONResponse(result)


@app.get("/store/success", response_class=HTMLResponse)
def store_success(request: Request, reference: str = ""):
    """Post-payment success page. Validates order status from DB and shows confirmation."""
    order: dict | None = None
    if reference:
        try:
            db = _store_db()
            order = _sf_get_order(db, reference)
        except Exception:
            pass
    return templates.TemplateResponse(
        request=request, name="store_success.html",
        context={"order": order},
    )


@app.get("/store/{slug}", response_class=HTMLResponse)
def store_personalize(slug: str, request: Request):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', slug):
        raise HTTPException(status_code=400, detail="Invalid book name")
    try:
        cfg = _store_read_config(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Book not found.")
    if not cfg.get("published"):
        raise HTTPException(status_code=404, detail="Book not found.")
    page_count = len(cfg.get("pages", []))
    quote = _store_price_quote(page_count)
    return templates.TemplateResponse(
        request=request, name="store_personalize.html",
        context={"slug": slug, "title": cfg.get("title", slug),
                 "page_count": page_count,
                 "price_display": quote["display"]},
    )


@app.post("/store/{slug}/order")
async def store_create_order(slug: str, request: Request,
                             child_name: str = Form(...),
                             photo: UploadFile = File(...)):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', slug):
        raise HTTPException(status_code=400, detail="Invalid book name")
    session = _require_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    child = (child_name or "").strip()
    if not child:
        raise HTTPException(status_code=400, detail="Child name is required.")
    try:
        cfg = _store_read_config(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Book not found.")
    if not cfg.get("published"):
        raise HTTPException(status_code=404, detail="Book not found.")

    data = await photo.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty photo.")
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Photo too large (max 12 MB).")
    png_data = _normalize_photo_to_png(data)

    page_count = len(cfg.get("pages", []))
    quote = _store_price_quote(page_count)
    amount_cents = int(round(quote["price"] * 100))

    db = _store_db()
    reference = _sf_new_reference(slug)
    order_dir = ROOT / ".storefront" / "orders" / reference
    order_dir.mkdir(parents=True, exist_ok=True)
    photo_path = order_dir / "photo.png"
    photo_path.write_bytes(png_data)

    _sf_create_order(
        db, reference=reference, slug=slug, email=session["email"],
        child_name=child, photo_path=str(photo_path), page_count=page_count,
        amount_cents=amount_cents, currency=quote["currency"], now=_dt.datetime.utcnow(),
    )
    return JSONResponse({
        "reference": reference, "amount": amount_cents,
        "currency": quote["currency"], "status": "pending",
    })


@app.post("/store/{slug}/checkout")
async def store_checkout(slug: str, request: Request):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', slug):
        raise HTTPException(status_code=400, detail="Invalid book name")
    session = _require_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    body = await request.json()
    reference = (body.get("reference") or "").strip()
    if not reference:
        raise HTTPException(status_code=400, detail="Missing order reference.")
    db = _store_db()
    order = _sf_get_order(db, reference)
    if order is None or order["slug"] != slug:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order["email"] != session["email"]:
        raise HTTPException(status_code=403, detail="This order belongs to another account.")

    base = str(request.base_url).rstrip("/")
    provider = _sf_get_payment_provider(_load_storefront_settings())
    checkout = provider.create_checkout(
        amount=order["amount_cents"], currency=order["currency"], reference=reference,
        success_url=f"{base}/store/success?reference={reference}",
        cancel_url=f"{base}/store/{slug}",
    )
    if checkout.status == "paid":
        _sf_set_order_status(db, reference, "paid", now=_dt.datetime.utcnow())
    return JSONResponse({
        "reference": checkout.reference, "amount": checkout.amount,
        "currency": checkout.currency, "status": checkout.status, "url": checkout.url,
    })


@app.post("/store/{slug}/pay")
async def store_pay(slug: str, request: Request,
                    child_name: str = Form(...),
                    photo: UploadFile = File(...)):
    """Single-step: create order + Stripe Checkout Session, return redirect URL."""
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', slug):
        raise HTTPException(status_code=400, detail="Invalid book name")
    session = _require_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    child = (child_name or "").strip()
    if not child:
        raise HTTPException(status_code=400, detail="Child name is required.")
    try:
        cfg = _store_read_config(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Book not found.")
    if not cfg.get("published"):
        raise HTTPException(status_code=404, detail="Book not found.")

    data = await photo.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty photo.")
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Photo too large (max 12 MB).")
    png_data = _normalize_photo_to_png(data)

    page_count = len(cfg.get("pages", []))
    quote = _store_price_quote(page_count)
    amount_cents = int(round(quote["price"] * 100))

    db = _store_db()
    reference = _sf_new_reference(slug)
    order_dir = ROOT / ".storefront" / "orders" / reference
    order_dir.mkdir(parents=True, exist_ok=True)
    photo_path = order_dir / "photo.png"
    photo_path.write_bytes(png_data)

    _sf_create_order(
        db, reference=reference, slug=slug, email=session["email"],
        child_name=child, photo_path=str(photo_path), page_count=page_count,
        amount_cents=amount_cents, currency=quote["currency"], now=_dt.datetime.utcnow(),
    )

    base = str(request.base_url).rstrip("/")
    provider = _sf_get_payment_provider(_load_storefront_settings())
    checkout = provider.create_checkout(
        amount=amount_cents, currency=quote["currency"], reference=reference,
        success_url=f"{base}/store/success?reference={reference}",
        cancel_url=f"{base}/store/{slug}",
        customer_email=session["email"],
    )
    if checkout.status == "paid":
        _sf_set_order_status(db, reference, "paid", now=_dt.datetime.utcnow())
    return JSONResponse({
        "reference": checkout.reference,
        "url": checkout.url,
        "status": checkout.status,
    })


@app.post("/store/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()

    if webhook_secret:
        import stripe as _stripe
        try:
            event = _stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid Stripe signature.")
    else:
        import json as _json
        event = _json.loads(payload)

    if event.get("type") == "checkout.session.completed":
        reference = (event.get("data") or {}).get("object", {}).get("client_reference_id") or ""
        if reference:
            db = _store_db()
            order = _sf_get_order(db, reference)
            if order:
                _sf_set_order_status(db, reference, "paid", now=_dt.datetime.utcnow())

    return JSONResponse({"received": True})


# ── Admin authentication (email allowlist + one-time code) ───────────────────────

def _require_admin(request: Request) -> dict | None:
    """Return admin session dict, or None. When admin auth is disabled, allow all."""
    if not _admin_enabled():
        return {"email": "local-admin", "admin": True}
    token = request.cookies.get("sf_admin")
    if not token:
        return None
    data = _sf_verify_session(token, _store_session_secret(),
                              max_age=_SF_ADMIN_MAX_AGE, now=_dt.datetime.utcnow())
    if not data or not data.get("admin"):
        return None
    return data


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login(request: Request):
    return templates.TemplateResponse(request=request, name="admin_login.html", context={})


@app.post("/admin/auth/request")
async def admin_auth_request(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="Invalid email address.")
    if not _sf_is_admin(_store_db(), email):
        raise HTTPException(status_code=403, detail="This email is not an administrator.")
    sender = _store_code_sender()
    if isinstance(sender, _SfFakeCodeSender):
        raise HTTPException(
            status_code=503,
            detail=(
                "Email delivery is not configured. Set storefront.smtp in settings.json "
                "or STOREFRONT_SMTP_* environment variables."
            ),
        )
    try:
        _sf_request_code(email, now=_dt.datetime.utcnow(),
                         code_sender=sender, store=_store_auth_store())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to send email code: {exc}")
    return JSONResponse({"sent": True})


@app.post("/admin/auth/verify")
async def admin_auth_verify(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    code = (body.get("code") or "").strip()
    if not _sf_is_admin(_store_db(), email):
        raise HTTPException(status_code=403, detail="This email is not an administrator.")
    ok = _sf_verify_code(email, code, now=_dt.datetime.utcnow(), store=_store_auth_store())
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid or expired code.")
    token = _sf_sign_session({"email": email, "admin": True}, _store_session_secret(),
                             now=_dt.datetime.utcnow())
    resp = JSONResponse({"authenticated": True})
    resp.set_cookie("sf_admin", token, httponly=True, samesite="lax",
                    secure=_store_https(), max_age=_SF_ADMIN_MAX_AGE)
    return resp


_ORDERS_PAGE_SIZE = 20


@app.get("/admin/orders", response_class=HTMLResponse)
def admin_orders(request: Request, q: str = "", status: str = "", page: int = 1):
    if _require_admin(request) is None:
        return RedirectResponse(url="/admin/login", status_code=303)

    db = _store_db()
    all_orders = _sf_list_orders(db, limit=10000)

    # Enrich with human-readable book title
    title_cache: dict[str, str] = {}
    for o in all_orders:
        slug = o["slug"]
        if slug not in title_cache:
            try:
                cfg = _store_read_config(slug)
                title_cache[slug] = cfg.get("title") or slug
            except Exception:
                title_cache[slug] = slug
        o["book_title"] = title_cache[slug]

    # Filter: text search on email, child_name, slug, reference
    if q:
        q_low = q.strip().lower()
        all_orders = [
            o for o in all_orders
            if q_low in o["email"].lower()
            or q_low in o["child_name"].lower()
            or q_low in o["slug"].lower()
            or q_low in o["reference"].lower()
        ]

    # Filter: status (all 6 valid values)
    valid_statuses = ("pending", "paid", "failed", "processing", "shipped", "refunded")
    if status in valid_statuses:
        all_orders = [o for o in all_orders if o["status"] == status]

    # Pagination
    total = len(all_orders)
    page = max(1, page)
    total_pages = max(1, (total + _ORDERS_PAGE_SIZE - 1) // _ORDERS_PAGE_SIZE)
    page = min(page, total_pages)
    start = (page - 1) * _ORDERS_PAGE_SIZE
    orders = all_orders[start: start + _ORDERS_PAGE_SIZE]

    # KPI stats
    now = _dt.datetime.utcnow()
    stats = _sf_get_stats(db, today=now.strftime("%Y-%m-%d"), month_prefix=now.strftime("%Y-%m"))

    return templates.TemplateResponse(
        request=request, name="admin_orders.html",
        context={
            "orders": orders,
            "q": q,
            "status_filter": status,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "stats": stats,
        },
    )


@app.get("/admin/orders/{reference}/photo")
def admin_order_photo(reference: str, request: Request):
    if _require_admin(request) is None:
        raise HTTPException(status_code=401, detail="Admin sign in required.")
    order = _sf_get_order(_store_db(), reference)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    path = pathlib.Path(order["photo_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photo not found.")
    return FileResponse(str(path), media_type="image/png",
                        headers={"Cache-Control": "no-store"})


@app.get("/admin/orders/{reference}", response_class=HTMLResponse)
def admin_order_detail(reference: str, request: Request):
    if _require_admin(request) is None:
        return RedirectResponse(url="/admin/login", status_code=303)
    order = _sf_get_order(_store_db(), reference)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    try:
        cfg = _store_read_config(order["slug"])
        book_title = cfg.get("title") or order["slug"]
    except Exception:
        book_title = order["slug"]
    return templates.TemplateResponse(
        request=request, name="admin_order_detail.html",
        context={"order": order, "book_title": book_title},
    )


@app.post("/admin/orders/{reference}/status")
async def admin_set_order_status(reference: str, request: Request):
    if _require_admin(request) is None:
        raise HTTPException(status_code=401, detail="Admin sign in required.")
    body = await request.json()
    new_status = (body.get("status") or "").strip()
    db = _store_db()
    order = _sf_get_order(db, reference)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    try:
        _sf_set_order_status(db, reference, new_status, now=_dt.datetime.utcnow())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"reference": reference, "status": new_status}


@app.post("/admin/orders/{reference}/notes")
async def admin_set_order_notes(reference: str, request: Request):
    if _require_admin(request) is None:
        raise HTTPException(status_code=401, detail="Admin sign in required.")
    body = await request.json()
    notes = (body.get("notes") or "")
    db = _store_db()
    order = _sf_get_order(db, reference)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    _sf_set_order_notes(db, reference, notes, now=_dt.datetime.utcnow())
    return {"reference": reference, "saved": True}


@app.get("/api/admin/stats")
def admin_stats(request: Request):
    if _require_admin(request) is None:
        raise HTTPException(status_code=401, detail="Admin sign in required.")
    now = _dt.datetime.utcnow()
    stats = _sf_get_stats(
        _store_db(),
        today=now.strftime("%Y-%m-%d"),
        month_prefix=now.strftime("%Y-%m"),
    )
    return stats


@app.post("/api/storyforge/{name}/publish")
def storyforge_publish(name: str, published: bool = True):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', name):
        raise HTTPException(status_code=400, detail="Invalid book name")
    try:
        cfg = read_config(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Book not found.")
    cfg["published"] = published
    write_config(name, cfg)
    return {"name": name, "published": published}


@app.get("/admin/stories", response_class=HTMLResponse)
def admin_stories(request: Request):
    if _require_admin(request) is None:
        return RedirectResponse(url="/admin/login", status_code=303)
    all_orders = _sf_list_orders(_store_db(), limit=10000)
    order_counts: dict[str, int] = {}
    for o in all_orders:
        order_counts[o["slug"]] = order_counts.get(o["slug"], 0) + 1
    entries = []
    for name in _list_books():
        status = _book_status(name)
        entries.append({
            "slug":        name,
            "title":       status.get("title", name),
            "category":    status.get("category", ""),
            "page_count":  status.get("in_sequence", 0),
            "order_count": order_counts.get(name, 0),
            "published":   status.get("published", False),
        })
    return templates.TemplateResponse(
        request=request, name="admin_stories.html", context={"entries": entries},
    )


if __name__ == "__main__":
    import uvicorn
    print("\nKDP Dashboard running at http://localhost:8000\n")
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=8000, reload=True, app_dir=str(ROOT))



