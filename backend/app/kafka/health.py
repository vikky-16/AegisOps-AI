"""
AegisOps AI - Kafka Health & Metrics Tracker
Exposes real-time throughput, lag, error counts, and connection health metrics.
"""

import time
from typing import Dict, Any, List
from collections import deque
from datetime import datetime, timezone


class KafkaHealthTracker:
    def __init__(self):
        self.is_connected = False
        self.broker_url = "localhost:9092"
        self.events_received = 0
        self.events_processed = 0
        self.events_failed = 0
        self.events_dropped = 0
        self.consumer_lag = 0
        self.last_event_timestamp = None
        self.recent_latencies: deque = deque(maxlen=200)
        self.start_time = time.time()
        self.status_state = "STANDBY"  # CONNECTED, STANDBY, DEGRADED, OFFLINE

    def record_received(self, count: int = 1):
        self.events_received += count
        self.last_event_timestamp = datetime.now(timezone.utc).isoformat()

    def record_processed(self, count: int = 1, latency_ms: float = 0.0):
        self.events_processed += count
        self.recent_latencies.append(latency_ms)

    def record_failed(self, count: int = 1):
        self.events_failed += count

    def record_dropped(self, count: int = 1):
        self.events_dropped += count

    def set_lag(self, lag: int):
        self.consumer_lag = max(0, lag)

    def set_connection_status(self, connected: bool, broker: str = "localhost:9092"):
        self.is_connected = connected
        self.broker_url = broker
        self.status_state = "CONNECTED" if connected else "STANDBY"

    def get_metrics_summary(self) -> Dict[str, Any]:
        lats = list(self.recent_latencies) or [0.5]
        avg_lat = sum(lats) / len(lats)
        sorted_lats = sorted(lats)
        p95_lat = sorted_lats[int(len(sorted_lats) * 0.95)] if sorted_lats else 0.5
        
        uptime_sec = max(1.0, time.time() - self.start_time)
        throughput_eps = round(self.events_processed / uptime_sec, 2)
        throughput_epm = round(throughput_eps * 60, 1)
        bytes_sec = round(throughput_eps * 512, 1)  # Average telemetry event size ~512 bytes

        return {
            "status": self.status_state,
            "is_connected": self.is_connected,
            "broker_url": self.broker_url,
            "events_received": self.events_received,
            "events_processed": self.events_processed,
            "events_failed": self.events_failed,
            "events_dropped": self.events_dropped,
            "consumer_lag": self.consumer_lag,
            "avg_processing_latency_ms": round(avg_lat, 2),
            "p95_processing_latency_ms": round(p95_lat, 2),
            "throughput_events_per_sec": throughput_eps,
            "throughput_events_per_min": throughput_epm,
            "throughput_bytes_per_sec": bytes_sec,
            "last_event_timestamp": self.last_event_timestamp,
            "uptime_seconds": round(uptime_sec, 1)
        }


kafka_health_tracker = KafkaHealthTracker()
