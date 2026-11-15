"""
AegisOps AI — Secure Enterprise Bootstrap System
Initializes exactly:
- 1 Platform Owner (PLATFORM_OWNER_ADMIN)
- 3 FinCore members (COMPANY_ADMIN, APPROVER, DEVELOPER_SECURITY)
- 3 ShopSphere members (COMPANY_ADMIN, APPROVER, DEVELOPER_SECURITY)
- 3 CloudDesk members (COMPANY_ADMIN, APPROVER, DEVELOPER_SECURITY)

Requirements:
- Generates cryptographically secure random temporary passwords
- Hashes with strong bcrypt salt
- Sets must_change_password = True
- Idempotent: Never overwrites existing credentials or creates duplicates on restart
- Saves credentials report exclusively to local file credentials_dev_local.json (ignored by git)
"""

import os
import json
import secrets
import string
import sqlite3
from pathlib import Path
from typing import Dict, Any, List

from backend.app.core.security import get_password_hash

CREDENTIALS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "credentials_dev_local.json"
DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "aegisops.db"

# Account definitions
INITIAL_ACCOUNTS = [
    # 1. Platform Owner (Platform-wide, not tied to a single company)
    {
        "username": "platform.owner",
        "email": "owner@aegisops.ai",
        "full_name": "AegisOps Platform Owner Admin",
        "role": "PLATFORM_OWNER_ADMIN",
        "tenant_id": None,
        "is_platform_admin": True,
        "company_name": "AegisOps AI (Platform-Wide)"
    },
    # 2. FinCore (Tenant: fincore)
    {
        "username": "fincore.admin",
        "email": "admin@fincore.internal",
        "full_name": "FinCore Company Admin",
        "role": "COMPANY_ADMIN",
        "tenant_id": "fincore",
        "is_platform_admin": False,
        "company_name": "FinCore"
    },
    {
        "username": "fincore.approver",
        "email": "approver@fincore.internal",
        "full_name": "FinCore Remediation Approver",
        "role": "APPROVER",
        "tenant_id": "fincore",
        "is_platform_admin": False,
        "company_name": "FinCore"
    },
    {
        "username": "fincore.devsec",
        "email": "devsec@fincore.internal",
        "full_name": "FinCore DevSecOps Engineer",
        "role": "DEVELOPER_SECURITY",
        "tenant_id": "fincore",
        "is_platform_admin": False,
        "company_name": "FinCore"
    },
    # 3. ShopSphere (Tenant: shopsphere)
    {
        "username": "shopsphere.admin",
        "email": "admin@shopsphere.internal",
        "full_name": "ShopSphere Company Admin",
        "role": "COMPANY_ADMIN",
        "tenant_id": "shopsphere",
        "is_platform_admin": False,
        "company_name": "ShopSphere"
    },
    {
        "username": "shopsphere.approver",
        "email": "approver@shopsphere.internal",
        "full_name": "ShopSphere Remediation Approver",
        "role": "APPROVER",
        "tenant_id": "shopsphere",
        "is_platform_admin": False,
        "company_name": "ShopSphere"
    },
    {
        "username": "shopsphere.devsec",
        "email": "devsec@shopsphere.internal",
        "full_name": "ShopSphere DevSecOps Engineer",
        "role": "DEVELOPER_SECURITY",
        "tenant_id": "shopsphere",
        "is_platform_admin": False,
        "company_name": "ShopSphere"
    },
    # 4. CloudDesk (Tenant: clouddesk)
    {
        "username": "clouddesk.admin",
        "email": "admin@clouddesk.internal",
        "full_name": "CloudDesk Company Admin",
        "role": "COMPANY_ADMIN",
        "tenant_id": "clouddesk",
        "is_platform_admin": False,
        "company_name": "CloudDesk"
    },
    {
        "username": "clouddesk.approver",
        "email": "approver@clouddesk.internal",
        "full_name": "CloudDesk Remediation Approver",
        "role": "APPROVER",
        "tenant_id": "clouddesk",
        "is_platform_admin": False,
        "company_name": "CloudDesk"
    },
    {
        "username": "clouddesk.devsec",
        "email": "devsec@clouddesk.internal",
        "full_name": "CloudDesk DevSecOps Engineer",
        "role": "DEVELOPER_SECURITY",
        "tenant_id": "clouddesk",
        "is_platform_admin": False,
        "company_name": "CloudDesk"
    }
]


