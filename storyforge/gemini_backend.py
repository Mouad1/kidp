import os

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover
    genai = None
    genai_types = None

IMAGE_MODEL = "gemini-3.1-flash-image"
TEXT_MODEL = "gemini-2.5-flash"


class GeminiBackend:
    """Real ImageGenerator over google-genai. The only module that touches the network."""

    def __init__(self, api_key: str | None = None, image_model: str = IMAGE_MODEL):
        if genai is None:
            raise RuntimeError("google-genai not installed. Run: pip install google-genai")
        key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        self._client = genai.Client(api_key=key)
        self._image_model = image_model

    def generate(
        self,
        prompt: str,
        reference_images: list[bytes] | None = None,
        preamble_images: list[bytes] | None = None,
        scene_reference_images: list[bytes] | None = None,
    ) -> bytes:
        """Generate an image from prompt + optional reference images.

        scene_reference_images: scene composition guide (layout/background).
            Placed before the prompt with label so the model uses it as a
            composition reference, not as a source to reproduce verbatim.
        preamble_images: legacy image-editing source (placed before prompt, unlabeled).
        reference_images: face/style references placed after the prompt.
        """
        contents = []
        if scene_reference_images:
            contents.append("Scene composition reference:")
            for img in scene_reference_images:
                contents.append(genai_types.Part.from_bytes(data=img, mime_type="image/png"))
        if preamble_images:
            contents.append("Source image to modify:")
            for img in preamble_images:
                contents.append(genai_types.Part.from_bytes(data=img, mime_type="image/png"))
            contents.append("Instructions:")
        contents.append(prompt)
        if reference_images:
            contents.append("Reference face photos of the target person:")
            for img in reference_images:
                contents.append(
                    genai_types.Part.from_bytes(data=img, mime_type="image/png")
                )
        response = self._client.models.generate_content(
            model=self._image_model,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) is not None:
                return part.inline_data.data
        raise RuntimeError("Gemini returned no image.")


def analyze_photos(photos: list[bytes], text_model: str = TEXT_MODEL, api_key: str | None = None) -> str:
    """Produce a compact physical descriptor of the person for hero consistency."""
    key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
    client = genai.Client(api_key=key)
    parts = [
        "Describe this person's physical appearance for a consistent children's book "
        "character: approximate age, hair color and style, eye color, skin tone, and any "
        "distinctive features. Reply with one compact comma-separated phrase, no sentences.",
    ]
    for img in photos:
        parts.append(genai_types.Part.from_bytes(data=img, mime_type="image/png"))
    response = client.models.generate_content(model=text_model, contents=parts)
    return (response.text or "").strip()


def expand_story(prompt: str, page_count: int, text_model: str = TEXT_MODEL,
                 api_key: str | None = None) -> list[dict[str, str]]:
    """Expand a base narrative into exactly page_count pages of {text, image_prompt}."""
    import json
    key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
    client = genai.Client(api_key=key)
    instruction = (
        f"{prompt}\n\n"
        f"Respond ONLY with a JSON array of exactly {page_count} objects, each with "
        f'keys "text" and "image_prompt". Keep every token in curly braces verbatim.'
    )
    response = client.models.generate_content(
        model=text_model,
        contents=[instruction],
        config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
    )
    data = json.loads(response.text or "[]")
    return [{"text": d["text"], "image_prompt": d["image_prompt"]} for d in data]


def detect_face_bbox(img_bytes: bytes, text_model: str = TEXT_MODEL, api_key: str | None = None, client = None) -> dict:
    """Identify the bounding box of the main character's face in the image using Gemini."""
    if genai is None:
        raise RuntimeError("google-genai not installed. Run: pip install google-genai")
    c = client
    if c is None:
        key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        c = genai.Client(api_key=key)
    
    prompt = (
        "Identify the bounding box of the main character's face in the image. "
        "Return the coordinates as a JSON object with keys: 'ymin', 'xmin', 'ymax', 'xmax'. "
        "The coordinates must be integers normalized on a 1000x1000 grid "
        "(where 0 is top/left, and 1000 is bottom/right)."
    )
    
    img_part = genai_types.Part.from_bytes(data=img_bytes, mime_type="image/png")
    
    response = c.models.generate_content(
        model=text_model,
        contents=[prompt, img_part],
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    
    import json
    try:
        return json.loads((response.text or "").strip())
    except Exception as exc:
        raise ValueError(f"Failed to parse face bounding box from Gemini: {response.text}") from exc


def extract_fixed_wardrobe(art_style: str, hero_descriptor: str, text_model: str = TEXT_MODEL, api_key: str | None = None, client = None) -> str:
    """Extract a consistent fixed wardrobe description for the hero."""
    if genai is None:
        raise RuntimeError("google-genai not installed.")
    c = client
    if c is None:
        key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        c = genai.Client(api_key=key)
    
    prompt = (
        f"Based on this story art style: '{art_style}' and character physical description: '{hero_descriptor}', "
        f"design a consistent fixed wardrobe (clothing and accessories) for a children's storybook hero to wear on every page for continuity. "
        f"Reply with one concise descriptive sentence, no wrapper or formatting."
    )
    response = c.models.generate_content(model=text_model, contents=[prompt])
    return (response.text or "").strip()


def extract_page_assets(image_prompt: str, text_model: str = TEXT_MODEL, api_key: str | None = None, client = None) -> dict:
    """Extract core background anchors and hero action from an image prompt using Gemini."""
    if genai is None:
        raise RuntimeError("google-genai not installed.")
    c = client
    if c is None:
        key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        c = genai.Client(api_key=key)
    
    prompt = (
        f"Analyze this children's storybook page image prompt: '{image_prompt}'. "
        f"Identify:\n"
        f"1. 3 to 5 core background anchors (critical environmental elements that must be locked/reproduced exactly).\n"
        f"2. The hero's exact action and emotion (physical pose, interaction, and expression matching the prompt).\n"
        f"Respond ONLY with a JSON object containing keys: 'core_background_anchors' (array of strings) and 'hero_action_and_emotion' (string)."
    )
    response = c.models.generate_content(
        model=text_model,
        contents=[prompt],
        config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
    )
    
    import json
    try:
        return json.loads((response.text or "").strip())
    except Exception as exc:
        raise ValueError(f"Failed to parse page assets from Gemini: {response.text}") from exc

