import re

with open("dashboard/app.py") as f:
    content = f.read()

new_routes = """
class AddImageRequest(BaseModel):
    source_book: str
    filename: str

@app.get("/api/images/all")
async def api_all_images():
    images_dir = ROOT / "images"
    res = {}
    if images_dir.exists():
        for d in images_dir.iterdir():
            if d.is_dir():
                imgs = [img.name for img in d.glob("*.png")]
                if imgs:
                    res[d.name] = sorted(imgs)
    return res

@app.post("/api/book/{book_name}/add-image")
async def api_add_imported_image(book_name: str, req: AddImageRequest):
    import shutil
    src = ROOT / "images" / req.source_book / req.filename
    dest_dir = ROOT / "images" / book_name
    dest_dir.mkdir(parents=True, exist_ok=True)
    prefix = book_name.split('-')[0]
    
    # Try to extract the core name
    core = req.filename
    if "_" in core: core = core.split("_", 1)[1]
    if core.endswith(".png"): core = core[:-4]
    
    new_filename = f"{prefix}_{core}.png"
    dest = dest_dir / new_filename
    
    # avoid overwrite
    counter = 1
    while dest.exists():
        new_filename = f"{prefix}_{core}_{counter}.png"
        dest = dest_dir / new_filename
        counter += 1
        
    shutil.copy2(src, dest)
    new_id = new_filename.replace(f"{prefix}_", "").replace(".png", "")
    return {"status": "ok", "new_filename": new_filename, "new_id": new_id}
"""

parts = content.split('if __name__ == "__main__":')
new_content = parts[0] + new_routes + '\nif __name__ == "__main__":' + parts[1]

with open("dashboard/app.py", "w") as f:
    f.write(new_content)
