"""
Operations AI Assistant API Endpoints
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from backend.app.ai.sre_chat_engine import sre_chat_engine

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


class AssistantQueryRequest(BaseModel):
    question: Optional[str] = None
    message: Optional[str] = None
    incident_id: Optional[str] = None
    context_incident_id: Optional[str] = None
    conversation_id: Optional[str] = None


@router.post("/query")
@router.post("/chat")
async def query_assistant(payload: AssistantQueryRequest):
    """
    Evaluates natural language operational queries and returns factual SRE insights
    grounded in actual live telemetry and incident evidence.
    """
    msg = payload.message or payload.question or ""
    inc_id = payload.incident_id or payload.context_incident_id
    res = await sre_chat_engine.chat(
        message=msg,
        incident_id=inc_id,
        conversation_id=payload.conversation_id
    )
    return {
        "answer": res["answer"],
        "sources": res.get("sources", []),
        "evidence_items": res.get("evidence_items", []),
        "suggested_actions": res.get("suggested_actions", []),
        "conversation_id": res.get("conversation_id"),
        "incident_id": res.get("incident_id"),
        "mode": res.get("mode", "DETERMINISTIC MODE")
    }
