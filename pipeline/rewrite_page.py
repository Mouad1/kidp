import sys
import json
import os
import argparse
from google import genai
from google.genai import types

def run(remark, text_fr, moral):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(json.dumps({"error": "GEMINI_API_KEY missing"}))
        sys.exit(1)
        
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
Tu es un auteur/traducteur professionnel de livres pour enfants. 
L'utilisateur a fait une remarque sur une page de son histoire.

Texte actuel (FR) : {text_fr}
Morale associée : {moral}

Remarque de l'utilisateur : {remark}

Objectif :
1. Réécris le texte en Français pour prendre en compte la remarque.
2. Traduis ce nouveau texte corrigé en Anglais (EN), Espagnol (ES) et Arabe (AR).
3. Adapte légèrement la morale si nécessaire, sinon garde la même.

Retourne STRICTEMENT ET UNIQUEMENT ce JSON valide :
{{
    "text": {{
        "fr": "Le nouveau texte en français",
        "en": "The translated text in english",
        "es": "El texto traducido en español",
        "ar": "النص المترجم بالعربية"
    }},
    "moral": "La morale (modifiée ou non)"
}}
"""
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        print(response.text)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--remark", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--moral", required=False, default="")
    args = parser.parse_args()
    run(args.remark, args.text, args.moral)
