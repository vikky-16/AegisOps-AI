import sqlite3

conn = sqlite3.connect('aegisops.db')
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

print("\n--- TENANTS ---")
cur.execute("SELECT id, name, slug FROM tenants")
for row in cur.fetchall():
    print(row)

print("\n--- USERS ---")
cur.execute("SELECT id, username, email, role, tenant_id, is_platform_admin FROM users")
for row in cur.fetchall():
    print(row)

print("\n--- INCIDENTS ---")
cur.execute("SELECT id, incident_id, title, tenant_id, primary_service, severity, status FROM incidents")
for row in cur.fetchall():
    print(row)

print("\n--- APPROVALS COUNT BY TENANT ---")
cur.execute("SELECT tenant_id, count(*) FROM approvals GROUP BY tenant_id")
for row in cur.fetchall():
    print(row)
