with open("backend/app/healing/closed_loop_engine.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for j in range(400, min(len(lines), 480)):
    print(f"{j+1:3d}: {lines[j].rstrip()}")

