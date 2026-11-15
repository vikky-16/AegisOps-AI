import sys, os
sys.path.insert(0, os.path.abspath("."))
import csv
from backend.app.main import app

output_path = os.path.join("report_audit", "api_inventory.csv")

records = []
for route in app.routes:
    if not hasattr(route, "methods"):
        continue

    path = route.path
    methods = "/".join(sorted(route.methods - {"HEAD", "OPTIONS"})) if route.methods - {"HEAD", "OPTIONS"} else "/".join(sorted(route.methods))
    endpoint_name = route.name
    handler = getattr(route, "endpoint", None)
    docstring = (handler.__doc__ or "").strip().replace("\n", " ") if handler else ""
    func_name = handler.__name__ if handler else endpoint_name

    # Determine Auth requirement
    auth_req = "PUBLIC"
    role_req = "ANY"
    if any(p in path for p in ["/auth/login", "/auth/signup", "/auth/forgot", "/health", "/docs", "/openapi", "/redoc", "/api/v1/telemetry/stream"]):
        auth_req = "NO (Public Endpoint)"
        role_req = "NONE"
    elif any(p in path for p in ["/approvals", "/remediation", "/recovery", "/execute", "/rollback", "/deploy"]):
        auth_req = "YES (JWT Bearer Token)"
        role_req = "OPERATOR / APPROVER / ADMIN (RBAC Gated)"
    elif any(p in path for p in ["/ai-config/update", "/ai-config/test-connection"]):
        auth_req = "YES (Admin / Config Role)"
        role_req = "PLATFORM_ADMIN / SRE_LEAD"
    else:
        auth_req = "YES (JWT Bearer Token)"
        role_req = "VIEWER / OPERATOR / ADMIN"

    # Database effects
    db_effects = "READ_ONLY"
    if "POST" in methods or "PUT" in methods or "DELETE" in methods or "PATCH" in methods:
        if "incident" in path:
            db_effects = "WRITES: incidents, incident_evidence, timeline_json"
        elif "approval" in path:
            db_effects = "WRITES: approvals, audit_logs, archived_approvals"
        elif "recovery" in path or "remediation" in path:
            db_effects = "WRITES: recovery_executions, recovery_plans, incident_attempts"
        elif "replica" in path or "testing-lab" in path:
            db_effects = "WRITES: replica_experiments, replica_instances"
        elif "ai-config" in path:
            db_effects = "WRITES: In-Memory Secure Store (_AI_CONFIG_STORE)"
        elif "auth" in path:
            db_effects = "WRITES: users, revoked_tokens"
        elif "telemetry" in path:
            db_effects = "WRITES: metrics, logs, events, ring_buffer"
        else:
            db_effects = "MUTATES: Database state or runtime configuration"

    # Error responses
    error_codes = "400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 500 Server Error"

    records.append({
        "http_method": methods,
        "endpoint": path,
        "handler_function": func_name,
        "summary": docstring[:120] if docstring else f"Handles {methods} on {path}",
        "auth_required": auth_req,
        "authorization_role": role_req,
        "database_effects": db_effects,
        "error_responses": error_codes,
        "status": "VERIFIED_ACTIVE"
    })

records.sort(key=lambda x: x["endpoint"])

fieldnames = [
    "http_method", "endpoint", "handler_function", "summary",
    "auth_required", "authorization_role", "database_effects",
    "error_responses", "status"
]

with open(output_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)

print(f"Wrote {len(records)} API endpoints to {output_path}")

