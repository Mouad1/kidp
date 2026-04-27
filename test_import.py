import sys
import subprocess
out = subprocess.run(["python3", "pipeline/assemble.py", "--book", "boo3-test"], capture_output=True, text=True)
print("Was draw_text_wrapped None?")
