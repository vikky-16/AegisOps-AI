"""
AegisOps AI - Autonomous Telemetry Incident Pipeline (Phases 9, 10, 11, 24, 36)
High-performance asynchronous background orchestration:
1. Ingestion: ultra-fast non-blocking buffering (<0.01ms per event).
2. Background Worker: evaluates windowed features, runs multi-detector anomaly engine,
   deduplicates into episodes, correlates across services/traces/time, generates incidents,
   reconstructs timelines, executes 7-factor RCA, compiles structured evidence, and broadcasts
   real-time WebSocket updates to the live dashboard.
"""

import time
import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import deque, defaultdict
import threading

from backend.app.analytics.feature_extractor import feature_extractor
from backend.app.analytics.baseline_engine import baseline_engine
from backend.app.analytics.anomaly_detector import anomaly_detector
from backend.app.analytics.deduplicator import anomaly_deduplicator, AnomalyEpisode
from backend.app.analytics.error_pattern_detector import error_pattern_detector
from backend.app.analytics.rca_engine import rca_engine
from backend.app.healing.solution_generator import solution_generator
from backend.app.rca.dynamic_graph import dynamic_graph
from backend.app.knowledge.incident_memory import incident_memory
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.incident import Incident as IncidentModel
from backend.app.models.evidence import EvidenceItem as EvidenceModel
from backend.app.models.service_dependency import RootCauseCandidate as RCAModel
from backend.app.models.anomaly_episode import AnomalyEpisodeModel
from backend.app.api.websocket import ws_manager
from backend.app.monitoring.collector import collector


