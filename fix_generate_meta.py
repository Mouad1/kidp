with open("dashboard/app.py") as f:
    text = f.read()

# Add the /api/generate_meta endpoint which is clearly missing in app.py

new_endpoint = '''
class GenerateMetaRequest(BaseModel):
    mode: str
    pages: list[dict]

@app.post("/api/generate_meta")
async def api_generate_meta(req: GenerateMetaRequest):
    import base64
    import os
    import json
    from google import genai
    from google.genai import types

    text_pages = []
    for p in req.pages:
        fr = ""
        if "text" in p and isinstance(p["text"], dict):
            fr = p["text"].get("fr", "")
        if fr:
            text_pages.append(f"Page {p.get('page_number', '?')}: {fr}")

    full_story = "\\n".join(text_pages)
    if not full_story.strip():
        raise HTTPException(status_code=400, detail="Pas de texte FR trouvé dans les pages pour générer le contenu.")

    if req.mode == "intro":
        prompt = f"Voici l'histoire complète d'un livre pour enfant:\\n\\n{full_story}\\n\\nDonne-moi UNIQUEMENT un court texte d'introduction accrocheur (2-3 phrases max) qui sera mis à la page de garde pour introduire le livre. En français. Pas de formatage markdown, juste le texte."
    else:
        # values
        prompt = f"Voici l'histoire complète d'un livre pour enfant:\\n\\n{full_story}\\n\\nDonne-moi UNIQUEMENT une liste ou un court paragraphe (2-3 phrases max) résumant la morale ou les valeurs apprises dans cette histoire, à placer en fin de livre. En français. Pas de formatage markdown, juste le texte."

    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY")) if os.environ.get("GEMINI_API_KEY") else genai.Client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return {"result": response.text.strip()}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
'''

if "/api/generate_meta" not in text:
    parts = text.split('if __name__ == "__main__":')
    parts[0] = parts[0] + new_endpoint + '\n'
    text = 'if __name__ == "__main__":'.join(parts)
    with open("dashboard/app.py", "w") as f:
        f.write(text)
