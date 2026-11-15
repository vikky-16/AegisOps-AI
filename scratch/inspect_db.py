import sqlite3

conn = sqlite3.connect('aegisops.db')
cursor = conn.cursor()

print("Approvals columns:")
for row in cursor.execute("PRAGMA table_info(approvals)").fetchall():
    print(f"  {row[1]} ({row[2]})")

print("\nIncidents columns:")
for row in cursor.execute("PRAGMA table_info(incidents)").fetchall():
    print(f"  {row[1]} ({row[2]})")

cursor.execute("""
    SELECT a.approval_id, a.incident_id, a.tenant_id, a.status, i.incident_id, i.tenant_id, i.status, a.solution_source
    FROM approvals a
    LEFT JOIN incidents i ON a.incident_id = i.incident_id
""")
rows = cursor.fetchall()
print(f"\nTotal approvals: {len(rows)}")
orphans = 0
for row in rows:
    found = row[4] is not None
    if not found:
        orphans += 1
    print(f"  Appr: {row[0]} | Inc: {row[1]} (Found: {found}) | ApprTenant: {row[2]} | IncTenant: {row[5]} | ApprStatus: {row[3]} | IncStatus: {row[6]} | Source: {row[7]}")
print(f"Orphaned approvals (no incident found): {orphans}")

conn.close()

