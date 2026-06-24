from dataclasses import dataclass, field


@dataclass
class Variable:
    key: str
    label: str
    type: str  # "text" | "select"
    options: list[str] = field(default_factory=list)
    default: str | None = None


@dataclass
class PageBeat:
    beat: str
    text: str
    image_prompt: str
    core_background_anchors: list[str] = field(default_factory=list)
    hero_action_and_emotion: str = ""


@dataclass
class Template:
    name: str
    mode: str  # "color" | "lineart"
    language_default: str
    art_style: str
    variables: list[Variable]
    pages: list[PageBeat]
    slug: str = ""
    fixed_wardrobe_description: str = ""


@dataclass
class CharacterSheet:
    descriptor: str
    canonical_portrait_png: bytes
    art_style: str
    source_photos: list[bytes] = field(default_factory=list)


@dataclass
class PageSpec:
    page_number: int
    text: str
    image_prompt: str
    mode: str
    reference_required: bool = True
    core_background_anchors: list[str] = field(default_factory=list)
    hero_action_and_emotion: str = ""
    fixed_wardrobe_description: str = ""

