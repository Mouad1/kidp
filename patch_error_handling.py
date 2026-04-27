with open("dashboard/app.py", "r") as f:
    text = f.read()

bad = '''            parsed_story = json.loads(stdout.decode().strip())
            story_base_prompt = parsed_story.get("story_base_prompt", "")'''
            
good = '''            stdout_text = stdout.decode().strip()
            try:
                parsed_story = json.loads(stdout_text)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Erreur Parse JSON de Gemini: {str(e)} | Sortie: {stdout_text[:500]}")
            
            story_base_prompt = parsed_story.get("story_base_prompt", "")'''

text = text.replace(bad, good)
with open("dashboard/app.py", "w") as f:
    f.write(text)
