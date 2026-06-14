# pipeline/config_io.py
"""
pipeline/config_io.py — Sérialisation/désérialisation des configs de livres.

Utilisé par le dashboard pour lire et écrire books/{name}/config.py.
"""

import importlib.util
import json    # used by write_config
import pathlib
import pprint  # used by write_config

from pipeline.prompt import compact_character_description

ROOT = pathlib.Path(__file__).parent.parent


def _normalize_character(c: dict) -> dict:
    """Return a backward-compatible character payload with optional reference fields."""
    return {
        "id": c.get("id", ""),
        "name": c.get("name", ""),
        "series": c.get("series", ""),
        "prompt": compact_character_description(c.get("prompt", "")),
        "source_type": c.get("source_type", ""),
        "source_title": c.get("source_title", ""),
        "source_character_name": c.get("source_character_name", ""),
    }


def _tuples_to_lists(data):
    """Convertit récursivement tuples → listes pour JSON round-trip cohérent."""
    if isinstance(data, (list, tuple)):
        return [_tuples_to_lists(item) for item in data]
    return data


def _lists_to_tuples(data):
    """Convertit récursivement listes → tuples pour compatibilité PIL."""
    if isinstance(data, list):
        return tuple(_lists_to_tuples(item) for item in data)
    return data


def read_config(book_name: str) -> dict:
    """Charge books/{book_name}/config.py et retourne un dict JSON-serializable."""
    config_path = ROOT / "books" / book_name / "config.py"
    if not config_path.exists():
        raise FileNotFoundError(f"config.py introuvable pour {book_name!r}")

    spec = importlib.util.spec_from_file_location(
        f"books.{book_name}.config", config_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    images_dir = getattr(module, "IMAGES_DIR", None)
    images_folder = images_dir.name if images_dir else book_name

    return {
        "category":             getattr(module, "CATEGORY", "coloring"),
        "published":            getattr(module, "PUBLISHED", False),
        "story_format":         getattr(module, "STORY_FORMAT", "colored"),
        "story_layout":         getattr(module, "STORY_LAYOUT", "top_bottom"),
        "languages":            getattr(module, "LANGUAGES", ["fr"]),
        "story_base_prompt":    getattr(module, "STORY_BASE_PROMPT", ""),
        "intro_text":           getattr(module, "INTRO_TEXT", ""),
        "values_learned":       getattr(module, "VALUES_LEARNED", ""),
        "pages":                getattr(module, "PAGES", []),
        "title":                getattr(module, "TITLE",    ""),
        "subtitle":             getattr(module, "SUBTITLE", ""),
        "author":               getattr(module, "AUTHOR",   ""),
        "testpen":              getattr(module, "TESTPEN",  ""),
        "images_folder":        images_folder,
        "characters":           [_normalize_character(c) for c in getattr(module, "CHARACTERS", [])],
        "page_sequence": [
            {"file": f, "label": lbl}
            for f, lbl in getattr(module, "PAGE_SEQUENCE", [])
        ],
        "title_page_lines":     _tuples_to_lists(getattr(module, "TITLE_PAGE_LINES",     [])),
        "copyright_page_lines": _tuples_to_lists(getattr(module, "COPYRIGHT_PAGE_LINES", [])),
        "back_page_lines":      _tuples_to_lists(getattr(module, "BACK_PAGE_LINES",      [])),
        "kdp_metadata": getattr(module, "KDP_METADATA", {
            "description": "",
            "keywords": [],
            "categories": [],
            "price_usd": 8.99,
            "amazon_asin": "",
        }),
    }


def write_config(book_name: str, data: dict) -> None:
    """Régénère books/{book_name}/config.py depuis un dict JSON."""
    config_path = ROOT / "books" / book_name / "config.py"

    # Préserver les sections non-éditables si le fichier existe déjà
    if config_path.exists():
        existing = read_config(book_name)
        title_page_lines     = data.get("title_page_lines",     existing["title_page_lines"])
        copyright_page_lines = data.get("copyright_page_lines", existing["copyright_page_lines"])
        back_page_lines      = data.get("back_page_lines",      existing["back_page_lines"])
        kdp_metadata         = data.get("kdp_metadata",         existing.get("kdp_metadata", {}))
    else:
        title_page_lines     = data.get("title_page_lines",     _default_title_page(data.get("title", ""), data.get("subtitle", "")))
        copyright_page_lines = data.get("copyright_page_lines", _default_copyright())
        back_page_lines      = data.get("back_page_lines",      _default_back())
        kdp_metadata         = data.get("kdp_metadata",         {})

    if not data.get("page_sequence"):
        if data.get("category") == "story" or data.get("category", existing.get("CATEGORY", "coloring") if "existing" in locals() else "coloring") == "story":
            book_prefix = book_name.split("-")[0]
            page_sequence = [
                {"file": f"{book_name}_page_{p.get('page_number', i+1)}.png", "label": f"Page {p.get('page_number', i+1)}"}
                for i, p in enumerate(data.get("pages", []))
            ]
        else:
            book_prefix = book_name.split("-")[0]  # "book2-modern-anime" → "book2"
            page_sequence = [
                {"file": f"{book_prefix}_{c['id']}.png", "label": c["name"]}
                for c in data.get("characters", [])
            ]
    else:
        page_sequence = data.get("page_sequence", [])

    content = _render_config(
        category             = data.get("category", "coloring"),
        published            = data.get("published", False),
        story_format         = data.get("story_format", "colored"),
        story_layout         = data.get("story_layout", "top_bottom"),
        languages            = data.get("languages", ["fr"]),
        story_base_prompt    = data.get("story_base_prompt", ""),
        intro_text           = data.get("intro_text", ""),
        values_learned       = data.get("values_learned", ""),
        pages                = data.get("pages", []),
        book_name            = book_name,
        title                = data.get("title", ""),
        subtitle             = data.get("subtitle", ""),
        author               = data.get("author", ""),
        testpen              = data.get("testpen", f"{book_name}_testpen.png"),
        images_folder        = data.get("images_folder", book_name),
        characters           = data.get("characters", []),
        page_sequence        = page_sequence,
        title_page_lines     = title_page_lines,
        copyright_page_lines = copyright_page_lines,
        back_page_lines      = back_page_lines,
        kdp_metadata         = kdp_metadata,
    )
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")


def _render_config(
    category: str,
    published: bool,
    story_format: str,
    story_layout: str,
    languages: list,
    story_base_prompt: str,
    intro_text: str,
    values_learned: str,
    pages: list,
    book_name: str,
    title: str,
    subtitle: str,
    author: str,
    testpen: str,
    images_folder: str,
    characters: list,
    page_sequence: list,
    title_page_lines: list,
    copyright_page_lines: list,
    back_page_lines: list,
    kdp_metadata: dict = None,
) -> str:
    if kdp_metadata is None:
        kdp_metadata = {}
    # Formater CHARACTERS
    char_blocks = []
    for c in characters:
        c = _normalize_character(c)
        char_blocks.append(
            "    {\n"
            f'        "id":     {json.dumps(c["id"], ensure_ascii=False)},\n'
            f'        "name":   {json.dumps(c["name"], ensure_ascii=False)},\n'
            f'        "series": {json.dumps(c["series"], ensure_ascii=False)},\n'
            f'        "prompt": {json.dumps(c["prompt"], ensure_ascii=False)},\n'
            f'        "source_type": {json.dumps(c["source_type"], ensure_ascii=False)},\n'
            f'        "source_title": {json.dumps(c["source_title"], ensure_ascii=False)},\n'
            f'        "source_character_name": {json.dumps(c["source_character_name"], ensure_ascii=False)},\n'
            "    }"
        )
    chars_str = "[\n" + ",\n".join(char_blocks) + "\n]" if char_blocks else "[]"

    # Formater PAGES (pour le mode "story")
    # Chaque page a: page_number, text (dict fr,ar,en,es), moral, image_prompt
    pages_blocks = []
    for p in pages:
        text_str = json.dumps(p.get("text", {}), ensure_ascii=False)
        pages_blocks.append(
            "    {\n"
            f'        "page_number":  {p.get("page_number", 0)},\n'
            f'        "text":         {text_str},\n'
            f'        "moral":        {json.dumps(p.get("moral", ""), ensure_ascii=False)},\n'
            f'        "image_prompt": {json.dumps(p.get("image_prompt", ""), ensure_ascii=False)}\n'
            "    }"
        )
    pages_str = "[\n" + ",\n".join(pages_blocks) + "\n]" if pages_blocks else "[]"

    # Formater PAGE_SEQUENCE
    seq_lines = []
    for p in page_sequence:
        seq_lines.append(f'    ({json.dumps(p["file"], ensure_ascii=False)}, {json.dumps(p["label"], ensure_ascii=False)})')
    seq_str = "[\n" + ",\n".join(seq_lines) + "\n]" if seq_lines else "[]"

    # Formater sections non-éditables avec pprint (tuples pour compatibilité PIL)
    tpl_str = pprint.pformat(_lists_to_tuples(title_page_lines),     width=100)
    cpl_str = pprint.pformat(_lists_to_tuples(copyright_page_lines), width=100)
    bpl_str = pprint.pformat(_lists_to_tuples(back_page_lines),      width=100)

    return (
        f'"""\n'
        f'books/{book_name}/config.py — Book data manifest\n\n'
        f'Generated by KDP Dashboard.\n'
        f'Identity, CHARACTERS, and PAGE_SEQUENCE are managed via the dashboard.\n'
        f'Edit TITLE_PAGE_LINES, COPYRIGHT_PAGE_LINES, BACK_PAGE_LINES directly if needed.\n'
        f'"""\n\n'
        f'import pathlib\n\n'
        f'# ── Identity ───────────────────────────────────────────────────────────────────\n\n'
        f'CATEGORY       = {json.dumps(category, ensure_ascii=False)}\n'
        f'PUBLISHED      = {published!r}\n'
        f'STORY_FORMAT   = {json.dumps(story_format, ensure_ascii=False)}\n'
        f'STORY_LAYOUT   = {json.dumps(story_layout, ensure_ascii=False)}\n'
        f'LANGUAGES      = {json.dumps(languages, ensure_ascii=False)}\n'
        f'TITLE          = {json.dumps(title, ensure_ascii=False)}\n'
        f'SUBTITLE       = {json.dumps(subtitle, ensure_ascii=False)}\n'
        f'AUTHOR         = {json.dumps(author, ensure_ascii=False)}\n'
        f'INTRO_TEXT     = {json.dumps(intro_text, ensure_ascii=False)}\n'
        f'VALUES_LEARNED = {json.dumps(values_learned, ensure_ascii=False)}\n\n'
        f'# ── Paths ──────────────────────────────────────────────────────────────────────\n\n'
        f'IMAGES_DIR = pathlib.Path(__file__).parent.parent.parent / "images" / {json.dumps(images_folder, ensure_ascii=False)}\n'
        f'TESTPEN    = {json.dumps(testpen, ensure_ascii=False)}\n\n'
        f'# ── Story settings ────────────────────────────────────────────────────────────\n\n'
        f'STORY_BASE_PROMPT = {json.dumps(story_base_prompt, ensure_ascii=False)}\n\n'
        f'# ── Story Pages ───────────────────────────────────────────────────────────────\n\n'
        f'PAGES = {pages_str}\n\n'
        f'# ── Character roster ──────────────────────────────────────────────────────────\n\n'
        f'CHARACTERS = {chars_str}\n\n'
        f'# ── Page sequence ─────────────────────────────────────────────────────────────\n\n'
        f'PAGE_SEQUENCE = {seq_str}\n\n'
        f'# ── KDP Metadata ────────────────────────────────────────────────────────────────\n\n'
        f'KDP_METADATA = {json.dumps(kdp_metadata, ensure_ascii=False, indent=4)}\n\n'
        f'# ── Title-page layout ─────────────────────────────────────────────────────────\n\n'
        f'TITLE_PAGE_LINES = {tpl_str}\n\n'
        f'# ── Copyright-page layout ────────────────────────────────────────────────────\n\n'
        f'COPYRIGHT_PAGE_LINES = {cpl_str}\n\n'
        f'# ── Back-matter layout ───────────────────────────────────────────────────────\n\n'
        f'BACK_PAGE_LINES = {bpl_str}\n'
    )


def _default_title_page(title: str, subtitle: str) -> list:
    return [
        [title, 120, True, [0, 0, 0]],
        ["Coloring Our Stories", 72, True, [0, 0, 0]],
        ["", 36, False, [255, 255, 255]],
        [subtitle, 46, False, [60, 60, 60]],
        ["", 24, False, [255, 255, 255]],
    ]


def _default_copyright() -> list:
    return [
        ["© 2026 All rights reserved.", 32, True, [40, 40, 40]],
        ["", 18, False, [255, 255, 255]],
        ["No part of this publication may be reproduced", 26, False, [80, 80, 80]],
        ["or distributed without prior written permission.", 26, False, [80, 80, 80]],
        ["", 18, False, [255, 255, 255]],
        ["All characters are original fictional archetypes", 26, False, [80, 80, 80]],
        ["inspired by the world of anime.", 26, False, [80, 80, 80]],
        ["", 18, False, [255, 255, 255]],
        ["Printed in the United States of America", 26, False, [80, 80, 80]],
        ["First Edition", 26, False, [80, 80, 80]],
    ]


def _default_back() -> list:
    return [
        ["Thank you for coloring with us!", 55, True, [0, 0, 0]],
        ["", 30, False, [255, 255, 255]],
        ["If you enjoyed this book,", 40, False, [60, 60, 60]],
        ["please leave a review on Amazon.", 40, False, [60, 60, 60]],
        ["", 24, False, [255, 255, 255]],
        ["It means the world to us", 34, False, [110, 110, 110]],
        ["and helps other families discover it.", 34, False, [110, 110, 110]],
    ]
