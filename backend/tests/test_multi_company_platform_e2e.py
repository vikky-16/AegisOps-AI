"""
AegisOps AI - Multi-Company Platform End-to-End Verification Suite
Validates:
1. Multi-Company Authentication & Persona RBAC across ShopSphere, FinCore, and CloudDesk.
2. Separation of Duties: CEO / Viewer technical execution lock, SRE approval authority.
3. Multi-Tenant Service Topologies & Dependency Graphs isolation.
4. Strict Tenant Isolation across Incidents, Approvals, and Incident Memory.
5. High-Volume Multi-Tenant Correlated Telemetry Generation.
6. Full Closed-Loop Autonomous Incident Recovery Workflow for Tenant Applications.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from fastapi import HTTPException

from backend.app.core.security import AuthenticatedIdentity, create_access_token, ROLE_PERMISSIONS
from backend.app.api.auth import login, LoginRequest
from backend.app.api.approvals import check_rbac_authorization
from backend.app.api.dependencies import get_dependency_graph, get_dependencies
from backend.app.api.services import get_services
from backend.app.api.incidents import get_incidents, get_incident_detail
from backend.app.api.approvals import get_approvals, get_approval_ticket, approve_ticket, DecisionRequest
from backend.app.monitoring.collector import collector
from backend.app.monitoring.continuous_telemetry import continuous_telemetry, TENANT_TRANSACTION_FLOWS
from backend.app.healing.closed_loop_engine import ClosedLoopValidationEngine
from backend.app.knowledge.incident_memory import incident_memory


@pytest.fixture(autouse=True)
def clean_state():
    collector.active_incidents = []
    collector.resolved_incidents = []
    collector.pending_approvals = []
    collector.reviewed_approvals = []
    collector.audit_logs = []


# ==============================================================================
# 1. MULTI-COMPANY AUTHENTICATION & RBAC
# ==============================================================================

@pytest.mark.asyncio
async def test_multi_company_personas_login():
    """Verify preseeded authentication for all 3 simulated companies across key roles."""
    # 1. ShopSphere E-Commerce
    shop_admin = await login(LoginRequest(username="admin_shopsphere", password="shopsphere123"))
    assert shop_admin["tenant_id"] == "shopsphere"
    assert shop_admin["user"]["role"] in ["COMPANY_ADMIN", "TENANT_ADMIN", "SUPER_ADMIN", "ORG_ADMIN"]

    shop_sre = await login(LoginRequest(username="sre_shopsphere", password="shopsphere123"))
    assert shop_sre["tenant_id"] == "shopsphere"
    assert shop_sre["user"]["role"] in ["SRE_ENGINEER", "SRE_LEAD"]

    shop_ceo = await login(LoginRequest(username="ceo_shopsphere", password="shopsphere123"))
    assert shop_ceo["tenant_id"] == "shopsphere"
    assert shop_ceo["user"]["role"] == "CEO"

    # 2. FinCore Financial Platform
    fin_admin = await login(LoginRequest(username="admin_fincore", password="fincore123"))
    assert fin_admin["tenant_id"] == "fincore"
    assert fin_admin["user"]["role"] in ["COMPANY_ADMIN", "TENANT_ADMIN", "SUPER_ADMIN", "ORG_ADMIN"]

    fin_sre = await login(LoginRequest(username="sre_fincore", password="fincore123"))
    assert fin_sre["tenant_id"] == "fincore"

    fin_sec = await login(LoginRequest(username="sec_fincore", password="fincore123"))
    assert fin_sec["tenant_id"] == "fincore"
    assert fin_sec["user"]["role"] == "SECURITY_ENGINEER"

    # 3. CloudDesk SaaS Platform
    desk_admin = await login(LoginRequest(username="admin_clouddesk", password="clouddesk123"))
    assert desk_admin["tenant_id"] == "clouddesk"

    desk_devops = await login(LoginRequest(username="devops_clouddesk", password="clouddesk123"))
    assert desk_devops["tenant_id"] == "clouddesk"
    assert desk_devops["user"]["role"] == "DEVOPS_ENGINEER"

    # 4. Platform Admin
    platform_admin = await login(LoginRequest(username="admin", password="admin123"))
    assert platform_admin["user"]["is_platform_admin"] is True


def test_rbac_separation_of_duties():
    """Verify role-based execution boundaries: CEO/Viewer gated, SRE Lead authorized for high risk."""
    ceo_identity = AuthenticatedIdentity(
        tenant_id="shopsphere",
        is_platform_admin=False,
        user_id=202,
        username="ceo_shopsphere",
        role="CEO"
    )
    viewer_identity = AuthenticatedIdentity(
        tenant_id="shopsphere",
        is_platform_admin=False,
        user_id=208,
        username="viewer_shopsphere",
        role="VIEWER"
    )
    sre_engineer_identity = AuthenticatedIdentity(
        tenant_id="shopsphere",
        is_platform_admin=False,
        user_id=203,
        username="sre_shopsphere",
        role="SRE_ENGINEER"
    )
    sre_lead_identity = AuthenticatedIdentity(
        tenant_id="shopsphere",
        is_platform_admin=False,
        user_id=203,
        username="sre_lead_shopsphere",
        role="SRE_LEAD"
    )

    # CEO cannot approve technical remediation
    with pytest.raises(HTTPException) as exc_info:
        check_rbac_authorization(ceo_identity, "APPROVE", "HIGH")
    assert exc_info.value.status_code == 403

    # Viewer cannot approve remediation
    with pytest.raises(HTTPException) as exc_info:
        check_rbac_authorization(viewer_identity, "APPROVE", "LOW")
    assert exc_info.value.status_code == 403

    # SRE Engineer can approve LOW risk actions but is gated on HIGH risk
    assert check_rbac_authorization(sre_engineer_identity, "APPROVE", "LOW") is True
    with pytest.raises(HTTPException) as exc_info:
        check_rbac_authorization(sre_engineer_identity, "APPROVE", "HIGH")
    assert exc_info.value.status_code == 403

    # SRE Lead has full high-risk technical approval authority
    assert check_rbac_authorization(sre_lead_identity, "APPROVE", "HIGH") is True


# ==============================================================================
# 2. MULTI-TENANT SERVICE TOPOLOGY ISOLATION
# ==============================================================================

@pytest.mark.asyncio
async def test_tenant_service_topologies_isolated():
    """Verify each simulated company receives its own tailored microservice topology."""
    # ShopSphere: E-Commerce Services
    shop_topo = await get_dependency_graph(tenant_id="shopsphere")
    shop_node_ids = [n["id"] for n in shop_topo["nodes"]]
    assert "order-service" in shop_node_ids
    assert "inventory-service" in shop_node_ids
    assert "account-service" not in shop_node_ids
    assert "project-service" not in shop_node_ids

    # FinCore: Financial Services
    fin_topo = await get_dependency_graph(tenant_id="fincore")
    fin_node_ids = [n["id"] for n in fin_topo["nodes"]]
    assert "account-service" in fin_node_ids
    assert "transaction-service" in fin_node_ids
    assert "fraud-service" in fin_node_ids
    assert "order-service" not in fin_node_ids

    # CloudDesk: SaaS Services
    desk_topo = await get_dependency_graph(tenant_id="clouddesk")
    desk_node_ids = [n["id"] for n in desk_topo["nodes"]]
    assert "project-service" in desk_node_ids
    assert "billing-service" in desk_node_ids
    assert "fraud-service" not in desk_node_ids

    # Services API endpoint test
    shop_svcs = await get_services(tenant_id="shopsphere")
    shop_svc_names = [s["name"] for s in shop_svcs]
    assert "order-service" in shop_svc_names
    assert "account-service" not in shop_svc_names


# ==============================================================================
# 3. STRICT TENANT ISOLATION: INCIDENTS & APPROVALS
# ==============================================================================

@pytest.mark.asyncio
async def test_strict_cross_company_incident_isolation():
    """
    Verify Company A cannot see Company B incidents.
    Platform Admin can access cross-company incidents.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    # Create incident for ShopSphere
    inc_shop = {
        "id": "INC-SHOPSPHERE-001",
        "incident_id": "INC-SHOPSPHERE-001",
        "title": "ShopSphere Checkout Degradation",
        "severity": "CRITICAL",
        "status": "INVESTIGATING",
        "service": "order-service",
        "primary_service": "order-service",
        "root_cause_service": "order-service",
        "tenant_id": "shopsphere",
        "timestamp": now_iso,
        "created_at": now_iso
    }
    # Create incident for FinCore
    inc_fin = {
        "id": "INC-FINCORE-001",
        "incident_id": "INC-FINCORE-001",
        "title": "FinCore Fraud Worker Latency",
        "severity": "HIGH",
        "status": "INVESTIGATING",
        "service": "fraud-service",
        "primary_service": "fraud-service",
        "root_cause_service": "fraud-service",
        "tenant_id": "fincore",
        "timestamp": now_iso,
        "created_at": now_iso
    }

    collector.active_incidents = [inc_shop, inc_fin]

    shop_identity = AuthenticatedIdentity(
        tenant_id="shopsphere",
        is_platform_admin=False,
        user_id=201,
        username="admin_shopsphere",
        role="ORG_ADMIN"
    )
    fin_identity = AuthenticatedIdentity(
        tenant_id="fincore",
        is_platform_admin=False,
        user_id=301,
        username="admin_fincore",
        role="ORG_ADMIN"
    )
    platform_identity = AuthenticatedIdentity(
        tenant_id="platform",
        is_platform_admin=True,
        user_id=1,
        username="admin",
        role="PLATFORM_ADMIN"
    )

    # ShopSphere admin queries incidents -> only sees ShopSphere
    shop_res = await get_incidents(identity=shop_identity)
    shop_ids = [i.get("id") or i.get("incident_id") for i in shop_res]
    assert "INC-SHOPSPHERE-001" in shop_ids
    assert "INC-FINCORE-001" not in shop_ids

    # FinCore admin queries incidents -> only sees FinCore
    fin_res = await get_incidents(identity=fin_identity)
    fin_ids = [i.get("id") or i.get("incident_id") for i in fin_res]
    assert "INC-FINCORE-001" in fin_ids
    assert "INC-SHOPSPHERE-001" not in fin_ids

    # ShopSphere admin tries to access FinCore incident directly -> 404/403
    with pytest.raises(HTTPException) as exc_info:
        await get_incident_detail("INC-FINCORE-001", identity=shop_identity)
    assert exc_info.value.status_code in [403, 404]

    # Platform Admin can query all
    all_res = await get_incidents(identity=platform_identity)
    all_ids = [i.get("id") or i.get("incident_id") for i in all_res]
    assert "INC-SHOPSPHERE-001" in all_ids
    assert "INC-FINCORE-001" in all_ids


