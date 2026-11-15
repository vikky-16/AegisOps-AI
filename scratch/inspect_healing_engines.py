import os
import inspect

files = [
    'backend/app/healing/closed_loop_engine.py',
    'backend/app/healing/solution_generator.py',
    'backend/app/replica/controlled_environment.py'
]

for p in files:
    print(f"=== {p} ===")
    with open(p, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print(f"Total lines: {len(lines)}")
    for l in lines[:35]:
        print("  ", l.rstrip())

