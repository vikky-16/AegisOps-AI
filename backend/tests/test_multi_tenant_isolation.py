"""
Enterprise Multi-Tenant Isolation & Autonomy Verification Tests
Validates:
- Scenario A: Complete data and operational isolation between Tenant A (Acme Corp) and Tenant B (Cyberdyne Systems).
              Platform Admin cross-tenant visibility.
- Scenario D: Policy-driven remediation gating: low-risk actions auto-remediate under policy; high-risk gate on human approval.
- Scenario E: Incident Memory: >= 0.80 similarity triggers known-pattern fast path with verified resolution.
- Scenario F: Novel anomaly (< 0.80 similarity) strictly enforces human authorization before any remediation.
- Scenario G: Security boundaries: Tenant A cannot access, query, or approve Tenant B incidents/tickets (403/404).
"""

import pytest
import asyncio
from datetime import datetime, timezone
from fastapi import HTTPException

from backend.app.core.security import AuthenticatedIdentity, create_access_token
from backend.app.monitoring.collector import collector
from backend.app.knowledge.incident_memory import incident_memory, IncidentVector
from backend.app.healing.decision_engine import decision_engine
from backend.app.api.incidents import get_incidents, get_incident_detail
from backend.app.api.approvals import get_approvals, get_approval_ticket, approve_ticket, reject_ticket, DecisionRequest


@pytest.fixture(autouse=True)
def clean_state():
    collector.active_incidents.clear()
    collector.resolved_incidents.clear()
    collector.pending_approvals.clear()
    collector.reviewed_approvals.clear()
    collector.audit_logs.clear()


# Identities for test scenarios
IDENTITY_TENANT_A = AuthenticatedIdentity(
    tenant_id="tenant-alpha",
    is_platform_admin=False,
    user_id=101,
    username="sre_acme",
    role="TENANT_ADMIN"
)

IDENTITY_TENANT_B = AuthenticatedIdentity(
    tenant_id="tenant-beta",
    is_platform_admin=False,
    user_id=102,
    username="sre_cyber",
    role="TENANT_ADMIN"
)

IDENTITY_PLATFORM_ADMIN = AuthenticatedIdentity(
    tenant_id="platform",
    is_platform_admin=True,
    user_id=1,
    username="admin",
    role="PLATFORM_ADMIN"
)


# ==============================================================================
# SCENARIO A: Complete Multi-Tenant Isolation & Platform Admin Visibility
# ==============================================================================

