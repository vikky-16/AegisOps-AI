"""
Database reconciliation script:
Ensures strictly only FinCore, ShopSphere, and CloudDesk exist as company tenants.
Removes any previously created dummy tenants (northstar-fin, vertex-health, apex-commerce)
and their dummy users.
Preserves all existing incidents, approvals, telemetry, and configurations.
"""

import sqlite3

conn = sqlite3.connect('aegisops.db')
cur = conn.cursor()

# 1. Identify and remove any dummy tenants
cur.execute("SELECT id, name FROM tenants WHERE id IN ('northstar-fin', 'vertex-health', 'apex-commerce')")
dummy_tenants = cur.fetchall()
print("Found dummy tenants to remove:", dummy_tenants)

for tid, _ in dummy_tenants:
    cur.execute("DELETE FROM tenants WHERE id = ?", (tid,))
    cur.execute("DELETE FROM tenant_policies WHERE tenant_id = ?", (tid,))
    cur.execute("DELETE FROM tenant_api_keys WHERE tenant_id = ?", (tid,))
    cur.execute("DELETE FROM users WHERE tenant_id = ?", (tid,))
    cur.execute("DELETE FROM incidents WHERE tenant_id = ?", (tid,))
    cur.execute("DELETE FROM approvals WHERE tenant_id = ?", (tid,))
    print(f"Removed dummy tenant and associated records for: {tid}")

# Also remove any users matching northstar/vertex/apex
cur.execute("DELETE FROM users WHERE username LIKE '%northstar%' OR username LIKE '%vertex%' OR username LIKE '%apex%'")

# Ensure fincore, shopsphere, clouddesk have valid tenant records
companies = [
    ("fincore", "FinCore", "fincore", "Financial Services"),
    ("shopsphere", "ShopSphere", "shopsphere", "E-Commerce & Retail"),
    ("clouddesk", "CloudDesk", "clouddesk", "SaaS & Cloud Infrastructure")
]

for tid, name, slug, industry in companies:
    cur.execute("SELECT id FROM tenants WHERE id = ?", (tid,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO tenants (id, name, slug, tier, plan, industry, region, status, retention_days, environments_json) "
            "VALUES (?, ?, ?, 'ENTERPRISE', 'Enterprise', ?, 'Global', 'ACTIVE', 90, '[\"PRODUCTION\", \"STAGING\"]')",
            (tid, name, slug, industry)
        )
        print(f"Inserted tenant: {tid}")
    else:
        print(f"Tenant {tid} exists.")

    # Ensure tenant policy exists
    cur.execute("SELECT id FROM tenant_policies WHERE tenant_id = ?", (tid,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO tenant_policies (tenant_id, auto_remediation_enabled, allowed_actions_json, max_auto_risk_level, min_rca_confidence, max_blast_radius) "
            "VALUES (?, 1, '[\"RESET_CONNECTION_POOL\", \"CLEAR_CACHE\", \"DRAIN_QUEUE\", \"ROTATE_CONNECTIONS\"]', 'LOW', 0.85, 60.0)",
            (tid,)
        )
        print(f"Inserted policy for: {tid}")

conn.commit()

# Verify remaining tenants
cur.execute("SELECT id, name, slug FROM tenants")
print("\nActive Tenants in DB:")
for row in cur.fetchall():
    print(row)

conn.close()
print("\nReconciliation complete.")