class IncidentPipelineCoordinator:
    """
    Coordinates feature extraction, anomaly evaluation, episode deduplication,
    incident correlation, timeline reconstruction, RCA, and database persistence.
    """
    def __init__(self, correlation_window_sec: float = 30.0):
        self.correlation_window_sec = correlation_window_sec
        
        # Recent raw events buffer per tenant for trace & timeline correlation: tenant_id -> deque
        self._recent_events: Dict[str, deque] = defaultdict(lambda: deque(maxlen=250))
        self.lock = threading.Lock()

        # Active incidents mapping: incident_id -> incident_dict
        self._active_incidents: Dict[str, Dict[str, Any]] = {}
        # Mapping: (tenant_id, primary_service) -> incident_id
        self._service_to_incident: Dict[Tuple[str, str], str] = {}

        # Background worker handle
        self._worker_task: Optional[asyncio.Task] = None
        self._is_running: bool = False

    def record_telemetry_event(self, event: Any):
        """
        Non-blocking ingestion hook. Appends event to sliding feature buffer and error tracker.
        Returns immediately (< 0.05ms) so HTTP requests and WebSocket streams are never delayed.
        """
        now = time.time()
        tenant_id = (
            getattr(event, "tenant_id", None) 
            or getattr(event, "company_id", None) 
            or "shopsphere"
        ).lower()
        service = getattr(event, "service_name", None) or getattr(event, "service", "unknown-service")

        # 1. Update multi-window feature buffer
        feature_extractor.process_event(event)

        # 2. Extract error information if present
        msg = str(getattr(event, "message", "") or "")
        status_code = getattr(event, "http_status", None) or getattr(event, "status_code", None)
        status_int = int(status_code) if (status_code is not None and str(status_code).isdigit()) else None
        sev = str(getattr(event, "severity", "INFO")).upper()
        if hasattr(sev, "value"):
            sev = sev.value.upper()

        is_err = (status_int and status_int >= 400) or sev in ("ERROR", "CRITICAL") or "error" in msg.lower() or "exception" in msg.lower()
        if is_err and msg:
            err_type = getattr(event, "error_type", None) or (f"HTTP_{status_int}" if status_int else "ApplicationError")
            error_pattern_detector.record_error(
                tenant_id=tenant_id,
                service=service,
                message=msg,
                error_type=err_type,
                status_code=status_int,
                timestamp=now
            )

        # 2b. Authoritative Canonical State Update (Single Source of Truth)
        try:
            from backend.app.services.canonical_state import canonical_state_manager
            lat_val = getattr(event, "latency", None) or getattr(event, "latency_ms", None)
            lat_float = float(lat_val) if lat_val is not None else None
            cpu_val = getattr(event, "cpu_percent", None)
            mem_val = getattr(event, "memory_mb", None)
            canonical_state_manager.record_telemetry(
                tenant_id=tenant_id,
                service_name=service,
                latency_ms=lat_float,
                is_error=is_err,
                cpu_percent=float(cpu_val) if cpu_val is not None else None,
                memory_mb=float(mem_val) if mem_val is not None else None,
                timestamp=now
            )
        except Exception:
            pass

        # 3. Store in bounded recent event queue for trace & timeline correlation
        event_dict = {
            "event_id": getattr(event, "event_id", f"evt-{uuid.uuid4().hex[:8]}"),
            "tenant_id": tenant_id,
            "company": tenant_id,
            "service": service,
            "service_name": service,
            "timestamp": getattr(event, "timestamp", datetime.now(timezone.utc).isoformat()),
            "ts_float": now,
            "message": msg,
            "severity": sev,
            "http_status": status_int,
            "latency": getattr(event, "latency", None) or getattr(event, "latency_ms", None),
            "trace_id": getattr(event, "trace_id", None),
            "span_id": getattr(event, "span_id", None),
            "parent_span_id": getattr(event, "parent_span_id", None)
        }
        with self.lock:
            self._recent_events[tenant_id].append(event_dict)

        # 4. Topology inference from traceparent
        trace_id = getattr(event, "trace_id", None)
        if trace_id and service != "gateway" and service != "api-gateway":
            gateway_name = "api-gateway" if tenant_id == "shopsphere" else ("gateway" if tenant_id == "fincore" else "clouddesk-gateway")
            dynamic_graph.add_or_update_dependency(
                source=gateway_name,
                target=service,
                relationship_type="HTTP_UPSTREAM",
                confidence=0.98,
                observation_count=1,
                correlated_failures_count=1 if is_err else 0
            )

    async def process_telemetry_event(self, event: Any, collector_instance: Any = None) -> Optional[Dict[str, Any]]:
        """
        Synchronous evaluation pipeline hook for direct testing & immediate validation:
        Ingests event, extracts features, runs multi-detector anomaly evaluation,
        correlates episodes, triggers 7-factor RCA, and returns active incident if created.
        """
        self.record_telemetry_event(event)
        now = time.time()
        tenant_id = (
            getattr(event, "tenant_id", None) 
            or getattr(event, "company_id", None) 
            or "shopsphere"
        ).lower()
        service = getattr(event, "service_name", None) or getattr(event, "service", "unknown-service")

        features = feature_extractor.get_features(tenant_id, service, window_sec=30.0)
        anom_res = anomaly_detector.evaluate(tenant_id, service, features, current_time=now)

        if anom_res.get("is_anomaly"):
            score = anom_res.get("combined_score", 0.85)
            sev = anom_res.get("severity", "HIGH")
            ep, is_new = anomaly_deduplicator.process_anomaly(
                tenant_id=tenant_id,
                service=service,
                feature="composite_telemetry",
                score=score,
                severity=sev,
                timestamp=now,
                metadata={"detectors": anom_res.get("detectors_triggered", []), "features": features}
            )
            await self._correlate_and_reconcile_incidents(tenant_id, [ep], now)
            with self.lock:
                inc_id = self._service_to_incident.get((tenant_id, service))
                if inc_id and inc_id in self._active_incidents:
                    inc = self._active_incidents[inc_id]
                    if "rca_result" in inc:
                        inc["rca"] = inc["rca_result"]
                    return inc
        return None

    async def start_background_worker(self):
        """Starts the periodic background evaluation worker."""
        if self._is_running:
            return
        self._is_running = True
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop_background_worker(self):
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def _worker_loop(self):
        """Runs anomaly evaluation and incident correlation every 2.0 seconds."""
        while self._is_running:
            try:
                await self.evaluate_operational_mesh()
            except Exception as e:
                pass
            await asyncio.sleep(2.0)

    async def evaluate_operational_mesh(self):
        """
        Core background processing cycle (Phase 36):
        Window Features -> Anomaly Detectors -> Episodes -> Correlation -> Incidents -> RCA -> Evidence.
        """
        now = time.time()
        active_services = feature_extractor.get_all_active_services()

        # Step 1: Evaluate each active service with multi-detector ensemble
        episodes_by_tenant: Dict[str, List[AnomalyEpisode]] = defaultdict(list)
        for tenant_id, service in active_services:
            features = feature_extractor.get_features(tenant_id, service, window_sec=30.0)
            
            # Evaluate Early Warning Degradation (Requirement 4 & 24)
            try:
                from backend.app.analytics.early_warning import early_warning_engine
                alert = early_warning_engine.evaluate_telemetry(tenant_id, service, features)
                if alert:
                    asyncio.create_task(early_warning_engine.broadcast_alert(alert))
            except Exception:
                pass

            anom_res = anomaly_detector.evaluate(tenant_id, service, features, current_time=now)
            
            if anom_res.get("is_anomaly"):
                score = anom_res.get("combined_score", 0.5)
                sev = anom_res.get("severity", "MEDIUM")
                try:
                    from backend.app.monitoring.failure_scheduler import failure_scheduler
                    if failure_scheduler.current_lifecycle_state == "FAILURE_INJECTED":
                        failure_scheduler.transition_lifecycle("FAILURE_DETECTED")
                except Exception:
                    pass
                ep, is_new = anomaly_deduplicator.process_anomaly(
                    tenant_id=tenant_id,
                    service=service,
                    feature="composite_telemetry",
                    score=score,
                    severity=sev,
                    timestamp=now,
                    metadata={"detectors": anom_res.get("detectors_triggered", []), "features": features}
                )
                episodes_by_tenant[tenant_id].append(ep)

        # Step 2: Correlate episodes per tenant and update/create incidents
        for tenant_id, episodes in episodes_by_tenant.items():
            if episodes:
                await self._correlate_and_reconcile_incidents(tenant_id, episodes, now)

    async def _correlate_and_reconcile_incidents(
        self,
        tenant_id: str,
        episodes: List[AnomalyEpisode],
        current_time: float
    ):
        """
        Correlates active episodes into incidents using:
        1. Same company (tenant_id)
        2. Same time window (30s)
        3. Service topology & traces
        """
        # Filter episodes active within correlation window
        active_eps = [
            ep for ep in episodes 
            if (current_time - ep.last_seen) <= self.correlation_window_sec
        ]
        if not active_eps:
            return

        affected_services = list(dict.fromkeys(ep.service for ep in active_eps))
        peak_score = max(ep.peak_score for ep in active_eps)
        total_events = sum(ep.event_count for ep in active_eps)

        # Determine severity based on measurable characteristics
        if peak_score >= 0.75 or len(affected_services) >= 3:
            sev = "CRITICAL"
        elif peak_score >= 0.55 or len(affected_services) >= 2:
            sev = "HIGH"
        elif peak_score >= 0.35:
            sev = "MEDIUM"
        else:
            sev = "LOW"

        # Check if an existing open incident exists for this tenant
        with self.lock:
            existing_inc_id = None
            for s in affected_services:
                cand_id = self._service_to_incident.get((tenant_id, s))
                if cand_id and cand_id in self._active_incidents and self._active_incidents[cand_id].get("status") not in ("RESOLVED", "CLOSED"):
                    existing_inc_id = cand_id
                    break

        if existing_inc_id and existing_inc_id in self._active_incidents and self._active_incidents[existing_inc_id].get("status") not in ("RESOLVED", "CLOSED"):
            # Update existing incident
            await self._update_active_incident(existing_inc_id, tenant_id, affected_services, active_eps, current_time)
        else:
            # Create new correlated incident
            await self._create_correlated_incident(tenant_id, affected_services, active_eps, peak_score, sev, current_time)

    async def _create_correlated_incident(
        self,
        tenant_id: str,
        affected_services: List[str],
        active_eps: List[AnomalyEpisode],
        peak_score: float,
        severity: str,
        current_time: float
    ):
        """Creates a new correlated incident with timeline, RCA, evidence, and DB persistence."""
        inc_id = f"INC-2026-{uuid.uuid4().hex[:6].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Fetch recent events for this tenant within active correlation window
        earliest_ep_time = min((ep.first_seen for ep in active_eps), default=current_time - 30.0)
        with self.lock:
            recent_evts = [
                ev for ev in self._recent_events[tenant_id]
                if (current_time - ev.get("ts_float", current_time)) <= 45.0
                and ev.get("ts_float", current_time) >= (earliest_ep_time - 10.0)
            ]

        # Step 1: Algorithmic Multi-Factor RCA (Phases 13 - 18)
        anomaly_snapshots = {
            ep.service: {
                "combined_score": ep.peak_score,
                "severity": ep.severity,
                "detectors": ep.metadata.get("detectors", []),
                "features": ep.metadata.get("features", {})
            }
            for ep in active_eps
        }
        rca_res = rca_engine.analyze(
            tenant_id=tenant_id,
            affected_services=affected_services,
            events=recent_evts,
            anomaly_snapshots=anomaly_snapshots
        )

        primary_root = rca_res.get("primary_root_cause", affected_services[0])
        root_category = rca_res.get("root_cause_category", "SERVICE_DEGRADATION")
        confidence = rca_res.get("confidence", 0.88)
        confidence_pct = rca_res.get("confidence_pct", 88)

        # Title
        company_name = "ShopSphere" if tenant_id == "shopsphere" else ("FinCore" if tenant_id == "fincore" else "CloudDesk")
        title = f"{company_name} - {primary_root.replace('-', ' ').title()} {root_category.replace('_', ' ').title()}"

        # Step 2: Build Reconstructed Timeline (Phase 11)
        timeline = []
        for ep in sorted(active_eps, key=lambda x: x.first_seen):
            timeline.append({
                "timestamp": datetime.fromtimestamp(ep.first_seen, tz=timezone.utc).isoformat(),
                "service": ep.service,
                "event": f"Anomaly detected on '{ep.service}' (peak score {ep.peak_score:.2f})",
                "severity": ep.severity,
                "anomaly_score": ep.peak_score,
                "event_count": ep.event_count
            })
        timeline.append({
            "timestamp": now_iso,
            "service": "incident_pipeline",
            "event": f"Correlated incident created: {title} (Severity: {severity}, Confidence: {confidence_pct}%)",
            "severity": severity,
            "anomaly_score": peak_score
        })

        # Step 3: Candidate Solutions (Phase 32)
        candidate_solutions = solution_generator.generate_candidate_solutions(
            hypothesis={
                "hypothesis": title,
                "target_service": primary_root,
                "failure_category": root_category
            },
            scenario_id=root_category.lower(),
            tenant_id=tenant_id
        )

        incident_dict = {
            "incident_id": inc_id,
            "tenant_id": tenant_id,
            "company": tenant_id,
            "title": title,
            "severity": severity,
            "status": "OPEN",
            "lifecycle_state": "DETECTED",
            "created_at": now_iso,
            "detected_at": now_iso,
            "updated_at": now_iso,
            "resolved_at": None,
            "primary_service": primary_root,
            "affected_services": affected_services,
            "affected_services_count": len(affected_services),
            "anomaly_count": len(active_eps),
            "event_count": sum(ep.event_count for ep in active_eps),
            "correlated_event_count": sum(ep.event_count for ep in active_eps),
            "root_cause": primary_root,
            "root_cause_service": primary_root,
            "root_cause_category": root_category,
            "root_cause_confidence": confidence,
            "rca_confidence": confidence,
            "rca_result": rca_res,
            "timeline": timeline,
            "evidence_items": rca_res.get("structured_evidence", []),
            "candidate_solutions": candidate_solutions,
            "selected_solution": candidate_solutions[0] if candidate_solutions else None,
            "alternative_hypotheses": rca_res.get("alternative_hypotheses", [])
        }

        # Step 3b: Evaluate Governance & Human Approval Gate (Part 1 & 8)
        rec_act = (candidate_solutions[0]["action"] if candidate_solutions else "RESET_CONNECTION_POOL")
        from backend.app.healing.approval_manager import calculate_action_risk, approval_manager
        action_risk = calculate_action_risk(rec_act, incident_dict)
        incident_dict["recommended_action"] = rec_act
        incident_dict["action_risk_level"] = action_risk

        if action_risk in ["HIGH", "CRITICAL"]:
            incident_dict["status"] = "AWAITING_APPROVAL"
            incident_dict["approval_status"] = "PENDING"
            incident_dict["recovery_status"] = "AWAITING_APPROVAL"
            try:
                await approval_manager.create_or_get_approval_ticket(incident_dict, rec_act)
            except Exception:
                pass
        else:
            incident_dict["status"] = "INVESTIGATING"
            incident_dict["approval_status"] = "AUTO_ALLOWED"
            incident_dict["recovery_status"] = "READY"

        # Associate episodes with incident
        for ep in active_eps:
            anomaly_deduplicator.associate_incident(ep.episode_id, inc_id)

        # Register in memory
        with self.lock:
            self._active_incidents[inc_id] = incident_dict
            for s in affected_services:
                self._service_to_incident[(tenant_id, s)] = inc_id

        # Register in in-memory collector for existing dashboards
        collector.active_incidents.insert(0, incident_dict)

        # Notify failure scheduler that real incident was created from detected telemetry
        try:
            from backend.app.monitoring.failure_scheduler import failure_scheduler
            failure_scheduler.transition_lifecycle("INCIDENT_CREATED", {"incident_id": inc_id})
        except Exception:
            pass

        # Step 4: Persist in SQLite / PostgreSQL database asynchronously (Phase 34)
        asyncio.create_task(self._persist_incident_to_db(incident_dict, rca_res, active_eps))

        # Step 5: Real-Time WebSocket Broadcast (Phase 24)
        await self._broadcast_incident_event("INCIDENT_CREATED", incident_dict)

    async def _update_active_incident(
        self,
        incident_id: str,
        tenant_id: str,
        affected_services: List[str],
        active_eps: List[AnomalyEpisode],
        current_time: float
    ):
        """Updates an existing incident with continuous telemetry evidence."""
        inc = self._active_incidents.get(incident_id)
        if not inc:
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Merge affected services
        cur_aff = set(inc.get("affected_services", []))
        cur_aff.update(affected_services)
        inc["affected_services"] = list(cur_aff)
        inc["affected_services_count"] = len(inc["affected_services"])

        # Update event count
        inc["anomaly_count"] = len(active_eps)
        inc["event_count"] = sum(ep.event_count for ep in active_eps)
        inc["correlated_event_count"] = inc["event_count"]
        inc["updated_at"] = now_iso

        # Escalate peak score / severity if needed
        peak = max(ep.peak_score for ep in active_eps)
        if peak >= 0.75:
            inc["severity"] = "CRITICAL"
        # Ensure it exists in collector.active_incidents if open
        if inc not in collector.active_incidents and inc.get("status") not in ("RESOLVED", "CLOSED"):
            collector.active_incidents.insert(0, inc)

        # Broadcast update
        await self._broadcast_incident_event("INCIDENT_UPDATED", inc)

    async def _persist_incident_to_db(
        self,
        incident_dict: Dict[str, Any],
        rca_res: Dict[str, Any],
        active_eps: List[AnomalyEpisode]
    ):
        """Persists Incident, Episodes, RCA Candidates, and Evidence to database."""
        try:
            async with AsyncSessionLocal() as session:
                # 1. Incident Record
                db_inc = IncidentModel(
                    incident_id=incident_dict["incident_id"],
                    tenant_id=incident_dict["tenant_id"],
                    title=incident_dict["title"],
                    severity=incident_dict["severity"],
                    status=incident_dict["status"],
                    primary_service=incident_dict["primary_service"],
                    affected_services_json=json.dumps(incident_dict["affected_services"]),
                    correlated_event_count=incident_dict["event_count"],
                    root_cause=incident_dict["root_cause"],
                    root_cause_service=incident_dict["root_cause_service"],
                    root_cause_category=incident_dict["root_cause_category"],
                    root_cause_confidence=incident_dict["root_cause_confidence"],
                    rca_confidence=incident_dict["rca_confidence"],
                    rca_evidence_json=json.dumps(rca_res.get("evidence", [])),
                    timeline_json=json.dumps(incident_dict["timeline"]),
                    hypotheses_json=json.dumps(rca_res.get("alternative_hypotheses", [])),
                    candidate_solutions_json=json.dumps(incident_dict.get("candidate_solutions", [])),
                    selected_solution_json=json.dumps(incident_dict.get("selected_solution") or {})
                )
                session.add(db_inc)

                # 2. RCA Candidates
                for cand in rca_res.get("ranked_candidates", []):
                    c_model = RCAModel(
                        tenant_id=incident_dict["tenant_id"],
                        incident_id=incident_dict["incident_id"],
                        service=cand.get("service") or cand.get("candidate"),
                        rank=cand.get("rank", 1),
                        confidence=cand.get("confidence_pct", 88) / 100.0,
                        score=cand.get("score", 0.8) * 100.0,
                        causal_onset_time=datetime.now(timezone.utc).isoformat(),
                        rationale=cand.get("reasoning", ""),
                        is_primary=cand.get("primary", False)
                    )
                    session.add(c_model)

                # 3. Structured Evidence Items
                for ev in rca_res.get("structured_evidence", []):
                    ev_item = EvidenceModel(
                        incident_id=incident_dict["incident_id"],
                        tenant_id=incident_dict["tenant_id"],
                        timestamp=float(ev.get("timestamp", time.time())),
                        source=ev.get("source", "telemetry_engine"),
                        service=ev.get("service", incident_dict["primary_service"]),
                        component=ev.get("component", "system"),
                        signal_type=ev.get("evidence_type", "METRIC").upper(),
                        metric_or_log_value=ev.get("observation", ""),
                        baseline="normal_baseline",
                        deviation=str(ev.get("deviation", "")),
                        evidence_type=ev.get("evidence_type", "metric"),
                        status="ANOMALOUS"
                    )
                    session.add(ev_item)

                # 4. Anomaly Episodes
                for ep in active_eps:
                    ep_model = AnomalyEpisodeModel(
                        episode_id=ep.episode_id,
                        tenant_id=ep.tenant_id,
                        service=ep.service,
                        feature=ep.feature,
                        severity=ep.severity,
                        first_seen=datetime.fromtimestamp(ep.first_seen, tz=timezone.utc),
                        last_seen=datetime.fromtimestamp(ep.last_seen, tz=timezone.utc),
                        duration_seconds=round(max(0.0, ep.last_seen - ep.first_seen), 1),
                        peak_score=ep.peak_score,
                        current_score=ep.current_score,
                        event_count=ep.event_count,
                        status="CORRELATED",
                        incident_id=incident_dict["incident_id"],
                        details_json=json.dumps(ep.metadata)
                    )
                    session.add(ep_model)

                await session.commit()
        except Exception:
            pass

    async def _broadcast_incident_event(self, event_type: str, incident_dict: Dict[str, Any]):
        """Broadcasts real-time incident event over existing WebSocket connections."""
        payload = {
            "type": event_type,
            "event_type": event_type,
            "incident": incident_dict,
            "active_incidents": collector.active_incidents,
            "tenant_id": incident_dict.get("tenant_id"),
            "company": incident_dict.get("tenant_id"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await ws_manager.broadcast_tenant_event(incident_dict.get("tenant_id", "shopsphere"), payload)
        await ws_manager.broadcast(payload)


incident_pipeline = IncidentPipelineCoordinator()
