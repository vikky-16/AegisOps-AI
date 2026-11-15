with open("backend/app/healing/closed_loop_engine.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for j in range(290, min(len(lines), 400)):
    print(f"{j+1:3d}: {lines[j].rstrip()}")

