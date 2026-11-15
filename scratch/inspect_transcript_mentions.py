import json

transcript_path = r"C:\Users\admin\.gemini\antigravity\brain\d47d8cb8-7ea1-40aa-a5b4-4a1017e2f7e1\.system_generated\logs\transcript_full.jsonl"

with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
    for line_idx, line in enumerate(f):
        if "1.875" in line or "FARR" in line:
            try:
                data = json.loads(line)
                print(f"--- Line {line_idx} (step {data.get('step_index')}, source {data.get('source')}, type {data.get('type')}) ---")
                content = str(data.get("content", ""))
                thinking = str(data.get("thinking", ""))
                text = content + "\n" + thinking
                for l in text.split("\n"):
                    if any(k in l for k in ["1.875", "FARR", "smoke", "One-Shot", "Closed-Loop"]):
                        print("  ", l[:150])
            except Exception as e:
                print(f"Error parsing line {line_idx}: {e}")

