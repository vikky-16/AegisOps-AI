import os
import csv
import sys

root_dir = os.path.abspath(".")
output_path = os.path.join(root_dir, "report_audit", "complete_file_inventory.csv")

exclude_dirs = {
    ".git", ".pytest_cache", "venv", "node_modules", "__pycache__",
    ".vscode", ".idea", "dist", "build", ".next"
}

records = []

for root, dirs, files in os.walk(root_dir):
    dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
    
    # Also skip if path contains excluded patterns
    if any(ex in root.split(os.sep) for ex in exclude_dirs):
        continue

    for f in sorted(files):
        if f.endswith((".pyc", ".pyo", ".pyd", ".DS_Store", ".log")):
            continue
        
        full_path = os.path.join(root, f)
        rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")
        
        # Determine component
        parts = rel_path.split("/")
        top = parts[0]
        if top == "backend":
            component = f"Backend / {parts[2] if len(parts) > 2 else 'Core'}"
        elif top == "frontend":
            component = f"Frontend / {parts[2] if len(parts) > 2 else 'Root'}"
        elif top in ["clouddesk", "fincore", "shopsphere"]:
            component = f"Tenant Service ({top.upper()})"
        elif top == "services":
            component = "Demo Microservices"
        elif top == "scripts":
            component = "Automation / Verification Scripts"
        elif top == "docs":
            component = "Documentation"
        elif top == "docker":
            component = "Containerization & Deployment"
        elif top == "otel":
            component = "OpenTelemetry Collector"
        elif top == "data" or top == "datasets":
            component = "Telemetry Data / Datasets"
        elif top == "backups":
            component = "Database Backups"
        else:
            component = "Project Root"

        size_bytes = os.path.getsize(full_path)
        ext = os.path.splitext(f)[1]

        # Determine purpose / classification
        status = "VERIFIED_EXISTING"
        if "test" in f.lower() or "test" in rel_path.lower():
            file_category = "Test Suite"
        elif ext in [".md", ".txt", ".rst"]:
            file_category = "Documentation"
        elif ext in [".py"]:
            file_category = "Python Source Code"
        elif ext in [".ts", ".tsx", ".js", ".jsx"]:
            file_category = "Frontend Source Code"
        elif ext in [".json", ".yaml", ".yml", ".toml", ".ini", ".env"]:
            file_category = "Configuration / Fixture"
        elif ext in [".db", ".sqlite", ".sqlite3"]:
            file_category = "SQLite Database"
        elif ext in [".sql"]:
            file_category = "Database Migration / Schema"
        elif ext in [".sh", ".ps1", ".bat"]:
            file_category = "Shell Script"
        else:
            file_category = "Asset / Binary"

        records.append({
            "component": component,
            "file_path": rel_path,
            "category": file_category,
            "size_bytes": size_bytes,
            "extension": ext,
            "status": status,
            "evidence": f"File verified on disk at {rel_path} ({size_bytes} bytes)"
        })

print(f"Discovered {len(records)} relevant files in project tree.")

fieldnames = ["component", "file_path", "category", "size_bytes", "extension", "status", "evidence"]
with open(output_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)

print(f"Wrote {len(records)} entries to {output_path}")

