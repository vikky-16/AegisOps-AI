"""
AegisOps AI - Kafka Dead Letter Queue (DLQ) Handler
Captures, isolates, and retains malformed or unprocessable telemetry events for forensic inspection.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from collections import deque


class DeadLetterHandler:
    def __init__(self, max_retained: int = 500):
        self.dlq_events: deque = deque(maxlen=max_retained)
        self.total_dlq_count = 0

    def route_to_dlq(self, raw_message: Any, error_reason: str, topic: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Isolates a malformed or failed event into the Dead Letter Queue."""
        self.total_dlq_count += 1
        dlq_entry = {
            "dlq_id": f"DLQ-{int(datetime.now(timezone.utc).timestamp()*1000)}-{self.total_dlq_count}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "original_topic": topic or "telemetry.raw",
            "error_reason": error_reason,
            "raw_payload": str(raw_message)[:1000],
            "metadata": metadata or {}
        }
        self.dlq_events.appendleft(dlq_entry)
        return dlq_entry

    def get_recent_dlq(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(self.dlq_events)[:limit]

    def clear_dlq(self):
        self.dlq_events.clear()


dead_letter_handler = DeadLetterHandler()
