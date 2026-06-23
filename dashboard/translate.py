import json
import os
from google import genai
from google.genai import types

_LANG_GUIDANCE = {
    "ar": (
        "Arabic (ar): Use Modern Standard Arabic (فصحى / MSA). "
        "Keep vocabulary simple and age-appropriate for young children (ages 4-8). "
        "Use short, clear sentences. Preserve the emotional warmth and narrative flow of the original. "
        "Do NOT transliterate — output must be in Arabic script."
    ),
    "fr": "French (fr): Use simple, warm language appropriate for young children.",
    "en": "English (en): Use simple, clear language appropriate for young children.",
    "es": "Spanish (es): Use simple, warm language appropriate for young children.",
}


def translate_text(text: str, target_langs: list) -> dict:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY")) if os.environ.get("GEMINI_API_KEY") else genai.Client()

    lang_notes = "\n".join(
        _LANG_GUIDANCE.get(lang, f"{lang}: translate naturally.")
        for lang in target_langs
    )
    prompt = (
        "You are a professional children's book translator. "
        "Translate the following story page text into the requested languages.\n\n"
        f"Per-language guidance:\n{lang_notes}\n\n"
        f"Text to translate:\n{text}\n\n"
        "Return EXACTLY a JSON object where keys are language codes "
        f"({', '.join(repr(l) for l in target_langs)}) and values are the translated text."
    )

    schema = {
        "type": "OBJECT",
        "properties": { lang: {"type": "STRING"} for lang in target_langs },
        "required": target_langs
    }

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are an expert multilingual children's book translator. "
                "Produce high-quality, natural translations. "
                "For Arabic, always use Modern Standard Arabic in Arabic script."
            ),
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.2,
        ),
    )
    
    try:
        out = response.text.strip()
    except ValueError as e:
        if response.candidates:
            # safety blocked?
            out = "{}"
            print("Safety blocked translation")
        else:
            raise e

    if out.startswith("```json"):
        out = out[7:]
    if out.startswith("```"):
        out = out[3:]
    if out.endswith("```"):
        out = out[:-3]
    return json.loads(out.strip())
