from typing import Callable
from storyforge.types import PageSpec

TranslateFn = Callable[[str, list[str]], dict[str, str]]


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
