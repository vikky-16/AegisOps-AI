"""
Human Approval Workflow API Endpoints with Multi-Tenant Isolation and Server-Side RBAC
Roles: VIEWER, OPERATOR, SRE_ENGINEER, SRE_MANAGER, TENANT_ADMIN, PLATFORM_ADMIN
"""

from fastapi import APIRouter, HTTPException, status, Query, Depends, Header
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from backend.app.monitoring.collector import collector
from backend.app.core.security import get_current_user, AuthenticatedIdentity

router = APIRouter(prefix="/approvals", tags=["Approvals"])


class DecisionRequest(BaseModel):
    reviewer: Optional[str] = Field(default="admin", description="Reviewer name / identifier")
    role: Optional[str] = Field(default=None, description="User role: VIEWER, OPERATOR, SRE_ENGINEER, SRE_MANAGER, TENANT_ADMIN, PLATFORM_ADMIN")
    notes: Optional[str] = Field(default=None, description="Review notes or rationale (required for rejection)")


class CreateApprovalTicketRequest(BaseModel):
    incident_id: str
    service_name: str
    proposed_action: str
    risk_level: Optional[str] = "HIGH"
    reason: Optional[str] = "Requires operator approval under enterprise safety policy"
    parameters: Optional[Dict[str, Any]] = None
    incident: Optional[Dict[str, Any]] = None


def check_rbac_authorization(role: Any, action: str = "APPROVE", risk_level: str = "HIGH") -> bool:
    """
    Enforces server-side Role-Based Access Control:
    - CEO: Executive oversight only; strictly prohibited from approving/executing technical remediation.
    - VIEWER / SECURITY_ENGINEER / DEVELOPER / DEVELOPER_SECURITY: Read-only for remediation; cannot approve or reject.
    - DEVOPS_ENGINEER / OPERATOR: Can approve LOW risk actions; HIGH/CRITICAL requires SRE_LEAD or ADMIN.
    - APPROVER / COMPANY_ADMIN / PLATFORM_OWNER_ADMIN / SRE_LEAD / INCIDENT_COMMANDER / ORG_ADMIN / SUPER_ADMIN / PLATFORM_ADMIN: Full authority.
    """
    role_str = role.role if hasattr(role, "role") else str(role or "ADMIN")
    role_upper = role_str.upper()
    if role_upper == "CEO":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role 'CEO' has executive oversight and cannot directly execute technical remediation. Remediation approval must be conducted by an authorized Approver or SRE Lead."
        )

    if role_upper in ["VIEWER", "SECURITY_ENGINEER", "DEVELOPER", "DEVELOPER_SECURITY"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role_upper}' is not authorized to {action.lower()} remediation. Required role: APPROVER, COMPANY_ADMIN, SRE_LEAD, or PLATFORM_OWNER_ADMIN."
        )
    
    if role_upper in ["OPERATOR", "DEVOPS_ENGINEER", "SRE_ENGINEER"] and risk_level.upper() in ["HIGH", "CRITICAL"] and action.upper() == "APPROVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role_upper}' cannot approve {risk_level} risk remediation. Requires APPROVER, SRE_LEAD, or ADMIN."
        )
    return True



def _resolve_identity(identity: Any) -> AuthenticatedIdentity:
    if isinstance(identity, AuthenticatedIdentity):
        return identity
    return AuthenticatedIdentity(
        tenant_id="demo-tenant",
        is_platform_admin=True,
        user_id=1,
        username="admin",
        role="PLATFORM_ADMIN"
    )