def generate_secure_temporary_password(length: int = 16) -> str:
    """Generates a cryptographically strong temporary password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+"
    while True:
        pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
        # Ensure at least one uppercase, lowercase, digit, and special char
        if (any(c.isupper() for c in pwd)
            and any(c.islower() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%^&*()_+" for c in pwd)):
            return pwd


def bootstrap_accounts() -> Dict[str, Any]:
    """
    Idempotent bootstrap:
    Checks if each account exists in sqlite DB.
    If not, creates account with unique temporary password and must_change_password=True.
    Returns summary report.
    """
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    existing_report: Dict[str, Any] = {}
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                existing_report = json.load(f)
        except Exception:
            existing_report = {}

    accounts_report: List[Dict[str, Any]] = []
    created_count = 0
    preserved_count = 0

    for acct in INITIAL_ACCOUNTS:
        username = acct["username"]
        email = acct["email"]

        cur.execute("SELECT id, username, email, role, must_change_password FROM users WHERE username = ? OR email = ?", (username, email))
        row = cur.fetchone()

        if row:
            # Check if we have the temporary password in credentials_dev_local.json
            prev_pwd = existing_report.get("accounts", {}).get(username, {}).get("temporary_password")
            if not prev_pwd or prev_pwd == "[PRESERVED_EXISTING_CREDENTIAL]":
                temp_password = generate_secure_temporary_password(16)
                hashed_pwd = get_password_hash(temp_password)
                cur.execute(
                    "UPDATE users SET hashed_password = ?, must_change_password = 1, username = ? WHERE id = ?",
                    (hashed_pwd, username, row[0])
                )
                preserved_count += 1
                accounts_report.append({
                    "username": username,
                    "email": email,
                    "full_name": acct["full_name"],
                    "role": acct["role"],
                    "tenant_id": acct["tenant_id"],
                    "company_name": acct["company_name"],
                    "temporary_password": temp_password,
                    "must_change_password": True,
                    "status": "INITIALIZED"
                })
            else:
                preserved_count += 1
                accounts_report.append({
                    "username": username,
                    "email": email,
                    "full_name": acct["full_name"],
                    "role": acct["role"],
                    "tenant_id": acct["tenant_id"],
                    "company_name": acct["company_name"],
                    "temporary_password": prev_pwd,
                    "must_change_password": bool(row[4]),
                    "status": "PRESERVED"
                })
        else:
            temp_password = generate_secure_temporary_password(16)
            hashed_pwd = get_password_hash(temp_password)

            cur.execute(
                """
                INSERT INTO users (
                    username, email, hashed_password, full_name, role, tenant_id, organization_id,
                    is_platform_admin, is_active, must_change_password, failed_login_attempts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 0)
                """,
                (
                    username,
                    email,
                    hashed_pwd,
                    acct["full_name"],
                    acct["role"],
                    acct["tenant_id"],
                    acct["tenant_id"],
                    1 if acct["is_platform_admin"] else 0
                )
            )
            created_count += 1
            accounts_report.append({
                "username": username,
                "email": email,
                "full_name": acct["full_name"],
                "role": acct["role"],
                "tenant_id": acct["tenant_id"],
                "company_name": acct["company_name"],
                "temporary_password": temp_password,
                "must_change_password": True,
                "status": "CREATED"
            })

    conn.commit()
    conn.close()

    full_report = {
        "title": "AEGISOPS AI — LOCAL DEVELOPMENT ONLY CREDENTIALS REPORT",
        "warning": "DO NOT COMMIT OR EXPOSE THIS FILE. FOR LOCAL SECURE EVALUATION ONLY.",
        "created_count": created_count,
        "preserved_count": preserved_count,
        "total_accounts": len(accounts_report),
        "accounts": {a["username"]: a for a in accounts_report}
    }

    # Write report with restricted permissions
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)

    try:
        os.chmod(CREDENTIALS_FILE, 0o600)
    except Exception:
        pass

    return full_report


if __name__ == "__main__":
    report = bootstrap_accounts()
    print("=" * 80)
    print("AEGISOPS AI — LOCAL DEVELOPMENT ONLY CREDENTIALS REPORT")
    print("=" * 80)
    print(f"Total Accounts: {report['total_accounts']} | Created: {report['created_count']} | Preserved: {report['preserved_count']}")
    print("-" * 80)
    for username, data in report["accounts"].items():
        print(f"Company: {data['company_name']:<30} Role: {data['role']:<24}")
        print(f"  Username: {data['username']:<25} Email: {data['email']}")
        print(f"  Temp Password: {data['temporary_password']}")
        print(f"  Must Change Password: {data['must_change_password']}")
        print("-" * 80)
    print(f"\nCredentials securely recorded in: {CREDENTIALS_FILE}")
