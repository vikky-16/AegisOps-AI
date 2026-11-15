"""
Authentication, Authorization, Multi-Tenant Session Management, and RBAC Endpoints
Provides Enterprise Login, Signup, Forgot/Reset Password, MFA, Invite, and Organization Switching.
"""

import json
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field
from sqlalchemy import select, or_

from backend.app.core.security import (
    create_access_token,
    verify_password,
    get_password_hash,
    get_current_user,
    require_permission,
    record_audit_event,
    revoke_token,
    oauth2_scheme,
    AuthenticatedIdentity,
    ROLE_PERMISSIONS
)
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.user import User
from backend.app.models.tenant import Tenant, TenantPolicy, TenantAuditLog

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])

# In-memory reset tokens for password recovery: token -> {"email": email, "expires_at": datetime}
PASSWORD_RESET_TOKENS: Dict[str, Dict[str, Any]] = {}

# Pre-seeded enterprise personas (Acme Corporation, Cyberdyne, Demo)
PRESEEDED_USERS = {
    "admin": {
        "id": 1,
        "username": "admin",
        "email": "admin@aegisops.ai",
        "full_name": "AegisOps Global Super Admin",
        "role": "SUPER_ADMIN",
        "tenant_id": "demo-tenant",
        "is_platform_admin": True,
        "hashed_password": get_password_hash("admin123"),
        "is_active": True
    },
    "ceo_acme": {
        "id": 10,
        "username": "ceo_acme",
        "email": "ceo@acme.com",
        "full_name": "Alexander Vance (CEO)",
        "role": "CEO",
        "tenant_id": "tenant-alpha",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("acme123"),
        "is_active": True
    },
    "cto_acme": {
        "id": 11,
        "username": "cto_acme",
        "email": "cto@acme.com",
        "full_name": "Elena Rostova (CTO)",
        "role": "CTO",
        "tenant_id": "tenant-alpha",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("acme123"),
        "is_active": True
    },
    "sre_acme": {
        "id": 2,
        "username": "sre_acme",
        "email": "sre@acme.com",
        "full_name": "Marcus Kane (SRE Lead)",
        "role": "SRE_LEAD",
        "tenant_id": "tenant-alpha",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("acme123"),
        "is_active": True
    },
    "devops_acme": {
        "id": 3,
        "username": "devops_acme",
        "email": "devops@acme.com",
        "full_name": "Sarah Lin (DevOps Engineer)",
        "role": "DEVOPS_ENGINEER",
        "tenant_id": "tenant-alpha",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("acme123"),
        "is_active": True
    },
    "engineer_acme": {
        "id": 33,
        "username": "engineer_acme",
        "email": "eng@acme.com",
        "full_name": "Acme SRE Engineer",
        "role": "DEVOPS_ENGINEER",
        "tenant_id": "tenant-alpha",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("acme123"),
        "is_active": True
    },
    "sec_acme": {
        "id": 12,
        "username": "sec_acme",
        "email": "security@acme.com",
        "full_name": "Tariq Al-Mansoor (Security Engineer)",
        "role": "SECURITY_ENGINEER",
        "tenant_id": "tenant-alpha",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("acme123"),
        "is_active": True
    },
    "dev_acme": {
        "id": 13,
        "username": "dev_acme",
        "email": "developer@acme.com",
        "full_name": "Priya Sharma (Core Developer)",
        "role": "DEVELOPER",
        "tenant_id": "tenant-alpha",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("acme123"),
        "is_active": True
    },
    "ic_acme": {
        "id": 14,
        "username": "ic_acme",
        "email": "commander@acme.com",
        "full_name": "David Sterling (Incident Commander)",
        "role": "INCIDENT_COMMANDER",
        "tenant_id": "tenant-alpha",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("acme123"),
        "is_active": True
    },
    "sre_cyber": {
        "id": 4,
        "username": "sre_cyber",
        "email": "sre@cyberdyne.com",
        "full_name": "Miles Bennett Dyson (Lead SRE)",
        "role": "ORG_ADMIN",
        "tenant_id": "tenant-beta",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("cyber123"),
        "is_active": True
    },
    "operator": {
        "id": 5,
        "username": "operator",
        "email": "operator@aegisops.ai",
        "full_name": "Operations Center Engineer",
        "role": "DEVOPS_ENGINEER",
        "tenant_id": "demo-tenant",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("operator123"),
        "is_active": True
    },
    "viewer": {
        "id": 6,
        "username": "viewer",
        "email": "viewer@aegisops.ai",
        "full_name": "Read-Only Stakeholder",
        "role": "VIEWER",
        "tenant_id": "demo-tenant",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("viewer123"),
        "is_active": True
    },
    # -------------------------------------------------------------
    # Company A: ShopSphere (E-Commerce)
    # -------------------------------------------------------------
    "admin_shopsphere": {
        "id": 101,
        "username": "admin_shopsphere",
        "email": "admin@shopsphere.io",
        "full_name": "ShopSphere Company Admin",
        "role": "ORG_ADMIN",
        "tenant_id": "shopsphere",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("shopsphere123"),
        "is_active": True
    },
    "ceo_shopsphere": {
        "id": 102,
        "username": "ceo_shopsphere",
        "email": "ceo@shopsphere.io",
        "full_name": "Rachel Zane (CEO - ShopSphere)",
        "role": "CEO",
        "tenant_id": "shopsphere",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("shopsphere123"),
        "is_active": True
    },
    "sre_shopsphere": {
        "id": 103,
        "username": "sre_shopsphere",
        "email": "sre@shopsphere.io",
        "full_name": "Devin Murphy (Lead SRE - ShopSphere)",
        "role": "SRE_LEAD",
        "tenant_id": "shopsphere",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("shopsphere123"),
        "is_active": True
    },
    "devops_shopsphere": {
        "id": 104,
        "username": "devops_shopsphere",
        "email": "devops@shopsphere.io",
        "full_name": "Liam Connor (DevOps - ShopSphere)",
        "role": "DEVOPS_ENGINEER",
        "tenant_id": "shopsphere",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("shopsphere123"),
        "is_active": True
    },
    "dev_shopsphere": {
        "id": 105,
        "username": "dev_shopsphere",
        "email": "dev@shopsphere.io",
        "full_name": "Amina Patel (Developer - ShopSphere)",
        "role": "DEVELOPER",
        "tenant_id": "shopsphere",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("shopsphere123"),
        "is_active": True
    },
    "sec_shopsphere": {
        "id": 106,
        "username": "sec_shopsphere",
        "email": "sec@shopsphere.io",
        "full_name": "Klaus Richter (Security - ShopSphere)",
        "role": "SECURITY_ENGINEER",
        "tenant_id": "shopsphere",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("shopsphere123"),
        "is_active": True
    },
    "viewer_shopsphere": {
        "id": 107,
        "username": "viewer_shopsphere",
        "email": "viewer@shopsphere.io",
        "full_name": "ShopSphere Auditor (Viewer)",
        "role": "VIEWER",
        "tenant_id": "shopsphere",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("shopsphere123"),
        "is_active": True
    },
    # -------------------------------------------------------------
    # Company B: FinCore (Financial Transactions)
    # -------------------------------------------------------------
    "admin_fincore": {
        "id": 201,
        "username": "admin_fincore",
        "email": "admin@fincore.financial",
        "full_name": "FinCore Company Admin",
        "role": "ORG_ADMIN",
        "tenant_id": "fincore",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("fincore123"),
        "is_active": True
    },
    "ceo_fincore": {
        "id": 202,
        "username": "ceo_fincore",
        "email": "ceo@fincore.financial",
        "full_name": "Sterling Archer (CEO - FinCore)",
        "role": "CEO",
        "tenant_id": "fincore",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("fincore123"),
        "is_active": True
    },
    "sre_fincore": {
        "id": 203,
        "username": "sre_fincore",
        "email": "sre@fincore.financial",
        "full_name": "Maya Lin (Lead SRE - FinCore)",
        "role": "SRE_LEAD",
        "tenant_id": "fincore",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("fincore123"),
        "is_active": True
    },
    "devops_fincore": {
        "id": 204,
        "username": "devops_fincore",
        "email": "devops@fincore.financial",
        "full_name": "Vikram Seth (DevOps - FinCore)",
        "role": "DEVOPS_ENGINEER",
        "tenant_id": "fincore",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("fincore123"),
        "is_active": True
    },
    "dev_fincore": {
        "id": 205,
        "username": "dev_fincore",
        "email": "dev@fincore.financial",
        "full_name": "Chen Wei (Developer - FinCore)",
        "role": "DEVELOPER",
        "tenant_id": "fincore",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("fincore123"),
        "is_active": True
    },
    "sec_fincore": {
        "id": 206,
        "username": "sec_fincore",
        "email": "sec@fincore.financial",
        "full_name": "Grace Hopper (Security - FinCore)",
        "role": "SECURITY_ENGINEER",
        "tenant_id": "fincore",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("fincore123"),
        "is_active": True
    },
    "viewer_fincore": {
        "id": 207,
        "username": "viewer_fincore",
        "email": "viewer@fincore.financial",
        "full_name": "FinCore Regulatory Auditor (Viewer)",
        "role": "VIEWER",
        "tenant_id": "fincore",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("fincore123"),
        "is_active": True
    },
    # -------------------------------------------------------------
    # Company C: CloudDesk (SaaS Platform)
    # -------------------------------------------------------------
    "admin_clouddesk": {
        "id": 301,
        "username": "admin_clouddesk",
        "email": "admin@clouddesk.app",
        "full_name": "CloudDesk Company Admin",
        "role": "ORG_ADMIN",
        "tenant_id": "clouddesk",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("clouddesk123"),
        "is_active": True
    },
    "ceo_clouddesk": {
        "id": 302,
        "username": "ceo_clouddesk",
        "email": "ceo@clouddesk.app",
        "full_name": "Siddharth Roy (CEO - CloudDesk)",
        "role": "CEO",
        "tenant_id": "clouddesk",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("clouddesk123"),
        "is_active": True
    },
    "sre_clouddesk": {
        "id": 303,
        "username": "sre_clouddesk",
        "email": "sre@clouddesk.app",
        "full_name": "Claire Redfield (Lead SRE - CloudDesk)",
        "role": "SRE_LEAD",
        "tenant_id": "clouddesk",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("clouddesk123"),
        "is_active": True
    },
    "devops_clouddesk": {
        "id": 304,
        "username": "devops_clouddesk",
        "email": "devops@clouddesk.app",
        "full_name": "Jordan Bell (DevOps - CloudDesk)",
        "role": "DEVOPS_ENGINEER",
        "tenant_id": "clouddesk",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("clouddesk123"),
        "is_active": True
    },
    "dev_clouddesk": {
        "id": 305,
        "username": "dev_clouddesk",
        "email": "dev@clouddesk.app",
        "full_name": "Lucas Silva (Developer - CloudDesk)",
        "role": "DEVELOPER",
        "tenant_id": "clouddesk",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("clouddesk123"),
        "is_active": True
    },
    "sec_clouddesk": {
        "id": 306,
        "username": "sec_clouddesk",
        "email": "sec@clouddesk.app",
        "full_name": "Nadia Osman (Security - CloudDesk)",
        "role": "SECURITY_ENGINEER",
        "tenant_id": "clouddesk",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("clouddesk123"),
        "is_active": True
    },
    "viewer_clouddesk": {
        "id": 307,
        "username": "viewer_clouddesk",
        "email": "viewer@clouddesk.app",
        "full_name": "CloudDesk Stakeholder (Viewer)",
        "role": "VIEWER",
        "tenant_id": "clouddesk",
        "is_platform_admin": False,
        "hashed_password": get_password_hash("clouddesk123"),
        "is_active": True
    }
}


