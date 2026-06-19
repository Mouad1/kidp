import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
SETTINGS_FILE = ROOT / "settings.json"


def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        return json.loads(SETTINGS_FILE.read_text())
    return {}


def _call_gemini(source_text: str, page_count: int) -> dict:
    """Appel Gemini réel — remplacé par monkeypatch dans les tests."""
    from google import genai
    from google.genai import types

    client = genai.Client()
    settings = _load_settings()
    model = settings.get("text_model", "gemini-2.5-flash")

    page_schema = {
        "type": "OBJECT",
        "properties": {
            "page_number": {"type": "INTEGER"},
            "text": {
                "type": "OBJECT",
                "properties": {
                    "fr": {"type": "STRING"}, "ar": {"type": "STRING"},
                    "en": {"type": "STRING"}, "es": {"type": "STRING"},
                },
                "required": ["fr", "ar", "en", "es"],
            },
            "moral": {"type": "STRING"},
            "image_prompt": {"type": "STRING"},
        },
        "required": ["page_number", "text", "moral", "image_prompt"],
    }
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "story_base_prompt": {"type": "STRING"},
            "default_character_description": {
                "type": "STRING",
                "description": "Visual description of the main character (appearance, style). Used as the default {HERO} reference.",
            },
            "intro_text": {"type": "STRING"},
            "values_learned": {"type": "STRING"},
            "pages": {"type": "ARRAY", "items": page_schema},
        },
        "required": ["story_base_prompt", "default_character_description",
                     "intro_text", "values_learned", "pages"],
    }

    prompt = f"""You are an expert children's book editor.
Analyze the following source material and generate a {page_count}-page children's storybook script.

Rules:
- Translate page text into French, Arabic, English, and Spanish.
- Each image_prompt MUST use {{HERO}} as placeholder for the main character.
  Example: "{{HERO}} running through a forest, soft morning light"
- default_character_description: detailed visual description of the main character
  (hair color/style, skin tone, clothing, expression). This will substitute {{HERO}}
  when generating template preview images.
- story_base_prompt: global art direction only (style, palette, atmosphere).
  Do NOT include character description here.
- Keep morals in French.
- Generate exactly {page_count} pages.

Source material:
{source_text}
"""

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.2,
        ),
    )
    return json.loads(response.text)


def generate_from_source(source: str, page_count: int = 8) -> dict:
    """Génère un script depuis texte ou URL (YouTube supporté nativement par Gemini).

    Retourne un dict avec :
    - story_base_prompt, default_character_description, intro_text, values_learned
    - pages[] : image_prompt contient {HERO} (pour template.json)
    - config_pages[] : image_prompt avec {HERO} substitué par default_character_description
                       (pour config.py — génération images sans hero photos)
    """
    raw = _call_gemini(source, page_count)
    char_desc = raw.get("default_character_description", "")

    config_pages = []
    for p in raw.get("pages", []):
        cp = dict(p)
        cp["image_prompt"] = p["image_prompt"].replace("{HERO}", char_desc)
        config_pages.append(cp)

    return {**raw, "config_pages": config_pages}


def parse_story_script(script_text: str) -> dict:
    """Compatibilité ascendante."""
    return generate_from_source(script_text, page_count=8)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=str, required=True)
    parser.add_argument("--pages", type=int, default=8)
    args = parser.parse_args()
    with open(args.script, "r") as f:
        content = f.read()
    result = generate_from_source(content, page_count=args.pages)
    print(json.dumps(result, indent=2, ensure_ascii=False))
