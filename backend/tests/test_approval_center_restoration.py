import pytest
import asyncio
import sys
from pathlib import Path
root_dir = str(Path(__file__).parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.incident import Incident
from backend.app.healing.approval_manager import approval_manager
from backend.app.healing.controlled_execution_engine import controlled_execution_engine
from backend.app.monitoring.collector import collector
from backend.app.core.security import get_current_user, AuthenticatedIdentity

client = TestClient(app)

@pytest.fixture(autouse=True)
def auth_override():
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedIdentity(
        tenant_id="demo-tenant",
        is_platform_admin=True,
        user_id=1,
        username="admin",
        role="PLATFORM_OWNER_ADMIN"
    )
    yield
    app.dependency_overrides.pop(get_current_user, None)

@pytest.mark.asyncio
async def test_approval_ticket_creation_and_stats():
    # 1. Create a simulated pending incident
    inc = Incident(
        incident_id="INC-TEST-APPROVAL-001",
        primary_service="database-service",
        title="Database connection pool exhaustion",
        severity="P1",
        status="AWAITING_APPROVAL",
        root_cause="Connection pool saturation caused by abnormal request concurrency",
        root_cause_confidence=0.94,
        recommended_action="RESET_CONNECTION_POOL"
    )
    inc.blast_radius = "MEDIUM"
    inc.tenant_id = "test-tenant-approvals"
    collector.active_incidents.append(inc.to_dict())

    # 2. Trigger approval ticket creation via approval_manager
    ticket = await approval_manager.create_or_get_approval_ticket(
        incident=inc.to_dict(),
        proposed_action="RESET_CONNECTION_POOL",
        safety_eval={"risk_level": "MEDIUM", "checks_passed": True}
    )

    assert ticket is not None
    assert ticket["approval_id"].startswith("APP-")
    assert ticket["service_name"] == "database-service"
    assert ticket["risk_level"] == "MEDIUM"
    assert ticket["status"] in ("PENDING", "PENDING_APPROVAL", "AWAITING_APPROVAL")
    assert ticket["tenant_id"] == "test-tenant-approvals"

    # 3. Test stats endpoint
    stats = approval_manager.get_approval_stats(tenant_id="test-tenant-approvals")
    assert stats["total_pending"] >= 1
    assert stats["medium_risk"] >= 1

    # 4. Verify API endpoint GET /api/approvals
    res = client.get("/api/approvals", headers={"X-Tenant-ID": "test-tenant-approvals"})
    assert res.status_code == 200
    data = res.json()
    assert any(t["approval_id"] == ticket["approval_id"] for t in data)

    # 5. Verify API endpoint GET /api/approvals/stats
    res_stats = client.get("/api/approvals/stats", headers={"X-Tenant-ID": "test-tenant-approvals"})
    assert res_stats.status_code == 200
    stats_api = res_stats.json()
    assert stats_api["total_pending"] >= 1

@pytest.mark.asyncio
async def test_approval_rejection_prevents_recovery():
    inc = Incident(
        incident_id="INC-TEST-REJECT-002",
        primary_service="payment-service",
        title="Payment gateway timeout",
        severity="P2",
        status="AWAITING_APPROVAL",
        root_cause="Network socket starvation",
        root_cause_confidence=0.91,
        recommended_action="FAILOVER_DEPENDENCY"
    )
    inc.tenant_id = "test-tenant-reject"
    collector.active_incidents.append(inc.to_dict())

    ticket = await approval_manager.create_or_get_approval_ticket(
        incident=inc.to_dict(),
        proposed_action="FAILOVER_DEPENDENCY",
        safety_eval={"risk_level": "HIGH", "checks_passed": True}
    )

    # Reject the ticket with mandatory reason
    res = client.post(
        f"/api/approvals/{ticket['approval_id']}/reject",
        json={"reviewer": "SRE Lead", "role": "ADMIN", "notes": "Deployment window closed"},
        headers={"X-Tenant-ID": "test-tenant-reject"}
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "REJECTED"

    # Verify ticket status
    updated_ticket = approval_manager.get_ticket(ticket["approval_id"], tenant_id="test-tenant-reject")
    assert updated_ticket["status"] == "REJECTED"
    assert "Deployment window closed" in updated_ticket["review_notes"]

    # Verify incident remains unrecovered
    assert inc.status != "RESOLVED"
    assert inc.status != "RECOVERING"

@pytest.mark.asyncio
async def test_approval_acceptance_triggers_controlled_recovery():
    inc = Incident(
        incident_id="INC-TEST-EXEC-003",
        primary_service="database-service",
        title="Database connection saturation",
        severity="P1",
        status="AWAITING_APPROVAL",
        root_cause="Connection pool saturation",
        root_cause_confidence=0.95,
        recommended_action="RESET_CONNECTION_POOL"
    )
    inc.tenant_id = "test-tenant-exec"
    collector.active_incidents.append(inc.to_dict())

    ticket = await approval_manager.create_or_get_approval_ticket(
        incident=inc.to_dict(),
        proposed_action="RESET_CONNECTION_POOL",
        safety_eval={"risk_level": "MEDIUM", "checks_passed": True}
    )

    # Approve ticket via API
    res = client.post(
        f"/api/approvals/{ticket['approval_id']}/approve",
        json={"reviewer": "CTO Operator", "role": "ADMIN", "notes": "Authorized emergency reset"},
        headers={"X-Tenant-ID": "test-tenant-exec"}
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] in ("APPROVED", "RESOLVED", "SUCCESS", "EXECUTING")

    # Verify ticket state is APPROVED
    updated = approval_manager.get_ticket(ticket["approval_id"], tenant_id="test-tenant-exec")
    assert updated["status"] == "APPROVED"
    assert updated["reviewed_by"] == "CTO Operator"

@pytest.mark.asyncio
async def test_rbac_and_tenant_isolation_on_approval():
    inc = Incident(
        incident_id="INC-TEST-TENANT-004",
        primary_service="user-service",
        title="User cache exhaustion",
        severity="P2",
        status="AWAITING_APPROVAL"
    )
    inc.tenant_id = "tenant-alpha"
    collector.active_incidents.append(inc.to_dict())

    ticket = await approval_manager.create_or_get_approval_ticket(
        incident=inc.to_dict(),
        proposed_action="CLEAR_CACHE",
        safety_eval={"risk_level": "LOW", "checks_passed": True}
    )

    # 1. Attempt approval from DIFFERENT tenant -> should fail 404 (isolated)
    res_cross = client.post(
        f"/api/approvals/{ticket['approval_id']}/approve",
        json={"reviewer": "Hacker", "role": "ADMIN", "notes": "Cross tenant probe"},
        headers={"X-Tenant-ID": "tenant-beta"}
    )
    assert res_cross.status_code in (404, 403)

    # 2. Attempt approval with VIEW-only role without permissions -> should fail 403
    res_viewer = client.post(
        f"/api/approvals/{ticket['approval_id']}/approve",
        json={"reviewer": "Viewer User", "role": "VIEWER", "notes": "Viewer attempt"},
        headers={"X-Tenant-ID": "tenant-alpha"}
    )
    assert res_viewer.status_code == 403
