"""
AegisOps AI — System Consistency Diagnostic API (Part 39)
Automated Truth Auditor checking 9 subsystems:
1. Service Status Consistency
2. Telemetry Consistency
3. Incident Consistency
4. Approval Consistency
5. Recovery Consistency
6. Dependency Consistency
7. ML Consistency
8. Tenant Isolation
9. Timestamp Consistency
"""

from fastapi import APIRouter, Query, Header
from typing import Dict, Any, Optional

from backend.app.services.canonical_state import canonical_state_manager
from backend.app.monitoring.collector import collector
from backend.app.rca.dynamic_graph import dynamic_graph

router = APIRouter(prefix="/system", tags=["System Consistency"])


@router.get("/consistency")
async def get_system_consistency(
    tenant_id: Optional[str] = Query(None),
    x_tenant_id: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    GET /api/system/consistency
    Automated diagnostic endpoint that audits operational truth across the backend subsystems.
    Returns:
    {
        "status": "PASS" | "FAIL",
        "checks": {
            "service_status": "PASS",
            "telemetry": "PASS",
            "incidents": "PASS",
            "approvals": "PASS",
            "recovery": "PASS",
            "dependencies": "PASS",
            "ml": "PASS",
            "tenant_isolation": "PASS",
            "timestamps": "PASS"
        },
        "discrepancies": []
    }
    """
    t_id = tenant_id or x_tenant_id or "shopsphere"
    
    # Optional pipeline coordinator import
    incident_pipeline_inst = None
    try:
        from backend.app.analytics.incident_pipeline import incident_pipeline
        incident_pipeline_inst = incident_pipeline
    except Exception:
        pass

    report = canonical_state_manager.run_consistency_audit(
        tenant_id=t_id,
        collector_inst=collector,
        dynamic_graph_inst=dynamic_graph,
        incident_pipeline_inst=incident_pipeline_inst
    )

    return report
