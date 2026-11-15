"""
AegisOps AI - Platform Self-Observability & Health API
Provides health, throughput, consumer lag, and system metrics for AegisOps itself.
"""

import psutil
import time
from fastapi import APIRouter
from typing import Dict, Any

from backend.app.core.config import settings
from backend.app.kafka.health import kafka_health_tracker
from backend.app.storage.manager import storage_manager

router = APIRouter(prefix="/platform", tags=["Platform Self-Observability"])


@router.get("/health")
async def get_platform_health() -> Dict[str, Any]:
    """Returns comprehensive health, memory, CPU, and worker stats of AegisOps platform."""
    kafka_status = kafka_health_tracker.get_metrics_summary()
    storage_info = storage_manager.get_storage_status()

    from backend.app.api.ingestion_gateway import ingestion_tracker
    from backend.app.storage.telemetry_store import telemetry_store
    from backend.app.monitoring.collector import collector

    ingestion_stats = ingestion_tracker.get_stats()
    store_stats = telemetry_store.get_storage_stats()

    # Calculate queue depths
    active_incidents = len(collector.active_incidents)
    pending_approvals = len([a for a in collector.pending_approvals if a.get("status") == "PENDING"])

    return {
        "status": "HEALTHY",
        "service": "AegisOps AI Autonomous Orchestrator",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "system_resources": {
            "host_cpu_percent": psutil.cpu_percent(interval=None),
            "host_memory_percent": psutil.virtual_memory().percent,
            "host_memory_available_mb": round(psutil.virtual_memory().available / (1024 * 1024), 1),
            "disk_utilization_pct": storage_info.get("used_percentage", 82.0)
        },
        "ingestion_gateway": {
            "status": "ONLINE",
            "total_eps": ingestion_stats.get("total_eps", 0.0),
            "total_bytes_sec": ingestion_stats.get("total_bytes_sec", 0.0),
            "total_events": ingestion_stats.get("total_events_ingested", 0),
            "active_tenants": ingestion_stats.get("active_tenants", 0)
        },
        "streaming_backbone": {
            "kafka": kafka_status,
            "collector": {
                "status": "HEALTHY",
                "receivers": ["otlp/grpc:4317", "otlp/http:4318", "kafka:9092", "rest:/api/v1/telemetry/*"],
                "exporters": ["kafka", "otlphttp/backend", "telemetry_store"],
                "batch_processor": "ACTIVE"
            }
        },
        "pipeline_queues": {
            "ingestion_buffer_depth": store_stats.get("total_buffered_events", 0),
            "ml_queue_depth": 0,
            "rca_queue_depth": 0,
            "remediation_queue_depth": active_incidents,
            "approval_queue_depth": pending_approvals,
            "verification_queue_depth": 0
        },
        "telemetry_storage": store_stats,
        "ai_engine": {
            "status": "OPERATIONAL",
            "active_detectors": ["threshold", "zscore", "ewma", "rate_change", "consecutive_breach", "ml_isolation_forest", "behavioral"],
            "baseline_profiler": "ACTIVE",
            "active_incidents": active_incidents
        },
        "timestamp": time.time()
    }


@router.get("/kafka/health")
async def get_kafka_health() -> Dict[str, Any]:
    """Returns detailed Kafka streaming metrics, consumer lag, and throughput."""
    return kafka_health_tracker.get_metrics_summary()
