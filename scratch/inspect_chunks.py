import glob
import json
import os

chunks = glob.glob(r"C:\Users\admin\.gemini\antigravity\brain\d47d8cb8-7ea1-40aa-a5b4-4a1017e2f7e1\.system_generated\logs\chunks\**\*.jsonl", recursive=True)
print(f"Found {len(chunks)} chunks.")

for c in chunks:
    with open(c, "r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f):
            if "1.875" in line or "FARR" in line:
                try:
                    d = json.loads(line)
                    step = d.get("step_index")
                    src = d.get("source")
                    if step != 1282:  # not the current user prompt
                        print(f"Earlier match in {os.path.basename(c)} line {line_no} step {step} source {src}")
                        content = str(d.get("content", "")) + "\n" + str(d.get("thinking", ""))
                        for l in content.split("\n"):
                            if "1.875" in l or "FARR" in l:
                                print("   ", l[:120])
                except Exception:
                    pass

