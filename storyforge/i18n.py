from typing import Callable
from storyforge.types import PageSpec, Template

TranslateFn = Callable[[str, list[str]], dict[str, str]]
ReadConfigFn = Callable[[str], dict]
WriteConfigFn = Callable[[str, dict], None]
LoadTemplateFn = Callable[[str], Template]


def translate_pages(
    specs: list[PageSpec],
    source_language: str,
    target_languages: list[str],
    translate_fn: TranslateFn,
) -> list[dict[str, str]]:
    """Return one {lang: text} dict per page for exactly the selected languages.

    The source language keeps the original spec text; the remaining selected
    languages are produced by translate_fn (injected; faked in tests).
    """
    others = [lang for lang in target_languages if lang != source_language]
    out: list[dict[str, str]] = []
    for spec in specs:
        page = {source_language: spec.text} if source_language in target_languages else {}
        if others:
            translated = translate_fn(spec.text, others)
            for lang in others:
                page[lang] = translated.get(lang, "")
        out.append(page)
    return out


def backfill_missing_translations(
    book_name: str,
    read_config_fn: ReadConfigFn,
    write_config_fn: WriteConfigFn,
    load_template_fn: LoadTemplateFn,
    translate_fn: TranslateFn,
    supported_languages: list[str] | None = None,
) -> list[str]:
    """Backfill missing translations for an existing book config.

    Reads the book config, identifies languages in ``supported_languages`` that
    are missing from ``config["languages"]`` or from any page text, translates
    them from the template's source language, and writes the updated config.

    Returns the list of languages that were added.
    """
    cfg = read_config_fn(book_name)
    tpl = load_template_fn(book_name)
    source_lang = tpl.language_default
    target_langs = list(supported_languages) if supported_languages else ["fr", "en", "es", "ar"]

    cfg_langs = set(cfg.get("languages", []))
    missing_langs: set[str] = set()

    # Languages missing from the book-level list.
    for lang in target_langs:
        if lang not in cfg_langs:
            missing_langs.add(lang)

    # Languages missing from any individual page text.
    for page in cfg.get("pages", []):
        texts = page.get("text") or {}
        if not isinstance(texts, dict):
            continue
        for lang in target_langs:
            if not texts.get(lang):
                missing_langs.add(lang)

    # Source language is never "missing" — it is the original text.
    missing_langs.discard(source_lang)

    if not missing_langs:
        return []

    missing_langs = sorted(missing_langs)

    # Build specs from the source-language text so we can reuse translate_pages.
    specs: list[PageSpec] = []
    for page in cfg.get("pages", []):
        texts = page.get("text") or {}
        source_text = ""
        if isinstance(texts, dict):
            source_text = texts.get(source_lang) or next(
                (t for t in texts.values() if t), ""
            )
        specs.append(PageSpec(
            page_number=page.get("page_number", len(specs) + 1),
            text=source_text,
            image_prompt=page.get("image_prompt", ""),
            mode=tpl.mode,
        ))

    translated = translate_pages(specs, source_lang, missing_langs, translate_fn)

    # Merge translations into the config.
    pages = cfg.get("pages", [])
    for i, page in enumerate(pages):
        if not isinstance(page.get("text"), dict):
            page["text"] = {}
        for lang in missing_langs:
            if i < len(translated):
                page["text"][lang] = translated[i].get(lang, "")

    # Ensure every supported language is declared at the book level.
    cfg["languages"] = sorted(set(cfg.get("languages", [])) | set(target_langs))

    write_config_fn(book_name, cfg)
    return missing_langs
