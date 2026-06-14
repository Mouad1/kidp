import json
import re
from pathlib import Path

from storyforge.types import Variable, PageBeat, Template
from storyforge.errors import TemplateError

ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = ROOT / "templates"

RESERVED_TOKENS = {"HERO", "HERO_NAME"}
_TOKEN_RE = re.compile(r"\{([A-Z_][A-Z0-9_]*)\}")


def extract_tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text or ""))


def parse_template(data: dict, slug: str = "") -> Template:
    try:
        variables = [
            Variable(
                key=v["key"],
                label=v.get("label", v["key"]),
                type=v.get("type", "text"),
                options=list(v.get("options", [])),
                default=v.get("default"),
            )
            for v in data.get("variables", [])
        ]
        pages = [
            PageBeat(
                beat=p.get("beat", ""),
                text=p["text"],
                image_prompt=p["image_prompt"],
            )
            for p in data.get("pages", [])
        ]
        return Template(
            name=data["name"],
            mode=data.get("mode", "color"),
            language_default=data.get("language_default", "fr"),
            art_style=data.get("art_style", ""),
            variables=variables,
            pages=pages,
            slug=slug,
        )
    except (KeyError, TypeError) as exc:
        raise TemplateError(f"Malformed template {slug!r}: missing field {exc}") from exc


def validate_template(tpl: Template) -> Template:
    if tpl.mode not in ("color", "lineart"):
        raise TemplateError(f"Invalid mode {tpl.mode!r} (must be 'color' or 'lineart')")
    if not tpl.pages:
        raise TemplateError("Template has no pages")

    declared = {v.key for v in tpl.variables} | RESERVED_TOKENS
    for v in tpl.variables:
        if v.type not in ("text", "select"):
            raise TemplateError(f"Variable {v.key!r} has invalid type {v.type!r}")
        if v.type == "select" and not v.options:
            raise TemplateError(f"Select variable {v.key!r} requires non-empty options")

    for i, page in enumerate(tpl.pages, start=1):
        used = extract_tokens(page.text) | extract_tokens(page.image_prompt)
        undeclared = used - declared
        if undeclared:
            raise TemplateError(
                f"Page {i} uses undeclared token(s): {', '.join(sorted(undeclared))}"
            )
    return tpl


def load_template(slug: str) -> Template:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*[a-z0-9]", slug):
        raise TemplateError(f"Invalid template slug: {slug!r}")
    path = TEMPLATES_DIR / slug / "template.json"
    if not path.exists():
        raise TemplateError(f"Template {slug!r} not found at {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TemplateError(f"Template {slug!r} is not valid JSON: {exc}") from exc
    return validate_template(parse_template(data, slug=slug))


def list_templates() -> list[Template]:
    if not TEMPLATES_DIR.exists():
        return []
    out = []
    for child in sorted(TEMPLATES_DIR.iterdir()):
        if (child / "template.json").exists():
            try:
                out.append(load_template(child.name))
            except TemplateError:
                continue
    return out
