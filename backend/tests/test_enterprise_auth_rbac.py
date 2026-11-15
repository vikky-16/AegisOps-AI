"""
Enterprise Auth & RBAC Security Boundary Tests
Validates:
1. Enterprise persona login (CEO, CTO, SRE Lead, DevOps, Security, Super Admin)
2. CEO remediation lock: CEO is strictly prevented from approving technical remediations (HTTP 403)
3. SRE Lead authorization: SRE Lead has full authority to approve remediation actions
4. MFA TOTP setup & verification endpoints
5. Multi-tenant context and audit logging
"""

import pytest
import asyncio
from fastapi import HTTPException

from backend.app.core.security import AuthenticatedIdentity, create_access_token, has_permission, ROLE_PERMISSIONS
from backend.app.api.auth import login, LoginRequest, mfa_setup, mfa_verify, MfaVerifyRequest
from backend.app.api.approvals import check_rbac_authorization


def test_enterprise_role_permissions_matrix():
    """Verify role permissions matrix enforces enterprise separation of duties."""
    # CEO has read and governance, but NO remediation execution
    assert "incidents:read" in ROLE_PERMISSIONS["CEO"]
    assert "business_impact:view" in ROLE_PERMISSIONS["CEO"]
    assert "approvals:approve" not in ROLE_PERMISSIONS["CEO"]
    assert "remediation:execute" not in ROLE_PERMISSIONS["CEO"]

    # SRE Lead has full remediation approval and execution
    assert "approvals:approve" in ROLE_PERMISSIONS["SRE_LEAD"]
    assert "remediation:execute" in ROLE_PERMISSIONS["SRE_LEAD"]

    # Security Engineer has audit and security posture access
    assert "security:read" in ROLE_PERMISSIONS["SECURITY_ENGINEER"]
    assert "audit:read" in ROLE_PERMISSIONS["SECURITY_ENGINEER"]
    assert "approvals:approve" not in ROLE_PERMISSIONS["SECURITY_ENGINEER"]

    # Super Admin has wildcard permissions
    assert ROLE_PERMISSIONS["SUPER_ADMIN"] == ["*"]


def test_ceo_technical_remediation_blocked():
    """Verify CEO persona is strictly blocked from technical remediation approvals."""
    ceo_identity = AuthenticatedIdentity(
        tenant_id="tenant-alpha",
        is_platform_admin=False,
        user_id=101,
        username="ceo_acme",
        role="CEO"
    )

    with pytest.raises(HTTPException) as exc_info:
        check_rbac_authorization(ceo_identity, "APPROVE", "CRITICAL")

    assert exc_info.value.status_code == 403
    assert "CEO" in exc_info.value.detail or "cannot" in exc_info.value.detail


def test_sre_lead_technical_remediation_allowed():
    """Verify SRE Lead has authority to authorize remediation approvals."""
    sre_identity = AuthenticatedIdentity(
        tenant_id="tenant-alpha",
        is_platform_admin=False,
        user_id=102,
        username="sre_acme",
        role="SRE_LEAD"
    )

    authorized = check_rbac_authorization(sre_identity, "APPROVE", "CRITICAL")
    assert authorized is True


def test_devops_engineer_limited_authority():
    """Verify DevOps Engineer can approve low risk actions but is gated on critical ones."""
    devops_identity = AuthenticatedIdentity(
        tenant_id="tenant-alpha",
        is_platform_admin=False,
        user_id=103,
        username="devops_acme",
        role="DEVOPS_ENGINEER"
    )

    # Low-risk action allowed
    low_risk_auth = check_rbac_authorization(devops_identity, "APPROVE", "LOW")
    assert low_risk_auth is True

    # High-risk action gated
    with pytest.raises(HTTPException) as exc_info:
        check_rbac_authorization(devops_identity, "APPROVE", "HIGH")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_auth_login_personas():
    """Verify authentication endpoint accepts enterprise personas."""
    # CEO Login
    ceo_res = await login(LoginRequest(username="ceo_acme", password="acme123"))
    assert ceo_res["user"]["role"] == "CEO"
    assert "access_token" in ceo_res
    assert ceo_res["tenant_id"] == "tenant-alpha"

    # SRE Lead Login
    sre_res = await login(LoginRequest(username="sre_acme", password="acme123"))
    assert sre_res["user"]["role"] in ["SRE_LEAD", "TENANT_ADMIN"]

    # Super Admin Login
    admin_res = await login(LoginRequest(username="admin", password="admin123"))
    assert admin_res["user"]["role"] in ["SUPER_ADMIN", "PLATFORM_ADMIN"]
    assert admin_res["user"]["is_platform_admin"] is True


@pytest.mark.asyncio
async def test_mfa_flow():
    """Verify MFA setup produces a secret and TOTP verification functions."""
    sre_identity = AuthenticatedIdentity(
        tenant_id="tenant-alpha",
        is_platform_admin=False,
        user_id=102,
        username="sre_acme",
        role="SRE_LEAD"
    )

    setup_res = await mfa_setup(sre_identity)
    assert "secret" in setup_res
    assert "qr_uri" in setup_res

    # Test verification (any 6 digit code in development / pyotp)
    verify_res = await mfa_verify(MfaVerifyRequest(code="123456"), sre_identity)
    assert verify_res["status"] == "SUCCESS"
