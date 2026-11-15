"""
Continuous Dummy Log Traffic & Failure Simulator
Generates realistic production traffic logs (Info, Warning, Error) at configurable rates,
injects randomized failures with stack traces, and simulates automated self-healing resolution.
"""

import asyncio
import random
import uuid
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from backend.app.logger import realtime_logger


# Realistic traffic templates
SERVICES = ["api-gateway", "auth-service", "payment-service", "order-service", "inventory-service", "database-cluster"]
ENDPOINTS = [
    ("/api/v1/users", "GET"),
    ("/api/v1/auth/login", "POST"),
    ("/api/v1/orders", "POST"),
    ("/api/v1/orders/status", "GET"),
    ("/api/v1/inventory/items", "GET"),
    ("/api/v1/checkout/process", "POST"),
    ("/api/v1/payments/verify", "POST"),
    ("/api/v1/analytics/events", "POST"),
    ("/api/v1/health", "GET"),
]
CACHE_KEYS = ["user:session:", "catalog:item:", "rate_limit:ip:", "config:global:", "pricing:tier:"]


FAILURE_SCENARIOS = [
    {
        "error_msg": "Database connection pool exhausted: timeout after 5000ms",
        "service": "database-cluster",
        "status_code": 500,
        "exception_type": "ConnectionTimeoutError",
        "stack_trace": """Traceback (most recent call last):
  File "/app/services/database.py", line 142, in get_connection
    conn = await self.pool.acquire(timeout=5.0)
  File "/app/vendor/asyncpg/pool.py", line 428, in acquire
    raise asyncio.TimeoutError("Connection pool acquisition timed out")
ConnectionTimeoutError: Database connection pool exhausted: timeout after 5000ms""",
        "resolutions": [
            ("info", "Database pool scaled up: +15 connections allocated, pool health restored."),
            ("info", "Failover to read-replica cluster node db-replica-02 completed successfully."),
            ("warn", "Circuit breaker opened for database write queries; serving from read-cache.")
        ]
    },
    {
        "error_msg": "500 Internal Server Error: Unhandled exception in payment processor",
        "service": "payment-service",
        "status_code": 500,
        "exception_type": "PaymentGatewayException",
        "stack_trace": """Traceback (most recent call last):
  File "/app/services/payment.py", line 89, in process_transaction
    response = await gateway_client.charge(payload)
  File "/app/integrations/stripe_mock.py", line 64, in charge
    raise PaymentGatewayException("HTTP 502 Bad Gateway from upstream bank processor")
PaymentGatewayException: 500 Internal Server Error: Unhandled exception in payment processor""",
        "resolutions": [
            ("info", "Idempotent payment retry succeeded on attempt 2 via secondary acquirer."),
            ("info", "Payment transaction queued into dead-letter replay pipeline for auto-retry.")
        ]
    },
    {
        "error_msg": "SocketTimeout: Upstream inventory-service failed to respond within 3000ms",
        "service": "order-service",
        "status_code": 504,
        "exception_type": "GatewayTimeoutError",
        "stack_trace": """Traceback (most recent call last):
  File "/app/services/orders.py", line 210, in verify_inventory
    res = await http_client.get(f"{INVENTORY_URL}/items/{item_id}", timeout=3.0)
  File "/app/vendor/httpx/_client.py", line 1054, in get
    return await self.send(request, auth=auth, follow_redirects=follow_redirects)
GatewayTimeoutError: SocketTimeout: Upstream inventory-service failed to respond within 3000ms""",
        "resolutions": [
            ("info", "Circuit breaker tripped: routing order validation to local redis inventory cache."),
            ("info", "Service mesh traffic rerouted to healthy inventory-service replica instance (pod-inv-3).")
        ]
    },
    {
        "error_msg": "Redis connection refused on cache-cluster:6379",
        "service": "api-gateway",
        "status_code": 503,
        "exception_type": "RedisConnectionError",
        "stack_trace": """Traceback (most recent call last):
  File "/app/core/cache.py", line 55, in get_session
    return await self.redis.get(key)
  File "/app/vendor/redis/asyncio/client.py", line 320, in execute_command
    return await conn.read_response()
RedisConnectionError: Redis connection refused on cache-cluster:6379""",
        "resolutions": [
            ("info", "Redis Sentinel failover complete: promoted cache-node-02 to master node."),
            ("warn", "Cache fallback enabled: bypassing cache and querying database directly.")
        ]
    }
]


