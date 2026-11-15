"""
Conversational SRE Assistant Database Models
Persists multi-turn conversations and message history across page navigation and sessions.
"""

from datetime import datetime, timezone
import json
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from backend.app.core.database import Base


class Conversation(Base):
    __tablename__ = "sre_conversations"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(64), unique=True, index=True, nullable=False)
    tenant_id = Column(String(64), default="demo-tenant", index=True, nullable=False)
    incident_id = Column(String(64), index=True, nullable=True)
    title = Column(String(256), default="SRE Operational Session")
    status = Column(String(32), default="ACTIVE")  # ACTIVE, ARCHIVED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "tenant_id": self.tenant_id,
            "incident_id": self.incident_id,
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ConversationMessage(Base):
    __tablename__ = "sre_conversation_messages"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(64), unique=True, index=True, nullable=False)
    conversation_id = Column(String(64), index=True, nullable=False)
    tenant_id = Column(String(64), default="demo-tenant", index=True)
    role = Column(String(16), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    sources_json = Column(Text, default="[]")
    evidence_json = Column(Text, default="[]")
    suggested_json = Column(Text, default="[]")
    status = Column(String(32), default="COMPLETED")  # PENDING, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        sources = []
        evidence = []
        suggested = []
        try:
            if self.sources_json:
                sources = json.loads(self.sources_json)
            if self.evidence_json:
                evidence = json.loads(self.evidence_json)
            if self.suggested_json:
                suggested = json.loads(self.suggested_json)
        except Exception:
            pass

        return {
            "id": self.message_id,
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "tenant_id": self.tenant_id,
            "sender": self.role,
            "role": self.role,
            "text": self.content,
            "content": self.content,
            "sources": sources,
            "evidence_items": evidence,
            "suggested_actions": suggested,
            "suggestedActions": suggested,
            "status": self.status,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
