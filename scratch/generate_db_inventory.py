import sqlite3
import os

db_path = "aegisops.db"
output_path = os.path.join("report_audit", "database_schema_inventory.md")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [r[0] for r in cur.fetchall()]

md = [
    "# AegisOps AI — Database Schema Inventory",
    "",
    "## 1. Database Overview",
    "",
    "- **RDBMS Engine**: SQLite 3 (WAL mode enabled: `PRAGMA journal_mode=WAL`)",
    f"- **Database File**: `{os.path.abspath(db_path)}`",
    f"- **Database File Size**: {os.path.getsize(db_path) / (1024*1024):.2f} MB",
    f"- **Total Managed Tables**: {len(tables)}",
    "- **ORM Layer**: SQLAlchemy 2.0 (AsyncSession with `aiosqlite`)",
    "",
    "## 2. Table Inventory and Row Counts",
    "",
    "| Table Name | Row Count | Column Count | Primary Key | Purpose / Description |",
    "| :--- | :--- | :--- | :--- | :--- |"
]

table_details = []

for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM "{t}";')
    cnt = cur.fetchone()[0]
    
    cur.execute(f'PRAGMA table_info("{t}");')
    cols = cur.fetchall()
    
    pk_cols = [c[1] for c in cols if c[5] > 0]
    pk_str = ", ".join(pk_cols) if pk_cols else "None"
    
    # Description mapping
    desc = "Application data table"
    if "incident" in t:
        desc = "Stores active and historical incident records, evidence, hypotheses, and life-cycle state"
    elif "approval" in t:
        desc = "Managed approval tickets, operator reviews, decisions, and audit archives"
    elif "recovery" in t:
        desc = "Automated and manual recovery plans, execution records, step logs, and verification state"
    elif "replica" in t:
        desc = "Digital twin instances, isolated test configurations, and experiment evaluation results"
    elif "tenant" in t:
        desc = "Multi-company isolation, tenant policies, API keys, workflows, and architecture nodes"
    elif "sre_" in t or "conversation" in t:
        desc = "SRE conversational operations session memory, message history, and evidence references"
    elif "anomaly" in t:
        desc = "Anomaly detection episodes, detector confidence, and metric breach history"
    elif "knowledge" in t:
        desc = "Curated knowledge base articles, verified symptoms, and standardized remediation runbooks"
    elif "metric" in t or "event" in t or "log" in t:
        desc = "Telemetry event store, normalized metrics, logs, and trace correlations"
    elif "user" in t or "auth" in t or "team" in t:
        desc = "RBAC user accounts, hashed credentials, roles (VIEWER, OPERATOR, APPROVER, ADMIN)"
    elif "audit" in t:
        desc = "Immutable audit log tracking operator decisions, actions, and administrative changes"
    elif "storage" in t or "archive" in t:
        desc = "Storage intelligence snapshots, tiering records, and retention compression logs"

    md.append(f"| `{t}` | {cnt} | {len(cols)} | `{pk_str}` | {desc} |")
    
    table_details.append((t, cnt, cols))

md.append("")
md.append("## 3. Comprehensive Column-Level Schema")
md.append("")

for t, cnt, cols in table_details:
    md.append(f"### Table: `{t}` (Rows: {cnt})")
    md.append("")
    md.append("| Column Name | Type | Not Null | Default Value | Primary Key |")
    md.append("| :--- | :--- | :--- | :--- | :--- |")
    for c in cols:
        cid, name, col_type, notnull, dflt_value, pk = c
        md.append(f"| `{name}` | `{col_type or 'BLOB/TEXT'}` | {'YES' if notnull else 'NO'} | `{dflt_value if dflt_value is not None else 'NULL'}` | {'PK' if pk else '-'} |")
    md.append("")

with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md))

print(f"Wrote database schema inventory to {output_path}")

