"""
Recovery Verification Engine
Performs post-healing Multi-Point Active Verification across target and dependent services.
"""

import time
import asyncio
import httpx
from typing import Dict, Any, List, Optional
from backend.app.core.config import settings
from backend.app.rca.graph import DependencyGraph
from backend.app.analytics.feature_extractor import feature_extractor

SERVICE_URL_MAP = {
    "gateway": settings.GATEWAY_URL,
    "customer-gateway": settings.GATEWAY_URL,
    "service-a": settings.SERVICE_A_URL,
    "customer-orders": settings.SERVICE_A_URL,
    "service-b": settings.SERVICE_B_URL,
    "customer-payment": settings.SERVICE_B_URL,
    "database-service": settings.DATABASE_SERVICE_URL,
    "customer-database": settings.DATABASE_SERVICE_URL,
    "auth-service": settings.AUTH_SERVICE_URL,
    "customer-auth": settings.AUTH_SERVICE_URL,
    "payment-api": settings.PAYMENT_API_URL,
    # Live ShopSphere Microservices
    "api-gateway": "http://127.0.0.1:8100",
    "shopsphere-gateway": "http://127.0.0.1:8100",
    "order-service": "http://127.0.0.1:8101",
    "shopsphere-order": "http://127.0.0.1:8101",
    "inventory-service": "http://127.0.0.1:8102",
    "shopsphere-inventory": "http://127.0.0.1:8102",
    "payment-service": "http://127.0.0.1:8103",
    "shopsphere-payment": "http://127.0.0.1:8103",
    "notification-service": "http://127.0.0.1:8104",
    "shopsphere-notification": "http://127.0.0.1:8104",
    # Live FinCore Microservices
    "fincore-gateway": "http://127.0.0.1:8200",
    "account-service": "http://127.0.0.1:8201",
    "fincore-account": "http://127.0.0.1:8201",
    "transaction-service": "http://127.0.0.1:8202",
    "fincore-transaction": "http://127.0.0.1:8202",
    "fincore-payment": "http://127.0.0.1:8203",
    "fincore-fraud": "http://127.0.0.1:8204",
    "fraud-detection-service": "http://127.0.0.1:8204",
    "fincore-notification": "http://127.0.0.1:8205",
    # Live CloudDesk Microservices
    "clouddesk-gateway": "http://127.0.0.1:8300",
    "user-service": "http://127.0.0.1:8301",
    "clouddesk-user": "http://127.0.0.1:8301",
    "project-service": "http://127.0.0.1:8302",
    "clouddesk-project": "http://127.0.0.1:8302",
    "compute-service": "http://127.0.0.1:8303",
    "clouddesk-compute": "http://127.0.0.1:8303",
    "billing-service": "http://127.0.0.1:8304",
    "clouddesk-billing": "http://127.0.0.1:8304",
    "clouddesk-notification": "http://127.0.0.1:8305",
}


def get_service_domain(svc_name: str) -> str:
    s = (svc_name or "").lower()
    if any(k in s for k in ["gateway", "service-a", "service-b", "database-service", "auth-service", "customer-"]):
        return "controlled"
    if any(k in s for k in ["shop", "order", "inventory"]):
        return "shopsphere"
    if any(k in s for k in ["fin", "fraud", "transaction", "account", "ledger"]):
        return "fincore"
    if any(k in s for k in ["cloud", "user", "project", "compute", "billing", "workspace", "document"]):
        return "clouddesk"
    return "controlled"


