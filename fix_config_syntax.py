with open("pipeline/config_io.py", "r") as f:
    text = f.read()

text = text.replace('    {\n"', r'    {\n"')
text = text.replace('",\n"', r'",\n"')

text_fixed = []
for line in text.split('\n'):
    if line.endswith('",') and not line.endswith(r'\n",') and 'page_number' in line:
        line = line.replace('",', r'\n",')
    text_fixed.append(line)

# Let's just do a clean replace for the pages block
new_block = """    pages_blocks = []
    for p in pages:
        text_str = json.dumps(p.get("text", {}), ensure_ascii=False)
        pages_blocks.append(
            "    {\\n"
            f'        "page_number":  {p.get("page_number", 0)},\\n'
            f'        "text":         {text_str},\\n'
            f'        "moral":        {json.dumps(p.get("moral", ""), ensure_ascii=False)},\\n'
            f'        "image_prompt": {json.dumps(p.get("image_prompt", ""), ensure_ascii=False)},\\n'
            "    }"
        )
    pages_str = "[\\n" + ",\\n".join(pages_blocks) + "\\n]" if pages_blocks else "[]"
"""

import re
text = re.sub(r'    pages_blocks = \[].*?pages_str = "\[\\n" \+ ",\\n"\.join\(pages_blocks\) \+ "\\n\]" if pages_blocks else "\[\]"', new_block, text, flags=re.DOTALL)
with open("pipeline/config_io.py", "w") as f:
    f.write(text)
