from storyforge.templates import extract_tokens, RESERVED_TOKENS
from storyforge.types import Template, CharacterSheet, PageSpec
from storyforge.errors import ResolutionError


def _substitute(text: str, mapping: dict[str, str]) -> str:
    out = text
    for token, value in mapping.items():
        out = out.replace("{" + token + "}", value)
    return out


def resolve(template: Template, variables: dict[str, str], hero: CharacterSheet) -> list[PageSpec]:
    used: set[str] = set()
    for page in template.pages:
        used |= extract_tokens(page.text) | extract_tokens(page.image_prompt)
    required = {t for t in used if t not in RESERVED_TOKENS}
    missing = required - set(variables)
    if missing:
        raise ResolutionError(f"Missing required variable(s): {', '.join(sorted(missing))}")

    text_mapping = dict(variables)
    image_mapping = dict(variables)
    image_mapping["HERO"] = hero.descriptor

    specs: list[PageSpec] = []
    for i, page in enumerate(template.pages, start=1):
        specs.append(
            PageSpec(
                page_number=i,
                text=_substitute(page.text, text_mapping),
                image_prompt=_substitute(page.image_prompt, image_mapping),
                mode=template.mode,
            )
        )
    return specs