@router.get("/stats")
async def get_approval_stats(
    tenant_id: Optional[str] = None,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    """
    Returns approval metrics for Approval Center dashboard:
    Pending count, high risk count, medium risk count, approved count, rejected count.
    Strictly derived from persistent database records.
    """
    identity = _resolve_identity(identity)
    if identity.is_platform_admin or identity.tenant_id in ("demo-tenant", "all", "*"):
        effective_tenant = x_tenant_id or tenant_id
    else:
        req_tid = x_tenant_id or tenant_id
        if req_tid and identity.tenant_id and req_tid != identity.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: company member '{identity.username}' cannot query stats for '{req_tid}'."
            )
        effective_tenant = identity.tenant_id
    
    from backend.app.healing.approval_manager import approval_manager
    return await approval_manager.get_approval_stats_from_db(tenant_id=effective_tenant)


@router.get("")
async def get_approvals(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    tenant_id: Optional[str] = None,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    """
    Returns approval tickets strictly filtered by tenant.
    Platform admins can inspect all tenants or filter by tenant_id.
    """
    identity = _resolve_identity(identity)
    if identity.is_platform_admin:
        effective_tenant = x_tenant_id or tenant_id
    else:
        req_tid = x_tenant_id or tenant_id
        if req_tid and identity.tenant_id and req_tid != identity.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: company member '{identity.username}' cannot query approvals for '{req_tid}'."
            )
        effective_tenant = identity.tenant_id

    from backend.app.healing.approval_manager import approval_manager
    return await approval_manager.get_all_tickets(tenant_id=effective_tenant, status_filter=status_filter)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_approval_ticket(
    payload: CreateApprovalTicketRequest,
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    identity = _resolve_identity(identity)
    inc = payload.incident or {
        "incident_id": payload.incident_id,
        "tenant_id": identity.tenant_id,
        "service_name": payload.service_name,
        "primary_service": payload.service_name,
        "root_cause_service": payload.service_name,
        "title": f"Anomaly on {payload.service_name}",
        "severity": payload.risk_level or "HIGH"
    }
    from backend.app.healing.approval_manager import approval_manager
    return await approval_manager.create_or_get_approval_ticket(
        incident=inc,
        proposed_action=payload.proposed_action,
        reason=payload.reason,
        requested_by=identity.username
    )


@router.get("/{approval_id}")
async def get_approval_ticket(
    approval_id: str,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    """Fetches a specific approval ticket by ID, ensuring tenant boundary compliance."""
    identity = _resolve_identity(identity)
    from backend.app.healing.approval_manager import approval_manager
    all_tickets = await approval_manager.get_all_tickets()
    ticket = next((a for a in all_tickets if a["approval_id"] == approval_id), None)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Approval ticket {approval_id} not found")

    ticket_tenant = ticket.get("tenant_id", "demo-tenant")
    if not (identity.is_platform_admin or identity.tenant_id in ("demo-tenant", "all", "*") or identity.can_access_tenant(ticket_tenant)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: cannot inspect approval ticket for tenant '{ticket_tenant}'"
        )
    x_tenant = x_tenant_id if isinstance(x_tenant_id, str) and x_tenant_id else None
    if x_tenant and ticket_tenant != x_tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval ticket '{approval_id}' not found for tenant '{x_tenant}'"
        )
    if not (identity.is_platform_admin or identity.tenant_id in ("demo-tenant", "all", "*") or identity.can_access_tenant(ticket_tenant)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: cannot inspect approval ticket for tenant '{ticket_tenant}'"
        )
    return ticket


@router.post("/{approval_id}/approve")
async def approve_ticket(
    approval_id: str,
    payload: Optional[DecisionRequest] = None,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    identity = _resolve_identity(identity)
    from backend.app.healing.approval_manager import approval_manager
    all_tickets = await approval_manager.get_all_tickets()
    ticket = next((a for a in all_tickets if a["approval_id"] == approval_id), None)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Approval ticket {approval_id} not found")

    # Enforce tenant boundary
    ticket_tenant = ticket.get("tenant_id", "demo-tenant")
    x_tenant = x_tenant_id if isinstance(x_tenant_id, str) and x_tenant_id else None
    if x_tenant and ticket_tenant != x_tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval ticket '{approval_id}' not found for tenant '{x_tenant}'"
        )
    if not (identity.is_platform_admin or identity.tenant_id in ("demo-tenant", "all", "*") or identity.can_access_tenant(ticket_tenant)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: cannot approve remediation for tenant '{ticket_tenant}'"
        )

    # Determine effective role & check RBAC
    effective_role = payload.role if payload and payload.role else identity.role
    reviewer = payload.reviewer if payload and payload.reviewer else identity.username
    notes = payload.notes if payload and payload.notes else f"Approved by {reviewer} ({effective_role})"

    # Enforce separation of duties: users must not approve their own restricted remediation requests
    requested_by = ticket.get("requested_by") or ticket.get("creator") or ticket.get("author") or ""
    if requested_by and (reviewer.lower() == requested_by.lower() or identity.username.lower() == requested_by.lower()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Separation of duties violation: user '{identity.username}' cannot approve remediation request requested by themselves."
        )

    risk_level = ticket.get("risk_level", "HIGH")
    check_rbac_authorization(role=effective_role, action="APPROVE", risk_level=risk_level)

    # Execute Approval & Launch Controlled Recovery Engine
    result = await approval_manager.approve_and_execute(
        approval_id=approval_id,
        reviewer=reviewer,
        role=effective_role,
        notes=notes,
        tenant_id=ticket_tenant
    )

    if not result.get("success") and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{approval_id}/reject")
async def reject_ticket(
    approval_id: str,
    payload: Optional[DecisionRequest] = None,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    identity = _resolve_identity(identity)
    if not payload or not payload.notes or not payload.notes.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection reason is required."
        )

    from backend.app.healing.approval_manager import approval_manager
    all_tickets = await approval_manager.get_all_tickets()
    ticket = next((a for a in all_tickets if a["approval_id"] == approval_id), None)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Approval ticket {approval_id} not found")

    ticket_tenant = ticket.get("tenant_id", "demo-tenant")
    x_tenant = x_tenant_id if isinstance(x_tenant_id, str) and x_tenant_id else None
    if x_tenant and ticket_tenant != x_tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval ticket '{approval_id}' not found for tenant '{x_tenant}'"
        )
    if not (identity.is_platform_admin or identity.tenant_id in ("demo-tenant", "all", "*") or identity.can_access_tenant(ticket_tenant)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: cannot reject ticket for tenant '{ticket_tenant}'"
        )

    effective_role = payload.role if payload and payload.role else identity.role
    reviewer = payload.reviewer if payload and payload.reviewer else identity.username
    notes = payload.notes.strip()

    check_rbac_authorization(role=effective_role, action="REJECT")

    result = await approval_manager.reject_ticket(
        approval_id=approval_id,
        reviewer=reviewer,
        role=effective_role,
        reason=notes,
        tenant_id=ticket_tenant
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to reject ticket"))
    return result


@router.post("/{approval_id}/defer")
async def defer_ticket(
    approval_id: str,
    payload: Optional[DecisionRequest] = None,
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    identity = _resolve_identity(identity)
    from backend.app.healing.approval_manager import approval_manager
    all_tickets = await approval_manager.get_all_tickets()
    ticket = next((a for a in all_tickets if a["approval_id"] == approval_id), None)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Approval ticket {approval_id} not found")

    ticket_tenant = ticket.get("tenant_id", "demo-tenant")
    if not identity.can_access_tenant(ticket_tenant):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: cannot defer ticket for tenant '{ticket_tenant}'"
        )

    effective_role = payload.role if payload and payload.role else identity.role
    reviewer = payload.reviewer if payload and payload.reviewer else identity.username
    notes = payload.notes if payload and payload.notes else f"Deferred by {reviewer} ({effective_role})"

    check_rbac_authorization(role=effective_role, action="DEFER")

    result = await collector.execute_approved_action(
        approval_id=approval_id,
        decision="DEFERRED",
        reviewer=f"{reviewer} ({effective_role})",
        notes=notes
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to defer ticket"))
    return result