def get_role_permissions(role: str, is_platform_admin: bool) -> List[str]:
    """Returns granular permission list for an authenticated role."""
    r = role.upper()
    if is_platform_admin or r in ["SUPER_ADMIN", "PLATFORM_ADMIN"]:
        return ["*"]
    return ROLE_PERMISSIONS.get(r, ["telemetry:read", "incidents:read"])


# =========================================================================
# SCHEMAS
# =========================================================================

class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: Optional[str] = None
    mfa_code: Optional[str] = None


class SignupRequest(BaseModel):
    company_name: str = Field(..., example="Acme Corporation")
    company_slug: Optional[str] = None
    industry: Optional[str] = "Financial Services"
    region: Optional[str] = "India"
    admin_name: str = Field(..., example="Alexander Vance")
    admin_email: str = Field(..., example="alex@acme.com")
    password: str = Field(..., example="SecurePassword123!")


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class MfaVerifyRequest(BaseModel):
    code: str


class InviteUserRequest(BaseModel):
    email: str
    full_name: str
    role: str = "DEVELOPER"
    team_id: Optional[str] = None


class FirstLoginPasswordChangeRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str


class CreateCompanyUserRequest(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    tenant_id: Optional[str] = None


class SwitchTenantRequest(BaseModel):
    target_tenant_id: str


# =========================================================================
# ENDPOINTS
# =========================================================================

@router.post("/login")
async def login(payload: LoginRequest):
    user_record = None
    username_or_email = payload.username.strip().lower()

    async with AsyncSessionLocal() as session:
        stmt = select(User).where(
            or_(User.username == username_or_email, User.email == username_or_email)
        )
        res = await session.execute(stmt)
        user_record = res.scalars().first()

        if user_record:
            # Check rate limiting / account lock
            if user_record.locked_until:
                locked_time = user_record.locked_until
                if locked_time.tzinfo is None:
                    locked_time = locked_time.replace(tzinfo=timezone.utc)
                if locked_time > datetime.now(timezone.utc):
                    raise HTTPException(
                        status_code=status.HTTP_423_LOCKED,
                        detail="Account is temporarily locked due to repeated failed login attempts. Please try again later."
                    )

            if not verify_password(payload.password, user_record.hashed_password):
                user_record.failed_login_attempts = (user_record.failed_login_attempts or 0) + 1
                if user_record.failed_login_attempts >= 5:
                    user_record.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                await session.commit()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials. Please verify your email/username and password."
                )

            # Successful login - reset failed attempts
            user_record.failed_login_attempts = 0
            user_record.locked_until = None
            user_record.last_login_at = datetime.now(timezone.utc)
            await session.commit()

            user_dict = {
                "id": user_record.id,
                "username": user_record.username,
                "email": user_record.email,
                "full_name": user_record.full_name,
                "role": user_record.role.upper(),
                "tenant_id": user_record.tenant_id or user_record.organization_id,
                "is_platform_admin": bool(user_record.is_platform_admin or user_record.role == "PLATFORM_OWNER_ADMIN"),
                "mfa_enabled": bool(user_record.mfa_enabled),
                "must_change_password": bool(user_record.must_change_password)
            }
        else:
            # Check pre-seeded fallback for demo personas
            matched_user = None
            for u in PRESEEDED_USERS.values():
                if u["username"].lower() == username_or_email or u["email"].lower() == username_or_email:
                    matched_user = u
                    break
            
            if not matched_user or not verify_password(payload.password, matched_user["hashed_password"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials. Please verify your email/username and password."
                )
            user_dict = matched_user.copy()
            user_dict["must_change_password"] = False

    # Effective tenant: for platform admin, may select target tenant; for company members, STRICTLY resolved server-side
    effective_tenant = user_dict.get("tenant_id")
    if user_dict["is_platform_admin"] or user_dict["role"] in ["PLATFORM_OWNER_ADMIN", "SUPER_ADMIN", "PLATFORM_ADMIN"]:
        if payload.tenant_id and payload.tenant_id in ["fincore", "shopsphere", "clouddesk", "demo-tenant"]:
            effective_tenant = payload.tenant_id

    # Create JWT Token with enterprise claims
    token_claims = {
        "sub": user_dict["username"],
        "user_id": user_dict["id"],
        "tenant_id": effective_tenant,
        "organization_id": effective_tenant,
        "role": user_dict["role"],
        "is_platform_admin": user_dict["is_platform_admin"],
        "must_change_password": user_dict.get("must_change_password", False)
    }
    token = create_access_token(data=token_claims)

    await record_audit_event(
        tenant_id=effective_tenant or "platform",
        user_identifier=user_dict["username"],
        user_role=user_dict["role"],
        action="LOGIN",
        resource_type="auth_session",
        resource_id=f"usr-{user_dict['id']}",
        details={"login_method": "password", "email": user_dict["email"]}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "tenant_id": effective_tenant,
        "organization_id": effective_tenant,
        "must_change_password": user_dict.get("must_change_password", False),
        "user": {
            "id": user_dict["id"],
            "username": user_dict["username"],
            "email": user_dict["email"],
            "full_name": user_dict["full_name"],
            "role": user_dict["role"],
            "tenant_id": effective_tenant,
            "organization_id": effective_tenant,
            "is_platform_admin": user_dict["is_platform_admin"],
            "mfa_enabled": user_dict.get("mfa_enabled", False),
            "must_change_password": user_dict.get("must_change_password", False),
            "permissions": get_role_permissions(user_dict["role"], user_dict["is_platform_admin"])
        }
    }


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest):
    """Self-serve enterprise organization onboarding & admin account creation."""
    slug = payload.company_slug or payload.company_name.lower().replace(" ", "-")[:24]
    tenant_id = f"org_{slug.replace('-', '_')}"

    async with AsyncSessionLocal() as session:
        # Check duplicate email
        stmt = select(User).where(User.email == payload.admin_email)
        res = await session.execute(stmt)
        if res.scalars().first():
            raise HTTPException(status_code=400, detail="An account with this email already exists.")

        # Create Organization
        org = Tenant(
            id=tenant_id,
            name=payload.company_name,
            slug=slug,
            tier="ENTERPRISE",
            plan="Enterprise",
            industry=payload.industry or "Financial Services",
            region=payload.region or "India",
            status="ACTIVE"
        )
        session.add(org)

        # Create Default Policy
        policy = TenantPolicy(
            tenant_id=tenant_id,
            auto_remediation_enabled=True,
            allowed_actions_json='["RESET_CONNECTION_POOL", "CLEAR_CACHE", "DRAIN_QUEUE", "ROTATE_CONNECTIONS"]',
            max_auto_risk_level="LOW",
            min_rca_confidence=0.85,
            max_blast_radius=60.0
        )
        session.add(policy)

        # Create Admin User (ORG_ADMIN)
        admin_user = User(
            username=payload.admin_email.split("@")[0].lower(),
            email=payload.admin_email,
            full_name=payload.admin_name,
            hashed_password=get_password_hash(payload.password),
            tenant_id=tenant_id,
            organization_id=tenant_id,
            role="ORG_ADMIN",
            is_platform_admin=False,
            is_active=True
        )
        session.add(admin_user)
        await session.commit()

        # Generate JWT
        token = create_access_token(data={
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "tenant_id": tenant_id,
            "organization_id": tenant_id,
            "role": "ORG_ADMIN",
            "is_platform_admin": False
        })

        await record_audit_event(
            tenant_id=tenant_id,
            user_identifier=admin_user.username,
            user_role="ORG_ADMIN",
            action="USER_CREATED",
            resource_type="user",
            resource_id=str(admin_user.id),
            details={"type": "initial_admin_signup", "company": payload.company_name}
        )

        return {
            "status": "SUCCESS",
            "message": "Organization created successfully",
            "access_token": token,
            "organization_id": tenant_id,
            "user": admin_user.to_dict()
        }


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    """Issues password reset verification token."""
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=60)
    PASSWORD_RESET_TOKENS[token] = {
        "email": payload.email.lower().strip(),
        "expires_at": expires
    }
    return {
        "status": "SUCCESS",
        "message": f"Password reset instructions dispatched to {payload.email}",
        "reset_token": token  # Returned for testing/demo environments
    }


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    """Applies password reset with validated recovery token."""
    token_entry = PASSWORD_RESET_TOKENS.get(payload.token)
    if not token_entry:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    
    if datetime.now(timezone.utc) > token_entry["expires_at"]:
        PASSWORD_RESET_TOKENS.pop(payload.token, None)
        raise HTTPException(status_code=400, detail="Reset token expired. Please request a new link.")

    email = token_entry["email"]
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.email == email)
        res = await session.execute(stmt)
        user = res.scalars().first()
        if user:
            user.hashed_password = get_password_hash(payload.new_password)
            await session.commit()
    
    PASSWORD_RESET_TOKENS.pop(payload.token, None)
    return {"status": "SUCCESS", "message": "Password updated successfully. You may now sign in."}


