"""
Central Monitoring & Real-Time AIOps Orchestrator Collector Loop
Consumes normalized telemetry streams, detects anomalies, correlates multi-service cascades,
executes declarative runbooks or requests approval, verifies recovery, and broadcasts live feeds.
"""

import os
import time
import asyncio
import httpx
import psutil
from collections import deque
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.core.config import settings
from backend.app.ai.model_manager import model_manager
from backend.app.rca.dynamic_graph import dynamic_graph
from backend.app.incidents.signature_normalizer import signature_normalizer
from backend.app.incidents.correlator import EventCorrelator
from backend.app.incidents.incident_manager import IncidentManager
from backend.app.healing.recommender import recommender
from backend.app.healing.executor import executor
from backend.app.healing.verifier import verifier
from backend.app.runbooks.engine import runbook_engine
from backend.app.storage.manager import storage_manager
from backend.app.knowledge.engine import knowledge_engine
from backend.app.api.websocket import ws_manager
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetrySeverity
from backend.app.schemas.telemetry_contract import UnifiedTelemetryEvent
from backend.app.kafka.event_bus import event_bus
from backend.app.kafka.health import kafka_health_tracker
from backend.app.ai.baselines import baseline_manager
from backend.app.ai.detectors.multi_detector_engine import multi_detector_engine
from backend.app.healing.decision_engine import decision_engine
from backend.app.monitoring.continuous_telemetry import continuous_telemetry
from backend.app.monitoring.failure_scheduler import failure_scheduler

SERVICES_CONFIG = [
    {"name": "gateway", "display_name": "API Gateway / Ingress", "port": 8001, "url": settings.GATEWAY_URL, "role": "Ingress & Routing", "criticality": "CRITICAL"},
    {"name": "service-a", "display_name": "Order Service A", "port": 8002, "url": settings.SERVICE_A_URL, "role": "Order Processing", "criticality": "HIGH"},
    {"name": "service-b", "display_name": "Payment Service B", "port": 8003, "url": settings.SERVICE_B_URL, "role": "Payment & Ledger", "criticality": "CRITICAL"},
    {"name": "database-service", "display_name": "Database Persistence", "port": 8004, "url": settings.DATABASE_SERVICE_URL, "role": "Distributed Persistence", "criticality": "CRITICAL"},
    {"name": "auth-service", "display_name": "Authentication & Sessions", "port": 8005, "url": settings.AUTH_SERVICE_URL, "role": "Identity & Tokens", "criticality": "CRITICAL"},
]


