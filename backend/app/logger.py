"""
Real-Time Structured Logging & Live Broadcast Engine
Captures info, warning, and error logs into a 300-entry in-memory ring buffer
and broadcasts them in real time to SSE and WebSocket clients.
"""

import sys
import logging
import traceback
import asyncio
import json
from datetime import datetime, timezone
from collections import deque
from typing import Dict, Any, List, Optional, Set
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class StructuredLogEntry:
    def __init__(
        self,
        level: str,
        message: str,
        meta: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ):
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.level = level.lower()  # "info", "warn", "warning", "error", "debug"
        # Normalize "warn" / "warning"
        if self.level == "warning":
            self.level = "warn"
        self.message = str(message)
        self.meta = meta or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "meta": self.meta
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class RealtimeLogger:
    def __init__(self, max_buffer_size: int = 300):
        self.buffer: deque = deque(maxlen=max_buffer_size)
        self._sse_subscribers: Set[asyncio.Queue] = set()
        self._ws_subscribers: Set[Any] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def get_history(self) -> List[Dict[str, Any]]:
        """Returns the current rolling history buffer (up to 300 entries)."""
        return [entry.to_dict() for entry in list(self.buffer)]

    def emit(
        self,
        level: str,
        message: str,
        meta: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ) -> StructuredLogEntry:
        """
        Emits a structured log, appends to the circular buffer,
        and broadcasts to all connected real-time clients.
        """
        entry = StructuredLogEntry(level=level, message=message, meta=meta, timestamp=timestamp)
        self.buffer.append(entry)

        # Broadcast asynchronously to active subscribers
        self._schedule_broadcast(entry)
        return entry

    def _schedule_broadcast(self, entry: StructuredLogEntry):
        payload = entry.to_dict()

        # Safely schedule coroutine from sync or async context
        try:
            loop = self._loop or asyncio.get_running_loop()
        except RuntimeError:
            loop = self._loop

        if loop and loop.is_running():
            try:
                loop.create_task(self._broadcast(payload))
            except RuntimeError:
                asyncio.run_coroutine_threadsafe(self._broadcast(payload), loop)

    async def _broadcast(self, payload: Dict[str, Any]):
        # 1. Broadcast to SSE queues
        dead_sse = set()
        for q in list(self._sse_subscribers):
            try:
                q.put_nowait(payload)
            except Exception:
                dead_sse.add(q)
        self._sse_subscribers.difference_update(dead_sse)

        # 2. Broadcast to WebSocket connections
        dead_ws = set()
        for ws in list(self._ws_subscribers):
            try:
                await ws.send_text(json.dumps({"type": "log", "data": payload}))
            except Exception:
                dead_ws.add(ws)
        self._ws_subscribers.difference_update(dead_ws)

    # SSE Subscription Management
    async def subscribe_sse(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._sse_subscribers.add(q)
        return q

    def unsubscribe_sse(self, q: asyncio.Queue):
        self._sse_subscribers.discard(q)

    # WebSocket Subscription Management
    def subscribe_ws(self, ws: Any):
        self._ws_subscribers.add(ws)

    def unsubscribe_ws(self, ws: Any):
        self._ws_subscribers.discard(ws)

    # Convenience Log Methods
    def info(self, message: str, **meta):
        return self.emit("info", message, meta=meta)

    def warn(self, message: str, **meta):
        return self.emit("warn", message, meta=meta)

    def warning(self, message: str, **meta):
        return self.emit("warn", message, meta=meta)

    def error(self, message: str, exc_info: bool = False, **meta):
        if exc_info:
            stack = traceback.format_exc()
            if stack and stack != "NoneType: None\n":
                meta["stack_trace"] = stack
        return self.emit("error", message, meta=meta)

    def debug(self, message: str, **meta):
        return self.emit("debug", message, meta=meta)


# Global singleton instance
realtime_logger = RealtimeLogger(max_buffer_size=300)


class RealtimeLogHandler(logging.Handler):
    """
    Standard Python logging.Handler that forwards all standard logging
    records (from uvicorn, fastapi, libraries, etc.) to the RealtimeLogger.
    """
    def emit(self, record: logging.LogRecord):
        # Prevent recursive loops from our own internal logging
        if record.name.startswith("aegisops.realtime"):
            return

        try:
            msg = self.format(record) if self.formatter else record.getMessage()
            level = record.levelname.lower()
            if level == "warning":
                level = "warn"
            elif level == "critical":
                level = "error"

            meta: Dict[str, Any] = {
                "logger": record.name,
                "module": record.module,
                "file": f"{record.filename}:{record.lineno}",
            }

            if record.exc_info:
                meta["stack_trace"] = "".join(traceback.format_exception(*record.exc_info))

            realtime_logger.emit(level=level, message=msg, meta=meta)
        except Exception:
            self.handleError(record)


def setup_unhandled_exception_hooks():
    """
    Installs global exception handlers for uncaught synchronous exceptions.
    """
    original_excepthook = sys.excepthook

    def custom_excepthook(exc_type, exc_value, exc_traceback):
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        realtime_logger.error(
            f"Uncaught Exception: {exc_type.__name__}: {exc_value}",
            meta={
                "exception_type": exc_type.__name__,
                "stack_trace": tb_str,
                "unhandled": True
            }
        )
        if original_excepthook:
            original_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = custom_excepthook


def setup_asyncio_exception_handler(loop: asyncio.AbstractEventLoop):
    """Hooks into asyncio loop for unhandled background tasks."""
    realtime_logger.set_event_loop(loop)
    original_handler = loop.get_exception_handler()

    def custom_async_handler(active_loop, context):
        exc = context.get("exception")
        msg = context.get("message", "Unhandled exception in asyncio task")
        meta = {
            "async_context": {k: str(v) for k, v in context.items() if k != "exception"},
            "unhandled_async": True
        }
        if exc:
            meta["stack_trace"] = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            realtime_logger.error(f"{msg}: {type(exc).__name__}: {exc}", meta=meta)
        else:
            realtime_logger.error(msg, meta=meta)

        if original_handler:
            original_handler(active_loop, context)
        else:
            active_loop.default_exception_handler(context)

    loop.set_exception_handler(custom_async_handler)


def init_logging_integration():
    """
    Hooks RealtimeLogHandler into the root Python logger so any existing
    or future standard logger calls automatically route to real-time streaming.
    """
    root_logger = logging.getLogger()
    
    # Avoid duplicate handler registration
    for h in root_logger.handlers:
        if isinstance(h, RealtimeLogHandler):
            return

    handler = RealtimeLogHandler()
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Also capture uvicorn error and access logs
    for log_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        l = logging.getLogger(log_name)
        if not any(isinstance(h, RealtimeLogHandler) for h in l.handlers):
            l.addHandler(handler)


class RealtimeErrorLoggingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that wraps HTTP requests to capture 5xx responses
    or unhandled route exceptions and stream them as structured error logs.
    """
    async def dispatch(self, request: Request, call_next):
        try:
            response: Response = await call_next(request)
            # Capture 500+ HTTP status errors
            if response.status_code >= 500:
                realtime_logger.error(
                    f"HTTP {response.status_code} Error on {request.method} {request.url.path}",
                    meta={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "client_ip": request.client.host if request.client else "unknown"
                    }
                )
            return response
        except Exception as exc:
            tb = traceback.format_exc()
            realtime_logger.error(
                f"Unhandled Exception on {request.method} {request.url.path}: {type(exc).__name__} - {str(exc)}",
                meta={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "exception_type": type(exc).__name__,
                    "stack_trace": tb,
                    "client_ip": request.client.host if request.client else "unknown"
                }
            )
            # Re-raise to let FastAPI's normal error handlers respond
            raise
