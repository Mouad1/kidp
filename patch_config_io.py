import re

with open("pipeline/config_io.py", "r") as f:
    config_data = f.read()

# 1. read_config changes: adding category, story_base_prompt, pages
config_data = config_data.replace(
'''    return {
        "title":                getattr(module, "TITLE",    ""),''',
'''    return {
        "category":             getattr(module, "CATEGORY", "coloring"),
        "story_base_prompt":    getattr(module, "STORY_BASE_PROMPT", ""),
        "pages":                getattr(module, "PAGES", []),
        "title":                getattr(module, "TITLE",    ""),'''
)

# 2. write_config changes: adding new kwargs
config_data = config_data.replace(
'''    content = _render_config(
        book_name            = book_name,
        title                = data.get("title", ""),''',
'''    content = _render_config(
        category             = data.get("category", "coloring"),
        story_base_prompt    = data.get("story_base_prompt", ""),
        pages                = data.get("pages", []),
        book_name            = book_name,
        title                = data.get("title", ""),'''
)

# 3. _render_config signature:
config_data = config_data.replace(
'''def _render_config(
    book_name: str,''',
'''def _render_config(
    category: str,
    story_base_prompt: str,
    pages: list,
    book_name: str,'''
)

# 4. _render_config content: adding pages formatter and category header
config_data = config_data.replace(
'''    # Formater PAGE_SEQUENCE
    seq_lines = []''',
'''    # Formater PAGES (pour le mode "story")
    # Chaque page a: page_number, text (dict fr,ar,en,es), moral, image_prompt
    pages_blocks = []
    for p in pages:
        text_str = json.dumps(p.get("text", {}), ensure_ascii=False)
        pages_blocks.append(
            "    {\n"
            f'        "page_number":  {p.get("page_number", 0)},\n'
            f'        "text":         {text_str},\n'
            f'        "moral":        {json.dumps(p.get("moral", ""), ensure_ascii=False)},\n'
            f'        "image_prompt": {json.dumps(p.get("image_prompt", ""), ensure_ascii=False)},\n'
            "    }"
        )
    pages_str = "[\n" + ",\n".join(pages_blocks) + "\n]" if pages_blocks else "[]"

    # Formater PAGE_SEQUENCE
    seq_lines = []'''
)

config_data = config_data.replace(
'''f'import pathlib\n\n'
        f'# ── Identity ───────────────────────────────────────────────────────────────────\n\n'
        f'TITLE    = {json.dumps(title, ensure_ascii=False)}\n'
        f'SUBTITLE = {json.dumps(subtitle, ensure_ascii=False)}\n'
        f'AUTHOR   = {json.dumps(author, ensure_ascii=False)}\n\n'
        f'# ── Paths ──────────────────────────────────────────────────────────────────────\n\n'
        f'IMAGES_DIR = pathlib.Path(__file__).parent.parent.parent / "images" / {json.dumps(images_folder, ensure_ascii=False)}\n'
        f'TESTPEN    = {json.dumps(testpen, ensure_ascii=False)}\n\n'
        f'# ── Character roster ──────────────────────────────────────────────────────────\n\n'
        f'CHARACTERS = {chars_str}\n\n'
        f'# ── Page sequence ─────────────────────────────────────────────────────────────\n\n'
        f'PAGE_SEQUENCE = {seq_str}\n\n'
        f'# ── KDP Metadata ────────────────────────────────────────────────────────────────\n\n'
        f'KDP_METADATA = {json.dumps(kdp_metadata, ensure_ascii=False, indent=4)}\n\n'
        f'# ── Title-page layout ─────────────────────────────────────────────────────────\n\n'
        f'TITLE_PAGE_LINES = {tpl_str}\n\n'''
,
'''f'import pathlib\n\n'
        f'# ── Identity ───────────────────────────────────────────────────────────────────\n\n'
        f'CATEGORY = {json.dumps(category, ensure_ascii=False)}\n'
        f'TITLE    = {json.dumps(title, ensure_ascii=False)}\n'
        f'SUBTITLE = {json.dumps(subtitle, ensure_ascii=False)}\n'
        f'AUTHOR   = {json.dumps(author, ensure_ascii=False)}\n\n'
        f'# ── Paths ──────────────────────────────────────────────────────────────────────\n\n'
        f'IMAGES_DIR = pathlib.Path(__file__).parent.parent.parent / "images" / {json.dumps(images_folder, ensure_ascii=False)}\n'
        f'TESTPEN    = {json.dumps(testpen, ensure_ascii=False)}\n\n'
        f'# ── Story (Type: Story) ───────────────────────────────────────────────────────\n\n'
        f'STORY_BASE_PROMPT = {json.dumps(story_base_prompt, ensure_ascii=False)}\n\n'
        f'PAGES = {pages_str}\n\n'
        f'# ── Character roster (Type: Coloring) ─────────────────────────────────────────\n\n'
        f'CHARACTERS = {chars_str}\n\n'
        f'# ── Page sequence ─────────────────────────────────────────────────────────────\n\n'
        f'PAGE_SEQUENCE = {seq_str}\n\n'
        f'# ── KDP Metadata ────────────────────────────────────────────────────────────────\n\n'
        f'KDP_METADATA = {json.dumps(kdp_metadata, ensure_ascii=False, indent=4)}\n\n'
        f'# ── Title-page layout ─────────────────────────────────────────────────────────\n\n'
        f'TITLE_PAGE_LINES = {tpl_str}\n\n'''
)

with open("pipeline/config_io.py", "w") as f:
    f.write(config_data)

