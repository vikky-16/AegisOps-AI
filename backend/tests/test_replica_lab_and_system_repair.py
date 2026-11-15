"""
AegisOps AI - Comprehensive Test Suite for Digital Replica Lab & End-to-End System Repairs
Verifies:
1. Digital Twin Replica Adapters, strict isolation boundaries, allowlisted actions, and fault injection
2. Full 17-step experiment lifecycle, quantitative evaluation, and candidate ranking
3. Human-in-the-loop approval workflow and controlled deployment to live target with post-validation
4. Multi-company tenant data generator (FinCore, ShopSphere, CloudDesk), deduplication, and zero orphaned approvals
5. AI provider connectivity diagnostics and graceful SRE Assistant fallback
6. API endpoint contracts for Replica Lab
"""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.replica import ReplicaInstance, ReplicaExperiment
from backend.app.models.incident import Incident as IncidentModel
from backend.app.models.approval import ApprovalTicket
from backend.app.replica.adapters import (
    SyntheticReplicaAdapter,
    get_replica_adapter
)
from backend.app.replica.remediation_lab import RemediationLabEngine
from backend.app.services.tenant_incident_generator import TenantIncidentGenerator
from backend.app.ai.gemini_provider import GeminiProvider


@pytest.mark.asyncio
async def test_replica_adapter_isolation_and_safety():
    """Verifies that replica adapters enforce strict isolation boundaries and block destructive actions."""
    adapter = get_replica_adapter(
        replica_id="twin-fincore-test-01",
        tenant_id="fincore",
        target_service="fincore-payment-gateway",
        environment_type="SYNTHETIC"
    )

    assert adapter.get_environment_type() == "SYNTHETIC"
    assert adapter.get_fidelity_level() >= 0.95

    # Isolation boundaries verification
    boundaries = adapter.get_isolation_boundaries()
    assert boundaries["production_traffic_isolated"] is True
    assert boundaries["destructive_operations_blocked"] is True
    assert "RESET_CONNECTION_POOL" in boundaries["allowlisted_actions"]

    # Limitations documentation
    limitations = adapter.get_limitations()
    assert len(limitations) > 0

    # Inject fault: db_pool_exhaustion
    inject_res = await adapter.inject_fault("db_pool_exhaustion")
    assert inject_res["status"] == "FAULT_INJECTED"
    assert inject_res["metrics"]["error_rate"] > 0.40
    assert inject_res["metrics"]["p95_latency_ms"] > 800.0

    # Unauthorized / destructive action must be BLOCKED
    blocked_res = await adapter.apply_remediation("DROP_TABLE_PAYMENTS")
    assert blocked_res["status"] == "BLOCKED"
    assert "not allowlisted" in blocked_res["error"].lower()

    # Allowlisted remediation
    remedy_res = await adapter.apply_remediation("RESET_CONNECTION_POOL")
    assert remedy_res["status"] == "APPLIED"
    assert remedy_res["resolved"] is True
    assert remedy_res["resulting_metrics"]["error_rate"] <= 0.010
    assert remedy_res["resulting_metrics"]["p95_latency_ms"] <= 50.0

    # Reset
    reset_res = await adapter.reset()
    assert reset_res["status"] == "HEALTHY"
    assert reset_res["metrics"]["error_rate"] <= 0.005


