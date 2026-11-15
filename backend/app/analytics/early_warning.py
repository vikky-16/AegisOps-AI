"""
AegisOps AI - Early Warning Detection Engine (Requirement 4 & 24)
Monitors telemetry streams and feature trends to detect degradation before complete failure.
States: NORMAL -> WARNING -> DEGRADING -> CRITICAL
Generates proactive alerts with evidence and recommended actions.
Broadcasts 'warning.created' events over WebSocket.
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from collections import deque, defaultdict

from backend.app.api.websocket import ws_manager
from backend.app.logger import realtime_logger


class EarlyWarningThresholds:
    """Configurable degradation boundaries."""
    # Error rate (fraction 0.0 to 1.0)
    ERROR_RATE_WARNING = 0.015     # 1.5%
    ERROR_RATE_DEGRADING = 0.045   # 4.5%
    ERROR_RATE_CRITICAL = 0.12     # 12.0%

    # Latency p95 in milliseconds
    LATENCY_WARNING_MS = 180.0
    LATENCY_DEGRADING_MS = 450.0
    LATENCY_CRITICAL_MS = 1200.0

    # CPU Utilization (%)
    CPU_WARNING = 68.0
    CPU_DEGRADING = 80.0
    CPU_CRITICAL = 90.0

    # Memory Utilization (%)
    MEM_WARNING = 72.0
    MEM_DEGRADING = 83.0
    MEM_CRITICAL = 92.0

    # Database Connection Pool Utilization (%)
    DB_POOL_WARNING = 65.0
    DB_POOL_DEGRADING = 82.0
    DB_POOL_CRITICAL = 95.0


class EarlyWarningEngine:
    def __init__(self):
        # Service current state: (tenant_id, service) -> "NORMAL" | "WARNING" | "HIGH RISK" | "INCIDENT"
        self._service_states: Dict[str, str] = {}
        # Recent active alerts: rolling 100 alerts
        self._alerts_history: deque = deque(maxlen=100)
        # Last alert timestamp per service to throttle duplicate bursts: (tenant_id, service) -> float
        self._last_alert_time: Dict[str, float] = {}
        # Historical metric readings for rate-of-change and acceleration: key -> deque of (ts, err, lat, cpu, pool)
        self._metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=30))

    def _get_key(self, tenant_id: str, service: str) -> str:
        return f"{tenant_id.lower()}:{service.lower()}"

    def get_service_state(self, tenant_id: str, service: str) -> str:
        key = self._get_key(tenant_id, service)
        return self._service_states.get(key, "NORMAL")

    def evaluate_telemetry(
        self,
        tenant_id: str,
        service: str,
        features: Dict[str, Any],
        raw_attributes: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates current features and trends against early degradation boundaries (Part 6).
        Calculates:
        - Trend acceleration
        - Baseline deviation
        - Forecast threshold crossing (predicted in 3 minutes)
        - Failure probability %
        - Risk level: NORMAL -> WARNING -> HIGH RISK -> INCIDENT
        """
        now = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        key = self._get_key(tenant_id, service)
        prev_state = self._service_states.get(key, "NORMAL")

        # Extract metrics
        err_rate = float(features.get("error_rate", 0.0))
        lat_p95 = float(features.get("p95_latency", features.get("latency_p95_ms", 25.0)))
        cpu = float(features.get("cpu_percent", features.get("cpu_utilization", 12.0)))
        mem = float(features.get("memory_mb", features.get("memory_utilization", 128.0)))
        mem_pct = min(100.0, (mem / 1024.0) * 100.0) if mem < 1000.0 else min(100.0, mem / 10.0)

        attrs = raw_attributes or {}
        db_pool_pct = float(attrs.get("pool_utilization", attrs.get("active_connections", 4)) / max(1, attrs.get("max_pool_size", 20)) * 100.0)
        if "connection_pool_utilization" in features:
            db_pool_pct = float(features["connection_pool_utilization"]) * 100.0
        elif "db_pool_utilization" in features:
            db_pool_pct = float(features["db_pool_utilization"]) * 100.0

        timeout_rate = float(features.get("timeout_rate", 0.0))
        traffic_growth = float(features.get("traffic_growth_rate", features.get("request_growth_rate", 0.0)))
        rps = float(features.get("requests_per_second", features.get("requests_sec", 10.0)))

        # Track history for trend & 3-minute prediction
        history = self._metric_history[key]
        history.append((now, err_rate, lat_p95, cpu, db_pool_pct))

        # Calculate rate of change (slopes per minute)
        err_slope_min = 0.0
        lat_slope_min = 0.0
        cpu_slope_min = 0.0
        pool_slope_min = 0.0

        if len(history) >= 4:
            dt = max(1.0, history[-1][0] - history[0][0])
            err_slope_min = (history[-1][1] - history[0][1]) / (dt / 60.0)
            lat_slope_min = (history[-1][2] - history[0][2]) / (dt / 60.0)
            cpu_slope_min = (history[-1][3] - history[0][3]) / (dt / 60.0)
            pool_slope_min = (history[-1][4] - history[0][4]) / (dt / 60.0)

        # 3-minute extrapolation (rolling forecast)
        pred_pool_3min = max(0.0, min(100.0, db_pool_pct + (pool_slope_min * 3.0)))
        pred_cpu_3min = max(0.0, min(100.0, cpu + (cpu_slope_min * 3.0)))
        pred_err_3min = max(0.0, min(1.0, err_rate + (err_slope_min * 3.0)))
        pred_lat_3min = max(5.0, lat_p95 + (lat_slope_min * 3.0))

        # Check conditions & gather evidence
        evidence: List[str] = []
        is_incident = False
        is_high_risk = False
        is_warning = False

        # 1. DB Connection Pool
        if db_pool_pct >= 95.0 or (db_pool_pct >= 85.0 and pred_pool_3min >= 95.0):
            if db_pool_pct >= 95.0:
                is_incident = True
            else:
                is_high_risk = True
            evidence.append(f"Connection pool saturation: current {db_pool_pct:.1f}%, predicted in 3m: {pred_pool_3min:.1f}%")
        elif db_pool_pct >= 70.0 or pool_slope_min > 5.0:
            is_warning = True
            evidence.append(f"Connection pool elevating: {db_pool_pct:.1f}% (+{pool_slope_min:.1f}%/min)")

        # 2. Error rate checks
        if err_rate >= 0.12 or pred_err_3min >= 0.20:
            if err_rate >= 0.12:
                is_incident = True
            else:
                is_high_risk = True
            evidence.append(f"Error rate critical: {err_rate*100:.1f}%, forecast 3m: {pred_err_3min*100:.1f}%")
        elif err_rate >= 0.045 or pred_err_3min >= 0.08:
            is_high_risk = True
            evidence.append(f"Error rate accelerating: {err_rate*100:.1f}%, forecast 3m: {pred_err_3min*100:.1f}%")
        elif err_rate >= 0.015:
            is_warning = True
            evidence.append(f"Error rate elevated: {err_rate*100:.1f}%")

        # 3. Latency checks
        if lat_p95 >= 1200.0 or pred_lat_3min >= 2000.0:
            if lat_p95 >= 1200.0:
                is_incident = True
            else:
                is_high_risk = True
            evidence.append(f"P95 latency critical: {lat_p95:.1f}ms, forecast 3m: {pred_lat_3min:.1f}ms")
        elif lat_p95 >= 450.0 or pred_lat_3min >= 800.0:
            is_high_risk = True
            evidence.append(f"P95 latency degrading: {lat_p95:.1f}ms, forecast 3m: {pred_lat_3min:.1f}ms")
        elif lat_p95 >= 180.0:
            is_warning = True
            evidence.append(f"P95 latency elevated: {lat_p95:.1f}ms")

        # 4. CPU & Resource checks
        if cpu >= 90.0 or pred_cpu_3min >= 95.0:
            if cpu >= 90.0:
                is_incident = True
            else:
                is_high_risk = True
            evidence.append(f"CPU critical: {cpu:.1f}%, forecast 3m: {pred_cpu_3min:.1f}%")
        elif cpu >= 75.0 or cpu_slope_min > 8.0:
            is_warning = True
            evidence.append(f"CPU elevating: {cpu:.1f}% (+{cpu_slope_min:.1f}%/min)")

        # 5. Upstream timeouts
        if timeout_rate >= 0.05:
            is_high_risk = True
            evidence.append(f"Upstream timeout rate critical: {timeout_rate*100:.1f}%")
        elif timeout_rate >= 0.01:
            is_warning = True
            evidence.append(f"Upstream timeout rate elevated: {timeout_rate*100:.1f}%")

        # Determine 4-tier state: NORMAL -> WARNING -> HIGH RISK -> INCIDENT
        if is_incident:
            new_state = "INCIDENT"
            risk = "CRITICAL"
            prob = min(0.98, max(0.85, 0.70 + (db_pool_pct / 300.0) + (err_rate * 0.5)))
        elif is_high_risk:
            new_state = "HIGH RISK"
            risk = "HIGH"
            prob = min(0.88, max(0.65, 0.50 + (pred_pool_3min / 250.0) + (pred_err_3min * 0.8)))
        elif is_warning:
            new_state = "WARNING"
            risk = "MEDIUM"
            prob = min(0.60, max(0.35, 0.25 + (db_pool_pct / 400.0) + (err_rate * 0.5)))
        else:
            new_state = "NORMAL"
            risk = "LOW"
            prob = 0.05

        self._service_states[key] = new_state

        if new_state == "NORMAL":
            return None

        # Check alert throttling: at most 1 alert every 5 seconds per service unless state escalated
        last_t = self._last_alert_time.get(key, 0.0)
        state_escalated = (
            (prev_state == "NORMAL" and new_state in ("WARNING", "HIGH RISK", "INCIDENT")) or
            (prev_state == "WARNING" and new_state in ("HIGH RISK", "INCIDENT")) or
            (prev_state == "HIGH RISK" and new_state == "INCIDENT")
        )
        if not state_escalated and (now - last_t) < 5.0:
            return None

        self._last_alert_time[key] = now

        # Construct explainable reason and recommended action
        if db_pool_pct >= 70.0 or pred_pool_3min >= 85.0:
            reason = f"Connection utilization is increasing ({db_pool_pct:.1f}% -> {pred_pool_3min:.1f}%) while request volume ({rps:.1f} rps) remains elevated."
            recommended_action = "Monitor / prepare controlled recovery. Investigate connection leaks and long-running queries."
        elif lat_p95 >= 300.0 or pred_lat_3min >= 600.0:
            reason = f"Latency distribution is accelerating upward (+{lat_slope_min:.1f} ms/min), approaching SLA breach."
            recommended_action = "Inspect downstream service dependencies and database query times; prepare rate limiter."
        elif cpu >= 75.0 or pred_cpu_3min >= 85.0:
            reason = f"Worker process CPU saturation detected ({cpu:.1f}%), potential compute bottleneck."
            recommended_action = "Scale worker replicas or prepare traffic throttling."
        else:
            reason = f"Telemetry parameters show anomalous trend acceleration across {len(evidence)} metrics."
            recommended_action = f"Monitor {service} closely; prepare controlled diagnostic recovery if deterioration continues."

        alert_id = f"WARN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        alert_obj = {
            "alert_id": alert_id,
            "tenant_id": tenant_id,
            "service": service,
            "state": new_state,
            "risk": risk,
            "severity": risk,
            "failure_probability": round(prob * 100.0, 1),
            "reason": reason,
            "primary_metric": evidence[0] if evidence else f"{service} abnormal trend",
            "evidence": evidence,
            "current_metrics": {
                "error_rate": round(err_rate, 4),
                "latency_p95_ms": round(lat_p95, 2),
                "cpu_percent": round(cpu, 1),
                "memory_pct": round(mem_pct, 1),
                "db_pool_pct": round(db_pool_pct, 1)
            },
            "predicted_in_3_min": {
                "db_pool_pct": round(pred_pool_3min, 1),
                "cpu_percent": round(pred_cpu_3min, 1),
                "error_rate": round(pred_err_3min, 4),
                "latency_p95_ms": round(pred_lat_3min, 2)
            },
            "trend_rates_per_min": {
                "pool_slope_pct": round(pool_slope_min, 2),
                "cpu_slope_pct": round(cpu_slope_min, 2),
                "lat_slope_ms": round(lat_slope_min, 2)
            },
            "recommended_action": recommended_action,
            "incident_forming": new_state in ("HIGH RISK", "INCIDENT"),
            "detected_at": now_iso,
            "timestamp": now_iso
        }

        self._alerts_history.appendleft(alert_obj)

        realtime_logger.warn(
            f"[Early Warning] {new_state} (Risk: {risk}, Prob: {alert_obj['failure_probability']}%) on {service} ({tenant_id}): {reason}",
            alert_id=alert_id,
            service=service,
            tenant_id=tenant_id,
            evidence=evidence
        )

        # Broadcast both WebSocket events
        try:
            import asyncio
            asyncio.create_task(ws_manager.broadcast({
                "type": "EARLY_WARNING",
                "event": "ml.early_warning",
                "alert": alert_obj,
                "timestamp": now_iso
            }))
            asyncio.create_task(ws_manager.broadcast({
                "type": "EARLY_WARNING",
                "event": "warning.created",
                "alert": alert_obj,
                "timestamp": now_iso
            }))
        except Exception:
            pass

        return alert_obj

    async def broadcast_alert(self, alert_obj: Dict[str, Any]):
        """Helper to broadcast alert if called asynchronously."""
        try:
            await ws_manager.broadcast({
                "type": "EARLY_WARNING",
                "event": "ml.early_warning",
                "alert": alert_obj,
                "timestamp": alert_obj.get("timestamp", datetime.now(timezone.utc).isoformat())
            })
        except Exception:
            pass

    def get_recent_alerts(self, tenant_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if not tenant_id or tenant_id.lower() == "all":
            return list(self._alerts_history)[:limit]
        t_lower = tenant_id.lower()
        return [a for a in self._alerts_history if a.get("tenant_id", "").lower() == t_lower][:limit]

    def get_summary(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        alerts = self.get_recent_alerts(tenant_id, limit=100)
        warnings_count = sum(1 for a in alerts if a.get("state") == "WARNING")
        high_risk_count = sum(1 for a in alerts if a.get("state") == "HIGH RISK")
        incident_count = sum(1 for a in alerts if a.get("state") == "INCIDENT")

        return {
            "total_alerts": len(alerts),
            "warnings_count": warnings_count,
            "high_risk_count": high_risk_count,
            "incident_forming_count": incident_count,
            "active_degraded_services": [
                svc for svc, state in self._service_states.items() if state != "NORMAL"
            ],
            "recent_alerts": alerts[:10]
        }

    def get_warning_summary(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        s = self.get_summary(tenant_id)
        s["active_alerts_count"] = s["total_alerts"]
        s["alerts"] = s["recent_alerts"]
        return s


# Global singleton early warning engine
early_warning_engine = EarlyWarningEngine()

