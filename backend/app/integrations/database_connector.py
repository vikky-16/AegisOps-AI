"""
Database Telemetry Connector
Ingests database operational health, connection pool states, slow query telemetry, and lock stalls.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.app.integrations.base import BaseConnector
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetryType, TelemetrySeverity


class DatabaseTelemetryConnector(BaseConnector):
    def __init__(self):
        super().__init__(
            connector_id="database-monitor",
            name="Database Telemetry Connector",
            connector_type="DATABASE_MONITOR",
            description="Continuous telemetry ingestion for connection pools, locks, query latencies, and storage.",
            auth_required=False,
            enabled=True
        )

    def normalize(self, raw_payload: Any, headers: Optional[Dict[str, str]] = None) -> List[NormalizedTelemetryEvent]:
        events: List[NormalizedTelemetryEvent] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        if isinstance(raw_payload, dict):
            items = [raw_payload]
        elif isinstance(raw_payload, list):
            items = raw_payload
        else:
            items = []

        for item in items:
            db_name = item.get("database_name") or item.get("service") or "database-service"
            pool_util = float(item.get("pool_utilization", 0.0))
            active_slots = int(item.get("active_connections", 0))
            max_slots = int(item.get("max_connections", 20))
            query_latency = float(item.get("avg_query_latency_ms", 0.0))
            lock_wait_sec = float(item.get("lock_wait_seconds", 0.0))

            sev = TelemetrySeverity.INFO
            evt_type = "DB_NORMAL_TELEMETRY"
            msg = f"Database '{db_name}' pool: {active_slots}/{max_slots} ({pool_util*100:.1f}%), Latency: {query_latency:.1f}ms"

            if pool_util >= 0.90 or active_slots >= max_slots:
                sev = TelemetrySeverity.CRITICAL
                evt_type = "CONNECTION_POOL_EXHAUSTION"
                msg = f"CRITICAL: Connection pool exhausted ({active_slots}/{max_slots} slots locked). Queries stalling."
            elif lock_wait_sec > 5.0:
                sev = TelemetrySeverity.ERROR
                evt_type = "DEADLOCK_TIMEOUT"
                msg = f"ERROR: Lock wait timeout ({lock_wait_sec:.1f}s) exceeded on '{db_name}' tablespace."
            elif query_latency > 1500.0:
                sev = TelemetrySeverity.WARNING
                evt_type = "SLOW_QUERY_DEGRADATION"
                msg = f"WARNING: Elevated average query latency ({query_latency:.1f}ms) on '{db_name}'."

            events.append(NormalizedTelemetryEvent(
                timestamp=item.get("timestamp") or now_iso,
                source=f"db-agent-{db_name}",
                environment="demo",
                service=db_name.lower(),
                type=TelemetryType.DATABASE_SIGNAL,
                severity=sev,
                event_type=evt_type,
                message=msg,
                metrics={
                    "pool_utilization": pool_util,
                    "active_connections": float(active_slots),
                    "query_latency_ms": query_latency,
                    "lock_wait_seconds": lock_wait_sec
                },
                metadata=item
            ))

        self.record_ingest(len(events))
        return events
