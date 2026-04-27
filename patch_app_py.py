import re

with open("dashboard/app.py", "r") as f:
    app_data = f.read()

# 1. Update NewBookModel
app_data = app_data.replace(
'''class NewBookModel(BaseModel):
    slug: str
    title: str
    subtitle: str
    author: str
    characters: list[CharacterModel] = []''',
'''class NewBookModel(BaseModel):
    slug: str
    category: str = "coloring"
    title: str
    subtitle: str
    author: str
    characters: list[CharacterModel] = []
    # For Story mode
    story_script: str = ""'''
)


# 2. Update `api_new_book` POST route
new_book_code = '''@app.post("/api/books/new")
async def api_new_book(data: NewBookModel):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', data.slug):
        raise HTTPException(status_code=400, detail="Slug invalide (alphanumérique + tirets)")
    book_dir = ROOT / "books" / data.slug
    if book_dir.exists():
        raise HTTPException(status_code=409, detail=f"Le livre {data.slug!r} existe déjà")
    
    # Si c'est un livre de conte avec script brut
    story_base_prompt = ""
    pages = []
    if data.category == "story" and data.story_script:
        # Appel du script Gemini
        import subprocess
        import json
        tmp_script = ROOT / f"tmp_script_{data.slug}.txt"
        tmp_script.write_text(data.story_script, encoding="utf-8")
        
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(ROOT / "pipeline" / "story_gen.py"),
                "--script", str(tmp_script),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy()
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise HTTPException(status_code=500, detail=f"Erreur génération script: {stderr.decode()}")
            
            parsed_story = json.loads(stdout.decode().strip())
            story_base_prompt = parsed_story.get("story_base_prompt", "")
            pages = parsed_story.get("pages", [])
            
            # Auto-generate page_sequence for story based on pages
            page_sequence = [
                {"file": f"{data.slug}_page_{p['page_number']}.png", "label": f"Page {p['page_number']}"}
                for p in pages
            ]
        finally:
            if tmp_script.exists():
                tmp_script.unlink()
    else:
        # Auto-generate page_sequence for coloring based on characters
        page_sequence = [] # will be handled by config_io if empty
        
    book_dir.mkdir(parents=True)
    (ROOT / "images" / data.slug).mkdir(parents=True, exist_ok=True)
    
    write_config(data.slug, {
        "category":      data.category,
        "title":         data.title,
        "subtitle":      data.subtitle,
        "author":        data.author,
        "images_folder": data.slug,
        "characters":    [c.model_dump() for c in data.characters],
        "page_sequence": page_sequence if data.category == "story" else [],
        "story_base_prompt": story_base_prompt,
        "pages":         pages
    })
    return {"status": "ok", "slug": data.slug}'''

app_data = re.sub(r'@app\.post\("/api/books/new"\).*?return \{"status": "ok", "slug": data\.slug\}', new_book_code, app_data, flags=re.DOTALL)

with open("dashboard/app.py", "w") as f:
    f.write(app_data)