@pytest.mark.asyncio
async def test_scenario_a_incident_isolation_between_tenants():
    """
    Scenario A: Company A (Acme) and Company B (Cyberdyne) incidents are strictly isolated.
    Acme user cannot see Cyberdyne incidents. Cyberdyne user cannot see Acme incidents.
    Platform Admin can query and view all incidents across tenants.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    inc_a = {
        "incident_id": "INC-ACME-001",
        "tenant_id": "tenant-alpha",
        "title": "Payment gateway latency spike",
        "severity": "HIGH",
        "status": "OPEN",
        "primary_service": "payment-api",
        "root_cause_service": "payment-api",
        "created_at": now_iso
    }
    inc_b = {
        "incident_id": "INC-CYBER-001",
        "tenant_id": "tenant-beta",
        "title": "Database deadlocks detected",
        "severity": "CRITICAL",
        "status": "OPEN",
        "primary_service": "database-service",
        "root_cause_service": "database-service",
        "created_at": now_iso
    }

    collector.active_incidents = [inc_a, inc_b]

    # 1. Tenant A queries incidents
    acme_view = await get_incidents(identity=IDENTITY_TENANT_A)
    assert len(acme_view) == 1
    assert acme_view[0]["incident_id"] == "INC-ACME-001"
    assert acme_view[0]["tenant_id"] == "tenant-alpha"

    # 2. Tenant B queries incidents
    cyber_view = await get_incidents(identity=IDENTITY_TENANT_B)
    assert len(cyber_view) == 1
    assert cyber_view[0]["incident_id"] == "INC-CYBER-001"
    assert cyber_view[0]["tenant_id"] == "tenant-beta"

    # 3. Platform Admin queries all incidents
    admin_view = await get_incidents(identity=IDENTITY_PLATFORM_ADMIN)
    assert len(admin_view) >= 2
    tenant_ids = {i["tenant_id"] for i in admin_view}
    assert "tenant-alpha" in tenant_ids
    assert "tenant-beta" in tenant_ids

    # 4. Platform Admin filters by specific tenant
    admin_filtered = await get_incidents(tenant_id="tenant-alpha", identity=IDENTITY_PLATFORM_ADMIN)
    assert len(admin_filtered) == 1
    assert admin_filtered[0]["incident_id"] == "INC-ACME-001"


# ==============================================================================
# SCENARIO G: Security Boundaries (403 Forbidden / 404 on Cross-Tenant Access)
# ==============================================================================

@pytest.mark.asyncio
async def test_scenario_g_cross_tenant_access_denied_with_403():
    """
    Scenario G: Automated test suite proving Company A attempts on Company B return 403 Forbidden.
    - Tenant A attempts to inspect Tenant B's incident -> 403 Forbidden.
    - Tenant A attempts to approve Tenant B's approval ticket -> 403 Forbidden.
    - Tenant A attempts to reject Tenant B's approval ticket -> 403 Forbidden.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    inc_b = {
        "incident_id": "INC-CYBER-999",
        "tenant_id": "tenant-beta",
        "title": "Cyberdyne secure vault alert",
        "severity": "CRITICAL",
        "status": "AWAITING_APPROVAL",
        "primary_service": "vault-service",
        "root_cause_service": "vault-service",
        "created_at": now_iso
    }
    collector.active_incidents = [inc_b]

    # 1. Tenant A attempts to read Tenant B's incident details
    with pytest.raises(HTTPException) as exc_info:
        await get_incident_detail(incident_id="INC-CYBER-999", identity=IDENTITY_TENANT_A)
    assert exc_info.value.status_code == 403
    assert "tenant-beta" in exc_info.value.detail

    # 2. Setup an approval ticket for Tenant B
    ticket_b = {
        "tenant_id": "tenant-beta",
        "approval_id": "APR-CYBER-001",
        "incident_id": "INC-CYBER-999",
        "severity": "CRITICAL",
        "service_name": "vault-service",
        "proposed_action": "RESTART_SERVICE",
        "risk_level": "HIGH",
        "status": "PENDING_APPROVAL",
        "created_at": now_iso
    }
    collector.pending_approvals = [ticket_b]

    # 3. Tenant A attempts to inspect Tenant B's approval ticket
    with pytest.raises(HTTPException) as exc_info:
        await get_approval_ticket(approval_id="APR-CYBER-001", identity=IDENTITY_TENANT_A)
    assert exc_info.value.status_code == 403

    # 4. Tenant A attempts to approve Tenant B's approval ticket
    with pytest.raises(HTTPException) as exc_info:
        await approve_ticket(
            approval_id="APR-CYBER-001",
            payload=DecisionRequest(reviewer="sre_acme", role="TENANT_ADMIN"),
            identity=IDENTITY_TENANT_A
        )
    assert exc_info.value.status_code == 403
    assert "tenant-beta" in exc_info.value.detail

    # 5. Tenant A attempts to reject Tenant B's approval ticket
    with pytest.raises(HTTPException) as exc_info:
        await reject_ticket(
            approval_id="APR-CYBER-001",
            payload=DecisionRequest(reviewer="sre_acme", role="TENANT_ADMIN", notes="Malicious cross-tenant attempt"),
            identity=IDENTITY_TENANT_A
        )
    assert exc_info.value.status_code == 403


# ==============================================================================
# SCENARIO E & F: Incident Memory Isolation & Autonomy Gates (>=0.80 vs Novel)
# ==============================================================================

