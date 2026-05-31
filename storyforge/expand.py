from typing import Callable
from storyforge.types import Template, CharacterSheet, PageSpec
from storyforge.engine import _substitute
from storyforge.errors import ResolutionError

# text_fn(prompt, page_count) -> list[{"text": str, "image_prompt": str}]
TextFn = Callable[[str, int], list[dict[str, str]]]


def _build_prompt(template: Template, variables: dict[str, str], page_count: int) -> str:
    beats = "\n".join(f"- {p.beat}: {p.text}" for p in template.pages)
    return (
        f"Expand this children's story into exactly {page_count} pages, "
        f"preserving the narrative arc and ALL tokens in curly braces "
        f"(e.g. {{HERO_NAME}}, {{HERO}}) verbatim.\n"
        f"Base beats:\n{beats}\n"
        f"Variables: {variables}\n"
        f"Return {page_count} pages, each with 'text' and 'image_prompt'."
    )


def expand_narrative(
    template: Template,
    variables: dict[str, str],
    hero: CharacterSheet,
    page_count: int,
    text_fn: TextFn,
) -> list[PageSpec]:
    prompt = _build_prompt(template, variables, page_count)
    raw = text_fn(prompt, page_count)
    if len(raw) != page_count:
        raise ResolutionError(
            f"Expansion returned {len(raw)} pages, expected {page_count}"
        )

    text_mapping = dict(variables)
    image_mapping = dict(variables)
    image_mapping["HERO"] = hero.descriptor

    specs: list[PageSpec] = []
    for i, page in enumerate(raw, start=1):
        specs.append(
            PageSpec(
                page_number=i,
                text=_substitute(page["text"], text_mapping),
                image_prompt=_substitute(page["image_prompt"], image_mapping),
                mode=template.mode,
            )
        )
    return specs
