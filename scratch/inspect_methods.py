import sys
sys.path.insert(0, ".")
with open("backend/app/healing/closed_loop_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
methods = re.findall(r"def ([a-zA-Z0-9_]+)\(", text)
print("Methods in closed_loop_engine.py:")
for m in methods:
    print("  -", m)

