"""
ShopSphere Structured JSON Logger & Real-Time AegisOps Log Streamer
Generates standardized JSON log events matching AegisOps specification.
Enforces tenant_id="shopsphere", W3C trace correlation, sensitive data masking,
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

TENANT_ID = os.getenv("TENANT_ID", "shopsphere")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
HOSTNAME = socket.gethostname()

AEGISOPS_GATEWAY_URL = os.getenv("AEGISOPS_GATEWAY_URL", "http://127.0.0.1:8000/api/v1/telemetry").rstrip("/")
AEGISOPS_API_KEY = os.getenv("AEGISOPS_API_KEY", "agt_live_shopsphere_11112222333344445555")

# Sensitive data redaction patterns (passwords, auth tokens, credit cards)
SENSITIVE_PATTERNS = [
    (re.compile(r'(?i)(password|secret|token|api[_-]?key|card[_-]?number|cvv|authorization)["\']?\s*[:=]\s*["\']?([^"\'\s&,]+)'), r'\1="[REDACTED]"'),
    (re.compile(r'\b(?:\d[ -]*?){13,16}\b'), '[CARD_REDACTED]'),
]


def redact_sensitive(text: str) -> str:
    """Masks secrets, passwords, tokens, and credit card numbers from logs."""
    if not text:
        return text
    result = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def extract_record_data(record: logging.LogRecord) -> Dict[str, Any]:
    """Extracts structured fields from a LogRecord into a standardized dictionary."""
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
        "event_type": getattr(record, "event_type", "operational_log"),
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
        "customer_id",
        "order_id",
        "sku",
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
    """
    Non-blocking background HTTP log handler.
    Batches structured log records and dispatches them directly to AegisOps Ingestion Gateway.
    """
    def __init__(self, endpoint: str, tenant_id: str = TENANT_ID, api_key: str = AEGISOPS_API_KEY):
        super().__init__()
        self.endpoint = endpoint
        self.tenant_id = tenant_id
        self.api_key = api_key
        self.queue: queue.Queue = queue.Queue(maxsize=10000)
        self.worker = threading.Thread(target=self._flush_loop, daemon=True, name="AegisOpsLogStreamer")
        self.worker.start()

    def emit(self, record: logging.LogRecord):
        # Filter internal urllib/logging records to prevent loops
        if record.name.startswith("urllib") or record.name.startswith("httpx"):
            return
        try:
            data = extract_record_data(record)
            self.queue.put_nowait(data)
        except queue.Full:
            pass  # Drop under extreme backpressure
        except Exception:
            pass

    def _flush_loop(self):
        import time
        while True:
            batch: List[Dict[str, Any]] = []
            try:
                # Block for first item up to 0.25 seconds
                item = self.queue.get(timeout=0.25)
                batch.append(item)
                # Drain queue up to 50 items
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
                "User-Agent": "ShopSphere-LogStreamer/1.0"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                pass
        except Exception as exc:
            if os.getenv("DEBUG_TELEMETRY") or os.getenv("DEBUG"):
                print(f"[SHOPSPHERE_LOGGER_ERR] Log shipment failed: {exc}", file=sys.stderr, flush=True)


# Singleton streaming handler
_http_handler: Optional[AegisOpsHttpLogHandler] = None


def get_service_logger(service_name: str) -> logging.Logger:
    """Configures and returns a structured JSON logger for the given microservice."""
    global _http_handler
    logger = logging.getLogger(f"shopsphere.{service_name}")
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if re-called
    if not logger.handlers:
        # 1. Console stdout JSON handler
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(JsonLogFormatter())
        logger.addHandler(stdout_handler)

        # 2. Live AegisOps Gateway HTTP streamer
        if _http_handler is None:
            _http_handler = AegisOpsHttpLogHandler(endpoint=AEGISOPS_GATEWAY_URL)
        logger.addHandler(_http_handler)

        logger.propagate = False
        
    return logger