class MonitoringCollector:
    def __init__(self):
        self.is_running = False
        self.interval_sec = settings.MONITORING_INTERVAL_SEC
        self.correlator = EventCorrelator(window_sec=settings.CORRELATION_WINDOW_SEC)
        self.environment_mode = "DEMO"  # DEMO, STAGING, PRODUCTION-CONNECTED
        
        # In-memory operational store
        self.latest_metrics: Dict[str, Dict[str, Any]] = {}
        self.latest_health: Dict[str, Dict[str, Any]] = {}
        self.metric_history: Dict[str, List[Dict[str, Any]]] = {s["name"]: [] for s in SERVICES_CONFIG}
        
        self.active_incidents: List[Dict[str, Any]] = []
        self.resolved_incidents: List[Dict[str, Any]] = []
        self.pending_approvals: List[Dict[str, Any]] = []
        self.reviewed_approvals: List[Dict[str, Any]] = []
        self.recovery_history: List[Dict[str, Any]] = []
        self.audit_logs: List[Dict[str, Any]] = []
        
        # Real-time Operations Center Event Feed (rolling 150 events)
        self.live_operations_feed: deque = deque(maxlen=150)
        
        self.system_health_score: float = 100.0
        self.last_tick_time: float = time.time()
        self.iteration_count: int = 0
        self.operating_mode: str = "CONTROLLED_DEMO"  # "CONTROLLED_DEMO" or "LIVE_STREAM"

        # Wire Continuous Telemetry Generator callback
        continuous_telemetry.register_collector_callback(self.handle_continuous_telemetry_event)

        # Wire Kafka / EventBus streaming callback
        event_bus.subscribe(self.ingest_unified_event)

        self.append_feed_event(
            phase="SYSTEM_STARTUP",
            service="orchestrator",
            message="AegisOps AI Real-Time Orchestrator initialized. Kafka & OpenTelemetry streaming active.",
            severity="INFO"
        )

    def append_feed_event(
        self,
        phase: str,
        service: str,
        message: str,
        severity: str = "INFO",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Appends a timestamped operational event to the real-time Operations Center ticker."""
        event_obj = {
            "id": f"evt-{int(time.time()*1000)}-{len(self.live_operations_feed)}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "time_display": datetime.now().strftime("%H:%M:%S"),
            "phase": phase,
            "service": service,
            "message": message,
            "severity": severity,
            "metadata": metadata or {}
        }
        self.live_operations_feed.appendleft(event_obj)

    def ingest_unified_event(self, event: UnifiedTelemetryEvent):
        """Processes unified telemetry events from Kafka, OpenTelemetry Collector, or REST ingestion."""
        now_iso = datetime.now(timezone.utc).isoformat()
        svc = event.service_name
        sev = event.severity.upper()

        # Append to live Operations Center feed
        self.append_feed_event(
            phase="TELEMETRY_STREAM",
            service=svc,
            message=f"[{event.source.upper()}] {event.event_type}: {event.message[:90] if event.message else f'Metric {event.metric_name}={event.metric_value}'}",
            severity=sev,
            metadata={"source": event.source, "trace_id": event.trace_id, "span_id": event.span_id}
        )

        # Record metric into baseline manager
        if event.metric_name and event.metric_value is not None:
            baseline_manager.record_sample(svc, event.metric_name, event.metric_value)

        # Record into multi-window feature extractor and error pattern tracker (< 0.05ms)
        try:
            from backend.app.analytics.incident_pipeline import incident_pipeline
            incident_pipeline.record_telemetry_event(event)
        except Exception:
            pass


    def ingest_normalized_event(self, event: NormalizedTelemetryEvent):
        """Receives normalized telemetry from any authorized connector and evaluates it."""
        now_iso = datetime.now(timezone.utc).isoformat()
        svc = event.service
        
        self.append_feed_event(
            phase="TELEMETRY_INGESTED",
            service=svc,
            message=f"[{event.type}] {event.event_type}: {event.message[:90]}",
            severity=event.severity.value,
            metadata={"source": event.source, "trace_id": event.trace_id}
        )

        # If abnormal, trigger immediate incident evaluation cycle
        if event.severity in [TelemetrySeverity.ERROR, TelemetrySeverity.CRITICAL]:
            self.append_feed_event(
                phase="ANOMALY_SIGNAL",
                service=svc,
                message=f"Abnormal signal detected on '{svc}' ({event.event_type}). Correlating dependencies.",
                severity="WARNING"
            )
            # Add to correlator
            self.correlator.add_event({
                "timestamp": now_iso,
                "service_name": svc,
                "event_type": event.event_type,
                "severity": event.severity.value,
                "message": event.message
            })

    def handle_continuous_telemetry_event(self, event: Any):
        """Processes continuous real-time telemetry events from the backend generator into the incident pipeline."""
        if isinstance(event, dict):
            svc_name = event.get("service", "database-service")
            sev_raw = event.get("severity", "INFO")
            try:
                sev_enum = TelemetrySeverity(sev_raw.upper()) if isinstance(sev_raw, str) else sev_raw
            except Exception:
                sev_enum = TelemetrySeverity.INFO
            event = NormalizedTelemetryEvent(
                tenant_id=event.get("tenant_id", "demo-tenant"),
                service=svc_name,
                severity=sev_enum,
                message=event.get("message", f"Continuous telemetry on {svc_name}"),
                latency_ms=float(event.get("latency_ms") or event.get("p95_latency") or 0.0)
            )
        svc = event.service
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Non-blocking ingestion into sliding feature window and baseline engine (Req 5, 6, 7)
        try:
            from backend.app.analytics.incident_pipeline import incident_pipeline
            incident_pipeline.record_telemetry_event(event)
        except Exception:
            pass

        if getattr(event, "latency_ms", None) is not None:
            baseline_manager.record_sample(svc, "latency_ms", float(event.latency_ms))

        # Evaluate Early Warning on error/critical events (Req 4, 24)
        if event.severity in [TelemetrySeverity.ERROR, TelemetrySeverity.CRITICAL]:
            try:
                from backend.app.analytics.early_warning import early_warning_engine
                early_warning_engine.evaluate_telemetry(
                    tenant_id=getattr(event, "tenant_id", "demo-tenant") or "demo-tenant",
                    service=svc,
                    features={
                        "error_rate": 0.45,
                        "p95_latency": float(getattr(event, "latency_ms", 2500) or 2500),
                        "latency_p95_ms": float(getattr(event, "latency_ms", 2500) or 2500),
                        "cpu_percent": 85.0 if "cpu" in str(event.event_type).lower() else 25.0
                    },
                    raw_attributes={"active_connections": 50, "max_pool_size": 50} if "database" in svc or "pool" in str(event.message).lower() else {}
                )
            except Exception:
                pass

        # If abnormal error, record anomaly signal into activity feed
        if event.severity in [TelemetrySeverity.ERROR, TelemetrySeverity.CRITICAL]:
            self.append_feed_event(
                phase="ANOMALY_SIGNAL",
                service=svc,
                message=f"[{event.type}] {event.event_type} on '{svc}': {event.message[:85]}",
                severity="CRITICAL" if event.severity == TelemetrySeverity.CRITICAL else "WARNING"
            )

            self.correlator.add_event({
                "timestamp": now_iso,
                "service": svc,
                "event_type": event.event_type,
                "message": event.message,
                "severity": event.severity.value,
                "metadata": event.metadata
            })

            # Check if event matches an existing active incident cluster
            matched_inc_id = self.correlator.find_matching_incident(
                service_name=svc,
                active_incidents=self.active_incidents,
                event_dict={"service_name": svc, "message": event.message, "severity": event.severity.value, "timestamp": now_iso}
            )
            matched_inc = next((i for i in self.active_incidents if i["incident_id"] == matched_inc_id), None) if matched_inc_id else None

            if matched_inc:
                self.correlator.merge_event_into_incident(
                    incident=matched_inc,
                    new_service=svc,
                    event_entry={"timestamp": now_iso, "message": event.message, "event_type": event.event_type, "severity": event.severity.value},
                    event_count=1
                )
                self.append_feed_event(
                    phase="CASCADE_CORRELATED",
                    service=svc,
                    message=f"Cascade event linked to active incident {matched_inc['incident_id']} (Total: {matched_inc['correlated_event_count']:,} events).",
                    severity="WARNING"
                )
            else:
                # Create correlated incident with RCA and declarative runbook recommendation
                new_inc = IncidentManager.create_incident_from_anomaly(
                    service_name=svc,
                    anomaly_score=0.92,
                    evidence=[f"Critical error pattern '{event.event_type}' detected on {svc}", event.message],
                    events=[{
                        "timestamp": now_iso,
                        "service_name": svc,
                        "event_type": event.event_type,
                        "severity": event.severity.value,
                        "message": event.message
                    }],
                    metrics_snapshot=self.latest_metrics
                )
                rec_result = recommender.recommend_remedy(
                    incident=new_inc,
                    history=self.recovery_history
                )
                new_inc["recommended_action"] = rec_result["primary_action"]
                new_inc["alternative_action"] = rec_result["alternative_action"]
                new_inc["action_risk_level"] = rec_result["risk_assessment"]["risk_level"]
                self.active_incidents.append(new_inc)

                self.append_feed_event(
                    phase="INCIDENT_CREATED",
                    service=svc,
                    message=f"Incident {new_inc['incident_id']} opened ({new_inc['severity']}). Root cause candidate: '{new_inc['root_cause_service']}'.",
                    severity="CRITICAL"
                )

                # Incident registered in open investigating state; approvals are created only when a solution is selected
                new_inc["status"] = "OPEN"
                new_inc["lifecycle_state"] = "INVESTIGATING"
                new_inc["recovery_status"] = "PENDING_SOLUTION_SELECTION"
                self.append_feed_event(
                    phase="INVESTIGATION_READY",
                    service=new_inc["root_cause_service"],
                    message=f"Root cause candidate '{new_inc['root_cause_service']}' identified. Awaiting SRE review and solution selection.",
                    severity="INFO"
                )

    async def start(self):
        self.is_running = True
        try:
            from backend.app.healing.persistence import sync_history_from_db
            await sync_history_from_db()
        except Exception as exc:
            pass

        # Start event bus, continuous telemetry engine and failure scheduler
        await event_bus.start()
        await continuous_telemetry.start()
        await failure_scheduler.start()
        
        while self.is_running:
            try:
                await self.poll_cycle()
            except Exception:
                pass
            await asyncio.sleep(self.interval_sec)

    def stop(self):
        self.is_running = False
        asyncio.create_task(event_bus.stop())
        asyncio.create_task(continuous_telemetry.stop())
        asyncio.create_task(failure_scheduler.stop())

    async def poll_cycle(self):
        self.iteration_count += 1
        now_iso = datetime.now(timezone.utc).isoformat()
        cycle_anomalies = []
        cycle_events = []
        
        # 1. Probe microservices concurrently with fast non-blocking timeout
        async def _probe_service(s, client):
            name = s["name"]
            url = s["url"]
            try:
                h_resp = await client.get(f"{url}/health", timeout=0.25)
                h_data = h_resp.json() if h_resp.status_code == 200 else {"status": "DOWN", "healthy": False, "state": "UNHEALTHY"}
                is_up = h_data.get("healthy", False) and h_data.get("state") != "CRASHED"
                try:
                    m_resp = await client.get(f"{url}/metrics", timeout=0.25)
                    m_data = m_resp.json() if m_resp.status_code == 200 else {
                        "service": name, "timestamp": now_iso, "cpu_percent": 0.0, "memory_mb": 0.0,
                        "request_count": 0, "error_count": 0 if is_up else 1, "error_rate": 0.0 if is_up else 1.0,
                        "latency_p50_ms": 0.0, "latency_p95_ms": 0.0, "active_connections": 0
                    }
                except Exception:
                    m_data = {
                        "service": name, "timestamp": now_iso, "cpu_percent": 0.0, "memory_mb": 0.0,
                        "request_count": 0, "error_count": 0 if is_up else 1, "error_rate": 0.0 if is_up else 1.0,
                        "latency_p50_ms": 0.0, "latency_p95_ms": 0.0, "active_connections": 0
                    }
            except Exception:
                h_data = {"status": "DOWN", "healthy": False, "state": "CRASHED"}
                m_data = {
                    "service": name, "timestamp": now_iso, "cpu_percent": 0.0, "memory_mb": 0.0,
                    "request_count": 0, "error_count": 1, "error_rate": 1.0,
                    "latency_p50_ms": 0.0, "latency_p95_ms": 0.0, "active_connections": 0
                }
            return name, h_data, m_data

        async with httpx.AsyncClient() as client:
            probe_results = await asyncio.gather(*[_probe_service(s, client) for s in SERVICES_CONFIG], return_exceptions=True)
            for res in probe_results:
                if isinstance(res, Exception):
                    continue
                name, h_data, m_data = res
                self.latest_health[name] = h_data
                self.latest_metrics[name] = m_data
                dynamic_graph.update_service_health(name, h_data.get("state", "HEALTHY"))

                # Sync to canonical state engine
                try:
                    from backend.app.services.canonical_state import canonical_state_manager
                    canonical_state_manager.update_probe_health(
                        tenant_id="shopsphere",
                        service_name=name,
                        healthy=h_data.get("healthy", True),
                        state=h_data.get("state", "HEALTHY")
                    )
                    canonical_state_manager.record_telemetry(
                        tenant_id="shopsphere",
                        service_name=name,
                        latency_ms=m_data.get("latency_p50_ms"),
                        is_error=(m_data.get("error_rate", 0.0) > 0.05),
                        cpu_percent=m_data.get("cpu_percent"),
                        memory_mb=m_data.get("memory_mb")
                    )
                except Exception:
                    pass

                # 2. Run AI Anomaly Detection
                is_anom, anom_score, evidence = model_manager.evaluate_telemetry(name, m_data)
                if not h_data.get("healthy", True) or h_data.get("state") in ["CRASHED", "UNHEALTHY"]:
                    is_anom = True
                    anom_score = max(anom_score, 0.95)
                    evidence.append(f"Service '{name}' reported state '{h_data.get('state', 'CRASHED')}'")

                m_data["anomaly_score"] = anom_score
                m_data["is_anomaly"] = 1 if is_anom else 0
                
                self.metric_history[name].append(m_data)
                if len(self.metric_history[name]) > 60:
                    self.metric_history[name].pop(0)

                if is_anom:
                    cycle_anomalies.append((name, anom_score, evidence))
                    cycle_events.append({
                        "timestamp": now_iso,
                        "service_name": name,
                        "event_type": "METRIC_ANOMALY" if is_up else "SERVICE_CRASHED",
                        "severity": "CRITICAL" if not is_up or anom_score > 0.8 else "WARNING",
                        "message": f"Anomaly detected on {name} (score={anom_score:.2f})"
                    })
                    self.correlator.add_event(cycle_events[-1])

        # 3. Calculate Aggregated Health Score (Single Source of Truth)
        try:
            from backend.app.services.canonical_state import canonical_state_manager
            health_eval = canonical_state_manager.compute_system_health(
                tenant_id="shopsphere",
                active_incidents=self.active_incidents
            )
            self.system_health_score = health_eval["health_score"]
        except Exception:
            healthy_count = sum(1 for h in self.latest_health.values() if h.get("healthy", False))
            total_services = len(SERVICES_CONFIG)
            base_health = (healthy_count / total_services) * 100.0 if total_services > 0 else 100.0
            avg_anom = sum(m.get("anomaly_score", 0.0) for m in self.latest_metrics.values()) / total_services if total_services > 0 else 0.0
            self.system_health_score = round(max(0.0, base_health - (avg_anom * 40.0)), 1)

        # 4. Incident Creation, Correlation & RCA
        if cycle_anomalies:
            for svc_name, anom_score, ev_list in cycle_anomalies:
                matched_incident_id = self.correlator.find_matching_incident(
                    service_name=svc_name,
                    active_incidents=self.active_incidents,
                    event_dict={"service_name": svc_name, "message": f"Anomaly detected on {svc_name}", "timestamp": now_iso}
                )
                matched_incident = next((i for i in self.active_incidents if i["incident_id"] == matched_incident_id), None) if matched_incident_id else None
                
                if matched_incident:
                    self.correlator.merge_event_into_incident(
                        incident=matched_incident,
                        new_service=svc_name,
                        event_entry={"timestamp": now_iso, "message": f"Cascading degradation on {svc_name}", "event_type": "CASCADE_ANOMALY"},
                        event_count=len(cycle_events)
                    )
                    self.append_feed_event(
                        phase="CASCADE_CORRELATED",
                        service=svc_name,
                        message=f"Cascade anomaly linked to active incident {matched_incident['incident_id']} (Total: {matched_incident['correlated_event_count']:,} events).",
                        severity="WARNING"
                    )
                else:
                    # Create New Incident
                    new_inc = IncidentManager.create_incident_from_anomaly(
                        service_name=svc_name,
                        anomaly_score=anom_score,
                        evidence=ev_list,
                        events=cycle_events,
                        metrics_snapshot=self.latest_metrics
                    )
                    
                    # Generate AI Recommendation using Declarative Runbooks
                    rec_result = recommender.recommend_remedy(
                        incident=new_inc,
                        history=self.recovery_history
                    )
                    new_inc["recommended_action"] = rec_result["primary_action"]
                    new_inc["alternative_action"] = rec_result["alternative_action"]
                    new_inc["action_risk_level"] = rec_result["risk_assessment"]["risk_level"]
                    
                    self.active_incidents.append(new_inc)

                    self.append_feed_event(
                        phase="INCIDENT_CREATED",
                        service=svc_name,
                        message=f"Incident {new_inc['incident_id']} opened ({new_inc['severity']}). RCA isolating root cause.",
                        severity="CRITICAL" if new_inc["severity"] == "CRITICAL" else "WARNING"
                    )

                    self.append_feed_event(
                        phase="RCA_EVALUATED",
                        service=new_inc["root_cause_service"],
                        message=f"RCA identified '{new_inc['root_cause_service']}' ({new_inc['root_cause_category']}) as root cause ({int(new_inc['rca_confidence']*100)}% confidence).",
                        severity="INFO"
                    )

                    # Decision Gate: Low Risk -> Autonomous Runbook vs High Risk -> Human Approval
                    risk_lvl = rec_result["risk_assessment"]["risk_level"]
                    requires_approval = rec_result["risk_assessment"].get("approval_required") or rec_result["risk_assessment"].get("requires_human_approval", False)

                    if requires_approval or risk_lvl in ["HIGH", "CRITICAL"]:
                        new_inc["status"] = "AWAITING_APPROVAL"
                        new_inc["recovery_status"] = "PENDING_APPROVAL"
                        self._create_approval_ticket(new_inc, rec_result)
                        self.append_feed_event(
                            phase="APPROVAL_REQUIRED",
                            service=new_inc["root_cause_service"],
                            message=f"Action '{rec_result['primary_action']}' gated. Awaiting administrator authorization.",
                            severity="WARNING"
                        )
                    else:
                        new_inc["status"] = "REMEDIATING"
                        new_inc["recovery_status"] = "EXECUTING"
                        self.append_feed_event(
                            phase="RUNBOOK_EXECUTING",
                            service=new_inc["root_cause_service"],
                            message=f"Executing allowlisted runbook '{rec_result['primary_action']}' autonomously.",
                            severity="INFO"
                        )
                        asyncio.create_task(self._handle_autonomous_recovery(new_inc, rec_result["primary_action"]))

        # 5. Broadcast live telemetry state over WebSockets
        storage_status = storage_manager.get_storage_status()
        
        # Synchronize active incidents with incident_pipeline Coordinator
        try:
            from backend.app.analytics.incident_pipeline import incident_pipeline
            with incident_pipeline.lock:
                for inc_id, inc_obj in incident_pipeline._active_incidents.items():
                    if inc_obj.get("status") != "RESOLVED" and not any(i.get("incident_id") == inc_id for i in self.active_incidents):
                        self.active_incidents.insert(0, inc_obj)
        except Exception:
            pass

        telemetry_payload = {
            "type": "TELEMETRY_UPDATE",
            "timestamp": now_iso,
            "health_score": self.system_health_score,
            "environment_mode": self.environment_mode,
            "operating_mode": self.operating_mode,
            "services": list(self.latest_metrics.values()),
            "services_health": self.latest_health,
            "active_incidents_count": len(self.active_incidents),
            "pending_approvals_count": len(self.pending_approvals),
            "storage_percentage": storage_status.get("used_percentage", 82.0),
            "storage_critical_hours": storage_status.get("predicted_critical_hours", 10.0),
            "live_feed": list(self.live_operations_feed)[:25],
            "host_cpu": psutil.cpu_percent(interval=None),
            "host_memory": psutil.virtual_memory().percent,
            "stream_status": {"mode": self.operating_mode, "status": "CONNECTED", "protocol": "OTLP/HTTP"},
            "kafka_status": kafka_health_tracker.get_metrics_summary(),
            "collector_status": {
                "status": "HEALTHY",
                "receivers": ["otlp/grpc:4317", "otlp/http:4318", "kafka:9092", "rest:/api/otel/*"],
                "batch_size": 256,
                "version": "1.0.0"
            },
            "continuous_telemetry": continuous_telemetry.get_status(),
            "failure_scheduler": failure_scheduler.get_status(),
            "diagnostics": continuous_telemetry.get_recent_diagnostics(25),
            "dependencies": dynamic_graph.get_topology_graph(),
            "active_incidents": self.active_incidents,
            "all_incidents": list(self.active_incidents + self.resolved_incidents),
            "baselines": baseline_manager.get_all_baselines()
        }
        await ws_manager.broadcast(telemetry_payload)

    def _create_approval_ticket(self, incident: Dict[str, Any], rec_result: Dict[str, Any]) -> Dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        approval_id = f"APP-{incident['incident_id'][-8:]}"
        
        existing = next((a for a in self.pending_approvals if a["approval_id"] == approval_id or a["incident_id"] == incident["incident_id"]), None)
        if existing:
            return existing

        failure_type = incident.get("failure_type") or incident.get("root_cause_category") or incident.get("title") or "SERVICE_ANOMALY"
        affected = incident.get("affected_services") or [incident.get("root_cause_service", "database-service")]
        blast_score = float(incident.get("business_impact_score", incident.get("blast_radius_score", 50.0)))
        blast_radius = incident.get("blast_radius") if isinstance(incident.get("blast_radius"), str) else (
            "CRITICAL" if blast_score >= 80 else "HIGH" if blast_score >= 50 else "MEDIUM"
        )
        conf_pct = int(float(incident.get("rca_confidence", incident.get("root_cause_confidence", 0.90))) * 100)
        hist_success = rec_result.get("historical_success") or "4/5 (80%)"
        exp_impact = rec_result.get("expected_impact") or (
            f"Remediation affects active traffic on '{incident.get('root_cause_service')}'. Requires human authorization."
        )
        rollback = rec_result.get("rollback_plan") or f"Execute rollback action '{rec_result.get('alternative_action', 'RESTART_SERVICE')}' if verification probe fails."

        problem_title = incident.get("title") or incident.get("root_cause_category") or "Database connection exhaustion"
        root_cause_svc = incident.get("root_cause_service") or incident.get("primary_service", "database-service")
        rec_action = rec_result["primary_action"]
        risk_lvl = rec_result["risk_assessment"]["risk_level"]
        exp_outcome = rec_result.get("expected_outcome") or "Database connectivity restored and latency normalized."

        recovery_proc = [
            "1. Confirm database health.",
            "2. Confirm connection exhaustion.",
            "3. Reset controlled connection pool.",
            "4. Restore affected service.",
            "5. Monitor database connections.",
            "6. Monitor HTTP error rate.",
            "7. Monitor latency.",
            "8. Verify successful requests.",
            "9. Check downstream services.",
            "10. Confirm no side effects."
        ]

        raw_evidence = incident.get("rca_evidence") or incident.get("evidence_items") or [
            "Database connection utilization reached abnormal threshold (>95%)",
            "Database query timeouts observed on database-service",
            "Downstream service HTTP requests failed with status 500",
            "Gateway error rate surged beyond 15% threshold"
        ]

        ticket = {
            "tenant_id": incident.get("tenant_id", "demo-tenant"),
            "approval_id": approval_id,
            "incident_id": incident["incident_id"],
            "severity": incident.get("severity", "HIGH"),
            "failure_type": failure_type,
            "problem": problem_title,
            "root_cause": root_cause_svc,
            "service_name": root_cause_svc,
            "affected_services": affected,
            "affected_services_count": len(affected),
            "blast_radius": blast_radius,
            "blast_radius_score": blast_score,
            "rca_confidence": conf_pct,
            "proposed_action": rec_action,
            "recommended_action": rec_action,
            "solution": rec_action,
            "alternative_action": rec_result.get("alternative_action", "RESTART_SERVICE"),
            "risk_level": risk_lvl,
            "risk_score": rec_result["risk_assessment"]["risk_score"],
            "historical_success": hist_success,
            "expected_impact": exp_impact,
            "expected_outcome": exp_outcome,
            "expected_result": exp_outcome,
            "verification_plan": "Compare pre/post error rate, latency, and database connections with active verification probes.",
            "recovery_procedure": recovery_proc,
            "evidence": raw_evidence,
            "estimated_downtime_sec": rec_result["risk_assessment"]["estimated_downtime_sec"],
            "rollback_plan": rollback,
            "status": "PENDING_APPROVAL",  # PENDING_APPROVAL, APPROVED, REJECTED, EXPIRED
            "reviewed_by": None,
            "review_notes": None,
            "created_at": now_iso
        }
        self.pending_approvals.append(ticket)
        
        self.audit_logs.append({
            "tenant_id": incident.get("tenant_id", "demo-tenant"),
            "timestamp": now_iso,
            "user_identifier": "AegisOps_Policy_Engine",
            "action": "APPROVAL_TICKET_GENERATED",
            "target_resource": approval_id,
            "details": f"Approval required for {rec_action} on {root_cause_svc} (Risk: {risk_lvl})"
        })
        return ticket

    def request_incident_approval(self, incident_id: str, requester: str = "Operator") -> Dict[str, Any]:
        """Transitions an incident to AWAITING_APPROVAL and generates an approval ticket."""
        now_iso = datetime.now(timezone.utc).isoformat()
        inc = next((i for i in self.active_incidents if i["incident_id"] == incident_id), None)
        if not inc:
            # Fallback 1: Check incident_pipeline coordinator memory
            try:
                from backend.app.analytics.incident_pipeline import incident_pipeline
                with incident_pipeline.lock:
                    if incident_id in incident_pipeline._active_incidents:
                        inc = incident_pipeline._active_incidents[incident_id]
                        if inc not in self.active_incidents:
                            self.active_incidents.insert(0, inc)
            except Exception:
                pass

        if not inc:
            if any(i["incident_id"] == incident_id for i in self.resolved_incidents):
                return {"success": False, "error": f"Incident {incident_id} is already resolved"}
            return {"success": False, "error": f"Incident {incident_id} not found"}

        if inc.get("status") == "RESOLVED":
            return {"success": False, "error": f"Incident {incident_id} is already resolved"}

        # Generate recommendation if not present
        rec_result = recommender.recommend_remedy(incident=inc, history=self.recovery_history)
        inc["recommended_action"] = rec_result["primary_action"]
        inc["alternative_action"] = rec_result["alternative_action"]
        inc["action_risk_level"] = rec_result["risk_assessment"]["risk_level"]
        inc["status"] = "AWAITING_APPROVAL"
        inc["lifecycle_state"] = "AWAITING_APPROVAL"
        inc["approval_status"] = "AWAITING_APPROVAL"
        inc["recovery_status"] = "PENDING_APPROVAL"

        ticket = self._create_approval_ticket(inc, rec_result)

        if "timeline" not in inc:
            inc["timeline"] = []
        inc["timeline"].append({
            "timestamp": now_iso,
            "service": inc.get("root_cause_service", inc.get("primary_service", "database-service")),
            "type": "APPROVAL_REQUESTED",
            "message": f"Review & Approval requested by {requester} for '{inc['recommended_action']}' ({inc['action_risk_level']} Risk)."
        })

        self.append_feed_event(
            phase="APPROVAL_REQUIRED",
            service=inc.get("root_cause_service", inc.get("primary_service", "database-service")),
            message=f"High-risk action '{inc['recommended_action']}' gated. Awaiting authorization (Ticket: {ticket['approval_id']}).",
            severity="WARNING"
        )

        # Synchronize with incident_pipeline coordinator
        try:
            from backend.app.analytics.incident_pipeline import incident_pipeline
            with incident_pipeline.lock:
                if incident_id in incident_pipeline._active_incidents:
                    incident_pipeline._active_incidents[incident_id].update({
                        "status": "AWAITING_APPROVAL",
                        "lifecycle_state": "AWAITING_APPROVAL",
                        "approval_status": "AWAITING_APPROVAL",
                        "recommended_action": inc.get("recommended_action"),
                        "action_risk_level": inc.get("action_risk_level")
                    })
        except Exception:
            pass

        # Broadcast real-time approval requirement & incident update to all connected UI clients
        try:
            import asyncio
            from backend.app.api.websocket import ws_manager
            asyncio.create_task(ws_manager.broadcast({
                "type": "approval.required",
                "approval_id": ticket["approval_id"],
                "incident_id": inc["incident_id"],
                "ticket": ticket,
                "incident": inc,
                "timestamp": now_iso
            }))
            asyncio.create_task(ws_manager.broadcast({
                "type": "INCIDENT_UPDATED",
                "event_type": "INCIDENT_UPDATED",
                "incident": inc,
                "active_incidents": self.active_incidents,
                "timestamp": now_iso
            }))
        except Exception:
            pass

        return {"success": True, "incident": inc, "approval_id": ticket["approval_id"], "ticket": ticket}

    async def execute_approved_action(
        self,
        approval_id: str,
        decision: str,
        reviewer: str = "admin",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Executes administrator approved recovery action with strict validation and multi-point verification probe."""
        now_iso = datetime.now(timezone.utc).isoformat()
        
        ticket = next((a for a in self.pending_approvals if a["approval_id"] == approval_id), None)
        if not ticket:
            reviewed = next((a for a in self.reviewed_approvals if a["approval_id"] == approval_id), None)
            if reviewed:
                if reviewed.get("status") == "APPROVED":
                    return {"success": False, "error": f"Approval ticket {approval_id} has already been approved"}
                if reviewed.get("status") == "REJECTED":
                    return {"success": False, "error": f"Approval ticket {approval_id} was rejected and cannot be approved"}
                if reviewed.get("status") == "EXPIRED":
                    return {"success": False, "error": f"Approval ticket {approval_id} has expired"}
            return {"success": False, "error": f"Approval ticket {approval_id} not found"}

        # Validate that associated incident is not already resolved
        inc = next((i for i in self.active_incidents if i["incident_id"] == ticket["incident_id"]), None)
        if not inc:
            try:
                from backend.app.analytics.incident_pipeline import incident_pipeline
                with incident_pipeline.lock:
                    if ticket["incident_id"] in incident_pipeline._active_incidents:
                        inc = incident_pipeline._active_incidents[ticket["incident_id"]]
                        if inc not in self.active_incidents:
                            self.active_incidents.insert(0, inc)
            except Exception:
                pass

        if not inc:
            if any(i["incident_id"] == ticket["incident_id"] for i in self.resolved_incidents):
                return {"success": False, "error": "Incident is already resolved and cannot be approved"}

        ticket["status"] = decision
        ticket["decision"] = decision
        ticket["reviewed_by"] = reviewer
        ticket["review_notes"] = notes
        ticket["reviewed_at"] = now_iso
        
        self.pending_approvals = [a for a in self.pending_approvals if a["approval_id"] != approval_id]
        self.reviewed_approvals.insert(0, ticket)

        self.audit_logs.append({
            "timestamp": now_iso,
            "user_identifier": reviewer,
            "action": f"APPROVAL_{decision}",
            "target_resource": approval_id,
            "details": f"Decision '{decision}' on action '{ticket['proposed_action']}' for {ticket['service_name']}. Notes: {notes or 'N/A'}"
        })

        if decision == "APPROVED":
            self.append_feed_event(
                phase="APPROVAL_GRANTED",
                service=ticket["service_name"],
                message=f"Administrator ({reviewer}) approved action '{ticket['proposed_action']}'. Executing runbook.",
                severity="INFO"
            )
            # Find matching incident
            inc = next((i for i in self.active_incidents if i["incident_id"] == ticket["incident_id"]), None)
            if inc:
                inc["status"] = "APPROVED"
                inc["approval_status"] = "APPROVED"
                inc["remediation_status"] = "EXECUTING"
                inc["timeline"].append({
                    "timestamp": now_iso,
                    "service": ticket["service_name"],
                    "type": "APPROVAL_GRANTED",
                    "message": f"Action '{ticket['proposed_action']}' approved by {reviewer}. Decision: APPROVED."
                })
                inc["timeline"].append({
                    "timestamp": now_iso,
                    "service": ticket["service_name"],
                    "type": "REMEDIATING",
                    "message": f"Executing predefined runbook for '{ticket['proposed_action']}'."
                })

            # Broadcast approval event
            try:
                from backend.app.api.websocket import ws_manager
                await ws_manager.broadcast({
                    "type": "approval.approved",
                    "approval_id": approval_id,
                    "incident_id": ticket["incident_id"],
                    "service": ticket["service_name"],
                    "action": ticket["proposed_action"],
                    "reviewer": reviewer,
                    "timestamp": now_iso
                })
            except Exception:
                pass

            # Capture BEFORE Metric Snapshot (Requirement 18 & 19)
            affected_svcs = inc.get("affected_services", []) if inc else []
            before_snapshot = await verifier.capture_metric_snapshot(ticket["service_name"], affected_svcs)
            if inc:
                inc["before_snapshot"] = before_snapshot

            # Broadcast recovery started event
            try:
                from backend.app.api.websocket import ws_manager
                await ws_manager.broadcast({
                    "type": "recovery.started",
                    "incident_id": ticket["incident_id"],
                    "service": ticket["service_name"],
                    "action": ticket["proposed_action"],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            except Exception:
                pass

            # Execute runbook
            exec_res = await executor.execute_action(ticket["service_name"], ticket["proposed_action"])
            exec_ok = bool(exec_res.get("success", False))

            # Broadcast recovery completed
            try:
                from backend.app.api.websocket import ws_manager
                await ws_manager.broadcast({
                    "type": "recovery.completed",
                    "incident_id": ticket["incident_id"],
                    "service": ticket["service_name"],
                    "action": ticket["proposed_action"],
                    "success": exec_ok,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            except Exception:
                pass

            if exec_ok:
                # Lifecycle Path: EXECUTION_SUCCESS -> VERIFYING -> Active probe comparison -> VERIFIED -> RESOLVED
                if inc:
                    inc["remediation_status"] = "EXECUTION_SUCCESS"
                    inc["status"] = "VERIFYING"
                    inc["verification_status"] = "WAITING_FOR_ACTIVE_PROBE"
                    inc["timeline"].append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "service": ticket["service_name"],
                        "type": "EXECUTION_SUCCESS",
                        "message": f"Remediation action '{ticket['proposed_action']}' executed successfully. Initiating Multi-Point Active Verification with Comparative Metrics."
                    })

                # Broadcast verification started
                try:
                    from backend.app.api.websocket import ws_manager
                    await ws_manager.broadcast({
                        "type": "verification.started",
                        "incident_id": ticket["incident_id"],
                        "service": ticket["service_name"],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                except Exception:
                    pass

                # Verify recovery against active probes & compare before vs after (Requirement 18 & 19)
                verif_res = await verifier.verify_recovery(
                    target_service=ticket["service_name"],
                    affected_services=affected_svcs,
                    probe_delay_sec=1.0,
                    before_snapshot=before_snapshot
                )
                verif_ok = bool(verif_res.get("verified", False))

                if verif_ok:
                    if inc:
                        inc["status"] = "RESOLVED"
                        inc["recovery_status"] = "SUCCESS"
                        inc["remediation_status"] = "EXECUTION_SUCCESS"
                        inc["verification_status"] = "VERIFIED"
                        inc["resolved_at"] = datetime.now(timezone.utc).isoformat()
                        inc["after_snapshot"] = verif_res.get("after_snapshot")
                        inc["metric_comparison"] = verif_res.get("comparison")
                        inc["validation_criteria"] = verif_res.get("validation_criteria")
                        inc["workflow_replay"] = verif_res.get("workflow_replay")
                        inc["timeline"].append({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "service": ticket["service_name"],
                            "type": "VERIFIED_RECOVERY",
                            "message": f"Verification passed on {ticket['service_name']} (Health OK, synthetic transactions healthy, metrics restored)."
                        })
                        inc["timeline"].append({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "service": ticket["service_name"],
                            "type": "RESOLVED",
                            "message": f"Incident {ticket['incident_id']} marked RESOLVED."
                        })
                        if inc in self.active_incidents:
                            self.active_incidents.remove(inc)
                        self.resolved_incidents.insert(0, inc)

                        # Sync with incident_pipeline
                        try:
                            from backend.app.analytics.incident_pipeline import incident_pipeline
                            with incident_pipeline.lock:
                                if ticket["incident_id"] in incident_pipeline._active_incidents:
                                    inc_data = incident_pipeline._active_incidents[ticket["incident_id"]]
                                    inc_data["status"] = "RESOLVED"
                                    inc_data["lifecycle_state"] = "VALIDATED"
                                    inc_data["resolved_at"] = inc.get("resolved_at")
                                    inc_data["validation_criteria"] = verif_res.get("validation_criteria")
                                    inc_data["workflow_replay"] = verif_res.get("workflow_replay")
                                    for aff_s in inc_data.get("affected_services", []):
                                        for tid in ["shopsphere", "fincore", "clouddesk", "default", inc_data.get("tenant_id", "default")]:
                                            incident_pipeline._service_to_incident.pop((tid, aff_s), None)
                        except Exception:
                            pass

                        # Broadcast verification passed and incident resolved
                        try:
                            from backend.app.api.websocket import ws_manager
                            await ws_manager.broadcast({
                                "type": "verification.passed",
                                "incident_id": ticket["incident_id"],
                                "service": ticket["service_name"],
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                            await ws_manager.broadcast({
                                "type": "INCIDENT_RESOLVED",
                                "event_type": "INCIDENT_RESOLVED",
                                "incident_id": ticket["incident_id"],
                                "service": ticket["service_name"],
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                            await ws_manager.broadcast({
                                "type": "incident.resolved",
                                "incident_id": ticket["incident_id"],
                                "service": ticket["service_name"],
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                        except Exception:
                            pass

                        # Learn from Incident and Advance Failure Scheduler Lifecycle
                        try:
                            from backend.app.knowledge.incident_memory import incident_memory
                            from backend.app.monitoring.failure_scheduler import failure_scheduler
                            incident_memory.index_resolved_incident(inc, ticket["proposed_action"], verif_res)
                            await failure_scheduler.transition_lifecycle("RESOLVED")
                            await failure_scheduler.transition_lifecycle("LEARNED")
                        except Exception:
                            pass

                    rec_entry = {
                        "execution_id": f"REC-{approval_id[-6:]}",
                        "incident_id": ticket["incident_id"],
                        "approval_id": approval_id,
                        "service_name": ticket["service_name"],
                        "action": ticket["proposed_action"],
                        "status": "SUCCESS",
                        "success": True,
                        "duration_ms": exec_res.get("duration_ms", 120),
                        "verification_status": "VERIFIED",
                        "verification_result": verif_res,
                        "verification_details": verif_res,
                        "result": exec_res.get("details", "Remediation executed successfully"),
                        "error": None,
                        "started_at": now_iso,
                        "executed_at": now_iso,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "execution_mode": "CONTROLLED_DEMO"
                    }
                    from backend.app.healing.persistence import save_recovery_execution
                    persisted = await save_recovery_execution(rec_entry)
                    self.recovery_history.insert(0, persisted)
                    return {"success": True, "status": "RESOLVED", "execution": persisted, "verification": verif_res}

                else:
                    # Broadcast verification failed
                    try:
                        from backend.app.api.websocket import ws_manager
                        await ws_manager.broadcast({
                            "type": "verification.failed",
                            "incident_id": ticket["incident_id"],
                            "service": ticket["service_name"],
                            "reason": verif_res.get("failure_reason"),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    except Exception:
                        pass

                    if inc:
                        iters = inc.get("recovery_iterations", 0) + 1
                        inc["recovery_iterations"] = iters
                        inc["after_snapshot"] = verif_res.get("after_snapshot")
                        inc["metric_comparison"] = verif_res.get("comparison")
                        if iters >= 3:
                            inc["status"] = "UNRESOLVED"
                            inc["lifecycle_state"] = "UNRESOLVED"
                            inc["recovery_status"] = "UNRESOLVED"
                            inc["verification_status"] = "UNRESOLVED"
                        else:
                            inc["status"] = verif_res.get("status", "VERIFICATION_FAILED")
                            inc["recovery_status"] = "FAILED"
                            inc["verification_status"] = verif_res.get("verification_status", "VERIFICATION_FAILED")

                        inc["timeline"].append({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "service": ticket["service_name"],
                            "type": "VERIFICATION_FAILED",
                            "message": f"Active verification failed (attempt {iters}/3): {verif_res.get('failure_reason', 'Degraded metrics')}."
                        })

                    rec_entry = {
                        "execution_id": f"REC-{approval_id[-6:]}",
                        "incident_id": ticket["incident_id"],
                        "approval_id": approval_id,
                        "service_name": ticket["service_name"],
                        "action": ticket["proposed_action"],
                        "status": "FAILED",
                        "success": False,
                        "duration_ms": exec_res.get("duration_ms", 120),
                        "verification_status": "VERIFICATION_FAILED",
                        "verification_result": verif_res,
                        "verification_details": verif_res,
                        "result": exec_res.get("details", "Execution succeeded but verification failed"),
                        "error": verif_res.get("failure_reason"),
                        "started_at": now_iso,
                        "executed_at": now_iso,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "execution_mode": "CONTROLLED_DEMO"
                    }
                    from backend.app.healing.persistence import save_recovery_execution
                    persisted = await save_recovery_execution(rec_entry)
                    self.recovery_history.insert(0, persisted)
                    return {
                        "success": False,
                        "status": "VERIFICATION_FAILED",
                        "error": f"Verification failed: {verif_res.get('failure_reason', 'Active probe failed')}",
                        "execution": persisted,
                        "verification": verif_res
                    }

            else:
                # Path 2 & 3: Primary remediation execution failed (REMEDIATION_FAILED)
                # do NOT immediately mark RESOLVED
                if inc:
                    inc["status"] = "REMEDIATION_FAILED"
                    inc["recovery_status"] = "FAILED"
                    inc["remediation_status"] = "REMEDIATION_FAILED"
                    inc["timeline"].append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "service": ticket["service_name"],
                        "type": "REMEDIATION_FAILED",
                        "message": f"Primary remediation action '{ticket['proposed_action']}' failed: {exec_res.get('error', 'Execution error')}."
                    })

                # Attempt configured fallback/retry/rollback action if policy allows
                fallback_action = ticket.get("alternative_action")
                if fallback_action and fallback_action != ticket["proposed_action"]:
                    if inc:
                        inc["timeline"].append({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "service": ticket["service_name"],
                            "type": "FALLBACK_ATTEMPT",
                            "message": f"Attempting configured fallback recovery action '{fallback_action}'..."
                        })
                    fallback_res = await executor.execute_action(ticket["service_name"], fallback_action)
                    if fallback_res.get("success"):
                        if inc:
                            inc["status"] = "VERIFYING"
                            inc["verification_status"] = "WAITING_FOR_ACTIVE_PROBE"
                        verif_res = await verifier.verify_recovery(ticket["service_name"], inc.get("affected_services", []) if inc else [])
                        if verif_res.get("verified"):
                            if inc:
                                inc["status"] = "RESOLVED"
                                inc["recovery_status"] = "RECOVERED_VIA_FALLBACK"
                                inc["remediation_status"] = "EXECUTION_SUCCESS"
                                inc["verification_status"] = "VERIFIED"
                                inc["resolved_at"] = datetime.now(timezone.utc).isoformat()
                                inc["timeline"].append({
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "service": ticket["service_name"],
                                    "type": "RESOLVED",
                                    "message": f"Incident {ticket['incident_id']} RESOLVED via fallback runbook '{fallback_action}'."
                                })
                                if inc in self.active_incidents:
                                    self.active_incidents.remove(inc)
                                self.resolved_incidents.insert(0, inc)

                            rec_entry = {
                                "execution_id": f"REC-{approval_id[-6:]}",
                                "incident_id": ticket["incident_id"],
                                "approval_id": approval_id,
                                "service_name": ticket["service_name"],
                                "action": fallback_action,
                                "status": "SUCCESS",
                                "success": True,
                                "duration_ms": fallback_res.get("duration_ms", 120),
                                "verification_status": "VERIFIED",
                                "verification_result": verif_res,
                                "verification_details": verif_res,
                                "result": f"Resolved via fallback: {fallback_res.get('details')}",
                                "error": None,
                                "started_at": now_iso,
                                "executed_at": now_iso,
                                "completed_at": datetime.now(timezone.utc).isoformat(),
                                "execution_mode": "CONTROLLED_DEMO"
                            }
                            from backend.app.healing.persistence import save_recovery_execution
                            persisted = await save_recovery_execution(rec_entry)
                            self.recovery_history.insert(0, persisted)
                            return {"success": True, "status": "RESOLVED", "recovery_path": "FALLBACK_RECOVERY", "execution": persisted, "verification": verif_res}

                # Path 3: If execution reports failure but independent verification proves the service recovered:
                # use explicit state RECOVERED_AFTER_EXECUTION_ERROR rather than falsely reporting normal remediation success
                independent_verif = await verifier.verify_recovery(ticket["service_name"], inc.get("affected_services", []) if inc else [])
                if independent_verif.get("verified"):
                    if inc:
                        inc["status"] = "RECOVERED_AFTER_EXECUTION_ERROR"
                        inc["recovery_status"] = "RECOVERED_AFTER_EXECUTION_ERROR"
                        inc["remediation_status"] = "REMEDIATION_FAILED"
                        inc["verification_status"] = "VERIFIED"
                        inc["resolved_at"] = datetime.now(timezone.utc).isoformat()
                        inc["timeline"].append({
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "service": ticket["service_name"],
                            "type": "RECOVERED_AFTER_EXECUTION_ERROR",
                            "message": (
                                f"Remediation action reported execution failure, but independent active probes "
                                f"confirmed service '{ticket['service_name']}' is healthy. Status: RECOVERED_AFTER_EXECUTION_ERROR."
                            )
                        })
                        if inc in self.active_incidents:
                            self.active_incidents.remove(inc)
                        self.resolved_incidents.insert(0, inc)

                    rec_entry = {
                        "execution_id": f"REC-{approval_id[-6:]}",
                        "incident_id": ticket["incident_id"],
                        "approval_id": approval_id,
                        "service_name": ticket["service_name"],
                        "action": ticket["proposed_action"],
                        "status": "RECOVERED_AFTER_EXECUTION_ERROR",
                        "success": True,
                        "duration_ms": exec_res.get("duration_ms", 120),
                        "verification_status": "VERIFIED",
                        "verification_result": independent_verif,
                        "verification_details": independent_verif,
                        "result": "Independent verification confirmed healthy service despite execution error",
                        "error": exec_res.get("error"),
                        "started_at": now_iso,
                        "executed_at": now_iso,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "execution_mode": "CONTROLLED_DEMO"
                    }
                    from backend.app.healing.persistence import save_recovery_execution
                    persisted = await save_recovery_execution(rec_entry)
                    self.recovery_history.insert(0, persisted)
                    return {
                        "success": True,
                        "status": "RECOVERED_AFTER_EXECUTION_ERROR",
                        "execution": persisted,
                        "verification": independent_verif
                    }

                # Strict failure: neither primary, fallback, nor independent probe recovered
                if inc:
                    inc["status"] = "REMEDIATION_FAILED"
                    inc["recovery_status"] = "FAILED_ESCALATED"
                    inc["verification_status"] = "VERIFICATION_FAILED"
                    inc["timeline"].append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "service": ticket["service_name"],
                        "type": "REMEDIATION_FAILED",
                        "message": f"Remediation failed and independent verification confirmed degraded state: {independent_verif.get('failure_reason')}."
                    })

                rec_entry = {
                    "execution_id": f"REC-{approval_id[-6:]}",
                    "incident_id": ticket["incident_id"],
                    "approval_id": approval_id,
                    "service_name": ticket["service_name"],
                    "action": ticket["proposed_action"],
                    "status": "FAILED",
                    "success": False,
                    "duration_ms": exec_res.get("duration_ms", 120),
                    "verification_status": "VERIFICATION_FAILED",
                    "verification_result": independent_verif,
                    "verification_details": independent_verif,
                    "result": exec_res.get("details", "Execution failed"),
                    "error": exec_res.get("error") or independent_verif.get("failure_reason"),
                    "started_at": now_iso,
                    "executed_at": now_iso,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "execution_mode": "CONTROLLED_DEMO"
                }
                from backend.app.healing.persistence import save_recovery_execution
                persisted = await save_recovery_execution(rec_entry)
                self.recovery_history.insert(0, persisted)
                return {
                    "success": False,
                    "status": "REMEDIATION_FAILED",
                    "error": f"Remediation failed: {exec_res.get('error') or independent_verif.get('failure_reason') or 'Execution failed'}",
                    "execution": persisted,
                    "verification": independent_verif
                }

        elif decision == "DEFERRED":
            if inc:
                inc["approval_status"] = "DEFERRED"
                inc["timeline"].append({
                    "timestamp": now_iso,
                    "service": ticket["service_name"],
                    "type": "APPROVAL_DEFERRED",
                    "message": f"Action '{ticket['proposed_action']}' deferred by {reviewer}."
                })
            self.append_feed_event(
                phase="APPROVAL_DEFERRED",
                service=ticket["service_name"],
                message=f"Action '{ticket['proposed_action']}' deferred for scheduled maintenance by {reviewer}.",
                severity="INFO"
            )
            return {"success": True, "status": "DEFERRED"}

        else:
            if inc:
                inc["status"] = "REJECTED"
                inc["approval_status"] = "REJECTED"
                inc["timeline"].append({
                    "timestamp": now_iso,
                    "service": ticket["service_name"],
                    "type": "APPROVAL_REJECTED",
                    "message": f"Action '{ticket['proposed_action']}' rejected by {reviewer}. Notes: {notes or 'None'}."
                })
            self.append_feed_event(
                phase="APPROVAL_REJECTED",
                service=ticket["service_name"],
                message=f"Administrator ({reviewer}) rejected action '{ticket['proposed_action']}'.",
                severity="WARNING"
            )
            return {"success": True, "status": "REJECTED"}

    async def _handle_autonomous_recovery(self, incident: Dict[str, Any], action: str):
        """Executes allowlisted low-risk runbook autonomously and verifies recovery."""
        svc = incident.get("root_cause_service", incident.get("primary_service", "database-service"))
        now_iso = datetime.now(timezone.utc).isoformat()
        incident["remediation_status"] = "EXECUTING"
        incident["timeline"].append({
            "timestamp": now_iso,
            "service": svc,
            "type": "REMEDIATING",
            "message": f"Autonomous execution of runbook '{action}' initiated."
        })
        
        exec_res = await executor.execute_action(svc, action)
        
        incident["status"] = "VERIFYING"
        incident["recovery_status"] = "VERIFYING"
        incident["verification_status"] = "WAITING_FOR_TELEMETRY"
        incident["timeline"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": svc,
            "type": "VERIFYING",
            "message": "Autonomous remediation applied. Verifying health against subsequent telemetry."
        })

        verif_res = await verifier.verify_recovery(svc, incident.get("affected_services", []))
        
        verif_ok = bool(verif_res.get("verified", False))
        status = "SUCCESS" if (exec_res.get("success", False) and verif_ok) else "FAILED"
        
        rec_entry = {
            "execution_id": f"REC-AUTO-{incident['incident_id'][-6:]}",
            "incident_id": incident["incident_id"],
            "approval_id": "AUTONOMOUS",
            "service_name": svc,
            "action": action,
            "status": status,
            "success": (status == "SUCCESS"),
            "duration_ms": exec_res.get("duration_ms", 120),
            "verification_status": "VERIFIED" if verif_ok else "VERIFICATION_FAILED",
            "verification_result": verif_res,
            "verification_details": verif_res,
            "result": exec_res.get("details", "Autonomous remediation executed"),
            "error": exec_res.get("error") or verif_res.get("failure_reason"),
            "started_at": now_iso,
            "executed_at": now_iso,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "execution_mode": "CONTROLLED_DEMO"
        }
        from backend.app.healing.persistence import save_recovery_execution
        persisted = await save_recovery_execution(rec_entry)
        self.recovery_history.insert(0, persisted)

        if verif_res["verified"]:
            incident["status"] = "RESOLVED"
            incident["recovery_status"] = "SUCCESS"
            incident["remediation_status"] = "SUCCESS"
            incident["verification_status"] = "VERIFIED"
            incident["resolved_at"] = datetime.now(timezone.utc).isoformat()
            incident["timeline"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": svc,
                "type": "RESOLVED",
                "message": "Incident autonomously RESOLVED. Health check verified."
            })
            self.append_feed_event(
                phase="VERIFICATION_SUCCESS",
                service=svc,
                message=f"Incident {incident['incident_id']} autonomously resolved and verified.",
                severity="INFO"
            )
            if incident in self.active_incidents:
                self.active_incidents.remove(incident)
            if incident not in self.resolved_incidents:
                self.resolved_incidents.insert(0, incident)

            # Learn from Incident and Advance Failure Scheduler Lifecycle
            try:
                from backend.app.knowledge.incident_memory import incident_memory
                from backend.app.monitoring.failure_scheduler import failure_scheduler
                incident_memory.index_resolved_incident(incident, action, verif_res)
                await failure_scheduler.transition_lifecycle("RESOLVED")
                await failure_scheduler.transition_lifecycle("LEARNED")
            except Exception:
                pass


# Global Singleton Collector Instance
collector = MonitoringCollector()
