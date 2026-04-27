import re
with open("pipeline/config_io.py", "r") as f:
    text = f.read()

# Brutal replace of the broken block
start = text.find("    pages_blocks = []")
end = text.find("    # Formater PAGE_SEQUENCE")

if start != -1 and end != -1:
    good_block = """    pages_blocks = []
    for p in pages:
        text_str = json.dumps(p.get("text", {}), ensure_ascii=False)
        pages_blocks.append(
            "    {\\n"
            f'        "page_number":  {p.get("page_number", 0)},\\n'
            f'        "text":         {text_str},\\n'
            f'        "moral":        {json.dumps(p.get("moral", ""), ensure_ascii=False)},\\n'
            f'        "image_prompt": {json.dumps(p.get("image_prompt", ""), ensure_ascii=False)}\\n'
            "    }"
        )
    pages_str = "[\\n" + ",\\n".join(pages_blocks) + "\\n]" if pages_blocks else "[]"\n\n"""
    
    text = text[:start] + good_block + text[end:]

with open("pipeline/config_io.py", "w") as f:
    f.write(text)
