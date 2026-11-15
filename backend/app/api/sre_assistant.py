"""
AegisOps AI - Conversational SRE Assistant API Router
Handles multi-turn conversational chat, context retrieval, and history inspection.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from backend.app.ai.sre_chat_engine import sre_chat_engine
from backend.app.core.security import get_current_user, AuthenticatedIdentity

router = APIRouter(prefix="/sre-assistant", tags=["SRE Assistant"])


class SREChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    incident_id: Optional[str] = None
    message: str


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


@router.get("/conversations")
async def list_conversations(
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    """
    Returns list of saved conversations for the authenticated tenant.
    """
    identity = _resolve_identity(identity)
    if identity.is_platform_admin:
        effective_tenant = x_tenant_id or "fincore"
    else:
        if x_tenant_id and identity.tenant_id and x_tenant_id != identity.tenant_id:
            raise HTTPException(status_code=403, detail="Cross-company access denied.")
        effective_tenant = identity.tenant_id or "fincore"
    convs = await sre_chat_engine.list_conversations(tenant_id=effective_tenant)
    return {"conversations": convs}


@router.post("/chat")
async def chat_with_sre(
    payload: SREChatRequest,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    """
    Submits a user message to the conversational SRE assistant.
    Maintains conversation memory across turns and grounds answers in live AegisOps telemetry.
    """
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    identity = _resolve_identity(identity)
    if identity.is_platform_admin:
        effective_tenant = x_tenant_id or "fincore"
    else:
        if x_tenant_id and identity.tenant_id and x_tenant_id != identity.tenant_id:
            raise HTTPException(status_code=403, detail="Cross-company access denied.")
        effective_tenant = identity.tenant_id or "fincore"

    resp = await sre_chat_engine.chat(
        message=payload.message,
        conversation_id=payload.conversation_id,
        incident_id=payload.incident_id,
        tenant_id=effective_tenant
    )
    return resp


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    identity: AuthenticatedIdentity = Depends(get_current_user)
):
    """Returns the message history for a specific conversation ID with tenant isolation."""
    identity = _resolve_identity(identity)
    if identity.is_platform_admin:
        effective_tenant = x_tenant_id or "fincore"
    else:
        if x_tenant_id and identity.tenant_id and x_tenant_id != identity.tenant_id:
            raise HTTPException(status_code=403, detail="Cross-company access denied.")
        effective_tenant = identity.tenant_id or "fincore"
    history = await sre_chat_engine.get_conversation_history_async(conversation_id, tenant_id=effective_tenant)
    is_gen = sre_chat_engine.is_generating(conversation_id)
    return {
        "conversation_id": conversation_id,
        "is_generating": is_gen,
        "status": "GENERATING" if is_gen else "READY",
        "messages": history
    }

