import sys
import json
import os
import argparse
from google import genai
from google.genai import types

def run(intro_or_values, pages_json):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(json.dumps({"error": "GEMINI_API_KEY missing"}))
        sys.exit(1)
        
    client = genai.Client(api_key=api_key)
    
    pages = json.loads(pages_json)
    story_texts = "\\n".join([f"Page {p.get('page_number', i+1)}: {p.get('text', {}).get('fr', '')}" for i, p in enumerate(pages)])
    morals = "\\n".join([f"Page {p.get('page_number', i+1)}: {p.get('moral', '')}" for i, p in enumerate(pages) if p.get('moral')])
    
    if intro_or_values == "intro":
        prompt = f"""
Voici le texte complet d'un livre pour enfants :
{story_texts}

Objectif : Rédige une introduction très courte (2-3 phrases) et très attractive pour la toute première page du livre, qui invite le lecteur à plonger dans l'histoire et à acheter le livre.
Uniquement le texte final en français, directement.
"""
    else:
        prompt = f"""
Voici les textes et morales d'un livre pour enfants :
Textes :
{story_texts}
Morales :
{morals}

Objectif : Rédige "Les valeurs apprises" (Dernière Page du livre) sous forme de 3 tirets (bullet points) inspirants et synthétiques en français, qui résument ce que l'enfant a pu apprendre (ex: "- Le courage d'affronter... - L'amitié...").
Uniquement le texte final en français, directement.
"""
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        print(json.dumps({"result": response.text.strip()}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["intro", "values"])
    parser.add_argument("--pages", required=True, help="JSON string of pages array")
    args = parser.parse_args()
    run(args.mode, args.pages)
