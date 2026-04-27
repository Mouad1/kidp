with open("pipeline/config_io.py") as f:
    content = f.read()

import re

# Update write_config to always use `characters` array for page_sequence in coloring books,
# even if `page_sequence` is passed but it's an empty list (which UI does currently).

# find `if data.get("page_sequence") is None:`
# replace with:
# if not data.get("page_sequence"): # None or []

content = content.replace('if data.get("page_sequence") is None:', 'if not data.get("page_sequence"):')

with open("pipeline/config_io.py", "w") as f:
    f.write(content)
