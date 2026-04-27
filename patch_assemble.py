import re

with open("pipeline/assemble.py", "r") as f:
    content = f.read()

# 1. Update text drawing size & alignment
content = content.replace(
    'f_text = _font(False, 70)',
    'f_text = _font(False, 65)  # 14pt-16pt equivalent'
)
content = content.replace(
    'f_text = _font(False, 60)',
    'f_text = _font(False, 65)'
)
content = content.replace(
    'f_text = _font(False, 100) # ~ 24pt at 300 DPI',
    'f_text = _font(False, 65) # 14-16pt equivalent'
)

# Replace all draw_text_wrapped without align with align="left"
content = content.replace(
    'line_spacing=1.5)',
    'line_spacing=1.5, align="left")'
)

# 2. Add add_blank_if_coloring and multi-language intro/values 
# We need to do regex or string replacements for blank pages

with open("pipeline/assemble.py", "w") as f:
    f.write(content)