class ContinuousLogSimulator:
    def __init__(
        self,
        log_rate_per_sec: float = 8.0,
        failure_rate_per_min: float = 5.0,
        max_logs: Optional[int] = None
    ):
        self.log_rate_per_sec = float(log_rate_per_sec)
        self.failure_rate_per_min = float(failure_rate_per_min)
        self.max_logs = max_logs

        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._total_emitted = 0
        self._total_errors = 0
        self._total_warns = 0
        self._total_infos = 0
        self._total_healed = 0
        self._start_time: Optional[float] = None
        self._pending_healing_tasks: List[asyncio.Task] = []

    def get_status(self) -> Dict[str, Any]:
        uptime_sec = round(time.time() - self._start_time, 1) if (self.is_running and self._start_time) else 0.0
        return {
            "is_running": self.is_running,
            "log_rate_per_sec": self.log_rate_per_sec,
            "failure_rate_per_min": self.failure_rate_per_min,
            "max_logs": self.max_logs,
            "total_emitted": self._total_emitted,
            "total_infos": self._total_infos,
            "total_warns": self._total_warns,
            "total_errors": self._total_errors,
            "total_healed": self._total_healed,
            "uptime_seconds": uptime_sec,
            "current_buffer_size": len(realtime_logger.buffer)
        }

    def update_config(
        self,
        log_rate_per_sec: Optional[float] = None,
        failure_rate_per_min: Optional[float] = None,
        max_logs: Optional[int] = None
    ):
        if log_rate_per_sec is not None:
            self.log_rate_per_sec = max(0.5, float(log_rate_per_sec))
        if failure_rate_per_min is not None:
            self.failure_rate_per_min = max(0.0, float(failure_rate_per_min))
        if max_logs is not None:
            self.max_logs = int(max_logs) if max_logs > 0 else None

    async def start(self) -> bool:
        if self.is_running:
            return False
        self.is_running = True
        self._start_time = time.time()
        self._task = asyncio.create_task(self._run_loop())
        realtime_logger.info(
            f"Dummy Log Traffic Simulator started at {self.log_rate_per_sec} logs/sec (~{self.failure_rate_per_min} failures/min).",
            source="log_simulator",
            rate=self.log_rate_per_sec
        )
        return True

    def stop(self) -> bool:
        if not self.is_running:
            return False
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
        for t in self._pending_healing_tasks:
            if not t.done():
                t.cancel()
        self._pending_healing_tasks.clear()

        realtime_logger.info(
            f"Dummy Log Traffic Simulator stopped. Total simulated logs emitted: {self._total_emitted:,} ({self._total_errors:,} errors resolved).",
            source="log_simulator",
            total_emitted=self._total_emitted
        )
        return True

    async def _run_loop(self):
        try:
            while self.is_running:
                # Check max logs limit if configured
                if self.max_logs and self._total_emitted >= self.max_logs:
                    self.is_running = False
                    break

                # Determine if this iteration should be a failure event
                # Failure probability per log event = (failures_per_min / 60) / logs_per_sec
                prob_failure = (self.failure_rate_per_min / 60.0) / max(0.1, self.log_rate_per_sec)
                # Cap probability between 0.001 and 0.5
                prob_failure = min(max(prob_failure, 0.001), 0.5)

                if random.random() < prob_failure:
                    self._emit_failure_with_resolution()
                else:
                    # 90% Info, 10% Warning
                    if random.random() < 0.10:
                        self._emit_warning()
                    else:
                        self._emit_info()

                self._total_emitted += 1

                # Dynamic sleep interval with slight jitter for natural traffic variance
                base_sleep = 1.0 / max(0.5, self.log_rate_per_sec)
                jitter = random.uniform(0.75, 1.25)
                await asyncio.sleep(base_sleep * jitter)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            realtime_logger.error(f"Error in Log Simulator loop: {e}", exc_info=True)
            self.is_running = False

    def _emit_info(self):
        path, method = random.choice(ENDPOINTS)
        svc = random.choice(SERVICES)
        user_id = f"usr_{random.randint(1000, 9999)}"
        trace_id = f"trc_{uuid.uuid4().hex[:12]}"
        duration_ms = random.randint(8, 120)

        info_types = [
            (
                f"{method} {path} 200 OK - {duration_ms}ms",
                {"service": svc, "method": method, "path": path, "status_code": 200, "duration_ms": duration_ms, "user_id": user_id, "trace_id": trace_id}
            ),
            (
                f"User login successful for {user_id} via session-auth",
                {"service": "auth-service", "user_id": user_id, "auth_provider": "jwt", "trace_id": trace_id}
            ),
            (
                f"Cache HIT for key '{random.choice(CACHE_KEYS)}{random.randint(10, 99)}' (latency: 1.2ms)",
                {"service": "api-gateway", "cache_tier": "l1_memory", "trace_id": trace_id}
            ),
            (
                f"Processed message batch (size: {random.randint(20, 100)}) from event-queue",
                {"service": "order-service", "queue": "orders.inbound", "trace_id": trace_id}
            ),
            (
                f"Background metric sync completed in {random.randint(4, 25)}ms",
                {"service": svc, "sync_type": "telemetry", "trace_id": trace_id}
            )
        ]

        msg, meta = random.choice(info_types)
        realtime_logger.info(msg, **meta)
        self._total_infos += 1

    def _emit_warning(self):
        svc = random.choice(SERVICES)
        trace_id = f"trc_{uuid.uuid4().hex[:12]}"
        slow_ms = random.randint(800, 2400)

        warn_types = [
            (
                f"Slow query detected on {svc}: execution took {slow_ms}ms (threshold: 500ms)",
                {"service": svc, "duration_ms": slow_ms, "query_type": "SELECT_JOIN", "trace_id": trace_id}
            ),
            (
                f"Rate limit approaching for IP 192.168.1.{random.randint(10, 254)}: 85% capacity reached",
                {"service": "api-gateway", "rate_limit_bucket": "sliding_window_1m", "trace_id": trace_id}
            ),
            (
                f"Memory utilization threshold exceeded: {random.randint(82, 94)}% allocated",
                {"service": svc, "memory_pct": random.randint(82, 94), "trace_id": trace_id}
            ),
            (
                f"Microservice latency spike on {svc} p99: {slow_ms}ms",
                {"service": svc, "p99_latency_ms": slow_ms, "trace_id": trace_id}
            )
        ]

        msg, meta = random.choice(warn_types)
        realtime_logger.warn(msg, **meta)
        self._total_warns += 1

    def _emit_failure_with_resolution(self):
        scenario = random.choice(FAILURE_SCENARIOS)
        trace_id = f"trc_err_{uuid.uuid4().hex[:10]}"
        user_id = f"usr_{random.randint(1000, 9999)}"

        meta = {
            "service": scenario["service"],
            "status_code": scenario["status_code"],
            "exception_type": scenario["exception_type"],
            "stack_trace": scenario["stack_trace"],
            "trace_id": trace_id,
            "user_id": user_id,
            "simulated_failure": True
        }

        # 1. Emit the Error log first
        realtime_logger.error(scenario["error_msg"], **meta)
        self._total_errors += 1

        # 2. Schedule automated realistic self-healing resolution after 1-5 seconds delay
        delay_sec = random.uniform(1.2, 4.5)
        res_level, res_msg = random.choice(scenario["resolutions"])

        healing_task = asyncio.create_task(
            self._emit_resolution_delayed(delay_sec, trace_id, scenario["service"], res_level, res_msg)
        )
        self._pending_healing_tasks.append(healing_task)

    async def _emit_resolution_delayed(
        self,
        delay: float,
        trace_id: str,
        service: str,
        level: str,
        message: str
    ):
        try:
            await asyncio.sleep(delay)
            if not self.is_running:
                return

            res_meta = {
                "service": service,
                "trace_id": trace_id,
                "healed_trace": True,
                "recovery_action": "automated_self_healing",
                "recovery_duration_sec": round(delay, 2)
            }

            if level == "warn":
                realtime_logger.warn(f"[Resolved: {trace_id}] {message}", **res_meta)
                self._total_warns += 1
            else:
                realtime_logger.info(f"[Resolved: {trace_id}] {message}", **res_meta)
                self._total_infos += 1

            self._total_healed += 1
            self._total_emitted += 1
        except asyncio.CancelledError:
            pass


# Global singleton simulator instance
log_simulator = ContinuousLogSimulator()
