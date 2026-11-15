import os

app_dir = 'backend/app'
modules = {}
for root, dirs, files in os.walk(app_dir):
    if '__pycache__' in root:
        continue
    rel = os.path.relpath(root, app_dir)
    py_files = [f for f in files if f.endswith('.py')]
    if py_files:
        modules[rel] = py_files

print(f"Total packages in backend/app: {len(modules)}")
for pkg, files in sorted(modules.items()):
    print(f"  {pkg:35}: {len(files)} files -> {', '.join(files[:4])}{'...' if len(files)>4 else ''}")