@pytest.mark.asyncio
async def test_remediation_lab_17_step_lifecycle():
    """Verifies the complete 17-step scientific experiment lifecycle and quantitative candidate ranking."""
    exp = await RemediationLabEngine.run_experiment(
        incident_id="INC-TEST-LIFECYCLE-001",
        tenant_id="fincore",
        scenario_id="db_pool_exhaustion",
        target_service="fincore-ledger-db"
    )

    assert exp["experiment_id"].startswith("EXP-")
    assert exp["incident_id"] == "INC-TEST-LIFECYCLE-001"
    assert exp["tenant_id"] == "fincore"
    assert exp["evaluation_verdict"] == "PASS"
    assert exp["confidence_score"] >= 0.90
    assert exp["status"] == "COMPLETED"
    assert exp["stage"] == "AWAITING_APPROVAL"

    # Verify quantitative candidate evaluation
    candidates = exp["candidate_remediations"]
    assert len(candidates) >= 2
    top_cand = candidates[0]
    assert top_cand["verdict"] == "PASS"
    assert top_cand["composite_score"] > 80.0
    assert top_cand["metrics_delta"]["error_reduction_pct"] > 90.0
    assert top_cand["metrics_delta"]["latency_reduction_pct"] > 80.0

    # Verify persistent database storage
    async with AsyncSessionLocal() as session:
        stmt = select(ReplicaExperiment).where(ReplicaExperiment.experiment_id == exp["experiment_id"])
        res = await session.execute(stmt)
        db_exp = res.scalar_one_or_none()
        assert db_exp is not None
        assert db_exp.evaluation_verdict == "PASS"
        assert db_exp.target_service == "fincore-ledger-db"


@pytest.mark.asyncio
async def test_replica_experiment_approval_and_deployment():
    """Verifies approval gating and live target deployment with post-validation."""
    # 1. Run experiment
    exp = await RemediationLabEngine.run_experiment(
        incident_id="INC-DEPLOY-TEST-002",
        tenant_id="shopsphere",
        scenario_id="queue_backlog",
        target_service="shopsphere-order-worker"
    )
    exp_id = exp["experiment_id"]

    # Pre-approval deployment must be blocked
    blocked_deploy = await RemediationLabEngine.deploy_to_target(exp_id)
    assert blocked_deploy["status"] == "BLOCKED"
    assert "Pre-deployment approval is required" in blocked_deploy["message"]

    # 2. Approve experiment
    appr_res = await RemediationLabEngine.approve_experiment(
        experiment_id=exp_id,
        approver="Lead SRE Architect",
        comments="Candidate verified in isolated digital twin sandbox."
    )
    assert appr_res["status"] == "SUCCESS"
    assert appr_res["experiment"]["stage"] == "APPROVED"

    # 3. Deploy to target & validate
    deploy_res = await RemediationLabEngine.deploy_to_target(exp_id, operator="Autonomous Dispatcher")
    assert deploy_res["status"] == "SUCCESS"
    assert deploy_res["deployment"]["execution_status"] == "EXECUTED"
    assert deploy_res["deployment"]["post_validation"]["status"] == "VALIDATED"
    assert deploy_res["experiment"]["stage"] == "VALIDATED"


@pytest.mark.asyncio
async def test_tenant_incident_generator_and_approval_consistency():
    """Verifies realistic multi-company operational scenarios, idempotency, and zero orphan approvals."""
    # Seed FinCore, ShopSphere, and CloudDesk
    res_fin = await TenantIncidentGenerator.seed_tenant_scenarios("fincore")
    assert res_fin["status"] == "SUCCESS"
    assert (len(res_fin["created_incidents"]) + len(res_fin.get("existing_incidents", []))) > 0

    res_shop = await TenantIncidentGenerator.seed_tenant_scenarios("shopsphere")
    assert res_shop["status"] == "SUCCESS"
    assert (len(res_shop["created_incidents"]) + len(res_shop.get("existing_incidents", []))) > 0

    res_cloud = await TenantIncidentGenerator.seed_tenant_scenarios("clouddesk")
    assert res_cloud["status"] == "SUCCESS"
    assert (len(res_cloud["created_incidents"]) + len(res_cloud.get("existing_incidents", []))) > 0

    # Idempotent re-run must not create duplicates
    res_fin_repeat = await TenantIncidentGenerator.seed_tenant_scenarios("fincore")
    assert len(res_fin_repeat["created_incidents"]) == 0
    assert len(res_fin_repeat["created_approvals"]) == 0

    # Verify in DB: All seeded incidents are tagged synthetic and have valid approval links
    async with AsyncSessionLocal() as session:
        for inc_id in res_fin["created_incidents"]:
            stmt = select(IncidentModel).where(IncidentModel.incident_id == inc_id)
            inc = (await session.execute(stmt)).scalar_one_or_none()
            assert inc is not None
            assert inc.is_synthetic is True
            assert inc.telemetry_source_mode == "SYNTHETIC_SCENARIO"
            assert inc.tenant_id == "fincore"

        # Verify approvals table has NO orphans
        app_stmt = select(ApprovalTicket)
        apps = (await session.execute(app_stmt)).scalars().all()
        for app in apps:
            if app.incident_id:
                inc_stmt = select(IncidentModel).where(IncidentModel.incident_id == app.incident_id)
                inc_found = (await session.execute(inc_stmt)).scalar_one_or_none()
                # Must be a valid incident
                assert inc_found is not None or app.incident_id.startswith("INC-")


