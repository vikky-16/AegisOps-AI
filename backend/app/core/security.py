"""
Security, Password Hashing, JWT Token Utilities, Multi-Tenant API Key Authentication, and RBAC
"""

import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any, List, Dict
from passlib.context import CryptContext
try:
    from jose import jwt, JWTError
except ImportError:
    import jwt  # type: ignore
    class JWTError(Exception):  # type: ignore
        pass
    _raw_decode = jwt.decode
    def _adapted_decode(*args, **kwargs):
        try:
            return _raw_decode(*args, **kwargs)
        except jwt.PyJWTError as exc:
            raise JWTError(str(exc)) from exc
    jwt.decode = _adapted_decode  # type: ignore
from fastapi import Depends, HTTPException, Security, Header, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy import select

from backend.app.core.config import settings

import bcrypt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# In-memory fast cache for validated API keys to avoid DB query overhead on high-throughput streaming
# Maps hashed_key -> {"tenant_id": str, "scopes": list, "name": str}
API_KEY_CACHE: Dict[str, Dict[str, Any]] = {}

_DEFAULT_SEED_KEYS = {
    "demo-tenant": "agt_live_demo_11112222333344445555",
    "tenant-alpha": "agt_live_acme_aaaa1111bbbb2222cccc",
    "tenant-beta": "agt_live_cyber_xxxx9999yyyy8888zzzz",
    "shopsphere": "agt_live_shopsphere_11112222333344445555",
    "fincore": "agt_live_fincore_aaaa1111bbbb2222cccc",
    "clouddesk": "agt_live_clouddesk_xxxx9999yyyy8888zzzz"
}
for _tid, _raw in _DEFAULT_SEED_KEYS.items():
    _h = hashlib.sha256(_raw.encode("utf-8")).hexdigest()
    API_KEY_CACHE[_h] = {
        "tenant_id": _tid,
        "name": f"{_tid} Primary Key",
        "scopes": ["telemetry:write", "telemetry:read"]
    }


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8")[:72], salt).decode("utf-8")


def generate_tenant_api_key(tenant_slug: str = "tenant") -> tuple[str, str, str]:
    """
    Generates a secure API key for ingestion.
    Returns: (raw_key, key_prefix, hashed_key)
    Example raw key: agt_live_acme_4f89d3a17e0b...
    """
    random_secret = secrets.token_hex(20)
    slug_sanitized = re_slug = tenant_slug.replace("-", "_")[:12]
    raw_key = f"agt_live_{slug_sanitized}_{random_secret}"
    key_prefix = raw_key[:16]
    hashed_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return raw_key, key_prefix, hashed_key


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def register_cached_api_key(raw_key: str, tenant_id: str, name: str = "Default Key", scopes: str = "telemetry:write,telemetry:read"):
    hashed = hash_api_key(raw_key)
    API_KEY_CACHE[hashed] = {
        "tenant_id": tenant_id,
        "name": name,
        "scopes": scopes.split(",") if scopes else []
    }


def evict_cached_api_key(key_or_hash: str):
    """Evicts a revoked key from the memory cache."""
    if len(key_or_hash) == 64:
        API_KEY_CACHE.pop(key_or_hash, None)
    else:
        API_KEY_CACHE.pop(hash_api_key(key_or_hash), None)
    API_KEY_CACHE.pop(key_or_hash, None)


# In-memory revocation set for revoked/logged out JWT tokens
REVOKED_TOKENS: set[str] = set()


def revoke_token(token: str) -> None:
    """Marks a JWT token as revoked."""
    if token:
        REVOKED_TOKENS.add(token.strip())


def is_token_revoked(token: str) -> bool:
    """Checks whether a token is in the revocation list."""
    return bool(token and token.strip() in REVOKED_TOKENS)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    if is_token_revoked(token):
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


# =========================================================================
# RBAC & MULTI-TENANT AUTHENTICATION DEPENDENCIES
# =========================================================================

