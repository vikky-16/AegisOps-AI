"""
LogHub Telemetry Streaming Replay Engine
Streams historical real-world LogHub telemetry into the common AegisOps ingestion pipeline
at controlled rates (100–1000 EPS) for 10K, 50K, 100K records.
"""

import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.loghub.parser import loghub_parser
from backend.app.loghub.models import LogHubReplayStatus
from backend.app.monitoring.collector import collector
from backend.app.logs.processor import log_processor
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetrySeverity


class LogHubReplayEngine:
    def __init__(self):
        self.status = "IDLE"  # IDLE, STREAMING, PAUSED, COMPLETED, ERROR
        self.selected_dataset = "HDFS"
        self.target_count = 100000
        self.configured_eps = 1000
        self.events_available = 0
        self.events_sent = 0
        self.events_received = 0
        self.events_processed = 0
        self.processing_rate = 0.0
        self.errors_count = 0
        self.anomalies_count = 0
        self.correlated_events_count = 0
        self.incidents_count = 0
        self.critical_incidents_count = 0

        self.start_time: Optional[float] = None
        self.pause_time: Optional[float] = None
        self.elapsed_seconds: float = 0.0
        
        self._streaming_task: Optional[asyncio.Task] = None
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._rate_meter: List[float] = []
        self._cached_records: Dict[str, List[NormalizedTelemetryEvent]] = {}

    def get_status(self) -> Dict[str, Any]:
        """Returns live replay engine status and all 10 diagnostic counters."""
        elapsed = 0.0
        if self.start_time:
            if self.status == "STREAMING":
                elapsed = time.time() - self.start_time
            else:
                elapsed = self.elapsed_seconds

        progress = round((self.events_processed / max(1, self.target_count)) * 100.0, 1)
        progress = min(100.0, progress)

        # Count live incidents from collector
        active_inc_count = len(collector.active_incidents)
        critical_inc_count = sum(1 for inc in collector.active_incidents if inc.get("severity") == "CRITICAL")

        return {
            "status": self.status,
            "dataset": self.selected_dataset,
            "events_available": self.events_available,
            "events_sent": self.events_sent,
            "events_received": self.events_received,
            "events_processed": self.events_processed,
            "processing_rate": self.processing_rate,
            "configured_eps": self.configured_eps,
            "target_count": self.target_count,
            "progress_percentage": progress,
            "elapsed_seconds": round(elapsed, 1),
            "errors": self.errors_count,
            "anomalies": self.anomalies_count,
            "correlated_events": self.correlated_events_count,
            "incidents": active_inc_count if active_inc_count > 0 else self.incidents_count,
            "critical_incidents": critical_inc_count if critical_inc_count > 0 else self.critical_incidents_count,
            "is_streaming": self.status == "STREAMING",
            "is_paused": self.status == "PAUSED"
        }

    async def start_replay(
        self,
        dataset: str = "HDFS",
        target_count: int = 100000,
        eps: int = 1000
    ) -> Dict[str, Any]:
        """Loads LogHub dataset records and begins asynchronous streaming."""
        if self._streaming_task and not self._streaming_task.done():
            self._streaming_task.cancel()

        self.selected_dataset = dataset
        self.target_count = target_count
        self.configured_eps = max(50, min(5000, eps))
        
        # Load or retrieve cached normalized records
        if dataset not in self._cached_records or not self._cached_records[dataset]:
            records = loghub_parser.load_dataset_records(dataset)
            self._cached_records[dataset] = records
        else:
            records = self._cached_records[dataset]

        self.events_available = len(records)
        if not records:
            self.status = "ERROR"
            return {"error": f"No raw records found for LogHub dataset '{dataset}'"}

        self.events_sent = 0
        self.events_received = 0
        self.events_processed = 0
        self.errors_count = 0
        self.anomalies_count = 0
        self.correlated_events_count = 0
        self.incidents_count = 0
        self.critical_incidents_count = 0
        self.start_time = time.time()
        self.elapsed_seconds = 0.0
        self.status = "STREAMING"
        self._pause_event.set()
        self._rate_meter = []

        collector.append_feed_event(
            phase="LOGHUB_REPLAY_STARTED",
            service=f"loghub-{dataset.lower()}",
            message=f"Started streaming {target_count:,} LogHub '{dataset}' records at {self.configured_eps} EPS.",
            severity="INFO"
        )

        self._streaming_task = asyncio.create_task(self._replay_loop(records))
        return self.get_status()

    def pause_replay(self) -> Dict[str, Any]:
        if self.status == "STREAMING":
            self.status = "PAUSED"
            self.pause_time = time.time()
            if self.start_time:
                self.elapsed_seconds += (self.pause_time - self.start_time)
            self._pause_event.clear()
            collector.append_feed_event(
                phase="LOGHUB_REPLAY_PAUSED",
                service=f"loghub-{self.selected_dataset.lower()}",
                message=f"LogHub replay paused at {self.events_processed:,} records.",
                severity="INFO"
            )
        return self.get_status()

    def resume_replay(self) -> Dict[str, Any]:
        if self.status == "PAUSED":
            self.status = "STREAMING"
            self.start_time = time.time()
            self._pause_event.set()
            collector.append_feed_event(
                phase="LOGHUB_REPLAY_RESUMED",
                service=f"loghub-{self.selected_dataset.lower()}",
                message=f"LogHub replay resumed towards {self.target_count:,} records.",
                severity="INFO"
            )
        return self.get_status()

    def stop_replay(self) -> Dict[str, Any]:
        if self._streaming_task and not self._streaming_task.done():
            self._streaming_task.cancel()
        self.status = "IDLE"
        self.processing_rate = 0.0
        collector.append_feed_event(
            phase="LOGHUB_REPLAY_STOPPED",
            service=f"loghub-{self.selected_dataset.lower()}",
            message="LogHub historical replay stopped by administrator.",
            severity="INFO"
        )
        return self.get_status()

    async def reset_replay_state(self) -> Dict[str, Any]:
        self.stop_replay()
        self.events_sent = 0
        self.events_received = 0
        self.events_processed = 0
        self.errors_count = 0
        self.anomalies_count = 0
        self.correlated_events_count = 0
        self.incidents_count = 0
        self.critical_incidents_count = 0
        self.start_time = None
        self.elapsed_seconds = 0.0

        collector.active_incidents = []
        collector.pending_approvals = []
        collector.system_health_score = 100.0
        await log_processor.clear_buffer()

        collector.append_feed_event(
            phase="LOGHUB_STATE_RESET",
            service="loghub-engine",
            message="LogHub replay state and telemetry buffer reset successfully.",
            severity="INFO"
        )
        return {"success": True, "message": "LogHub replay state reset successfully."}

    async def _replay_loop(self, base_records: List[NormalizedTelemetryEvent]):
        """Streams records in micro-batches to achieve target EPS without freezing event loop."""
        num_base = len(base_records)
        batch_size = max(10, min(250, self.configured_eps // 4))
        sleep_interval = batch_size / self.configured_eps

        try:
            while self.events_processed < self.target_count:
                await self._pause_event.wait()

                batch_start = time.time()
                remaining = self.target_count - self.events_processed
                curr_batch_size = min(batch_size, remaining)

                batch_events: List[NormalizedTelemetryEvent] = []
                log_dicts: List[Dict[str, Any]] = []

                now_iso = datetime.now(timezone.utc).isoformat()

                for i in range(curr_batch_size):
                    base_idx = (self.events_processed + i) % num_base
                    base_evt = base_records[base_idx]

                    # Clone and stamp current replay time
                    cloned_evt = NormalizedTelemetryEvent(
                        timestamp=now_iso,
                        source=base_evt.source,
                        environment="loghub-historical",
                        service=base_evt.service,
                        type=base_evt.type,
                        severity=base_evt.severity,
                        event_type=base_evt.event_type,
                        message=base_evt.message,
                        trace_id=base_evt.trace_id,
                        host=base_evt.host,
                        metrics=base_evt.metrics,
                        metadata=base_evt.metadata
                    )
                    batch_events.append(cloned_evt)

                    log_dicts.append({
                        "timestamp": now_iso,
                        "service": cloned_evt.service,
                        "level": cloned_evt.severity.value,
                        "event_type": cloned_evt.event_type,
                        "message": cloned_evt.message,
                        "trace_id": cloned_evt.trace_id,
                        "metadata": cloned_evt.metadata
                    })

                self.events_sent += curr_batch_size
                self.events_received += curr_batch_size

                # 1. Ingest into high-speed log ring buffer
                await log_processor.ingest_batch(log_dicts)

                # 2. Ingest events into collector for anomaly & correlation stream
                for evt in batch_events:
                    is_err = evt.severity in [TelemetrySeverity.ERROR, TelemetrySeverity.CRITICAL]
                    if is_err:
                        self.errors_count += 1
                        self.anomalies_count += 1
                    
                    # Feed anomalies and sample of normal traffic into incident collector
                    if is_err or (self.events_processed % 20 == 0):
                        collector.ingest_normalized_event(evt)
                        self.correlated_events_count += 1

                self.events_processed += curr_batch_size

                now = time.time()
                self._rate_meter.append(now)
                self._rate_meter = [t for t in self._rate_meter if now - t <= 5.0]
                self.processing_rate = round((len(self._rate_meter) * curr_batch_size) / max(1.0, (now - self._rate_meter[0] + 0.1)), 1) if len(self._rate_meter) > 1 else float(self.configured_eps)

                batch_elapsed = time.time() - batch_start
                sleep_time = max(0.005, sleep_interval - batch_elapsed)
                await asyncio.sleep(sleep_time)

            self.status = "COMPLETED"
            self.processing_rate = 0.0
            collector.append_feed_event(
                phase="LOGHUB_REPLAY_COMPLETED",
                service=f"loghub-{self.selected_dataset.lower()}",
                message=f"Completed streaming all {self.target_count:,} LogHub '{self.selected_dataset}' records.",
                severity="INFO"
            )

        except asyncio.CancelledError:
            self.status = "IDLE"
        except Exception as e:
            self.status = "ERROR"
            collector.append_feed_event(
                phase="LOGHUB_REPLAY_ERROR",
                service="loghub-engine",
                message=f"LogHub replay exception: {str(e)}",
                severity="CRITICAL"
            )


# Global singleton replay engine
loghub_engine = LogHubReplayEngine()
