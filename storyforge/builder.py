import pathlib

from pipeline.config_io import write_config
from storyforge.identity import save_sheet
from storyforge.types import PageSpec, CharacterSheet

ROOT = pathlib.Path(__file__).parent.parent


_ALL_LANGS = ("fr", "ar", "en", "es")


def build_book(
    book_name: str,
    title: str,
    author: str,
    mode: str,
    specs: list[PageSpec],
    page_pngs: list[bytes],
    hero: CharacterSheet,
    languages: list[str] | None = None,
    page_texts: list[dict[str, str]] | None = None,
) -> None:
    images_dir = ROOT / "images" / book_name
    images_dir.mkdir(parents=True, exist_ok=True)

    for spec, png in zip(specs, page_pngs):
        (images_dir / f"{book_name}_page_{spec.page_number}.png").write_bytes(png)

    category = "story" if mode == "color" else "coloring"
    story_format = "colored" if mode == "color" else "coloring"

    languages = languages or ["fr"]

    def _text_for(i: int, spec: PageSpec) -> dict[str, str]:
        provided = page_texts[i] if page_texts is not None and i < len(page_texts) else None
        text = {lang: "" for lang in _ALL_LANGS}
        if provided is not None:
            for lang, value in provided.items():
                text[lang] = value
        else:
            for lang in languages:
                text[lang] = spec.text
        return text

    pages = [
        {
            "page_number": spec.page_number,
            "text": _text_for(i, spec),
            "moral": "",
            "image_prompt": spec.image_prompt,
        }
        for i, spec in enumerate(specs)
    ]

    data = {
        "category": category,
        "story_format": story_format,
        "story_layout": "top_bottom",
        "languages": languages,
        "story_base_prompt": hero.art_style,
        "intro_text": "",
        "values_learned": "",
        "pages": pages,
        "title": title,
        "subtitle": "",
        "author": author,
        "images_folder": book_name,
        "characters": [],
    }
    write_config(book_name, data)

    save_sheet(ROOT / "books" / book_name, hero)