def test_scenario_e_and_f_incident_memory_isolation_and_similarity():
    """
    Scenario E & F:
    - Incident memory is strictly partitioned by tenant: Tenant A's memories cannot be seen by Tenant B.
    - Similarity >= 0.80 on recurring failure pattern allows autonomous fast-path.
    - Novel anomaly (< 0.80 similarity or unobserved signature) strictly requires human approval.
    """
    # Reset cooldown state to guarantee test isolation from previous test files
    decision_engine.last_action_per_service.clear()

    # 1. Record a verified resolution in Tenant A's memory
    sig_feature_vec = [0.1, 0.85, 0.03, 0.40, 0.50, 0.20, 0.15, 0.67, 0.85, 0.80, 0.30, 0.90]
    vec_a = IncidentVector(
        incident_id="INC-ACME-HIST-01",
        failure_signature={"symptoms": ["DATABASE_CONNECTION_POOL_EXHAUSTION"]},
        root_cause_service="database-service",
        remediation_action="RESET_CONNECTION_POOL",
        success=True,
        mttr_seconds=2.1,
        tenant_id="tenant-alpha"
    )
    incident_memory.record_incident(vec_a, tenant_id="tenant-alpha")

    # Also add vector representation directly to history for vector comparison
    entry = {
        "tenant_id": "tenant-alpha",
        "incident_id": "INC-ACME-HIST-01",
        "primary_service": "database-service",
        "failure_type": "DATABASE_CONNECTION_POOL_EXHAUSTION",
        "failure_category": "Database",
        "telemetry_signature": {"symptoms": ["DATABASE_CONNECTION_POOL_EXHAUSTION"]},
        "feature_vector": sig_feature_vec,
        "remediation_action": "RESET_CONNECTION_POOL",
        "verification_status": "VERIFIED",
        "success": True,
        "time_to_recover_sec": 2.1
    }
    incident_memory.record_incident(entry, tenant_id="tenant-alpha")

    # 2. Tenant B searches memory with the exact same failure signature
    # Because Tenant B is isolated, it must NOT find Tenant A's past incident
    tenant_b_pattern = incident_memory.get_repeated_failure_pattern(
        service="database-service",
        failure_type="DATABASE_CONNECTION_POOL_EXHAUSTION",
        query_vector=sig_feature_vec,
        tenant_id="tenant-beta"
    )
    assert tenant_b_pattern["is_novel"] is True
    assert tenant_b_pattern["is_known_pattern"] is False
    assert tenant_b_pattern["historical_occurrences"] == 0
    assert tenant_b_pattern["requires_approval"] is True

    # 3. Tenant A searches memory with matching signature -> finds high similarity match (>= 0.80)
    tenant_a_pattern = incident_memory.get_repeated_failure_pattern(
        service="database-service",
        failure_type="DATABASE_CONNECTION_POOL_EXHAUSTION",
        query_vector=sig_feature_vec,
        tenant_id="tenant-alpha"
    )
    assert tenant_a_pattern["is_known_pattern"] is True
    assert tenant_a_pattern["is_novel"] is False
    assert tenant_a_pattern["historical_occurrences"] >= 1
    assert tenant_a_pattern["similarity_score"] >= 0.80
    assert tenant_a_pattern["recommended_action"] == "RESET_CONNECTION_POOL"

    # 4. Decision Engine on Known Pattern for Tenant A (Scenario E)
    incident_known = {
        "incident_id": "INC-ACME-NEW-01",
        "tenant_id": "tenant-alpha",
        "root_cause_service": "database-service",
        "recommended_action": "RESET_CONNECTION_POOL",
        "rca_confidence": 0.94,
        "blast_radius_score": 30.0,
        "historical_match": tenant_a_pattern
    }
    decision_known = decision_engine.evaluate(incident_known, telemetry_fresh=True)
    assert decision_known["decision"] == "AUTO_REMEDIATE"
    assert decision_known["requires_approval"] is False

    # 5. Decision Engine on Novel Anomaly for Tenant B (Scenario F)
    incident_novel = {
        "incident_id": "INC-CYBER-NEW-01",
        "tenant_id": "tenant-beta",
        "root_cause_service": "database-service",
        "recommended_action": "RESET_CONNECTION_POOL",
        "rca_confidence": 0.94,
        "blast_radius_score": 30.0,
        "historical_match": tenant_b_pattern,
        "is_novel": True
    }
    decision_novel = decision_engine.evaluate(incident_novel, telemetry_fresh=True)
    assert decision_novel["decision"] == "REQUEST_APPROVAL"
    assert decision_novel["requires_approval"] is True
    assert "Novel Anomaly" in decision_novel["reason"]