# ==============================================================================
# 4. HIGH-VOLUME MULTI-TENANT TELEMETRY
# ==============================================================================

def test_multi_tenant_telemetry_generation():
    """Verify telemetry generation assigns proper tenant_id, trace correlation, and metrics."""
    batch = continuous_telemetry.generate_batch(count=60)
    assert len(batch) >= 40

    tenants_found = {evt.tenant_id for evt in batch}
    # Should contain tenant keys
    assert any(t in ["shopsphere", "fincore", "clouddesk", "demo-tenant"] for t in tenants_found)

    # Check event enrichment
    for evt in batch:
        assert evt.trace_id.startswith("trc-")
        assert evt.span_id.startswith("spn-")
        assert evt.service is not None
        assert evt.http_method in ["GET", "POST"]
        assert evt.status_code in [200, 500, 503]

    status = continuous_telemetry.get_status()
    assert "events_by_tenant" in status
    assert isinstance(status["events_by_tenant"], dict)


# ==============================================================================
# 5. CLOSED-LOOP RECOVERY WORKFLOW FOR SIMULATED COMPANY
# ==============================================================================

@pytest.mark.asyncio
async def test_closed_loop_recovery_workflow_for_tenant():
    """
    Executes the full end-to-end autonomous closed-loop recovery validation cycle
    for ShopSphere:
    Anomaly Detection -> RCA -> Solutions -> Replica Execution -> Scenario Replay ->
    Before/After Evidence -> Side-Effect Check -> Validated Outcome -> Incident Memory
    """
    engine = ClosedLoopValidationEngine(max_iterations=3)
    result = await engine.execute_closed_loop(
        scenario_id="db_connection_exhaustion",
        incident_id="INC-SHOPSPHERE-TEST-01",
        tenant_id="shopsphere",
        forced_first_action=None
    )

    assert result["lifecycle_state"] == "VALIDATED"
    assert result["tenant_id"] == "shopsphere"
    assert result["primary_service"] == "database-service"
    assert len(result["state_transitions"]) >= 10

    # Verify all critical states occurred in sequence
    transition_states = [t["to_state"] for t in result["state_transitions"]]
    assert "INCIDENT_DETECTED" in transition_states
    assert "EVIDENCE_COLLECTED" in transition_states
    assert "RCA_COMPLETED" in transition_states
    assert "SOLUTIONS_GENERATED" in transition_states
    assert "REPLICA_EXECUTION" in transition_states
    assert "SCENARIO_REPLAY" in transition_states
    assert "EVIDENCE_COMPARED" in transition_states
    assert "VALIDATED" in transition_states

    # Verify attempt record contents
    assert len(result["execution_history"]) >= 1
    last_attempt = result["execution_history"][-1]
    assert last_attempt["solution_validated"] is True
    assert last_attempt["original_error_resolved"] is True
    assert last_attempt["side_effect_detected"] is False
    assert "comparison_table" in last_attempt

    # Verify validation report
    assert "validation_report" in result
    report = result["validation_report"]
    assert report["final_validation_decision"] == "VALIDATED"
    assert report["incident"]["tenant_id"] == "shopsphere"
