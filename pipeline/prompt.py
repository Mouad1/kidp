"""
pipeline/prompt.py — Shared prompt assembly for Gemini image generation.

Used by both pipeline/generate.py (CLI) and dashboard/app.py (web).
"""

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


def build_prompt(
    description: str,
    style_tags: list[str] | None = None,
    pose_tags: list[str] | None = None,
    element_tags: list[str] | None = None,
    theme_tags: list[str] | None = None,
    extra_notes: str = "",
) -> str:
    parts = [description]
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
