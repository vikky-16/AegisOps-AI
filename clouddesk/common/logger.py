"""
CloudDesk Structured JSON Logger & Real-Time AegisOps Telemetry Streamer
Generates standardized cloud/SaaS JSON log events for CloudDesk.
Enforces tenant_id="clouddesk", W3C trace correlation, secret token masking,
and streams real log events directly to the AegisOps Ingestion Gateway.
"""

import os
import sys
import json
import re
import socket
import logging
import queue
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

TENANT_ID = os.getenv("TENANT_ID", "clouddesk")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
HOSTNAME = socket.gethostname()

AEGISOPS_GATEWAY_URL = os.getenv("AEGISOPS_GATEWAY_URL", "http://127.0.0.1:8000/api/v1/telemetry").rstrip("/")
AEGISOPS_API_KEY = os.getenv("AEGISOPS_API_KEY", "agt_live_clouddesk_xxxx9999yyyy8888zzzz")

# Sensitive data redaction patterns (credentials, API secrets, JWT tokens, private SSH keys)
SENSITIVE_PATTERNS = [
    (re.compile(r'(?i)(password|secret|token|api[_-]?key|jwt|auth[_-]?bearer|ssh[_-]?key)["\']?\s*[:=]\s*["\']?([^"\'\s&,]+)'), r'\1="[REDACTED]"'),
    (re.compile(r'\b(?:\d[ -]*?){13,16}\b'), '[CARD_REDACTED]'),
]


def redact_sensitive(text: str) -> str:
    if not text:
        return text
    result = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def extract_record_data(record: logging.LogRecord) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tenant_id": TENANT_ID,
        "company_id": TENANT_ID,
        "service": getattr(record, "service", "unknown-service"),
        "service_name": getattr(record, "service", "unknown-service"),
        "environment": ENVIRONMENT,
        "hostname": HOSTNAME,
        "level": record.levelname,
        "severity": record.levelname,
        "event_type": getattr(record, "event_type", "cloud_operation"),
        "message": redact_sensitive(record.getMessage()),
    }

    # Structured correlation fields
    for field in [
        "request_id",
        "trace_id",
        "span_id",
        "http_method",
        "route",
        "http_route",
        "status_code",
        "http_status",
        "latency_ms",
        "latency",
        "error_type",
        "error_message",
        "dependency",
        "user_id",
        "project_id",
        "instance_id",
        "resource_type",
        "cpu_cores",
        "memory_gb",
        "cost",
    ]:
        val = getattr(record, field, None)
        if val is not None:
            if isinstance(val, str):
                data[field] = redact_sensitive(val)
            else:
                data[field] = val

    if record.exc_info and not data.get("error_message"):
        data["error_message"] = redact_sensitive(logging.Formatter().formatException(record.exc_info))
        data["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"

    return data


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = extract_record_data(record)
        return json.dumps(data)


class AegisOpsHttpLogHandler(logging.Handler):
    def __init__(self, endpoint: str, tenant_id: str = TENANT_ID, api_key: str = AEGISOPS_API_KEY):
        super().__init__()
        self.endpoint = endpoint
        self.tenant_id = tenant_id
        self.api_key = api_key
        self.queue: queue.Queue = queue.Queue(maxsize=10000)
        self.worker = threading.Thread(target=self._flush_loop, daemon=True, name="CloudDeskLogStreamer")
        self.worker.start()

    def emit(self, record: logging.LogRecord):
        if record.name.startswith("urllib") or record.name.startswith("httpx"):
            return
        try:
            data = extract_record_data(record)
            self.queue.put_nowait(data)
        except queue.Full:
            pass
        except Exception:
            pass

    def _flush_loop(self):
        while True:
            batch: List[Dict[str, Any]] = []
            try:
                item = self.queue.get(timeout=0.25)
                batch.append(item)
                while len(batch) < 50:
                    try:
                        batch.append(self.queue.get_nowait())
                    except queue.Empty:
                        break
            except queue.Empty:
                pass

            if batch:
                self._send_batch(batch)

    def _send_batch(self, batch: List[Dict[str, Any]]):
        payload = json.dumps(batch).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/logs",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Tenant-ID": self.tenant_id,
                "X-API-Key": self.api_key,
                "User-Agent": "CloudDesk-LogStreamer/1.0"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                pass
        except Exception as exc:
            if os.getenv("DEBUG_TELEMETRY") or os.getenv("DEBUG"):
                print(f"[CLOUDDESK_LOGGER_ERR] Log shipment failed: {exc}", file=sys.stderr, flush=True)


_http_handler: Optional[AegisOpsHttpLogHandler] = None


def get_service_logger(service_name: str) -> logging.Logger:
    global _http_handler
    logger = logging.getLogger(f"clouddesk.{service_name}")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(JsonLogFormatter())
        logger.addHandler(stdout_handler)

        if _http_handler is None:
            _http_handler = AegisOpsHttpLogHandler(endpoint=AEGISOPS_GATEWAY_URL)
        logger.addHandler(_http_handler)

        logger.propagate = False
        
    return logger
