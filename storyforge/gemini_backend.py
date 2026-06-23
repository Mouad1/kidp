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

    def generate(self, prompt: str, reference_images: list[bytes] | None = None) -> bytes:
        contents = [prompt]
        if reference_images:
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