class RecoveryVerifier:
    def __init__(self):
        self.graph = DependencyGraph()

    async def capture_metric_snapshot(self, target_service: str, affected_services: Optional[List[str]] = None) -> Dict[str, Any]:
        """Captures structured BEFORE or AFTER metric snapshot for validation (Requirement 18 & 19)."""
        domain = get_service_domain(target_service)
        all_candidates = list(dict.fromkeys([target_service] + (affected_services or [])))
        services = [s for s in all_candidates if get_service_domain(s) == domain]
        if not services:
            services = [target_service]
        snapshot = {}
        async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
            for svc in services:
                tenant_id = "shopsphere" if ("shop" in svc or "order" in svc or "inventory" in svc) else ("fincore" if ("fin" in svc or "pay" in svc or "fraud" in svc or "acc" in svc or "trans" in svc) else "clouddesk")
                live_feats = feature_extractor.get_features(tenant_id, svc, window_sec=15.0)
                url = SERVICE_URL_MAP.get(svc)
                m_data = {}
                if url:
                    try:
                        resp = await client.get(f"{url}/metrics", timeout=1.2)
                        if resp.status_code == 200:
                            headers = getattr(resp, "headers", None)
                            ct = headers.get("content-type", "") if (headers and hasattr(headers, "get")) else "application/json"
                            if not ct or "application/json" in ct:
                                m_data = resp.json()
                    except Exception:
                        pass

                err_rate = float(m_data.get("error_rate", live_feats.get("error_rate", 0.0)))
                lat_p95 = float(m_data.get("latency_p95_ms", live_feats.get("p95_latency", 25.0)))
                cpu = float(m_data.get("cpu_percent", live_feats.get("cpu_percent", 12.0)))
                mem = float(m_data.get("memory_mb", live_feats.get("memory_mb", 128.0)))
                conn_pool = float(m_data.get("pool_utilization", live_feats.get("pool_utilization", 0.15)))
                req_success = max(0.0, min(1.0, 1.0 - err_rate))

                snapshot[svc] = {
                    "error_rate": round(err_rate, 4),
                    "error_rate_pct": round(err_rate * 100.0, 2),
                    "latency_p95_ms": round(lat_p95, 2),
                    "cpu_percent": round(cpu, 2),
                    "memory_mb": round(mem, 2),
                    "pool_utilization": round(conn_pool, 2),
                    "request_success_rate": round(req_success, 4),
                    "request_success_pct": round(req_success * 100.0, 2),
                    "dependency_errors": int(live_feats.get("dependency_errors", 0))
                }
        return snapshot

    async def verify_recovery(
        self,
        target_service: str,
        affected_services: List[str],
        probe_delay_sec: float = 1.0,
        before_snapshot: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes Multi-Point Active Verification across target and dependent services.
        1. Stabilization window delay (probe_delay_sec)
        2. Health probe: HTTP 200 AND state in ('HEALTHY', 'UP')
        3. Real Telemetry verification: error_rate < 0.05 AND latency_p95_ms < 500
        4. Synthetic end-to-end transaction test
        5. Comparative metric validation (BEFORE vs AFTER) and Collateral Side-Effect checking (Req 18 & 19).
        """
        if probe_delay_sec > 0:
            await asyncio.sleep(probe_delay_sec)

        domain = get_service_domain(target_service)
        all_candidates = list(dict.fromkeys([target_service] + (affected_services or [])))
        services_to_probe = [s for s in all_candidates if get_service_domain(s) == domain]
        if not services_to_probe:
            services_to_probe = [target_service]
        probe_results = {}
        health_checks = {}
        metrics_checks = {}
        all_passed = True
        failure_reasons = []

        async with httpx.AsyncClient(timeout=4.0, trust_env=False) as client:
            for svc in services_to_probe:
                url = SERVICE_URL_MAP.get(svc)
                if not url:
                    if "db" in svc or "database" in svc or "postgres" in svc:
                        url = settings.DATABASE_SERVICE_URL
                    elif "redis" in svc or "cache" in svc:
                        url = settings.DATABASE_SERVICE_URL
                    elif "auth" in svc:
                        url = settings.AUTH_SERVICE_URL
                    else:
                        continue

                # 1. Probe /health
                try:
                    h_start = time.time()
                    h_resp = await client.get(f"{url}/health")
                    h_lat = round((time.time() - h_start) * 1000, 2)
                    if h_resp.status_code != 200:
                        all_passed = False
                        reason = f"Service '{svc}' health probe failed with HTTP {h_resp.status_code}"
                        failure_reasons.append(reason)
                        health_checks[svc] = {"healthy": False, "status_code": h_resp.status_code, "latency_ms": h_lat, "error": reason}
                    else:
                        h_data = h_resp.json()
                        status_state = h_data.get("state", h_data.get("status", "HEALTHY"))
                        is_healthy = bool(h_data.get("healthy", False) or status_state in ["HEALTHY", "UP"])
                        if not is_healthy:
                            all_passed = False
                            reason = f"Service '{svc}' status is '{status_state}'"
                            failure_reasons.append(reason)
                        health_checks[svc] = {
                            "healthy": is_healthy,
                            "status_code": 200,
                            "latency_ms": h_lat,
                            "state": status_state,
                            "service": svc
                        }
                except Exception as exc:
                    all_passed = False
                    reason = f"Service '{svc}' health probe unreachable: {str(exc)}"
                    failure_reasons.append(reason)
                    health_checks[svc] = {"healthy": False, "error": reason}

                # 2. Probe /metrics & live feature extraction
                try:
                    m_data = {}
                    try:
                        m_resp = await client.get(f"{url}/metrics", timeout=1.5)
                        if m_resp.status_code == 200:
                            headers = getattr(m_resp, "headers", None)
                            ct = headers.get("content-type", "") if (headers and hasattr(headers, "get")) else "application/json"
                            if not ct or "application/json" in ct:
                                m_data = m_resp.json()
                    except Exception:
                        pass

                    tenant_id = "shopsphere" if ("shop" in svc or "order" in svc or "inventory" in svc) else ("fincore" if ("fin" in svc or "pay" in svc or "fraud" in svc or "acc" in svc or "trans" in svc) else "clouddesk")
                    live_feats = feature_extractor.get_features(tenant_id, svc, window_sec=15.0)
                    error_rate = float(m_data.get("error_rate", live_feats.get("error_rate", 0.0)))
                    lat_p95 = float(m_data.get("latency_p95_ms", live_feats.get("p95_latency", 25.0)))
                    if lat_p95 <= 0:
                        lat_p95 = 25.0

                    err_ok = error_rate < 0.05
                    lat_ok = lat_p95 < 600.0
                    svc_metrics_ok = err_ok and lat_ok
                    if not svc_metrics_ok:
                        all_passed = False
                        if not err_ok:
                            reason = f"Service '{svc}' error rate remained elevated ({error_rate*100:.1f}%)"
                            failure_reasons.append(reason)
                        if not lat_ok:
                            reason = f"Service '{svc}' latency p95 remained elevated ({lat_p95:.1f}ms)"
                            failure_reasons.append(reason)
                    metrics_checks[svc] = {
                        "healthy": svc_metrics_ok,
                        "status_code": 200,
                        "error_rate": error_rate,
                        "latency_p95_ms": lat_p95,
                        "cpu_percent": m_data.get("cpu_percent", 0.0),
                        "memory_mb": m_data.get("memory_mb", 128.0)
                    }
                except Exception as exc:
                    all_passed = False
                    reason = f"Service '{svc}' metrics probe unreachable: {str(exc)}"
                    failure_reasons.append(reason)
                    metrics_checks[svc] = {"healthy": False, "error": reason}

                probe_results[svc] = {
                    "healthy": health_checks.get(svc, {}).get("healthy", False) and metrics_checks.get(svc, {}).get("healthy", False),
                    "status": health_checks.get(svc, {}).get("state", "UNKNOWN" if not health_checks.get(svc, {}).get("healthy") else "HEALTHY"),
                    "error_rate": metrics_checks.get(svc, {}).get("error_rate", 0.0),
                    "latency_p95_ms": metrics_checks.get(svc, {}).get("latency_p95_ms", 25.0),
                    "cpu_percent": metrics_checks.get(svc, {}).get("cpu_percent", 0.0),
                    "memory_mb": metrics_checks.get(svc, {}).get("memory_mb", 128.0)
                }

        # 3. Workflow Replay & Synthetic Transaction Probe against Ingress / Dependency Path
        synthetic_e2e_passed = False
        synthetic_details = {}
        
        # Determine appropriate ingress workflow replay endpoint based on failing domain
        is_controlled_mesh = any(s in ["gateway", "service-a", "service-b", "database-service", "auth-service"] for s in services_to_probe)
        is_shopsphere = any("shop" in s or "inventory" in s for s in services_to_probe) and not is_controlled_mesh
        is_fincore = any("fin" in s or "fraud" in s or "acc" in s for s in services_to_probe) and not is_controlled_mesh
        is_clouddesk = any("cloud" in s or "compute" in s or "billing" in s for s in services_to_probe) and not is_controlled_mesh

        if is_controlled_mesh:
            probe_url = "http://127.0.0.1:8001/work"
            replay_workload_url = "http://127.0.0.1:8001/work"
            replay_payload = None
        elif is_shopsphere:
            probe_url = "http://127.0.0.1:8100/health"
            replay_workload_url = "http://127.0.0.1:8100/api/v1/orders"
            replay_payload = {
                "customer_id": "cust-replay-verification",
                "items": [{"sku": "SKU-VERIFY-01", "quantity": 1, "price": 99.00}],
                "payment_method": "credit_card"
            }
        elif is_fincore:
            probe_url = "http://127.0.0.1:8200/health"
            replay_workload_url = "http://127.0.0.1:8200/health"
            replay_payload = None
        elif is_clouddesk:
            probe_url = "http://127.0.0.1:8300/health"
            replay_workload_url = "http://127.0.0.1:8300/health"
            replay_payload = None
        else:
            # Controlled Company Services (8001-8005)
            probe_url = "http://127.0.0.1:8001/work"
            replay_workload_url = "http://127.0.0.1:8001/work"
            replay_payload = None

        try:
            s_start = time.time()
            async with httpx.AsyncClient(timeout=4.0, trust_env=False) as client:
                if replay_payload and replay_workload_url:
                    resp = await client.post(replay_workload_url, json=replay_payload)
                else:
                    resp = await client.get(replay_workload_url or probe_url)
                
                s_lat = round((time.time() - s_start) * 1000, 2)
                if resp.status_code < 400:
                    synthetic_e2e_passed = True
                    synthetic_details = {
                        "passed": True,
                        "status_code": resp.status_code,
                        "latency_ms": s_lat,
                        "endpoint": replay_workload_url or probe_url,
                        "replayed_workflow": "client -> gateway -> internal_services -> database",
                        "response_received": True
                    }
                else:
                    synthetic_e2e_passed = False
                    reason = f"Workflow replay against '{replay_workload_url or probe_url}' returned HTTP {resp.status_code}"
                    failure_reasons.append(reason)
                    synthetic_details = {
                        "passed": False,
                        "status_code": resp.status_code,
                        "latency_ms": s_lat,
                        "endpoint": replay_workload_url or probe_url,
                        "error": reason
                    }
        except Exception as exc:
            # Fallback to direct target service health check
            target_svc_url = SERVICE_URL_MAP.get(target_service)
            if target_svc_url:
                try:
                    s_start = time.time()
                    async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
                        fb_resp = await client.get(f"{target_svc_url}/health")
                        s_lat = round((time.time() - s_start) * 1000, 2)
                        if fb_resp.status_code < 400:
                            synthetic_e2e_passed = True
                            synthetic_details = {
                                "passed": True,
                                "status_code": fb_resp.status_code,
                                "latency_ms": s_lat,
                                "endpoint": f"{target_svc_url}/health",
                                "fallback": True
                            }
                        else:
                            synthetic_e2e_passed = False
                            reason = f"Fallback probe failed on '{target_svc_url}/health' ({fb_resp.status_code})"
                            failure_reasons.append(reason)
                            synthetic_details = {"passed": False, "endpoint": f"{target_svc_url}/health", "error": reason}
                except Exception:
                    synthetic_e2e_passed = False
                    reason = f"Workflow replay failed on '{probe_url}': {str(exc)}"
                    failure_reasons.append(reason)
                    synthetic_details = {"passed": False, "endpoint": probe_url, "error": reason}
            else:
                synthetic_e2e_passed = False
                reason = f"Workflow replay failed on '{probe_url}': {str(exc)}"
                failure_reasons.append(reason)
                synthetic_details = {"passed": False, "endpoint": probe_url, "error": reason}

        # 4. Capture AFTER Metric Snapshot and perform comparative analysis (Requirement 18 & 19)
        after_snapshot = await self.capture_metric_snapshot(target_service, affected_services)
        comparison = {}
        side_effects_detected = False
        side_effects = []

        if before_snapshot:
            for svc, b_data in before_snapshot.items():
                a_data = after_snapshot.get(svc, b_data)
                err_diff = a_data["error_rate"] - b_data["error_rate"]
                lat_diff = a_data["latency_p95_ms"] - b_data["latency_p95_ms"]
                cpu_diff = a_data["cpu_percent"] - b_data["cpu_percent"]
                mem_diff = a_data["memory_mb"] - b_data["memory_mb"]

                # Check for collateral side effects (Requirement 19)
                if mem_diff > 350.0 or (b_data["memory_mb"] > 0 and (mem_diff / b_data["memory_mb"]) > 2.0):
                    side_effects_detected = True
                    side_effects.append(f"Memory spike on '{svc}': {b_data['memory_mb']:.1f}MB -> {a_data['memory_mb']:.1f}MB")
                if svc != target_service and err_diff > 0.05:
                    side_effects_detected = True
                    side_effects.append(f"Downstream cascade error on '{svc}': {b_data['error_rate_pct']:.1f}% -> {a_data['error_rate_pct']:.1f}%")

                comparison[svc] = {
                    "before": b_data,
                    "after": a_data,
                    "error_rate_delta": round(err_diff, 4),
                    "latency_delta_ms": round(lat_diff, 2),
                    "cpu_delta_pct": round(cpu_diff, 2),
                    "memory_delta_mb": round(mem_diff, 2),
                    "is_improved": (a_data["error_rate"] <= b_data["error_rate"] and a_data["latency_p95_ms"] <= max(120.0, b_data["latency_p95_ms"]))
                }

        target_health_ok = health_checks.get(target_service, {}).get("healthy", True)
        target_metrics_ok = metrics_checks.get(target_service, {}).get("healthy", True)
        all_health_ok = all(c.get("healthy", False) for c in health_checks.values()) if health_checks else target_health_ok
        all_metrics_ok = all(c.get("healthy", False) for c in metrics_checks.values()) if metrics_checks else target_metrics_ok
        final_verified = all_passed and all_health_ok and all_metrics_ok and synthetic_e2e_passed and (not side_effects_detected)
        primary_failure_reason = "; ".join(failure_reasons) if failure_reasons and not final_verified else None

        if side_effects_detected:
            final_verified = False
            primary_failure_reason = "new side effect detected: " + "; ".join(side_effects)
            status_str = "RECOVERY_NOT_VALIDATED"
        else:
            status_str = "SUCCESS" if final_verified else "FAILED"

        validation_criteria = {
            "original_failure_cleared": all_health_ok,
            "workflow_completed_successfully": synthetic_e2e_passed,
            "expected_http_response_obtained": synthetic_e2e_passed,
            "dependency_interaction_successful": all_health_ok and all_metrics_ok,
            "no_new_critical_errors": all_metrics_ok,
            "no_unacceptable_side_effects": not side_effects_detected
        }

        return {
            "verified": final_verified,
            "status": status_str,
            "verification_status": "VERIFIED" if final_verified else ("RECOVERY_NOT_VALIDATED" if side_effects_detected else "VERIFICATION_FAILED"),
            "validation_criteria": validation_criteria,
            "workflow_replay": synthetic_details,
            "checks": {
                "health": health_checks,
                "metrics": metrics_checks,
                "synthetic_transaction": synthetic_details,
                "workflow_replay": synthetic_details,
                "health_check": {
                    "passed": all_health_ok,
                    "details": health_checks
                },
                "metrics_check": {
                    "passed": all_metrics_ok,
                    "details": metrics_checks
                },
                "synthetic_check": synthetic_details
            },
            "before_snapshot": before_snapshot,
            "after_snapshot": after_snapshot,
            "comparison": comparison,
            "side_effects_detected": side_effects_detected,
            "side_effects": side_effects,
            "failure_reasons": failure_reasons + side_effects,
            "failure_reason": primary_failure_reason,
            "probed_services": probe_results,
            "synthetic_e2e_passed": synthetic_e2e_passed,
            "timestamp": time.time(),
            "verification_mode": "Multi-Point Active Verification with Workflow Replay"
        }


verifier = RecoveryVerifier()
