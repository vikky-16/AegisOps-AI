"""
Runtime Verification Sequence for AegisOps AI Self-Healing Engine
Tests:
1. Baseline query against database-service (8004)
2. Failure injection (connection_exhaustion)
3. Verified failure (query returns 500)
4. Manual remediation trigger via POST /api/recovery/manual
5. Multi-Point Active Verification inspection
6. Verified recovery (query returns 200)
7. Recovery history verification via GET /api/recovery
8. Route aliases verification (/execute, /history)
"""

import sys
import json
import time
import urllib.request
import urllib.error

def request(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            content = resp.read().decode("utf-8")
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = content
            return status, parsed
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = content
        return e.code, parsed

def main():
    print("=" * 70)
    print("AEGISOPS AI: SELF-HEALING ENGINE RUNTIME VERIFICATION SEQUENCE")
    print("=" * 70)
    
    # 1. Baseline check
    print("\n[Step 1] Baseline check on database-service...")
    status, res = request("http://127.0.0.1:8004/query")
    print(f"Status: {status}, Response: {res}")
    assert status == 200, f"Expected 200, got {status}"
    assert res.get("status") == "SUCCESS", f"Expected SUCCESS, got {res}"
    print("--> BASELINE PASS: database-service is responding normally.")

    # 2. Inject failure
    print("\n[Step 2] Injecting connection_exhaustion failure into database-service...")
    status, res = request(
        "http://127.0.0.1:8004/simulate/failure",
        method="POST",
        data={"type": "connection_exhaustion", "duration_sec": 120}
    )
    print(f"Status: {status}, Response: {res}")
    assert status == 200, f"Expected 200 from failure injection, got {status}"

    # 3. Verify failure is active
    print("\n[Step 3] Verifying database-service fails as expected...")
    status, res = request("http://127.0.0.1:8004/query")
    print(f"Status: {status}, Response: {res}")
    assert status == 500, f"Expected 500, got {status}"
    print("--> FAILURE CONFIRMED: database-service returns 500 Pool Exhausted.")

    # 4. Trigger remediation hook via POST /api/recovery/manual
    print("\n[Step 4] Triggering remediation hook via POST /api/recovery/manual...")
    start_time = time.time()
    status, res = request(
        "http://127.0.0.1:8000/api/recovery/manual",
        method="POST",
        data={
            "service_name": "database-service",
            "action": "RESET_CONNECTION_POOL",
            "incident_id": "INC-TEST-001"
        }
    )
    elapsed = time.time() - start_time
    print(f"Status: {status} (elapsed: {elapsed:.2f}s)")
    print(f"Response: {json.dumps(res, indent=2)}")
    
    assert status == 200, f"Expected 200 from manual recovery, got {status}"
    assert res.get("success") is True, f"Expected success: True, got {res.get('success')}"
    assert res.get("execution_mode") == "CONTROLLED_DEMO", f"Expected CONTROLLED_DEMO, got {res.get('execution_mode')}"
    
    # Check verification details
    verification = res.get("verification", {})
    assert verification.get("verified") is True, f"Expected verification.verified: True, got {verification}"
    checks = verification.get("checks", {})
    print("\nActive Probes Evidence:")
    print(f"  - health: {checks.get('health', {}).get('database-service')}")
    print(f"  - metrics: {checks.get('metrics', {}).get('database-service')}")
    print(f"  - synthetic_transaction: {checks.get('synthetic_transaction')}")
    
    assert checks.get("health", {}).get("database-service", {}).get("healthy") is True
    assert checks.get("metrics", {}).get("database-service", {}).get("healthy") is True
    assert checks.get("synthetic_transaction", {}).get("passed") is True
    print("--> REMEDIATION & MULTI-POINT ACTIVE VERIFICATION PASS!")

    # 5. Verify database-service query works again
    print("\n[Step 5] Verifying database-service query returns 200 post-remediation...")
    status, res = request("http://127.0.0.1:8004/query")
    print(f"Status: {status}, Response: {res}")
    assert status == 200, f"Expected 200, got {status}"
    assert res.get("status") == "SUCCESS"
    print("--> SERVICE RESTORATION CONFIRMED: 200 OK.")

    # 6. Check recovery history endpoint
    print("\n[Step 6] Verifying recovery history via GET /api/recovery...")
    status, history = request("http://127.0.0.1:8000/api/recovery")
    print(f"Status: {status}, Total records: {len(history)}")
    assert status == 200
    assert len(history) > 0
    latest = history[0]
    print(f"Latest record: {json.dumps(latest, indent=2)}")
    assert latest.get("service_name") == "database-service"
    assert latest.get("action") == "RESET_CONNECTION_POOL"
    assert latest.get("success") is True
    assert latest.get("verification_status") in ("VERIFIED", "SUCCESS")
    print("--> RECOVERY HISTORY PERSISTENCE PASS!")

    # 7. Check route aliases
    print("\n[Step 7] Verifying route alias GET /api/recovery/history...")
    status, alias_history = request("http://127.0.0.1:8000/api/recovery/history")
    assert status == 200
    assert len(alias_history) == len(history)
    print("--> Route alias /api/recovery/history OK.")

    print("\n[Step 8] Verifying route alias POST /api/recovery/execute...")
    status, alias_exec = request(
        "http://127.0.0.1:8000/api/recovery/execute",
        method="POST",
        data={
            "service_name": "database-service",
            "action": "RESET_CONNECTION_POOL"
        }
    )
    assert status == 200
    assert alias_exec.get("success") is True
    print("--> Route alias /api/recovery/execute OK.")

    # 9. Verify SQLite Database Persistence directly
    print("\n[Step 9] Inspecting SQLite database file aegisops.db directly...")
    import sqlite3
    conn = sqlite3.connect("aegisops.db")
    cursor = conn.cursor()
    cursor.execute("SELECT execution_id, service_name, action, success, verification_status, execution_mode FROM recovery_executions ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()
    print("Recent SQLite records in recovery_executions table:")
    for row in rows:
        print(f"  Row: {row}")
    assert len(rows) > 0
    assert rows[0][1] == "database-service"
    assert rows[0][2] == "RESET_CONNECTION_POOL"
    assert rows[0][3] == 1  # success = True
    assert rows[0][4] == "VERIFIED"
    assert rows[0][5] == "CONTROLLED_DEMO"
    conn.close()
    print("--> SQLITE DATABASE PERSISTENCE DIRECT AUDIT PASS!")

    print("\n" + "=" * 70)
    print("ALL RUNTIME VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
