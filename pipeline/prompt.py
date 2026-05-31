"""
pipeline/prompt.py — Shared prompt assembly for Gemini image generation.

Used by both pipeline/generate.py (CLI) and dashboard/app.py (web).
"""

import re

STYLE_TAGS = [
    "thick outlines",
    "thin detailed lines",
    "chibi style",
    "realistic proportions",
    "manga style",
]

POSE_TAGS = [
    "standing portrait",
    "action pose",
    "dynamic battle scene",
    "calm expression",
    "walking forward",
]

ELEMENT_TAGS = [
    "weapon",
    "energy aura",
    "companion animal",
    "background elements",
    "shadow army silhouettes",
    "magical effects",
    "detailed environment",
]

THEME_TAGS = [
    "Art Nouveau",
    "Mandala-infused",
    "Kawaii",
    "Geometric",
    "Baroque",
]

GROUP_DYNAMICS = [
    "back-to-back",
    "facing each other",
    "battle formation",
    "side by side",
    "walking together",
]

_BASE_TEMPLATE = (
    "Create a professional adult coloring book page. "
    "CRITICAL RULE: THIS IS A PURE BLACK AND WHITE IMAGE. Do NOT use any color whatsoever — no blue, no red, no green, no yellow, no pink. The ONLY ink is BLACK lines on WHITE paper. "
    "Ignore the character's canonical color scheme entirely. Render everything as pure black outlines on white. "
    "This is a printed coloring page — imagine it has already been printed on white paper and a person will now color it with markers. "
    "Everything on the page is blank white waiting to be colored. Nothing is pre-colored. Nothing is pre-filled. "
    "Character: {character_prompt}. "
    "Full body, centered, pure white background. "
    "Render ONLY thin-to-medium black outlines and interior line details. "
    "KEY RULE — HAIR: no matter what color the character's hair is in the source material, "
    "draw the hair as fine individual strands and locks on a WHITE background. "
    "The hair region must be WHITE with black line details drawn over it — never a solid black mass, never gray. "
    "KEY RULE — DARK CLOTHING, BOOTS, ACCESSORIES: outline the shape with black lines and add interior texture lines — "
    "the interior must remain WHITE. Never fill any clothing region solid. "
    "KEY RULE — EVERYTHING ELSE: skin, eyes, weapons, background elements — outline only, white interior. "
    "Forbidden: solid fills, gray fills, shading, gradients, hatching, color of any kind. "
    "Style: Johanna Basford 'Secret Garden' coloring book — every enclosed area is white and empty, waiting for color. "
    "Output: high contrast black line art on pure white, 300 DPI, ready to color."
)


def compact_character_description(description: str) -> str:
    """
    Normalize legacy dashboard prompt payloads into compact character descriptions.

    Older UI versions sometimes saved a fully templated prompt into CHARACTERS.prompt,
    then generation wrapped it again via _BASE_TEMPLATE, which weakens fidelity.
    This sanitizer strips known wrappers so build_prompt always receives only the
    compact character description payload.
    """
    s = (description or "").strip()
    if not s:
        return ""

    # Remove repeated legacy wrapper prefixes.
    wrapper_prefixes = [
        "Provide Professional adult coloring book page of ",
        "Create a professional adult coloring book page. ",
        "Character: ",
    ]
    changed = True
    while changed:
        changed = False
        for pref in wrapper_prefixes:
            if s.startswith(pref):
                s = s[len(pref):].strip()
                changed = True

    # If a full technical tail is embedded, keep only the semantic lead.
    cut_markers = [
        "full body centered, pure white background.",
        "CRITICAL: zero black fills",
        "Thick, bold black vector-style outlines only.",
        "High contrast, clean line art, 300 DPI quality",
    ]
    lower_s = s.lower()
    cut_idx = None
    for marker in cut_markers:
        idx = lower_s.find(marker.lower())
        if idx != -1:
            cut_idx = idx if cut_idx is None else min(cut_idx, idx)
    if cut_idx is not None and cut_idx > 0:
        s = s[:cut_idx].strip().rstrip(",")

    # Collapse accidental duplicated wrapper fragments in the middle.
    s = re.sub(r"\bProvide Professional adult coloring book page of\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,")

    # Remove repeated comma-separated segments while preserving order.
    seen = set()
    seen_identity = False
    seen_reference = False
    deduped = []
    for part in [p.strip() for p in s.split(",") if p.strip()]:
        lower_part = part.lower()
        if lower_part.startswith("character identity:"):
            if seen_identity:
                continue
            seen_identity = True
        if lower_part.startswith("reference source:"):
            if seen_reference:
                continue
            seen_reference = True
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(part)
    s = ", ".join(deduped)

    return s


# Backward-compatible alias for existing internal callers/tests.
def _sanitize_character_description(description: str) -> str:
    return compact_character_description(description)


def build_prompt(
    description: str,
    style_tags: list[str] | None = None,
    pose_tags: list[str] | None = None,
    element_tags: list[str] | None = None,
    theme_tags: list[str] | None = None,
    extra_notes: str = "",
) -> str:
    parts = [compact_character_description(description)]
    if extra_notes and extra_notes.strip():
        parts.append(extra_notes.strip())
    for tag_list in (style_tags, pose_tags, element_tags, theme_tags):
        if tag_list:
            parts.extend(tag_list)
    character_prompt = ", ".join(p.strip() for p in parts if p.strip())
    return _BASE_TEMPLATE.format(character_prompt=character_prompt)


def build_group_prompt(
    character_descriptions: list[str],
    style_tags: list[str] | None = None,
    element_tags: list[str] | None = None,
    theme_tags: list[str] | None = None,
    group_dynamic: str = "",
    extra_notes: str = "",
) -> str:
    desc = " alongside ".join(d.strip() for d in character_descriptions if d.strip())
    parts = [desc]
    if extra_notes and extra_notes.strip():
        parts.append(extra_notes.strip())
    if group_dynamic:
        parts.append(group_dynamic)
    for tag_list in (style_tags, element_tags, theme_tags):
        if tag_list:
            parts.extend(tag_list)
    character_prompt = ", ".join(p.strip() for p in parts if p.strip())
    return _BASE_TEMPLATE.format(character_prompt=character_prompt)


def build_story_prompt(story_base: str, scene: str, is_coloring: bool = False) -> str:
    color_instructions = (
        "CRITICAL RULE: THIS IS A PURE BLACK AND WHITE LINEART IMAGE FOR A COLORING BOOK. "
        "Do NOT use any color whatsoever. The ONLY ink is BLACK lines on pure WHITE paper. "
        "EVERYTHING MUST BE WHITE WITH THIN TO MEDIUM BLACK OUTLINES OUTLINING THE SHAPES. "
        "No solid fills, no dark shading, no grey, no color. Keep it simple and clear for kids to color in."
    ) if is_coloring else (
        "Use vibrant, harmonious colors suited for kids. "
        "Keep the artistic style, character designs, and lighting highly consistent."
    )
    
    return (
        "You are an expert children's book illustrator. "
        f"Create a beautiful illustration that captures the magic, " 
        f"warmth, and wonder of a classic children's storybook. "
        "CRITICAL RULES: NO text, NO words, NO letters in the image. "
        f"{color_instructions} "
        f"Art Direction: {story_base.strip()}\n\n"
        f"Scene to draw: {scene.strip()}\n"
    )
