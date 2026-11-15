"""
Services Observatory API Endpoints
Provides service discovery, live health, metrics, downstream dependencies, and upstream dependents.
"""

from fastapi import APIRouter, HTTPException, Header, Query
from typing import List, Dict, Any, Optional
from backend.app.monitoring.collector import collector, SERVICES_CONFIG
from backend.app.rca.dynamic_graph import dynamic_graph

router = APIRouter(prefix="/services", tags=["Services"])


@router.get("")
async def get_services(
    tenant_id: Optional[str] = Query(None),
    x_tenant_id: Optional[str] = Header(None)
):
    """Returns registered microservices with their canonical operational and telemetry state, isolated by tenant."""
    t_id = tenant_id or x_tenant_id or "shopsphere"
    from backend.app.services.canonical_state import canonical_state_manager
    canonical_states = canonical_state_manager.get_all_services_state(t_id, active_incidents=collector.active_incidents)

    result = []
    for st in canonical_states:
        result.append({
            "service_id": st.service_id,
            "name": st.service_name,
            "display_name": st.display_name,
            "role": st.role,
            "service_type": st.service_type,
            "environment": st.environment,
            "resource_id": f"/services/{t_id}/workloads/{st.service_name}",
            "resource_group": "aegisops-mesh",
            "owner": "Core SRE",
            "criticality": "CRITICAL" if st.service_name in ["database-service", "gateway", "api-gateway"] else "HIGH",
            "port": st.port,
            "url": f"http://127.0.0.1:{st.port}",
            "status": st.operational_status.value,
            "operational_status": st.operational_status.value,
            "telemetry_status": st.telemetry_status.value,
            "healthy": st.operational_status.value == "HEALTHY",
            "cpu_percent": st.cpu,
            "memory_mb": st.memory,
            "request_count": int(st.request_rate * 5),
            "request_rate": st.request_rate,
            "error_count": int(st.request_rate * 5 * st.error_rate),
            "error_rate": st.error_rate,
            "latency_p50_ms": st.p50,
            "latency_p90_ms": st.p90,
            "latency_p95_ms": st.p95,
            "latency_p99_ms": st.p99,
            "active_connections": 8 if st.operational_status.value == "HEALTHY" else 0,
            "anomaly_score": 0.95 if st.operational_status.value in ["CRITICAL", "DOWN"] else (0.45 if st.operational_status.value == "DEGRADED" else 0.0),
            "is_anomaly": 1 if st.operational_status.value in ["CRITICAL", "DEGRADED", "DOWN"] else 0,
            "tenant_id": t_id,
            "last_telemetry_at": st.last_telemetry_at,
            "last_health_check_at": st.last_health_check_at,
            "is_stale": st.is_stale,
            "stale_seconds": st.stale_seconds,
            "updated_at": st.updated_at,
            "status_reasons": st.status_reasons
        })
    return result


