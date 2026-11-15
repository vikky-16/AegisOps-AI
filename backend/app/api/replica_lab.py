"""
AegisOps AI - Digital Replica Testing Lab API Router
Provides endpoints for digital twin inventory, controlled fault injection,
full 17-step replica experiments, and safe target deployment.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from backend.app.replica.remediation_lab import RemediationLabEngine
from backend.app.replica.adapters import SyntheticReplicaAdapter, get_replica_adapter

router = APIRouter(prefix="/replica", tags=["Replica Lab"])


class CreateReplicaRequest(BaseModel):
    tenant_id: str = "demo-tenant"
    target_service: str = "database-service"
    environment_type: str = "SYNTHETIC"


class FaultInjectRequest(BaseModel):
    scenario_id: str = "db_pool_exhaustion"
    parameters: Optional[Dict[str, Any]] = None


class RunExperimentRequest(BaseModel):
    incident_id: str
    tenant_id: str = "demo-tenant"
    replica_id: Optional[str] = None
    scenario_id: Optional[str] = "db_pool_exhaustion"
    target_service: Optional[str] = "database-service"
    candidates: Optional[List[Dict[str, Any]]] = None


class ApproveExperimentRequest(BaseModel):
    approver: str = "Principal SRE"
    comments: Optional[str] = None


class DeployTargetRequest(BaseModel):
    operator: str = "Automated SRE Dispatcher"


@router.get("/inventory")
async def get_replica_inventory(
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID")
) -> Dict[str, Any]:
    """Lists all digital twin replica test environments, optionally filtered by tenant."""
    replicas = await RemediationLabEngine.list_replicas(tenant_id=tenant_id)
    return {
        "status": "SUCCESS",
        "count": len(replicas),
        "replicas": replicas
    }


@router.post("/create")
async def create_replica(payload: CreateReplicaRequest) -> Dict[str, Any]:
    """Creates or allocates an isolated digital twin replica for the tenant and service."""
    rep = await RemediationLabEngine.get_or_create_replica(
        tenant_id=payload.tenant_id,
        target_service=payload.target_service,
        environment_type=payload.environment_type
    )
    return {
        "status": "SUCCESS",
        "message": f"Allocated isolated replica {rep.replica_id}",
        "replica": rep.to_dict()
    }


@router.get("/scenarios")
async def get_available_scenarios() -> Dict[str, Any]:
    """Returns available reproducible fault injection scenarios with expected baselines."""
    scenarios = []
    for s_id, s_data in SyntheticReplicaAdapter.SCENARIOS.items():
        scenarios.append({
            "scenario_id": s_id,
            "name": s_data["name"],
            "description": s_data["description"],
            "baseline": s_data["baseline"],
            "supported_actions": list(s_data.get("remediation_effects", {}).keys())
        })
    return {
        "status": "SUCCESS",
        "scenarios": scenarios
    }


@router.post("/{replica_id}/fault-inject")
async def inject_fault_to_replica(replica_id: str, payload: FaultInjectRequest) -> Dict[str, Any]:
    """Injects a controlled fault scenario inside the isolated replica boundary only."""
    adapter = get_replica_adapter(replica_id=replica_id, tenant_id="demo-tenant")
    res = await adapter.inject_fault(payload.scenario_id, payload.parameters)
    return {
        "status": "SUCCESS",
        "injection_result": res
    }


@router.post("/{replica_id}/reset")
async def reset_replica(replica_id: str) -> Dict[str, Any]:
    """Resets an isolated replica to its clean, healthy baseline state."""
    adapter = get_replica_adapter(replica_id=replica_id, tenant_id="demo-tenant")
    res = await adapter.reset()
    return {
        "status": "SUCCESS",
        "reset_result": res
    }


@router.post("/experiments/run")
async def run_experiment(payload: RunExperimentRequest) -> Dict[str, Any]:
    """
    Executes the full 17-step scientific experiment:
    baseline capture -> fault reproduction -> candidate remediation testing -> quantitative evaluation.
    """
    res = await RemediationLabEngine.run_experiment(
        incident_id=payload.incident_id,
        tenant_id=payload.tenant_id,
        replica_id=payload.replica_id,
        scenario_id=payload.scenario_id,
        target_service=payload.target_service,
        custom_candidates=payload.candidates
    )
    return {
        "status": "SUCCESS",
        "experiment": res
    }


@router.get("/experiments")
async def list_experiments(
    tenant_id: Optional[str] = Query(None),
    incident_id: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Lists persistent experiment history with quantitative evaluation scores."""
    experiments = await RemediationLabEngine.list_experiments(
        tenant_id=tenant_id,
        incident_id=incident_id
    )
    return {
        "status": "SUCCESS",
        "count": len(experiments),
        "experiments": experiments
    }


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str) -> Dict[str, Any]:
    """Retrieves full details, before/after metrics, logs, and evidence for an experiment."""
    exp = await RemediationLabEngine.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return {
        "status": "SUCCESS",
        "experiment": exp
    }


@router.post("/experiments/{experiment_id}/approve")
async def approve_experiment(experiment_id: str, payload: ApproveExperimentRequest) -> Dict[str, Any]:
    """Approves an evaluated candidate solution for production target deployment."""
    res = await RemediationLabEngine.approve_experiment(
        experiment_id=experiment_id,
        approver=payload.approver,
        comments=payload.comments
    )
    if res.get("status") == "ERROR":
        raise HTTPException(status_code=404, detail=res.get("message"))
    return res


@router.post("/experiments/{experiment_id}/deploy-to-target")
async def deploy_experiment_to_target(experiment_id: str, payload: DeployTargetRequest) -> Dict[str, Any]:
    """Executes permitted candidate remediation against live service target with post-validation."""
    res = await RemediationLabEngine.deploy_to_target(
        experiment_id=experiment_id,
        operator=payload.operator
    )
    if res.get("status") == "BLOCKED":
        raise HTTPException(status_code=400, detail=res.get("message"))
    elif res.get("status") == "ERROR":
        raise HTTPException(status_code=404, detail=res.get("message"))
    return res

