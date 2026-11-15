with open("backend/app/healing/closed_loop_engine.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
for idx, l in enumerate(lines):
    if "async def execute_closed_loop" in l or "def execute_closed_loop" in l:
        for j in range(idx, min(len(lines), idx + 80)):
            print(f"{j+1:3d}: {lines[j].rstrip()}")
        break

