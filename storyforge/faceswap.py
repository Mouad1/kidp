import os

from storyforge.types import PageSpec, CharacterSheet
from storyforge.imagegen import ImageGenerator
from storyforge.gemini_backend import extract_fixed_wardrobe, extract_page_assets

def generate_story_prompt(
    base_template_image: str,
    client_photo_reference: str,
    character_visual_identity: str,
    fixed_wardrobe_description: str,
    core_background_anchors: list[str],
    hero_action_and_emotion: str,
    art_style: str,
) -> str:
    anchors = ", ".join(core_background_anchors) if core_background_anchors else "background and secondary characters"
    return (
        f"Create a children's storybook illustration in {art_style} style, "
        f"using the scene composition reference image as the layout guide.\n\n"
        f"[ENVIRONMENT LOCK]:\n"
        f"Replicate the exact composition, perspective, lighting, and background from the scene reference. "
        f"The scene must retain: {anchors}.\n\n"
        f"[HERO REPLACEMENT]:\n"
        f"Replace the main protagonist from the scene reference with the child shown in the face reference photos. "
        f"The new hero must have these exact physical traits: {character_visual_identity}. "
        f"Match the art style ({art_style}) exactly.\n\n"
        f"[WARDROBE CONTINUITY]:\n"
        f"Dress the new hero in: {fixed_wardrobe_description}.\n\n"
        f"[ACTION MATCH]:\n"
        f"Position the new hero exactly where the original was, performing this action: {hero_action_and_emotion}. "
        f"Do not change any other characters or elements."
    )

def run_hybrid_faceswap(
    spec: PageSpec,
    hero: CharacterSheet,
    gen: ImageGenerator,
    template_image_bytes: bytes,
) -> bytes:
    # 1. Check if generator is fake or missing real backend client
    client = getattr(gen, "_client", None)
    is_fake = client is None

    # Determine background anchors and hero action
    core_background_anchors = spec.core_background_anchors
    hero_action_and_emotion = spec.hero_action_and_emotion
    fixed_wardrobe_description = spec.fixed_wardrobe_description

    if is_fake:
        if not core_background_anchors:
            core_background_anchors = ["original background elements"]
        if not hero_action_and_emotion:
            hero_action_and_emotion = "posing in the scene"
        if not fixed_wardrobe_description:
            fixed_wardrobe_description = "matching outfit"
    else:
        if not fixed_wardrobe_description:
            try:
                fixed_wardrobe_description = extract_fixed_wardrobe(
                    hero.art_style, hero.descriptor, client=client
                )
            except Exception:
                fixed_wardrobe_description = "matching outfit"

        if not core_background_anchors or not hero_action_and_emotion:
            try:
                assets = extract_page_assets(spec.image_prompt, client=client)
                if not core_background_anchors:
                    core_background_anchors = assets.get("core_background_anchors", ["original background elements"])
                if not hero_action_and_emotion:
                    hero_action_and_emotion = assets.get("hero_action_and_emotion", "posing in the scene")
            except Exception:
                if not core_background_anchors:
                    core_background_anchors = ["original background elements"]
                if not hero_action_and_emotion:
                    hero_action_and_emotion = "posing in the scene"

    base_template_image = f"template_page_{spec.page_number}.png"
    client_photo_reference = "hero_portrait.png"
    character_visual_identity = hero.descriptor or "main character"

    prompt = generate_story_prompt(
        base_template_image=base_template_image,
        client_photo_reference=client_photo_reference,
        character_visual_identity=character_visual_identity,
        fixed_wardrobe_description=fixed_wardrobe_description,
        core_background_anchors=core_background_anchors,
        hero_action_and_emotion=hero_action_and_emotion,
        art_style=hero.art_style,
    )

    # Template is the scene composition reference; hero photos drive face identity.
    scene_reference_images = [template_image_bytes]
    reference_images = [hero.canonical_portrait_png] + list(hero.source_photos)

    # Return the generated image directly — scene_reference mode already
    # produces a stylistically consistent result without needing a crop+paste.
    return gen.generate(
        prompt=prompt,
        reference_images=reference_images,
        preamble_images=None,
        scene_reference_images=scene_reference_images,
    )
