import json
import os
from google import genai
from google.genai import types

def translate_text(text: str, target_langs: list) -> dict:
    
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY")) if os.environ.get("GEMINI_API_KEY") else genai.Client()
    prompt = f"Translate the following text into these languages: {', '.join(target_langs)}.\n\nText:\n{text}\n\nReturn EXACTLY a JSON object where keys are language codes (like 'en', 'es', 'ar', 'fr') and values are the translated text."
    
    schema = {
        "type": "OBJECT",
        "properties": { lang: {"type": "STRING"} for lang in target_langs },
        "required": target_langs
    }
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.3
        )
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