@router.get("/status")
async def get_services_status(
    tenant_id: Optional[str] = Query(None),
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Canonical Service Status & Connection Endpoint (Part 8).
    Returns authoritative operational status, connection status, timestamps, and health score.
    """
    t_id = tenant_id or x_tenant_id or "shopsphere"
    from backend.app.services.canonical_state import canonical_state_manager
    canonical_states = canonical_state_manager.get_all_services_state(t_id, active_incidents=collector.active_incidents)
    health_eval = canonical_state_manager.compute_system_health(t_id, active_incidents=collector.active_incidents)

    return {
        "tenant_id": t_id,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "system_health": health_eval,
        "services": [s.model_dump() for s in canonical_states]
    }


@router.get("/{service_id}/state")
async def get_single_service_state(
    service_id: str,
    tenant_id: Optional[str] = Query(None),
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Returns single authoritative canonical state for a given service (Part 1).
    """
    t_id = tenant_id or x_tenant_id or "shopsphere"
    name = service_id.replace("SVC-", "").lower()
    from backend.app.services.canonical_state import canonical_state_manager
    state = canonical_state_manager.get_service_operational_state(t_id, name, active_incidents=collector.active_incidents)
    return state.model_dump()


@router.get("/{service_id}/dependencies")
async def get_service_dependencies(service_id: str):
    """Returns direct downstream services that service_id depends on."""
    # Normalize ID / name
    name = service_id.replace("SVC-", "").lower()
    if name not in dynamic_graph.services and service_id in dynamic_graph.services:
        name = service_id
    
    deps = dynamic_graph.get_dependencies(name)
    return {
        "service": name,
        "dependencies": deps,
        "count": len(deps)
    }


@router.get("/{service_id}/dependents")
async def get_service_dependents(service_id: str):
    """Returns all upstream caller services that depend on service_id (downstream blast radius)."""
    name = service_id.replace("SVC-", "").lower()
    if name not in dynamic_graph.services and service_id in dynamic_graph.services:
        name = service_id

    dependents = dynamic_graph.get_dependents(name)
    return {
        "service": name,
        "dependents": dependents,
        "count": len(dependents),
        "dependency_chain": dynamic_graph.get_dependency_chain(name)
    }


@router.get("/observability/global")
async def get_global_service_observability(
    tenant_id: Optional[str] = Query(None),
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Returns enterprise global service health rollups, early warning states,
    and a dense service health matrix table computed from the canonical operational state.
    """
    t_id = tenant_id or x_tenant_id or "demo-tenant"
    from datetime import datetime, timezone
    from backend.app.services.canonical_state import canonical_state_manager
    canonical_states = canonical_state_manager.get_all_services_state(t_id, active_incidents=collector.active_incidents)
    health_eval = canonical_state_manager.compute_system_health(t_id, active_incidents=collector.active_incidents)

    services_list = []
    all_req_rates = []
    all_err_rates = []
    all_p95s = []

    for st in canonical_states:
        s_name = st.service_name
        deps = dynamic_graph.get_dependencies(s_name)

        all_req_rates.append(st.request_rate)
        all_err_rates.append(st.error_rate)
        if st.p95 is not None:
            all_p95s.append(st.p95)

        services_list.append({
            "name": s_name,
            "display_name": st.display_name,
            "service_id": st.service_id,
            "service_type": st.service_type,
            "status": st.operational_status.value,
            "operational_status": st.operational_status.value,
            "telemetry_status": st.telemetry_status.value,
            "health_state": st.operational_status.value,
            "request_rate": st.request_rate,
            "error_rate": round(st.error_rate * 100, 2),
            "latency_p50": st.p50,
            "latency_p95": st.p95,
            "latency_p99": st.p99,
            "cpu_percent": st.cpu,
            "memory_mb": st.memory,
            "availability": 0.0 if st.operational_status.value in ["CRITICAL", "DOWN"] else max(0.0, round(100.0 - (st.error_rate * 100), 2)),
            "dependencies_count": len(deps),
            "dependencies": [d["target_service"] for d in deps],
            "active_incident_id": None if st.active_incidents == 0 else "ACTIVE_INCIDENT",
            "is_stale": st.is_stale,
            "stale_seconds": st.stale_seconds,
            "last_telemetry_at": st.last_telemetry_at,
            "trend": "DEGRADING" if st.operational_status.value in ["DEGRADED", "CRITICAL"] else "STABLE"
        })

    counts = health_eval["counts"]
    avg_avail = round(sum(s["availability"] for s in services_list) / max(1, len(services_list)), 2)
    overall_err = round((sum(all_err_rates) / max(1, len(all_err_rates))) * 100, 2)
    overall_req = sum(all_req_rates)
    overall_p95 = round(sum(all_p95s) / max(1, len(all_p95s)), 1) if all_p95s else 0.0
    
    # Strictly filter active incidents by tenant
    active_tenant_incs = [
        i for i in collector.active_incidents 
        if i.get("status") not in ["RESOLVED", "CLOSED", "REJECTED"] 
        and (i.get("tenant_id") == t_id or not i.get("tenant_id") or t_id in ("demo-tenant", "all", "*"))
    ]
    active_incidents_cnt = len(active_tenant_incs)

    incidents_by_severity = {
        "CRITICAL": len([i for i in active_tenant_incs if (i.get("severity") or "").upper() == "CRITICAL"]),
        "HIGH": len([i for i in active_tenant_incs if (i.get("severity") or "").upper() == "HIGH"]),
        "MEDIUM": len([i for i in active_tenant_incs if (i.get("severity") or "").upper() == "MEDIUM"]),
        "LOW": len([i for i in active_tenant_incs if (i.get("severity") or "").upper() in ("LOW", "INFO")])
    }

    degraded_services = [
        {
            "name": s["name"],
            "display_name": s["display_name"],
            "status": s["status"],
            "error_rate": s["error_rate"],
            "latency_p95": s["latency_p95"],
            "is_stale": s["is_stale"]
        }
        for s in services_list if s["status"] in ["DEGRADED", "CRITICAL", "DOWN", "CRASHED"]
    ]

    uninstrumented_services = [
        {
            "name": s["name"],
            "display_name": s["display_name"],
            "status": s["status"],
            "telemetry_status": s["telemetry_status"],
            "is_stale": s["is_stale"]
        }
        for s in services_list if s["status"] == "UNKNOWN" or s["telemetry_status"] in ["DISCONNECTED", "PENDING"] or s["is_stale"]
    ]

    now_iso = datetime.now(timezone.utc).isoformat()
    last_update_ts = max((s["last_telemetry_at"] for s in services_list if s.get("last_telemetry_at")), default=now_iso)
    monitored_services_count = len([s for s in services_list if s["telemetry_status"] != "DISCONNECTED"])
    telemetry_coverage_pct = round((monitored_services_count / max(1, len(services_list))) * 100.0, 1)

    if counts["critical"] > 0 or counts["down"] > 0:
        early_warning = "CRITICAL"
    elif counts["degraded"] > 0:
        early_warning = "DEGRADING"
    elif counts["unknown"] > 0:
        early_warning = "WARNING"
    else:
        early_warning = "NORMAL"

    return {
        "summary": {
            "tenant_id": t_id,
            "total_services": len(services_list),
            "monitored_services": monitored_services_count,
            "telemetry_coverage_pct": telemetry_coverage_pct,
            "healthy": counts["healthy"],
            "warning": counts["unknown"],
            "degraded": counts["degraded"],
            "critical": counts["critical"] + counts["down"],
            "unknown": counts["unknown"],
            "availability": avg_avail,
            "overall_error_rate": overall_err,
            "overall_request_rate": overall_req,
            "p95_latency": overall_p95,
            "active_incidents": active_incidents_cnt,
            "incidents_by_severity": incidents_by_severity,
            "degraded_services": degraded_services,
            "uninstrumented_services": uninstrumented_services,
            "early_warning": early_warning,
            "system_health_score": health_eval["health_score"],
            "last_telemetry_at": last_update_ts,
            "telemetry_freshness_seconds": 2
        },
        "services": services_list
    }


@router.get("/observability/telemetry-analysis")
async def get_telemetry_analysis(
    time_range: str = Query("15m", pattern="^(5m|15m|30m|1h|6h|24h)$"),
    tenant_id: Optional[str] = Query(None),
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Returns enterprise operational observability visualizations:
    - Incident Signature Heatmap (Time vs Failure Category)
    - Error Rate by Failure Type (Time Series)
    - Service Error Profiles (Per-service operational metrics)
    - Reliability Fingerprints (Multi-dimensional radar metrics)
    - Error Taxonomy Summary (Categorized counts and rates)
    """
    t_id = tenant_id or x_tenant_id or "demo-tenant"
    from backend.app.services.canonical_state import canonical_state_manager
    from datetime import datetime, timezone, timedelta

    canonical_states = canonical_state_manager.get_all_services_state(t_id, active_incidents=collector.active_incidents)
    active_incs = [i for i in collector.active_incidents if i.get("status") not in ["RESOLVED", "CLOSED", "REJECTED"]]

    # 1. Categories for Incident Signature Heatmap
    categories = [
        "HTTP 400", "HTTP 401", "HTTP 403", "HTTP 404", "HTTP 429",
        "HTTP 500", "HTTP 502", "HTTP 503", "TIMEOUT", "DATABASE",
        "CACHE", "DEPENDENCY", "EXCEPTION", "LATENCY", "RESOURCE",
        "DEPLOYMENT", "OTHER"
    ]

    now = datetime.now(timezone.utc)
    window_deltas = {
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "24h": timedelta(hours=24),
    }
    span = window_deltas.get(time_range, timedelta(minutes=15))
    num_buckets = 8
    bucket_step = span / num_buckets

    buckets = []
    for b in range(num_buckets):
        b_time = now - (span - (b * bucket_step))
        buckets.append({
            "index": b,
            "timestamp": b_time.isoformat(),
            "time_label": b_time.strftime("%H:%M:%S" if time_range in ["5m", "15m", "30m", "1h"] else "%m-%d %H:%M")
        })

    active_failure_map = {}
    taxonomy_counts = {cat: {"count": 0, "incident_ids": set(), "rate": 0.0} for cat in [
        "HTTP 5xx", "HTTP 4xx", "TIMEOUTS", "DATABASE", "DEPENDENCY", "EXCEPTIONS", "LATENCY", "RESOURCE", "OTHER"
    ]}

    for inc in active_incs:
        inc_id = inc.get("incident_id", "INC-001")
        root_cat = (inc.get("root_cause_category") or inc.get("title") or "").upper()
        root_svc = inc.get("primary_service", "database-service")
        aff_svcs = inc.get("affected_services", [root_svc])

        if "CONNECTION" in root_cat or "DATABASE" in root_cat or "POOL" in root_cat:
            active_failure_map["DATABASE"] = {"services": [root_svc], "incidents": [inc_id], "intensity": 0.95}
            active_failure_map["TIMEOUT"] = {"services": [s for s in aff_svcs if s != root_svc], "incidents": [inc_id], "intensity": 0.75}
            active_failure_map["RESOURCE"] = {"services": [root_svc], "incidents": [inc_id], "intensity": 0.85}
            active_failure_map["HTTP 500"] = {"services": ["gateway"], "incidents": [inc_id], "intensity": 0.65}
            active_failure_map["HTTP 502"] = {"services": ["gateway"], "incidents": [inc_id], "intensity": 0.55}
            active_failure_map["DEPENDENCY"] = {"services": [s for s in aff_svcs if s != root_svc], "incidents": [inc_id], "intensity": 0.70}

            taxonomy_counts["DATABASE"]["count"] += 142
            taxonomy_counts["DATABASE"]["incident_ids"].add(inc_id)
            taxonomy_counts["TIMEOUTS"]["count"] += 89
            taxonomy_counts["TIMEOUTS"]["incident_ids"].add(inc_id)
            taxonomy_counts["RESOURCE"]["count"] += 67
            taxonomy_counts["RESOURCE"]["incident_ids"].add(inc_id)
            taxonomy_counts["HTTP 5xx"]["count"] += 128
            taxonomy_counts["HTTP 5xx"]["incident_ids"].add(inc_id)
            taxonomy_counts["DEPENDENCY"]["count"] += 54
            taxonomy_counts["DEPENDENCY"]["incident_ids"].add(inc_id)
        elif "DEPLOYMENT" in root_cat or "ROLLBACK" in root_cat:
            active_failure_map["DEPLOYMENT"] = {"services": [root_svc], "incidents": [inc_id], "intensity": 0.90}
            active_failure_map["EXCEPTION"] = {"services": [root_svc], "incidents": [inc_id], "intensity": 0.80}
            taxonomy_counts["EXCEPTIONS"]["count"] += 76
            taxonomy_counts["EXCEPTIONS"]["incident_ids"].add(inc_id)
            taxonomy_counts["OTHER"]["count"] += 35
            taxonomy_counts["OTHER"]["incident_ids"].add(inc_id)
        else:
            active_failure_map["OTHER"] = {"services": [root_svc], "incidents": [inc_id], "intensity": 0.60}
            taxonomy_counts["OTHER"]["count"] += 20
            taxonomy_counts["OTHER"]["incident_ids"].add(inc_id)

    heatmap_matrix = []
    for cat in categories:
        cells = []
        is_active_cat = cat in active_failure_map
        for b_idx, b in enumerate(buckets):
            if is_active_cat and b_idx >= 4:
                info = active_failure_map[cat]
                cnt = int(info["intensity"] * (b_idx - 3) * 18)
                cells.append({
                    "category": cat,
                    "bucket_index": b_idx,
                    "time_label": b["time_label"],
                    "timestamp": b["timestamp"],
                    "count": cnt,
                    "intensity": min(1.0, round(info["intensity"] * ((b_idx - 3) / 4.0), 2)),
                    "services": info["services"],
                    "incident_ids": info["incidents"]
                })
            else:
                cells.append({
                    "category": cat,
                    "bucket_index": b_idx,
                    "time_label": b["time_label"],
                    "timestamp": b["timestamp"],
                    "count": 0,
                    "intensity": 0.0,
                    "services": [],
                    "incident_ids": []
                })
        heatmap_matrix.append({
            "category": cat,
            "cells": cells,
            "total_count": sum(c["count"] for c in cells)
        })

    # 2. Error Rate by Failure Type (Time Series)
    time_series_by_type = []
    has_active = len(active_incs) > 0
    num_pts = 12
    pt_step = span / num_pts
    for p in range(num_pts):
        pt_time = now - (span - (p * pt_step))
        t_label = pt_time.strftime("%H:%M:%S" if time_range in ["5m", "15m", "30m", "1h"] else "%m-%d %H:%M")
        escalation = (p / (num_pts - 1)) if has_active and p >= 4 else 0.0

        all_prob = round(0.4 + (escalation * 41.6), 2)
        db_err = round(0.1 + (escalation * 38.2), 2) if "DATABASE" in active_failure_map else 0.1
        timeout_err = round(0.05 + (escalation * 18.5), 2) if "TIMEOUT" in active_failure_map else 0.05
        http_err = round(0.2 + (escalation * 21.0), 2) if "HTTP 500" in active_failure_map else 0.2
        dep_err = round(0.05 + (escalation * 14.0), 2) if "DEPENDENCY" in active_failure_map else 0.05
        exc_err = round(0.02 + (escalation * 8.5), 2) if "EXCEPTION" in active_failure_map else 0.02
        lat_val = round(24.0 + (escalation * 821.0), 1)
        res_val = round(15.0 + (escalation * 85.0), 1)

        is_anom = has_active and p == 7
        anom_note = "Incident Inception: Connection Pool Saturation Detected" if is_anom else None

        time_series_by_type.append({
            "timestamp": pt_time.isoformat(),
            "time_label": t_label,
            "all_problems": all_prob,
            "http_errors": http_err,
            "database": db_err,
            "timeouts": timeout_err,
            "dependency": dep_err,
            "exceptions": exc_err,
            "latency": lat_val,
            "resource": res_val,
            "is_anomaly": is_anom,
            "anomaly_note": anom_note
        })

    # 3. Service Error Profiles
    service_profiles = []
    for st in canonical_states:
        s_name = st.service_name
        is_crit = st.operational_status.value == "CRITICAL"
        is_deg = st.operational_status.value == "DEGRADED"

        if is_crit:
            dom_problem = "DB_CONNECTION_EXHAUSTION" if "database" in s_name else "HTTP_500_CRITICAL_FAILURE"
        elif is_deg:
            dom_problem = "DATABASE_TIMEOUT_CASCADE" if "b" in s_name else "HTTP_502_BAD_GATEWAY" if "gateway" in s_name else "DOWNSTREAM_LATENCY"
        else:
            dom_problem = "CLEAN_BASELINE"

        base_rate = 0.35 if "database" in s_name else 0.15

        service_profiles.append({
            "service": s_name,
            "display_name": st.display_name,
            "current_error_rate": round(st.error_rate * 100, 2),
            "baseline_error_rate": base_rate,
            "p95_latency": round(st.p95, 1) if st.p95 else 24.0,
            "request_volume": st.request_rate,
            "dominant_failure_type": dom_problem,
            "severity": st.operational_status.value,
            "status": st.operational_status.value,
            "active_incident_id": active_incs[0].get("incident_id") if (is_crit or is_deg) and active_incs else None
        })

    # 4. Reliability Fingerprints
    reliability_fingerprints = []
    for st in canonical_states:
        s_name = st.service_name
        err_pct = st.error_rate * 100
        p95 = st.p95 or 24.0

        err_score = max(5.0, round(100.0 - (err_pct * 2.2), 1))
        lat_score = max(5.0, round(100.0 - min(95.0, max(0.0, (p95 - 20.0) / 8.5)), 1))
        traffic_score = 92.0 if st.request_rate > 500 else 60.0
        dep_score = 35.0 if st.operational_status.value in ["CRITICAL", "DEGRADED"] else 98.0
        exc_score = max(10.0, round(100.0 - (err_pct * 1.5), 1))
        res_score = max(10.0, round(100.0 - (st.cpu or 20.0), 1))

        reliability_fingerprints.append({
            "service": s_name,
            "display_name": st.display_name,
            "status": st.operational_status.value,
            "dimensions": [
                {"dimension": "Error Rate", "score": err_score, "raw": f"{round(err_pct, 1)}%"},
                {"dimension": "Latency", "score": lat_score, "raw": f"{round(p95, 1)}ms"},
                {"dimension": "Traffic", "score": traffic_score, "raw": f"{st.request_rate} req/m"},
                {"dimension": "Dependency Health", "score": dep_score, "raw": f"{'DEGRADED' if dep_score < 70 else 'CLEAN'}"},
                {"dimension": "Exception Rate", "score": exc_score, "raw": f"{'ELEVATED' if exc_score < 70 else 'LOW'}"},
                {"dimension": "Resource Pressure", "score": res_score, "raw": f"{round(st.cpu or 20, 1)}% CPU"}
            ]
        })

    # 5. Error Taxonomy Summary
    taxonomy_list = []
    for cat_name, val in taxonomy_counts.items():
        taxonomy_list.append({
            "category": cat_name,
            "count": val["count"],
            "rate_pct": round((val["count"] / max(1, sum(v["count"] for v in taxonomy_counts.values()))) * 100, 1) if val["count"] > 0 else 0.0,
            "incident_ids": list(val["incident_ids"])
        })

    return {
        "time_range": time_range,
        "tenant_id": t_id,
        "heatmap": {
            "categories": categories,
            "buckets": buckets,
            "rows": heatmap_matrix
        },
        "error_rate_by_type": time_series_by_type,
        "service_error_profiles": service_profiles,
        "reliability_fingerprints": reliability_fingerprints,
        "error_taxonomy_summary": taxonomy_list
    }


@router.get("/{service_id}/observability")
async def get_service_observability(
    service_id: str,
    time_range: str = Query("15m", pattern="^(5m|15m|30m|1h|6h|24h)$"),
    tenant_id: Optional[str] = Query(None),
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Returns granular operational observability metrics, real historical time-series,
    waterfall performance analysis, baseline vs current comparisons, and health trends
    for the requested service across time windows (5m, 15m, 30m, 1h, 6h, 24h).
    """
    t_id = tenant_id if isinstance(tenant_id, str) and tenant_id else (x_tenant_id if isinstance(x_tenant_id, str) and x_tenant_id else "demo-tenant")
    name = service_id.replace("SVC-", "").lower()
    alias_map = {
        "order-service": "service-a",
        "payment-service": "service-b",
        "api-gateway": "gateway",
        "redis": "cache"
    }
    canonical_name = alias_map.get(name, name)
    
    from backend.app.services.canonical_state import canonical_state_manager
    c_st = canonical_state_manager.get_service_operational_state(t_id, canonical_name, collector.active_incidents)
    raw_history = collector.metric_history.get(canonical_name, [])
    m = collector.latest_metrics.get(canonical_name, {})
    h = collector.latest_health.get(canonical_name, {})
    svc = next((s for s in SERVICES_CONFIG if s["name"] == canonical_name), {})

    computed_status = c_st.operational_status.value
    is_healthy = (computed_status == "HEALTHY")
    err_rate = c_st.error_rate
    p95_lat = c_st.p95 or m.get("latency_p95_ms", 18.0)
    p50_lat = c_st.p50 or m.get("latency_p50_ms", 12.0)
    p99_lat = c_st.p99 or (p95_lat * 1.35)

    availability = 0.0 if computed_status in ["CRITICAL", "DOWN"] else max(0.0, round(100.0 - (err_rate * 100), 2))
    req_rate = c_st.request_rate
    throughput = round(req_rate / 60.0, 1)

    # Convert raw_history to time_series
    time_series = []
    points_source = raw_history if len(raw_history) > 0 else [m]
    
    window_limits = {
        "5m": 15,
        "15m": 30,
        "30m": 45,
        "1h": 60,
        "6h": 60,
        "24h": 60
    }
    limit = window_limits.get(time_range, 30)
    selected_points = points_source[-limit:]

    for i, pt in enumerate(selected_points):
        pt_ts = pt.get("timestamp")
        if pt_ts:
            try:
                t_str = pt_ts.split("T")[1][:8] if "T" in pt_ts else pt_ts[:8]
            except Exception:
                t_str = f"-{(len(selected_points) - i) * 5}s"
        else:
            t_str = f"-{(len(selected_points) - i) * 5}s"

        p_err = pt.get("error_rate", err_rate)
        p_p95 = pt.get("latency_p95_ms", p95_lat)
        p_p50 = pt.get("latency_p50_ms", p50_lat)
        p_req = max(10, int(pt.get("request_count", 10) * 12))
        p_cpu = pt.get("cpu_percent", m.get("cpu_percent", c_st.cpu or 10.0))
        p_ram = pt.get("memory_mb", m.get("memory_mb", c_st.memory or 128.0))
        
        # Determine status of this point
        if p_err > 0.25 or p_p95 > 500:
            pt_status = "CRITICAL"
        elif p_err > 0.05 or p_p95 > 250:
            pt_status = "DEGRADED"
        else:
            pt_status = "HEALTHY"

        time_series.append({
            "time": t_str,
            "timestamp": pt_ts or f"T-{i}",
            "request_rate": p_req,
            "error_rate": round(p_err * 100, 2),
            "latency_p50": round(p_p50, 1),
            "latency_p95": round(p_p95, 1),
            "latency_p99": round(p_p95 * 1.35, 1),
            "cpu_percent": round(p_cpu, 1),
            "memory_mb": round(p_ram, 1),
            "throughput": round(p_req / 60.0, 1),
            "availability": 0.0 if p_err >= 1.0 else max(0.0, round(100.0 - (p_err * 100), 1)),
            "status": pt_status
        })

    # Health trend sequence
    health_trend = []
    for idx, pt in enumerate(time_series[-8:]):
        health_trend.append({
            "step": idx + 1,
            "time": pt["time"],
            "status": pt["status"]
        })
    if not health_trend:
        health_trend = [{"step": 1, "time": "Now", "status": computed_status}]

    # Recent incidents involving this service strictly filtered by tenant
    matching_incidents = [
        {
            "incident_id": inc.get("incident_id"),
            "severity": inc.get("severity", "CRITICAL"),
            "title": inc.get("title", "Service Anomaly"),
            "status": inc.get("status", "OPEN"),
            "root_cause_service": inc.get("root_cause_service", inc.get("primary_service")),
            "problem_type": inc.get("root_cause_category") or inc.get("problem_type") or "ANOMALY",
            "created_at": inc.get("created_at") or inc.get("timestamp"),
            "tenant_id": inc.get("tenant_id")
        }
        for inc in (collector.active_incidents + collector.resolved_incidents[:10])
        if (inc.get("tenant_id", "demo-tenant") == t_id or t_id in ("demo-tenant", "all", "*")) and (
            inc.get("primary_service") == canonical_name or
            inc.get("root_cause_service") == canonical_name or
            canonical_name in inc.get("affected_services", [])
        )
    ]

    # Baseline definitions & deviation calculations
    base_map = {
        "gateway": {"latency_p95_ms": 18.0, "error_rate": 0.05, "throughput": 25.0, "cpu_percent": 8.0, "memory_mb": 128.0},
        "service-a": {"latency_p95_ms": 22.0, "error_rate": 0.1, "throughput": 15.0, "cpu_percent": 12.0, "memory_mb": 140.0},
        "service-b": {"latency_p95_ms": 25.0, "error_rate": 0.15, "throughput": 12.0, "cpu_percent": 14.0, "memory_mb": 160.0},
        "database-service": {"latency_p95_ms": 15.0, "error_rate": 0.02, "throughput": 30.0, "cpu_percent": 22.0, "memory_mb": 256.0},
        "cache": {"latency_p95_ms": 2.0, "error_rate": 0.0, "throughput": 40.0, "cpu_percent": 6.0, "memory_mb": 80.0},
    }
    base = base_map.get(canonical_name, {"latency_p95_ms": 20.0, "error_rate": 0.1, "throughput": 20.0, "cpu_percent": 10.0, "memory_mb": 128.0})

    cur_p95 = round(p95_lat, 1)
    cur_err = round(err_rate * 100.0, 2)
    cur_thr = round(throughput, 1)
    cur_cpu = round(m.get("cpu_percent", c_st.cpu or 10.0), 1)
    cur_mem = round(m.get("memory_mb", c_st.memory or 128.0), 1)

    p95_dev = round(((cur_p95 - base["latency_p95_ms"]) / max(1.0, base["latency_p95_ms"])) * 100.0, 1)
    err_dev = round(((cur_err - base["error_rate"]) / max(0.01, base["error_rate"])) * 100.0, 1)
    thr_dev = round(((cur_thr - base["throughput"]) / max(1.0, base["throughput"])) * 100.0, 1)
    cpu_dev = round(((cur_cpu - base["cpu_percent"]) / max(1.0, base["cpu_percent"])) * 100.0, 1)
    mem_dev = round(((cur_mem - base["memory_mb"]) / max(1.0, base["memory_mb"])) * 100.0, 1)

    baseline_comparison = {
        "latency": {
            "current": cur_p95,
            "baseline": base["latency_p95_ms"],
            "unit": "ms",
            "deviation_pct": p95_dev,
            "is_elevated": p95_dev > 20.0
        },
        "error_rate": {
            "current": cur_err,
            "baseline": base["error_rate"],
            "unit": "%",
            "deviation_pct": err_dev,
            "is_elevated": err_dev > 50.0
        },
        "throughput": {
            "current": cur_thr,
            "baseline": base["throughput"],
            "unit": "req/s",
            "deviation_pct": thr_dev,
            "is_elevated": abs(thr_dev) > 40.0
        },
        "cpu": {
            "current": cur_cpu,
            "baseline": base["cpu_percent"],
            "unit": "%",
            "deviation_pct": cpu_dev,
            "is_elevated": cpu_dev > 30.0
        },
        "memory": {
            "current": cur_mem,
            "baseline": base["memory_mb"],
            "unit": "MB",
            "deviation_pct": mem_dev,
            "is_elevated": mem_dev > 30.0
        }
    }

    # Waterfall & Bottleneck Analysis
    waterfall_services = ["gateway", "service-a", "service-b", "database-service"]
    waterfall_stages = []
    total_path_latency = 0.0
    max_lat = 0.0
    bottleneck_svc = "database-service"

    # Distributed tracing check
    try:
        from backend.app.storage.telemetry_store import telemetry_store
        spans = await telemetry_store.query_traces(t_id, service=canonical_name, limit=5)
        has_real_traces = bool(len(spans) > 0 or len(raw_history) > 0)
    except Exception:
        has_real_traces = bool(len(raw_history) > 0)

    for s_id in waterfall_services:
        st_state = canonical_state_manager.get_service_operational_state(t_id, s_id, collector.active_incidents)
        st_m = collector.latest_metrics.get(s_id, {})
        st_lat = st_state.p95 or st_m.get("latency_p95_ms", 18.0)
        total_path_latency += st_lat
        if st_lat > max_lat:
            max_lat = st_lat
            bottleneck_svc = s_id

    for s_id in waterfall_services:
        st_state = canonical_state_manager.get_service_operational_state(t_id, s_id, collector.active_incidents)
        st_m = collector.latest_metrics.get(s_id, {})
        st_lat = round(st_state.p95 or st_m.get("latency_p95_ms", 18.0), 1)
        st_err = round(st_state.error_rate * 100, 2)
        is_bottleneck = (s_id == bottleneck_svc)

        if s_id == "database-service":
            proc_time = st_lat
            wait_time = 0.0
            prob = "DB CONNECTION EXHAUSTION" if st_state.operational_status.value == "CRITICAL" else "DATABASE LOCK CONTENTION" if st_state.operational_status.value == "DEGRADED" else "NORMAL_EXECUTION"
        elif s_id == "service-b":
            proc_time = round(max(5.0, st_lat * 0.25), 1)
            wait_time = round(max(0.0, st_lat - proc_time), 1)
            prob = "DATABASE TIMEOUT" if st_state.operational_status.value in ["DEGRADED", "CRITICAL"] else "HEALTHY"
        elif s_id == "service-a":
            proc_time = round(max(8.0, st_lat * 0.35), 1)
            wait_time = round(max(0.0, st_lat - proc_time), 1)
            prob = "UPSTREAM LATENCY CASCADE" if st_state.operational_status.value in ["DEGRADED", "CRITICAL"] else "HEALTHY"
        else: # gateway
            proc_time = round(max(4.0, st_lat * 0.20), 1)
            wait_time = round(max(0.0, st_lat - proc_time), 1)
            prob = "HTTP 502/504 GATEWAY ERRORS" if st_state.operational_status.value in ["DEGRADED", "CRITICAL"] else "HEALTHY"

        waterfall_stages.append({
            "stage_id": s_id,
            "service": s_id,
            "display_name": s_id.replace("-", " ").title(),
            "latency_ms": st_lat,
            "latency_contribution_pct": round((st_lat / max(1.0, total_path_latency)) * 100.0, 1),
            "error_rate_pct": st_err,
            "status": st_state.operational_status.value,
            "processing_time_ms": proc_time,
            "dependency_wait_ms": wait_time,
            "problem": prob,
            "is_bottleneck": is_bottleneck
        })

    # Dominant problem for selected service
    if computed_status == "CRITICAL":
        dominant_prob = "DB CONNECTION EXHAUSTION" if "database" in canonical_name else "HTTP 500 CRITICAL FAILURE"
    elif computed_status == "DEGRADED":
        dominant_prob = "DATABASE TIMEOUT" if "b" in canonical_name else "HTTP 502 BAD GATEWAY" if "gateway" in canonical_name else "LATENCY CASCADE"
    else:
        dominant_prob = "CLEAN BASELINE"

    # Recent anomalies
    anomalies = [
        {
            "timestamp": pt.get("timestamp", ""),
            "anomaly_score": pt.get("anomaly_score", 0.0),
            "error_rate": pt.get("error_rate", 0.0),
            "latency_p95_ms": pt.get("latency_p95_ms", 0.0)
        }
        for pt in raw_history
        if pt.get("is_anomaly", 0) == 1 or pt.get("anomaly_score", 0.0) > 0.5
    ][-10:]

    # Recent logs for this service from live operations feed
    service_logs = [
        {
            "timestamp": ev.get("timestamp"),
            "phase": ev.get("phase"),
            "message": ev.get("message"),
            "severity": ev.get("severity")
        }
        for ev in list(collector.live_operations_feed)
        if ev.get("service") == canonical_name or ev.get("service") == name
    ][-15:]

    # Dependency health check
    deps = dynamic_graph.get_dependencies(canonical_name)
    dependents = dynamic_graph.get_dependents(canonical_name)

    dep_health_summary = []
    for d in deps:
        t_name = d["target_service"]
        t_h = collector.latest_health.get(t_name, {})
        t_m = collector.latest_metrics.get(t_name, {})
        t_healthy = t_h.get("healthy", True) and t_h.get("state") not in ["CRASHED", "DOWN"]
        dep_health_summary.append({
            "service": t_name,
            "status": "HEALTHY" if t_healthy and t_m.get("error_rate", 0) < 0.05 else "DEGRADED" if t_healthy else "CRITICAL",
            "relationship": d["relationship_type"],
            "latency": t_m.get("latency_p95_ms", 15.0)
        })

    missing_instrumentation_map = {
        "gateway": ["GPU Utilization: No GPU attached", "Custom Connection Pool: Uses standard epoll"],
        "service-a": ["JVM Heap Profiling: Non-JVM runtime", "GPU Acceleration: Uninstrumented"],
        "service-b": ["Hardware Cryptographic Accelerator: Fallback software AES", "GPU Acceleration: Uninstrumented"],
        "database-service": ["Disk IOPS Latency Histogram: Available via eBPF on host only", "GPU Acceleration: Not applicable"],
        "cache": ["GPU Acceleration: Not applicable", "Disk Write Latency: In-memory mode active"]
    }
    missing_instrumentation = missing_instrumentation_map.get(canonical_name, ["GPU Acceleration: Uninstrumented", "Host Disk IOPS: eBPF exporter required"])

    return {
        "tenant_id": t_id,
        "missing_instrumentation": missing_instrumentation,
        "service_overview": {
            "service_id": f"SVC-{canonical_name.upper()}",
            "name": canonical_name,
            "display_name": svc.get("display_name", canonical_name.replace("-", " ").title()),
            "service_type": svc.get("service_type", "api"),
            "port": svc.get("port", 8000),
            "owner": svc.get("owner", "Core SRE"),
            "criticality": svc.get("criticality", "HIGH"),
            "status": computed_status,
            "health_state": h.get("state", "HEALTHY"),
            "dominant_problem": dominant_prob,
            "active_incident": matching_incidents[0] if matching_incidents else None
        },
        "current_health": {
            "status": computed_status,
            "health_state": h.get("state", "HEALTHY"),
            "healthy": is_healthy,
            "availability": availability,
            "request_rate": req_rate,
            "error_rate": cur_err,
            "latency_p50_ms": p50_lat,
            "latency_p95_ms": cur_p95,
            "latency_p99_ms": p99_lat,
            "cpu_percent": cur_cpu,
            "memory_mb": cur_mem,
            "throughput_rps": cur_thr,
            "active_connections": m.get("active_connections", 0),
            "anomaly_score": m.get("anomaly_score", 0.0),
            "dominant_problem": dominant_prob
        },
        "time_range": time_range,
        "time_series": time_series,
        "health_trend": health_trend,
        "baseline_comparison": baseline_comparison,
        "waterfall": {
            "stages": waterfall_stages,
            "total_latency_ms": round(total_path_latency, 1),
            "bottleneck_service": bottleneck_svc,
            "has_trace_data": has_real_traces
        },
        "dependencies": dep_health_summary,
        "dependents": dependents,
        "recent_incidents": matching_incidents,
        "recent_anomalies": anomalies,
        "recent_logs": service_logs
    }


@router.get("/{service_name}")
async def get_service_detail(service_name: str):
    name = service_name.replace("SVC-", "").lower()
    svc = next((s for s in SERVICES_CONFIG if s["name"] == name), None)
    if not svc and name in dynamic_graph.services:
        svc = dynamic_graph.services[name]
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
    
    m = collector.latest_metrics.get(name, {})
    h = collector.latest_health.get(name, {})
    history = collector.metric_history.get(name, [])
    graph_meta = dynamic_graph.services.get(name, {})
    
    dependencies = dynamic_graph.get_dependencies(name)
    dependents = dynamic_graph.get_dependents(name)

    return {
        "metadata": {
            **svc,
            "service_id": graph_meta.get("service_id", f"SVC-{name.upper()}"),
            "owner": graph_meta.get("owner", "Core SRE"),
            "criticality": graph_meta.get("criticality", svc.get("criticality", "HIGH")),
            "resource_id": graph_meta.get("resource_id")
        },
        "health": h,
        "metrics": m,
        "dependencies": dependencies,
        "dependents": dependents,
        "history": history[-30:]
    }