# ==============================================================================
# SCENARIO D: Policy-Controlled Remediation & Risk Gating
# ==============================================================================

def test_scenario_d_policy_controlled_risk_gating():
    """
    Scenario D:
    - Low-risk allowlisted action with high confidence -> AUTO_REMEDIATE.
    - High-risk action (e.g. Critical service restart or wide blast radius) -> REQUEST_APPROVAL.
    - Tenant policy with auto_remediation_enabled=False -> forces REQUEST_APPROVAL on all actions.
    - Unallowlisted action -> ESCALATE with critical risk.
    """
    # Reset cooldown state to guarantee test isolation from previous test files
    decision_engine.last_action_per_service.clear()

    # 1. Low risk action, high confidence -> AUTO_REMEDIATE
    incident_low_risk = {
        "incident_id": "INC-LOW-01",
        "tenant_id": "tenant-alpha",
        "root_cause_service": "database-service",
        "recommended_action": "RESET_CONNECTION_POOL",
        "rca_confidence": 0.92,
        "blast_radius_score": 25.0
    }
    dec_low = decision_engine.evaluate(incident_low_risk, telemetry_fresh=True)
    assert dec_low["decision"] == "AUTO_REMEDIATE"
    assert dec_low["risk_level"] == "LOW"

    # 2. High risk action (Restarting critical gateway) -> REQUEST_APPROVAL
    incident_high_risk = {
        "incident_id": "INC-HIGH-01",
        "tenant_id": "tenant-alpha",
        "root_cause_service": "gateway",
        "recommended_action": "RESTART_SERVICE",
        "rca_confidence": 0.95,
        "blast_radius_score": 85.0
    }
    dec_high = decision_engine.evaluate(incident_high_risk, telemetry_fresh=True)
    assert dec_high["decision"] == "REQUEST_APPROVAL"
    assert dec_high["requires_approval"] is True
    assert dec_high["risk_level"] == "HIGH"

    # 3. Tenant Policy: auto_remediate_enabled is explicitly False
    incident_disabled_policy = {
        "incident_id": "INC-POLICY-01",
        "tenant_id": "tenant-alpha",
        "root_cause_service": "database-service",
        "recommended_action": "RESET_CONNECTION_POOL",
        "rca_confidence": 0.95,
        "blast_radius_score": 20.0,
        "tenant_policy": {
            "auto_remediate_enabled": False,
            "max_auto_remediate_risk": "LOW"
        }
    }
    dec_disabled = decision_engine.evaluate(incident_disabled_policy, telemetry_fresh=True)
    assert dec_disabled["decision"] == "REQUEST_APPROVAL"
    assert dec_disabled["requires_approval"] is True
    assert "disabled" in dec_disabled["reason"].lower()

    # 4. Unallowlisted action -> ESCALATE
    incident_unallowlisted = {
        "incident_id": "INC-UNALLOW-01",
        "tenant_id": "tenant-alpha",
        "root_cause_service": "database-service",
        "recommended_action": "DROP_DATABASE_TABLES",
        "rca_confidence": 0.90,
        "blast_radius_score": 50.0
    }
    dec_unallow = decision_engine.evaluate(incident_unallowlisted, telemetry_fresh=True)
    assert dec_unallow["decision"] == "ESCALATE"
    assert dec_unallow["risk_level"] == "CRITICAL"