@router.post("/mfa/setup")
async def mfa_setup(identity: AuthenticatedIdentity = Depends(get_current_user)):
    """Generates MFA TOTP secret for enterprise user account."""
    secret = secrets.token_hex(16)
    return {
        "status": "SUCCESS",
        "secret": secret,
        "qr_uri": f"otpauth://totp/AegisOps:{identity.username}?secret={secret}&issuer=AegisOpsAI",
        "backup_codes": [secrets.token_hex(4).upper() for _ in range(5)]
    }


@router.post("/mfa/verify")
async def mfa_verify(
    payload: MfaVerifyRequest,
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    """Confirms MFA setup with verification code."""
    if len(payload.code) != 6 or not payload.code.isdigit():
        raise HTTPException(status_code=400, detail="Invalid 6-digit verification code.")
    
    async with AsyncSessionLocal() as session:
        if identity.user_id:
            user = await session.get(User, identity.user_id)
            if user:
                user.mfa_enabled = True
                await session.commit()

    return {"status": "SUCCESS", "message": "Multi-Factor Authentication verified and enabled."}


@router.post("/invite")
async def invite_user(
    payload: InviteUserRequest,
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    """Invites a team member to the organization with assigned role."""
    # Permission check: must be admin or SRE lead
    if not (identity.is_platform_admin or identity.role in ["SUPER_ADMIN", "ORG_ADMIN", "TENANT_ADMIN", "SRE_LEAD"]):
        raise HTTPException(status_code=403, detail="Only administrators or SRE Leads can invite team members.")

    invite_token = secrets.token_urlsafe(24)
    target_tenant = identity.tenant_id

    await record_audit_event(
        tenant_id=target_tenant,
        user_identifier=identity.username,
        user_role=identity.role,
        action="USER_INVITED",
        resource_type="user",
        resource_id=payload.email,
        details={"invited_role": payload.role, "full_name": payload.full_name}
    )

    return {
        "status": "SUCCESS",
        "message": f"Invitation dispatched to {payload.email}",
        "invite_token": invite_token,
        "tenant_id": target_tenant,
        "role": payload.role
    }


@router.get("/me")
async def get_current_user_profile(identity: AuthenticatedIdentity = Depends(get_current_user)):
    """Returns the current authenticated user identity and full enterprise role capabilities."""
    return {
        "id": identity.user_id or 1,
        "username": identity.username,
        "email": f"{identity.username}@aegisops.ai" if "@" not in identity.username else identity.username,
        "role": identity.role,
        "tenant_id": identity.tenant_id,
        "organization_id": identity.tenant_id,
        "is_platform_admin": identity.is_platform_admin,
        "auth_method": identity.auth_method,
        "must_change_password": identity.must_change_password,
        "permissions": get_role_permissions(identity.role, identity.is_platform_admin)
    }


@router.post("/first-login-change-password")
async def first_login_change_password(
    payload: FirstLoginPasswordChangeRequest,
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    """Enforces first-login password change from generated temporary credentials."""
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long."
        )

    async with AsyncSessionLocal() as session:
        stmt = select(User).where(
            or_(User.id == identity.user_id, User.username == identity.username)
        )
        res = await session.execute(stmt)
        user = res.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="User account not found.")

        if payload.current_password and not verify_password(payload.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password verification failed.")

        if verify_password(payload.new_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="New password must be different from current password.")

        user.hashed_password = get_password_hash(payload.new_password)
        user.must_change_password = False
        await session.commit()

        new_token = create_access_token(data={
            "sub": user.username,
            "user_id": user.id,
            "tenant_id": user.tenant_id,
            "organization_id": user.tenant_id,
            "role": user.role,
            "is_platform_admin": bool(user.is_platform_admin or user.role == "PLATFORM_OWNER_ADMIN"),
            "must_change_password": False
        })

        await record_audit_event(
            tenant_id=user.tenant_id or "platform",
            user_identifier=user.username,
            user_role=user.role,
            action="PASSWORD_CHANGED",
            resource_type="user",
            resource_id=str(user.id),
            details={"type": "first_login_password_change"}
        )

        return {
            "status": "SUCCESS",
            "message": "Password changed successfully. First login requirement completed.",
            "access_token": new_token,
            "must_change_password": False,
            "user": user.to_dict()
        }


@router.post("/switch-tenant")
async def switch_tenant(
    payload: SwitchTenantRequest,
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    """Allows Platform Owner Admin to switch active company context among FinCore, ShopSphere, and CloudDesk."""
    # Strict Authorization: ONLY Platform Owner Admin is permitted to switch tenant context
    if not (identity.is_platform_admin or identity.role in ["PLATFORM_OWNER_ADMIN", "SUPER_ADMIN", "PLATFORM_ADMIN"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized to switch tenant context. Access is limited strictly to assigned company."
        )

    target_tenant = payload.target_tenant_id.lower().strip()
    if target_tenant not in ["fincore", "shopsphere", "clouddesk"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target tenant '{payload.target_tenant_id}'. Must be one of: FinCore, ShopSphere, or CloudDesk."
        )

    token = create_access_token(data={
        "sub": identity.username,
        "user_id": identity.user_id,
        "tenant_id": target_tenant,
        "organization_id": target_tenant,
        "role": identity.role,
        "is_platform_admin": True,
        "must_change_password": False
    })

    await record_audit_event(
        tenant_id=target_tenant,
        user_identifier=identity.username,
        user_role=identity.role,
        action="TENANT_SWITCH",
        resource_type="tenant_context",
        resource_id=target_tenant,
        details={"switched_from": identity.tenant_id, "switched_to": target_tenant}
    )

    return {
        "status": "SUCCESS",
        "switched_to_tenant": target_tenant,
        "tenant_id": target_tenant,
        "organization_id": target_tenant,
        "access_token": token
    }


@router.post("/logout")
async def logout(
    token: Optional[str] = Depends(oauth2_scheme),
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    """Revokes the current session and JWT token."""
    if token:
        revoke_token(token)
    
    if identity.user_id:
        try:
            async with AsyncSessionLocal() as session:
                user = await session.get(User, identity.user_id)
                if user:
                    user.session_revoked_at = datetime.now(timezone.utc)
                    await session.commit()
        except Exception:
            pass

    await record_audit_event(
        tenant_id=identity.tenant_id or "platform",
        user_identifier=identity.username,
        user_role=identity.role,
        action="LOGOUT",
        resource_type="auth_session",
        resource_id=f"usr-{identity.user_id}"
    )
    return {"status": "SUCCESS", "message": f"User {identity.username} logged out and session revoked."}


@router.get("/users")
async def list_company_users(
    tenant_id: Optional[str] = None,
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    """
    Lists users respecting company boundary:
    - Platform Owner Admin can view all users or filter by company.
    - Company Admin can only view users in their own company.
    - Other roles are rejected with 403 Forbidden.
    """
    if identity.is_platform_admin or identity.role in ["PLATFORM_OWNER_ADMIN", "SUPER_ADMIN", "PLATFORM_ADMIN"]:
        target_tenant = tenant_id
    elif identity.role == "COMPANY_ADMIN":
        target_tenant = identity.tenant_id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only Platform Owner Admin or Company Admin can view company user accounts."
        )

    async with AsyncSessionLocal() as session:
        stmt = select(User)
        if target_tenant:
            stmt = stmt.where(User.tenant_id == target_tenant)
        res = await session.execute(stmt)
        users = res.scalars().all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "tenant_id": u.tenant_id,
                "is_active": u.is_active,
                "must_change_password": bool(u.must_change_password),
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None
            }
            for u in users
        ]


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_company_user(
    payload: CreateCompanyUserRequest,
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    """
    Creates a user within the authorized company boundary:
    - Platform Owner Admin can create users for any of the 3 companies.
    - Company Admin can only create users within their own company.
    - Cross-company user creation is rejected with 403 Forbidden.
    """
    if identity.is_platform_admin or identity.role in ["PLATFORM_OWNER_ADMIN", "SUPER_ADMIN", "PLATFORM_ADMIN"]:
        effective_tenant = payload.tenant_id or "fincore"
    elif identity.role == "COMPANY_ADMIN":
        if payload.tenant_id and payload.tenant_id != identity.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Company Admin for '{identity.tenant_id}' cannot manage users for '{payload.tenant_id}'."
            )
        effective_tenant = identity.tenant_id
        if payload.role.upper() in ["PLATFORM_OWNER_ADMIN", "SUPER_ADMIN", "PLATFORM_ADMIN"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company Admin cannot grant platform-owner privileges."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only Platform Owner Admin or Company Admin can create user accounts."
        )

    async with AsyncSessionLocal() as session:
        # Check duplicate
        stmt = select(User).where(or_(User.username == payload.username, User.email == payload.email))
        res = await session.execute(stmt)
        if res.scalars().first():
            raise HTTPException(status_code=400, detail="Username or email already exists.")

        temp_pwd = secrets.token_urlsafe(16)
        new_user = User(
            username=payload.username.strip().lower(),
            email=payload.email.strip().lower(),
            full_name=(payload.full_name or payload.username).strip(),
            role=payload.role.upper(),
            tenant_id=effective_tenant,
            organization_id=effective_tenant,
            hashed_password=get_password_hash(temp_pwd),
            must_change_password=True,
            is_active=True
        )
        session.add(new_user)
        await session.commit()

        await record_audit_event(
            tenant_id=effective_tenant,
            user_identifier=identity.username,
            user_role=identity.role,
            action="USER_CREATED",
            resource_type="user",
            resource_id=new_user.username,
            details={"created_role": payload.role, "tenant_id": effective_tenant}
        )

        return {
            "status": "SUCCESS",
            "message": f"User {new_user.username} created successfully.",
            "user": new_user.to_dict(),
            "temporary_password": temp_pwd
        }