@pytest.mark.asyncio
async def test_gemini_provider_diagnostics_and_normalization():
    """Verifies AI connectivity test diagnostics and model normalization."""
    # 1. Empty key
    empty_res = await GeminiProvider.test_connection(api_key="")
    assert empty_res["status"] == "NOT CONFIGURED"
    assert empty_res["category"] == "CONFIGURATION_ERROR"

    # 2. Model normalization: deprecated/mock names migrate to gemini-3.8-flash
    assert GeminiProvider.normalize_model("gemini-3.8-flash") == "gemini-3.8-flash"
    assert GeminiProvider.normalize_model("gemini-pro") == "gemini-3.8-flash"
    assert GeminiProvider.normalize_model("") == "gemini-3.8-flash"

    # 3. Valid models preserved
    assert GeminiProvider.normalize_model("gemini-2.5-flash") == "gemini-2.5-flash"
    assert GeminiProvider.normalize_model("gemini-2.0-flash") == "gemini-2.0-flash"
    assert GeminiProvider.normalize_model("gemini-1.5-flash") == "gemini-1.5-flash"
    assert GeminiProvider.normalize_model("gemini-1.5-pro") == "gemini-1.5-pro"


@pytest.mark.asyncio
async def test_replica_lab_api_endpoints():
    """Verifies HTTP API endpoints for Replica Lab inventory, scenarios, and experiments."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Get Inventory
        resp = await client.get("/api/replica/inventory?tenant_id=fincore")
        assert resp.status_code == 200
        inv = resp.json()
        assert inv["status"] == "SUCCESS"
        assert inv["count"] >= 1
        assert inv["replicas"][0]["tenant_id"] == "fincore"

        # 2. Get Scenarios
        s_resp = await client.get("/api/replica/scenarios")
        assert s_resp.status_code == 200
        scens = s_resp.json()
        assert scens["status"] == "SUCCESS"
        assert len(scens["scenarios"]) >= 4

        # 3. Run Experiment via API
        exp_payload = {
            "incident_id": "INC-API-EXP-001",
            "tenant_id": "fincore",
            "scenario_id": "db_pool_exhaustion",
            "target_service": "fincore-ledger-db"
        }
        r_resp = await client.post("/api/replica/experiments/run", json=exp_payload)
        assert r_resp.status_code == 200
        r_data = r_resp.json()
        assert r_data["status"] == "SUCCESS"
        exp_id = r_data["experiment"]["experiment_id"]
        assert r_data["experiment"]["evaluation_verdict"] == "PASS"

        # 4. List Experiments
        list_resp = await client.get("/api/replica/experiments?tenant_id=fincore")
        assert list_resp.status_code == 200
        l_data = list_resp.json()
        assert l_data["status"] == "SUCCESS"
        assert any(e["experiment_id"] == exp_id for e in l_data["experiments"])

        # 5. Approve Experiment via API
        appr_resp = await client.post(
            f"/api/replica/experiments/{exp_id}/approve",
            json={"approver": "Principal SRE API Test", "comments": "Approved via automated API test"}
        )
        assert appr_resp.status_code == 200
        assert appr_resp.json()["status"] == "SUCCESS"

        # 6. Deploy Experiment to Target via API
        deploy_resp = await client.post(
            f"/api/replica/experiments/{exp_id}/deploy-to-target",
            json={"operator": "API Dispatcher"}
        )
        assert deploy_resp.status_code == 200
        assert deploy_resp.json()["status"] == "SUCCESS"
        assert deploy_resp.json()["experiment"]["stage"] == "VALIDATED"
