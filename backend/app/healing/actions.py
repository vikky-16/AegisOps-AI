"""
Remediation Actions Registry
"""

from typing import Dict, Any

AVAILABLE_ACTIONS = {
    "RESTART_SERVICE": {
        "action": "restart",
        "title": "Restart Microservice",
        "description": "Performs a graceful restart of the service process, clears corrupted memory state, and reinitializes workers.",
        "base_risk": "MEDIUM",
        "estimated_duration_sec": 4.0,
        "is_destructive": False,
        "reversible": True
    },
    "RESET_CONNECTION_POOL": {
        "action": "reset_connections",
        "title": "Reset Database Connection Pool",
        "description": "Flushes idle and zombie database connections, resets pool slots, and re-establishes healthy pooled sockets.",
        "base_risk": "MEDIUM",
        "estimated_duration_sec": 2.0,
        "is_destructive": False,
        "reversible": True
    },
    "SCALE_WORKERS": {
        "action": "scale_workers",
        "title": "Scale Worker Concurrency",
        "description": "Increases worker thread capacity to alleviate CPU saturation and high queue latency.",
        "base_risk": "LOW",
        "estimated_duration_sec": 3.0,
        "is_destructive": False,
        "reversible": True
    },
    "CLEAR_CACHE": {
        "action": "clear_cache",
        "title": "Flush Memory Buffers & Caches",
        "description": "Purges temporary memory buffers, reclaims heap space, and eliminates memory leak pressure.",
        "base_risk": "LOW",
        "estimated_duration_sec": 2.0,
        "is_destructive": False,
        "reversible": True
    },
    "ROTATE_AND_COMPRESS_LOGS": {
        "action": "rotate_logs",
        "title": "Rotate & Compress Application Logs",
        "description": "Rotates large active log files, applies gzip compression, and moves archives to secondary storage.",
        "base_risk": "LOW",
        "estimated_duration_sec": 3.0,
        "is_destructive": False,
        "reversible": True
    },
    "COMPACT_STORAGE": {
        "action": "compact_storage",
        "title": "Compact Storage & Archive Old Logs",
        "description": "Reclaims disk space by compacting tables and archiving logs older than retention policy.",
        "base_risk": "MEDIUM",
        "estimated_duration_sec": 5.0,
        "is_destructive": False,
        "reversible": True
    },
    "RECONNECT_DATABASE": {
        "action": "reconnect_database",
        "title": "Reconnect Database & Reset Connection Pool",
        "description": "Flushes idle/zombie handles, resets database connection pool, and verifies ping connectivity.",
        "base_risk": "MEDIUM",
        "estimated_duration_sec": 2.5,
        "is_destructive": False,
        "reversible": True
    },
    "FAILOVER_DATABASE": {
        "action": "failover_database",
        "title": "Failover Database to Read Replica",
        "description": "Promotes standby database replica to active primary upon primary node failure.",
        "base_risk": "HIGH",
        "estimated_duration_sec": 8.0,
        "is_destructive": False,
        "reversible": True
    },
    "SCALE_SERVICE": {
        "action": "scale_service",
        "title": "Scale Service Worker Capacity",
        "description": "Increases service worker thread and replica capacity to absorb traffic surges.",
        "base_risk": "LOW",
        "estimated_duration_sec": 3.0,
        "is_destructive": False,
        "reversible": True
    },
    "ROLLBACK_DEPLOYMENT": {
        "action": "rollback_deployment",
        "title": "Rollback Faulty Deployment",
        "description": "Rolls back to the previous stable release artifact and reverts canary configuration.",
        "base_risk": "MEDIUM",
        "estimated_duration_sec": 5.0,
        "is_destructive": False,
        "reversible": True
    },
    "DISABLE_FAULTY_DEPENDENCY": {
        "action": "disable_dependency",
        "title": "Trip Circuit Breaker for Faulty Dependency",
        "description": "Opens circuit breaker to fail fast and prevent cascading timeout exhaustion.",
        "base_risk": "LOW",
        "estimated_duration_sec": 1.5,
        "is_destructive": False,
        "reversible": True
    },
    "RETRY_FAILED_REQUESTS": {
        "action": "retry_requests",
        "title": "Retry Failed Requests with Exponential Backoff",
        "description": "Replays transiently failed idempotent requests with jittered backoff.",
        "base_risk": "LOW",
        "estimated_duration_sec": 2.0,
        "is_destructive": False,
        "reversible": True
    }
}