# Valid enterprise roles
ENTERPRISE_ROLES = [
    # AegisOps AI Core Multi-Company Roles
    "PLATFORM_OWNER_ADMIN",
    "COMPANY_ADMIN",
    "APPROVER",
    "DEVELOPER_SECURITY",
    # Enterprise Personas
    "SUPER_ADMIN",
    "ORG_ADMIN",
    "CEO",
    "CTO",
    "SRE_LEAD",
    "DEVOPS_ENGINEER",
    "SECURITY_ENGINEER",
    "DEVELOPER",
    "INCIDENT_COMMANDER",
    "VIEWER",
    # Backward compatibility roles
    "PLATFORM_ADMIN",
    "TENANT_ADMIN",
    "SRE_MANAGER",
    "SRE_ENGINEER",
    "OPERATOR"
]

ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "PLATFORM_OWNER_ADMIN": ["*"],
    "SUPER_ADMIN": ["*"],
    "PLATFORM_ADMIN": ["*"],
    "COMPANY_ADMIN": [
        "executive:view", "architecture:view", "telemetry:read", "telemetry:write",
        "services:read", "incidents:read", "incidents:write", "rca:inspect",
        "recovery:plan", "recovery:execute", "simulations:run", "knowledge:read",
        "users:manage", "settings:manage", "audit:read", "approvals:read"
    ],
    "APPROVER": [
        "executive:view", "services:read", "telemetry:read", "incidents:read",
        "rca:inspect", "recovery:plan", "approvals:read", "approvals:approve",
        "approvals:reject", "knowledge:read"
    ],
    "DEVELOPER_SECURITY": [
        "services:read", "traces:read", "logs:read", "telemetry:read", "telemetry:write",
        "incidents:read", "incidents:write", "rca:inspect", "recovery:plan",
        "diagnostics:run", "simulations:run", "knowledge:read", "security:read"
    ],
    "ORG_ADMIN": [
        "executive:view", "architecture:view", "telemetry:read", "telemetry:write",
        "services:read", "incidents:read", "incidents:write", "approvals:approve",
        "approvals:reject", "remediation:execute", "policies:manage", "integrations:manage",
        "users:manage", "teams:manage", "audit:read", "security:read", "reliability:read"
    ],
    "TENANT_ADMIN": [
        "executive:view", "architecture:view", "telemetry:read", "telemetry:write",
        "services:read", "incidents:read", "incidents:write", "approvals:approve",
        "approvals:reject", "remediation:execute", "policies:manage", "integrations:manage",
        "users:manage", "teams:manage", "audit:read", "security:read", "reliability:read"
    ],
    "CEO": [
        "executive:view", "business_impact:view", "incidents:read", "availability:view",
        "customer_impact:view", "reliability:read", "risk:view", "audit:read", "services:read"
    ],
    "CTO": [
        "executive:view", "architecture:view", "reliability:read", "incidents:read",
        "engineering_performance:view", "services:read", "risk:view", "telemetry:read"
    ],
    "INCIDENT_COMMANDER": [
        "incidents:read", "incidents:write", "telemetry:read", "approvals:approve",
        "approvals:reject", "remediation:execute", "rca:inspect", "policies:read", "services:read"
    ],
    "SRE_LEAD": [
        "incidents:read", "incidents:write", "telemetry:read", "approvals:approve",
        "approvals:reject", "policies:manage", "rca:inspect", "remediation:execute",
        "reliability:read", "services:read"
    ],
    "SRE_MANAGER": [
        "incidents:read", "incidents:write", "telemetry:read", "approvals:approve",
        "approvals:reject", "policies:manage", "rca:inspect", "remediation:execute",
        "reliability:read", "services:read"
    ],
    "DEVOPS_ENGINEER": [
        "services:read", "telemetry:read", "telemetry:write", "incidents:read",
        "incidents:write", "remediation:execute_low_risk", "remediation:execute"
    ],
    "SRE_ENGINEER": [
        "services:read", "telemetry:read", "telemetry:write", "incidents:read",
        "incidents:write", "remediation:execute_low_risk", "remediation:execute"
    ],
    "OPERATOR": [
        "services:read", "telemetry:read", "telemetry:write", "incidents:read",
        "remediation:execute_low_risk"
    ],
    "SECURITY_ENGINEER": [
        "security:read", "audit:read", "telemetry:read", "incidents:read",
        "suspicious_activity:investigate", "access_events:inspect", "services:read"
    ],
    "DEVELOPER": [
        "services:read", "traces:read", "logs:read", "telemetry:read", "incidents:read"
    ],
    "VIEWER": [
        "executive:view", "services:read", "telemetry:read", "incidents:read",
        "reliability:read", "audit:read"
    ]
}


