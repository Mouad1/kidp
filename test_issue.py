import sys
import subprocess
out = subprocess.run(["python3", "pipeline/assemble.py", "--help"], capture_output=True, text=True)
import re
print("import error?", out.stdout)
