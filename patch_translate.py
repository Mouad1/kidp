with open("dashboard/translate.py") as f:
    text = f.read()

new_text = text.replace("return json.loads(response.text)", """
    out = response.text.strip()
    if out.startswith("```json"):
        out = out[7:]
    if out.startswith("```"):
        out = out[3:]
    if out.endswith("```"):
        out = out[:-3]
    return json.loads(out.strip())
""")

with open("dashboard/translate.py", "w") as f:
    f.write(new_text)