def has_permission(role: str, permission: str, is_platform_admin: bool = False) -> bool:
    if is_platform_admin or role.upper() in ["SUPER_ADMIN", "PLATFORM_ADMIN", "PLATFORM_OWNER_ADMIN"]:
        return True
    perms = ROLE_PERMISSIONS.get(role.upper(), ["telemetry:read", "incidents:read"])
    if "*" in perms:
        return True
    return permission in perms



class AuthenticatedIdentity:
    """Represents an authenticated caller (user or API key) with tenant context."""
    def __init__(
        self,
        user_id: Optional[int],
        username: str,
        role: str,
        tenant_id: Optional[str] = None,
        is_platform_admin: bool = False,
        auth_method: str = "jwt",
        must_change_password: bool = False
    ):
        self.user_id = user_id
        self.username = username
        self.role = role.upper()
        self.tenant_id = tenant_id
        self.is_platform_admin = is_platform_admin or (self.role in ["PLATFORM_OWNER_ADMIN", "SUPER_ADMIN", "PLATFORM_ADMIN"])
        self.auth_method = auth_method
        self.must_change_password = must_change_password

    def can_access_tenant(self, target_tenant_id: str) -> bool:
        if self.is_platform_admin:
            return True
        return self.tenant_id == target_tenant_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "tenant_id": self.tenant_id,
            "is_platform_admin": self.is_platform_admin,
            "auth_method": self.auth_method,
            "must_change_password": self.must_change_password
        }


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    x_api_key: Optional[str] = Security(api_key_header)
) -> AuthenticatedIdentity:
    """
    Resolves the authenticated caller from either JWT Bearer token or API key.
    Enforces strict authentication: unauthenticated callers are rejected with 401.
    """
    # 1. Try API Key Header
    if x_api_key:
        identity = await resolve_api_key_identity(x_api_key)
        if identity:
            return identity
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API Key"
        )

    # 2. Try JWT Bearer Token
    if token:
        payload = decode_access_token(token)
        if payload and "sub" in payload:
            return AuthenticatedIdentity(
                user_id=payload.get("user_id"),
                username=payload.get("sub"),
                role=payload.get("role", "VIEWER"),
                tenant_id=payload.get("tenant_id"),
                is_platform_admin=bool(payload.get("is_platform_admin", False)),
                auth_method="jwt",
                must_change_password=bool(payload.get("must_change_password", False))
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token"
        )

    # 3. Unauthenticated requests to protected endpoints MUST be rejected
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: please provide an Authorization Bearer token or X-API-Key."
    )


