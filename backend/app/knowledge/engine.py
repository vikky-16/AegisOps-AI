"""
Knowledge Base & Case-Based Reasoning (CBR) Engine
Manages incident post-mortems and matches incoming incidents with historical resolutions.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from backend.app.knowledge.vector_matcher import VectorMatcher

INITIAL_KNOWLEDGE_ARTICLES = [
    {
        "incident_code": "KB-2025-089",
        "title": "Database Connection Pool Exhaustion under Concurrency Surge",
        "primary_service": "database-service",
        "symptoms_summary": "Active connections reached 20/20 max capacity. Upstream Service B experienced HTTP 504 gateway timeouts and transaction lock wait aborts.",
        "root_cause": "Long-running transaction locks held during peak traffic exhausted database connection pool slots.",
        "recommended_remedy": "RESET_CONNECTION_POOL",
        "recovery_action_taken": "RESET_CONNECTION_POOL",
        "recovery_duration_sec": 2.1,
        "outcome": "RESOLVED",
        "historical_success_rate": 94.5,
        "tags": ["database", "connection_pool", "timeout", "service-b"],
        "times_referenced": 18,
        "created_at": "2025-11-14T08:22:00Z"
    },
    {
        "incident_code": "KB-2025-112",
        "title": "Payment Service Worker Thread Starvation and CPU Saturation",
        "primary_service": "service-b",
        "symptoms_summary": "CPU utilization surged past 88%. Request queue latency p95 jumped to 1420ms. Ingress Gateway returned 502 errors.",
        "root_cause": "Worker concurrency saturation during cryptographic payment signature verification.",
        "recommended_remedy": "SCALE_WORKERS",
        "recovery_action_taken": "SCALE_WORKERS",
        "recovery_duration_sec": 3.4,
        "outcome": "RESOLVED",
        "historical_success_rate": 91.2,
        "tags": ["service-b", "cpu", "workers", "latency"],
        "times_referenced": 12,
        "created_at": "2025-12-05T14:10:00Z"
    },
    {
        "incident_code": "KB-2026-004",
        "title": "Service Process Crash from Segmentation Fault / Unhandled Signal",
        "primary_service": "service-a",
        "symptoms_summary": "Service A became abruptly unreachable (HTTP 503 / Connection Refused). Gateway unable to forward order traffic.",
        "root_cause": "Process termination due to out-of-bounds pointer or memory corruption in legacy serialization worker.",
        "recommended_remedy": "RESTART_SERVICE",
        "recovery_action_taken": "RESTART_SERVICE",
        "recovery_duration_sec": 4.2,
        "outcome": "RESOLVED",
        "historical_success_rate": 98.0,
        "tags": ["service-a", "crash", "restart", "503"],
        "times_referenced": 24,
        "created_at": "2026-01-19T09:45:00Z"
    },
    {
        "incident_code": "KB-2026-019",
        "title": "Rapid Log Explosion Causing Tablespace Disk Pressure",
        "primary_service": "database-service",
        "symptoms_summary": "Storage volume crossed 85% warning threshold. Log generation velocity exceeded 1.8 GB/hour.",
        "root_cause": "Repeated unindexed query error loop generated 40,000 duplicate warning logs per minute.",
        "recommended_remedy": "ROTATE_AND_COMPRESS_LOGS",
        "recovery_action_taken": "ROTATE_AND_COMPRESS_LOGS",
        "recovery_duration_sec": 4.8,
        "outcome": "RESOLVED",
        "historical_success_rate": 96.0,
        "tags": ["storage", "logs", "disk", "archive"],
        "times_referenced": 15,
        "created_at": "2026-02-02T11:30:00Z"
    }
]


class KnowledgeBaseEngine:
    def __init__(self):
        self.matcher = VectorMatcher()
        self.articles: List[Dict[str, Any]] = list(INITIAL_KNOWLEDGE_ARTICLES)
        self.matcher.index_articles(self.articles)

    def get_all_articles(self) -> List[Dict[str, Any]]:
        return self.articles

    def search_similar(self, symptoms_query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        return self.matcher.find_similar_cases(symptoms_query, top_k=top_k)

    def record_resolved_incident(self, incident: Dict[str, Any], recovery: Dict[str, Any]) -> Dict[str, Any]:
        """
        Indexes a newly verified and resolved incident into the Knowledge Base.
        """
        article = {
            "incident_code": f"KB-{datetime.now(timezone.utc).strftime('%Y-%m%d')}-{incident.get('incident_id', '001')[-4:]}",
            "title": incident.get("title", "Resolved System Incident"),
            "primary_service": incident.get("primary_service", "unknown"),
            "symptoms_summary": incident.get("description", "") + " " + " ".join(incident.get("rca_evidence", [])),
            "root_cause": incident.get("root_cause_summary", "Unspecified root cause"),
            "recommended_remedy": incident.get("recommended_action", "RESTART_SERVICE"),
            "recovery_action_taken": recovery.get("action", incident.get("recommended_action", "RESTART_SERVICE")),
            "recovery_duration_sec": round(recovery.get("duration_ms", 3000) / 1000.0, 1),
            "outcome": "RESOLVED",
            "historical_success_rate": 95.0,
            "tags": [incident.get("primary_service", "")] + incident.get("affected_services", []),
            "times_referenced": 1,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.articles.append(article)
        self.matcher.index_articles(self.articles)
        return article


knowledge_engine = KnowledgeBaseEngine()
