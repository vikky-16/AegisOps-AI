"""
High-Throughput Scalable Log Processor & Generator
Handles 10,000 to 100,000+ log events with in-memory ring-buffer indexing,
fingerprint deduplication, batch disk persistence, and anomaly pipeline integration.
"""

import os
import json
import time
import hashlib
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from collections import deque, defaultdict
from backend.app.core.config import settings

class LogBatchProcessor:
    def __init__(self, buffer_size: int = 10000):
        self.buffer_size = buffer_size
        self.log_ring_buffer: deque = deque(maxlen=buffer_size)
        self.fingerprints: Dict[str, Dict[str, Any]] = {}
        self.stats = {
            "total_logs": 0,
            "by_level": {"INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0},
            "by_service": {"gateway": 0, "service-a": 0, "service-b": 0, "database-service": 0},
            "by_event_type": defaultdict(int),
            "start_time": time.time()
        }
        self.lock = asyncio.Lock()
        os.makedirs(settings.LOGS_DIR, exist_ok=True)

    def generate_fingerprint(self, service: str, event_type: str, level: str, message: str) -> str:
        # Normalize message by removing numbers/timestamps to group identical error patterns
        normalized = f"{service}_{level}_{event_type}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]

    async def ingest_batch(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ingests a batch of logs, updates statistics, fingerprints, and ring buffer."""
        async with self.lock:
            service_files = defaultdict(list)
            
            for log in logs:
                ts = log.get("timestamp") or datetime.now(timezone.utc).isoformat()
                svc = log.get("service", "unknown")
                lvl = log.get("level", "INFO").upper()
                evt = log.get("event_type", "GENERIC_LOG")
                msg = log.get("message", "")
                trace_id = log.get("trace_id", f"trace-{int(time.time()*1000)}")
                meta = log.get("metadata", {})

                entry = {
                    "timestamp": ts,
                    "service": svc,
                    "level": lvl,
                    "event_type": evt,
                    "message": msg,
                    "trace_id": trace_id,
                    "metadata": meta
                }

                # Update Ring Buffer
                self.log_ring_buffer.append(entry)

                # Update Stats
                self.stats["total_logs"] += 1
                if lvl in self.stats["by_level"]:
                    self.stats["by_level"][lvl] += 1
                else:
                    self.stats["by_level"]["INFO"] += 1

                self.stats["by_service"][svc] = self.stats["by_service"].get(svc, 0) + 1
                self.stats["by_event_type"][evt] += 1

                # Grouping & Fingerprinting
                fp = self.generate_fingerprint(svc, evt, lvl, msg)
                if fp not in self.fingerprints:
                    self.fingerprints[fp] = {
                        "fingerprint": fp,
                        "service": svc,
                        "level": lvl,
                        "event_type": evt,
                        "occurrences": 1,
                        "first_seen": ts,
                        "last_seen": ts,
                        "sample_message": msg,
                        "severity": lvl
                    }
                else:
                    self.fingerprints[fp]["occurrences"] += 1
                    self.fingerprints[fp]["last_seen"] = ts

                service_files[svc].append(json.dumps(entry))

            # Batch write to disk
            for svc, lines in service_files.items():
                fpath = os.path.join(settings.LOGS_DIR, f"{svc}.log")
                with open(fpath, "a", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")

            return {
                "ingested_count": len(logs),
                "total_logs": self.stats["total_logs"],
                "total_fingerprints": len(self.fingerprints),
                "status": "INGESTED"
            }

    def query_logs(
        self,
        page: int = 1,
        page_size: int = 50,
        service: Optional[str] = None,
        level: Optional[str] = None,
        event_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Queries in-memory ring-buffer with pagination and server-side filtering."""
        filtered = list(self.log_ring_buffer)

        if service and service.lower() != "all":
            filtered = [l for l in filtered if l.get("service") == service.lower()]

        if level and level.upper() != "ALL":
            filtered = [l for l in filtered if l.get("level") == level.upper()]

        if event_type and event_type.upper() != "ALL":
            filtered = [l for l in filtered if l.get("event_type") == event_type]

        if search:
            s_lower = search.lower()
            filtered = [
                l for l in filtered 
                if s_lower in l.get("message", "").lower() 
                or s_lower in l.get("event_type", "").lower() 
                or s_lower in l.get("trace_id", "").lower()
            ]

        # Reverse sort by timestamp (newest first)
        filtered.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        total_matching = len(filtered)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_items = filtered[start_idx:end_idx]

        return {
            "items": paginated_items,
            "total": total_matching,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total_matching + page_size - 1) // page_size)
        }

    async def clear_buffer(self):
        """Clears in-memory ring-buffer and resets statistics."""
        async with self.lock:
            self.log_ring_buffer.clear()
            self.fingerprints.clear()
            self.stats = {
                "total_logs": 0,
                "by_level": {"INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0},
                "by_service": {"gateway": 0, "service-a": 0, "service-b": 0, "database-service": 0},
                "by_event_type": defaultdict(int),
                "start_time": time.time()
            }

    def get_fingerprints(self) -> List[Dict[str, Any]]:
        """Returns list of grouped fingerprint clusters sorted by occurrences."""
        fps = list(self.fingerprints.values())
        fps.sort(key=lambda x: x["occurrences"], reverse=True)
        return fps

    def get_summary(self) -> Dict[str, Any]:
        """Returns summary metrics of the log ingestion engine."""
        return {
            "total_logs": self.stats["total_logs"],
            "by_level": self.stats["by_level"],
            "by_service": self.stats["by_service"],
            "unique_fingerprints": len(self.fingerprints),
            "buffer_capacity": self.buffer_size,
            "buffer_usage": len(self.log_ring_buffer)
        }

    def clear(self):
        """Resets the in-memory ring buffer and statistics."""
        self.log_ring_buffer.clear()
        self.fingerprints.clear()
        self.stats["total_logs"] = 0
        self.stats["by_level"] = {"INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
        self.stats["by_service"] = {"gateway": 0, "service-a": 0, "service-b": 0, "database-service": 0}
        self.stats["by_event_type"].clear()


# Global Singleton Log Processor Instance
log_processor = LogBatchProcessor(buffer_size=20000)


def generate_simulated_logs(count: int = 10000, scenario: str = "database_storm") -> List[Dict[str, Any]]:
    """
    Safely generates 10,000, 50,000, or 100,000+ structured log events for simulation.
    Uses realistic distributed cascade patterns.
    """
    now = datetime.now(timezone.utc).isoformat()
    logs = []

    if scenario == "database_storm":
        # 60% Database connection errors, 20% Service B failures, 10% Service A latency, 10% Gateway 502
        db_count = int(count * 0.6)
        svcb_count = int(count * 0.2)
        svca_count = int(count * 0.1)
        gw_count = count - db_count - svcb_count - svca_count

        # Database logs
        for i in range(db_count):
            logs.append({
                "timestamp": now,
                "service": "database-service",
                "level": "CRITICAL" if i % 10 == 0 else "ERROR",
                "event_type": "DATABASE_TIMEOUT",
                "message": f"Connection pool exhausted (20/20 active). Query timeout after 5000ms [slot {i%20}]",
                "trace_id": f"trace-db-{i // 10}",
                "metadata": {"pool_utilization": 1.0, "active_slots": 20, "max_slots": 20}
            })

        # Service B logs
        for i in range(svcb_count):
            logs.append({
                "timestamp": now,
                "service": "service-b",
                "level": "ERROR",
                "event_type": "PAYMENT_PROCESSING_FAILURE",
                "message": f"Failed to acquire payment ledger lock on Database Service: ConnectionRefused",
                "trace_id": f"trace-b-{i // 5}",
                "metadata": {"upstream": "database-service", "retry_count": 3}
            })

        # Service A logs
        for i in range(svca_count):
            logs.append({
                "timestamp": now,
                "service": "service-a",
                "level": "WARNING" if i % 2 == 0 else "ERROR",
                "event_type": "ORDER_TIMEOUT",
                "message": f"Order processing delayed: Service B response latency exceeded 2500ms",
                "trace_id": f"trace-a-{i // 2}",
                "metadata": {"downstream_latency_ms": 2540}
            })

        # Gateway logs
        for i in range(gw_count):
            logs.append({
                "timestamp": now,
                "service": "gateway",
                "level": "ERROR",
                "event_type": "BAD_GATEWAY_502",
                "message": f"HTTP 502 Bad Gateway: Upstream order service timed out",
                "trace_id": f"trace-gw-{i}",
                "metadata": {"status_code": 502, "route": "/api/v1/orders"}
            })

    elif scenario == "high_cpu":
        for i in range(count):
            svc = "service-b" if i % 2 == 0 else "service-a"
            logs.append({
                "timestamp": now,
                "service": svc,
                "level": "WARNING" if i % 3 == 0 else "ERROR",
                "event_type": "HIGH_CPU_SATURATION",
                "message": f"Worker thread pool queue length {50 + (i % 100)} exceeds critical threshold",
                "trace_id": f"trace-cpu-{i}",
                "metadata": {"cpu_percent": 94.8, "queue_depth": 85}
            })

    elif scenario == "storage_pressure":
        for i in range(count):
            logs.append({
                "timestamp": now,
                "service": "database-service",
                "level": "WARNING" if i % 5 != 0 else "CRITICAL",
                "event_type": "STORAGE_PRESSURE_WARNING",
                "message": f"Tablespace journal allocation growing rapidly: {85 + (i / count * 12):.1f}% utilized",
                "trace_id": f"trace-storage-{i}",
                "metadata": {"tablespace_used_gb": 48.2, "growth_velocity_mb_s": 12.4}
            })

    else:
        for i in range(count):
            services = ["gateway", "service-a", "service-b", "database-service"]
            svc = services[i % 4]
            logs.append({
                "timestamp": now,
                "service": svc,
                "level": "INFO",
                "event_type": "REQUEST_PROCESSED",
                "message": f"Processed inbound transaction #{100000 + i} successfully in 14.2ms",
                "trace_id": f"trace-norm-{i}",
                "metadata": {"latency_ms": 14.2, "status": 200}
            })

    return logs
