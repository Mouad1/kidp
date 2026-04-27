import re

with open("dashboard/app.py") as f:
    text = f.read()

# Replace the api_translate function
new_api = """@app.post("/api/translate")
async def api_translate(req: TranslateRequest):
    import importlib.util
    import traceback
    try:
        spec = importlib.util.spec_from_file_location("translate", str(ROOT / "dashboard" / "translate.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.translate_text(req.text, req.langs)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")"""

text = re.sub(r'@app\.post\("/api/translate"\)\nasync def api_translate\(req: TranslateRequest\):.*?raise HTTPException\(status_code=500, detail=str\(e\)\)', new_api, text, flags=re.DOTALL)

with open("dashboard/app.py", "w") as f:
    f.write(text)
