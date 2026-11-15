import os
import zipfile
import re

print("=== SEARCHING CURRENT WORKSPACE ===")
for root, dirs, files in os.walk("."):
    if any(x in root for x in ["venv", "node_modules", ".git", "report_audit"]):
        continue
    for f in files:
        if f.endswith((".py", ".json", ".md", ".txt", ".csv")):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                if "1.875" in content or "FARR" in content or "87.5%" in content or "false recoveries" in content.lower():
                    print(f"Match in workspace: {path}")
            except Exception:
                pass

print("\n=== SEARCHING ZIP ARCHIVE ===")
zip_path = r"C:\Users\admin\AegisOps AI.zip"
if os.path.exists(zip_path):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for info in zf.infolist():
                if info.file_size < 2000000 and info.filename.endswith((".py", ".json", ".md", ".txt", ".csv")):
                    try:
                        content = zf.read(info.filename).decode('utf-8', errors='ignore')
                        if "1.875" in content or "FARR" in content or "87.5%" in content or "false recoveries" in content.lower():
                            print(f"Match in zip: {info.filename}")
                    except Exception:
                        pass
    except Exception as e:
        print(f"Error reading zip: {e}")

print("\n=== SEARCHING TRANSCRIPTS ===")
transcript_dir = r"C:\Users\admin\.gemini\antigravity\brain"
if os.path.exists(transcript_dir):
    for root, dirs, files in os.walk(transcript_dir):
        for f in files:
            if f.endswith((".jsonl", ".txt")):
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                        content = fp.read()
                    if "1.875" in content or "FARR" in content:
                        print(f"Match in transcript: {path}")
                except Exception:
                    pass