async def resolve_api_key_identity(raw_key: str) -> Optional[AuthenticatedIdentity]:
    """Validates an API key using fast cache first, then database."""
    hashed = hash_api_key(raw_key)
    
    # Check memory cache
    if hashed in API_KEY_CACHE:
        cached = API_KEY_CACHE[hashed]
        return AuthenticatedIdentity(
            user_id=None,
            username=f"apikey:{cached.get('name', 'ingestion')}",
            role="OPERATOR",
            tenant_id=cached["tenant_id"],
            is_platform_admin=False,
            auth_method="api_key"
        )

    # Check database
    try:
        from backend.app.core.database import AsyncSessionLocal
        from backend.app.models.tenant import TenantAPIKey
        async with AsyncSessionLocal() as session:
            stmt = select(TenantAPIKey).where(
                TenantAPIKey.hashed_key == hashed,
                TenantAPIKey.is_active == True
            )
            result = await session.execute(stmt)
            key_record = result.scalars().first()
            if key_record:
                # Cache for subsequent high-speed requests
                API_KEY_CACHE[hashed] = {
                    "tenant_id": key_record.tenant_id,
                    "name": key_record.name,
                    "scopes": key_record.scopes.split(",") if key_record.scopes else []
                }
                return AuthenticatedIdentity(
                    user_id=None,
                    username=f"apikey:{key_record.name}",
                    role="OPERATOR",
                    tenant_id=key_record.tenant_id,
                    is_platform_admin=False,
                    auth_method="api_key"
                )
    except Exception:
        pass

    return None


async def get_authenticated_tenant(
    x_api_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme),
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID")
) -> str:
    """
    Strictly derives the effective tenant_id from API key or JWT token.
    For ingestion endpoints, an API key or bearer token is required.
    """
    if not x_api_key and not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: please provide an X-API-Key header or Authorization Bearer token."
        )

    identity = await get_current_user(token=token, x_api_key=x_api_key)
    
    # If caller is platform admin and explicitly passes an X-Tenant-ID, permit cross-tenant targeting
    if identity.is_platform_admin and x_tenant_id:
        return x_tenant_id.strip()
    
    # Otherwise, strictly enforce caller's assigned tenant
    return identity.tenant_id or "fincore"


def require_role(allowed_roles: List[str]):
    """Decorator / dependency enforcing role-based permissions."""
    allowed_upper = [r.upper() for r in allowed_roles]

    async def role_checker(identity: AuthenticatedIdentity = Depends(get_current_user)) -> AuthenticatedIdentity:
        if identity.is_platform_admin:
            return identity
        if identity.role not in allowed_upper:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Role '{identity.role}' does not have required permissions ({', '.join(allowed_upper)})."
            )
        return identity

    return role_checker


async def require_platform_admin(
    identity: AuthenticatedIdentity = Depends(get_current_user)
) -> AuthenticatedIdentity:
    """Enforces that only platform administrators can access cross-tenant management."""
    if not identity.is_platform_admin and identity.role not in ["PLATFORM_OWNER_ADMIN", "PLATFORM_ADMIN", "SUPER_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrative privilege required (PLATFORM_OWNER_ADMIN, PLATFORM_ADMIN, or SUPER_ADMIN)."
        )
    return identity



def require_permission(permission: str):
    """FastAPI dependency enforcing granular action permission."""
    async def permission_checker(identity: AuthenticatedIdentity = Depends(get_current_user)) -> AuthenticatedIdentity:
        if not has_permission(identity.role, permission, identity.is_platform_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Role '{identity.role}' does not have required permission '{permission}'."
            )
        return identity
    return permission_checker


async def record_audit_event(
    tenant_id: str,
    user_identifier: str,
    user_role: str,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = "127.0.0.1",
    result: str = "SUCCESS"
):
    """Records an immutable audit trail entry."""
    import json
    try:
        from backend.app.core.database import AsyncSessionLocal
        from backend.app.models.tenant import TenantAuditLog
        async with AsyncSessionLocal() as session:
            audit = TenantAuditLog(
                tenant_id=tenant_id,
                user_identifier=user_identifier,
                user_role=user_role,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details_json=json.dumps(details or {}),
                ip_address=ip_address or "127.0.0.1",
                result=result
            )
            session.add(audit)
            await session.commit()
    except Exception:
        pass

