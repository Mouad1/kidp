import argparse

import json
from pathlib import Path
ROOT = Path(__file__).parent.parent
SETTINGS_FILE = ROOT / "settings.json"

import json
import os
import sys
from google import genai
from google.genai import types

def parse_story_script(script_text: str) -> dict:
    """
    Parses a raw story script using Gemini and returns a structured JSON dict.
    The output schema strictly defines:
    - story_base_prompt: The global artistic direction and character definitions.
    - pages: List of pages, each with translations, moral, and image prompt.
    """
    client = genai.Client()
    
    # Schema definition
    page_schema = {
        "type": "OBJECT",
        "properties": {
            "page_number": {"type": "INTEGER"},
            "text": {
                "type": "OBJECT",
                "properties": {
                    "fr": {"type": "STRING"},
                    "ar": {"type": "STRING"},
                    "en": {"type": "STRING"},
                    "es": {"type": "STRING"}
                },
                "required": ["fr", "ar", "en", "es"]
            },
            "moral": {"type": "STRING", "description": "The moral of the page, ideally in French"},
            "image_prompt": {"type": "STRING", "description": "Detailed image prompt in English referencing the base style"}
        },
        "required": ["page_number", "text", "moral", "image_prompt"]
    }
    
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "story_base_prompt": {"type": "STRING", "description": "The main graphic charter and persistent characters definition"},
            "intro_text": {"type": "STRING", "description": "Write a highly attractive short introductory text indicating what the book is about, to captivate parents/children"},
            "values_learned": {"type": "STRING", "description": "Extract a bullet point list of 3 educational or moral values taught in this story in French"},
            "pages": {
                "type": "ARRAY",
                "items": page_schema
            }
        },
        "required": ["story_base_prompt", "intro_text", "values_learned", "pages"]
    }

    prompt = f"""
    You are an expert children's book editor and AI pipeline engineer.
    Analyze the following raw script for a storybook.
    
    Extract the main artistic direction ('Charte Graphique' / 'Main Prompt') into 'story_base_prompt'.
    Extract all pages. For each page, the user may have provided text in only one language (e.g., French). 
    You MUST translate the storytelling text into French, Arabic, English, and Spanish for the 'text' object.
    Keep the 'moral' in the original language (usually French).
    Extract the exact 'image_prompt' provided for the page (usually English).
    Also generate a highly attractive introductory text ('intro_text') to make people want to buy the book, and a summary list of the top 3 'values_learned' based on the story's morals.
    
    Raw Script:
    {script_text}
    """

    settings = {}
    if SETTINGS_FILE.exists():
        settings = json.loads(SETTINGS_FILE.read_text())
    ai_model = settings.get("text_model", "gemini-2.5-flash")

    response = client.models.generate_content(
        model=ai_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.2,
        ),
    )
    
    return json.loads(response.text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=str, required=True, help="Raw script text")
    args = parser.parse_args()
    
    with open(args.script, "r") as f:
        script_content = f.read()
    result = parse_story_script(script_content)
    print(json.dumps(result, indent=2, ensure_ascii=False))
