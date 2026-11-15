"""
AegisOps AI - Error Pattern Detector (Phase 6)
Normalizes dynamic variables in log error messages (IP addresses, UUIDs, IDs, hex, ports, URLs)
into parameterized templates, groups errors by service and pattern, generates deterministic
error_pattern_ids, and detects sudden frequency surges against baseline.
"""

import re
import time
import hashlib
from datetime import datetime, timezone
from collections import deque, defaultdict
from typing import Dict, List, Any, Optional, Tuple
import threading


# Pre-compiled normalization regexes
_RE_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_RE_IP = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d{2,5})?\b")
_RE_HEX = re.compile(r"\b0x[0-9a-fA-F]+\b")
_RE_TIMESTAMP = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b")
_RE_ID_PARAM = re.compile(r"\b(?:id|order|payment|req|trace|span|txn)[-_:][a-zA-Z0-9_-]+\b", re.IGNORECASE)
_RE_NUMBER = re.compile(r"\b\d+(?:\.\d+)?(?:ms|s|kb|mb|gb|%|px)?\b", re.IGNORECASE)
_RE_WHITESPACE = re.compile(r"\s+")



def normalize_error_message(message: str) -> str:
    """
    Normalizes variable parts of an error message into a canonical template.
    Example:
    'Connection timeout to database 10.0.0.1:5432 after 2500ms'
    -> 'Connection timeout to database <IP> after <NUM>ms'
    """
    if not message:
        return "<EMPTY>"
    text = str(message).strip()
    text = _RE_TIMESTAMP.sub("<TIMESTAMP>", text)
    text = _RE_UUID.sub("<UUID>", text)
    text = _RE_IP.sub("<IP>", text)
    text = _RE_ID_PARAM.sub("<ID>", text)
    text = _RE_HEX.sub("<HEX>", text)
    text = _RE_NUMBER.sub("<NUM>", text)
    text = _RE_WHITESPACE.sub(" ", text)
    return text.strip()


_RE_STACK_FRAME = re.compile(r'File "([^"]+)", line (\d+), in (\w+)')
_RE_EXC_LINE = re.compile(r'([a-zA-Z0-9_.]*(?:Error|Exception|Fault|Timeout)):\s*(.*)')


def extract_stack_trace_info(message: str, exception: Any = None) -> Dict[str, Any]:
    """
    Part 3: Extracts exception_type, exception_message, top_stack_frame, and originating_module
    from structured exceptions or raw log stack traces.
    """
    exc_type = None
    exc_msg = None
    top_frame = None
    orig_module = None

    if isinstance(exception, dict):
        exc_type = exception.get("type") or exception.get("error_type")
        exc_msg = exception.get("message") or exception.get("error_message")
        top_frame = exception.get("top_frame") or exception.get("stacktrace")
        orig_module = exception.get("module")

    raw_text = f"{message} {str(exception or '')}"
    if not exc_type:
        exc_match = _RE_EXC_LINE.search(raw_text)
        if exc_match:
            exc_type = exc_match.group(1)
            exc_msg = exc_match.group(2).strip()

    frames = _RE_STACK_FRAME.findall(raw_text)
    if frames:
        last_file, last_line, last_func = frames[-1]
        top_frame = f'{os.path.basename(last_file)}:{last_line} in {last_func}'
        orig_module = os.path.splitext(os.path.basename(last_file))[0]

    return {
        "exception_type": exc_type,
        "exception_message": exc_msg,
        "top_stack_frame": top_frame,
        "originating_module": orig_module
    }


class ErrorPatternRecord:
    def __init__(
        self,
        pattern_id: str,
        service: str,
        template: str,
        error_type: str,
        status_code: Optional[int],
        endpoint: Optional[str] = None,
        severity: str = "ERROR",
        exception_info: Optional[Dict[str, Any]] = None
    ):
        self.pattern_id = pattern_id
        self.service = service
        self.template = template
        self.error_type = error_type
        self.status_code = status_code
        self.endpoint = endpoint
        self.severity = severity
        self.exception_info = exception_info or {}
        self.count: int = 0
        self.first_seen: float = time.time()
        self.last_seen: float = time.time()
        # Rolling recent timestamps (last 60s) to detect sudden surges
        self.recent_occurrences: deque = deque(maxlen=500)
        self.baseline_rate_per_sec: float = 0.01

    def record_occurrence(self, now: float, endpoint: Optional[str] = None, severity: Optional[str] = None, exception_info: Optional[Dict[str, Any]] = None):
        self.count += 1
        self.last_seen = now
        if endpoint:
            self.endpoint = endpoint
        if severity:
            self.severity = severity
        if exception_info and not self.exception_info.get("exception_type"):
            self.exception_info = exception_info
        self.recent_occurrences.append(now)
        # Prune older than 60s
        cutoff = now - 60.0
        while self.recent_occurrences and self.recent_occurrences[0] < cutoff:
            self.recent_occurrences.popleft()

    def get_frequency_stats(self, now: float) -> Tuple[float, float, float]:
        """
        Returns: (recent_rate_per_sec_last_30s, baseline_rate, frequency_change_ratio)
        """
        cutoff_30 = now - 30.0
        c30 = sum(1 for ts in self.recent_occurrences if ts >= cutoff_30)
        recent_rate = round(c30 / 30.0, 3)
        base = max(0.01, self.baseline_rate_per_sec)
        change_ratio = round((recent_rate - base) / base, 2)
        return recent_rate, base, change_ratio


class ErrorPatternDetector:
    """
    Tracks and detects surges in parameterized error patterns per (tenant_id, service).
    """
    def __init__(self):
        # (tenant_id, pattern_id) -> ErrorPatternRecord
        self.patterns: Dict[Tuple[str, str], ErrorPatternRecord] = {}
        self.lock = threading.Lock()

    def _generate_pattern_id(self, service: str, error_type: str, template: str) -> str:
        key_str = f"{service.lower()}:{error_type.lower()}:{template}"
        digest = hashlib.md5(key_str.encode("utf-8")).hexdigest()[:12]
        return f"ERR-PAT-{digest}"

    def record_error(
        self,
        tenant_id: str,
        service: str,
        message: str,
        error_type: Optional[str] = None,
        exception_type: Optional[str] = None,
        status_code: Optional[int] = None,
        endpoint: Optional[str] = None,
        severity: str = "ERROR",
        exception: Any = None,
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Records an error event, extracts template, updates frequency, and returns pattern metadata.
        """
        now = timestamp or time.time()
        tenant = tenant_id.lower()
        exc_details = extract_stack_trace_info(message, exception)
        err_type = error_type or exc_details.get("exception_type") or exception_type or (f"HTTP_{status_code}" if status_code else "GenericError")
        template = normalize_error_message(message)
        pattern_id = self._generate_pattern_id(service, err_type, template)

        key = (tenant, pattern_id)
        with self.lock:
            if key not in self.patterns:
                self.patterns[key] = ErrorPatternRecord(
                    pattern_id=pattern_id,
                    service=service,
                    template=template,
                    error_type=err_type,
                    status_code=status_code,
                    endpoint=endpoint,
                    severity=severity,
                    exception_info=exc_details
                )
            record = self.patterns[key]
            record.record_occurrence(now, endpoint=endpoint, severity=severity, exception_info=exc_details)
            recent_rate, base_rate, change_ratio = record.get_frequency_stats(now)

        return {
            "error_pattern_id": pattern_id,
            "tenant_id": tenant,
            "service": service,
            "endpoint": record.endpoint,
            "severity": record.severity,
            "error_type": err_type,
            "template": template,
            "status_code": status_code,
            "count": record.count,
            "exception_info": record.exception_info,
            "first_seen": datetime.fromtimestamp(record.first_seen, tz=timezone.utc).isoformat(),
            "last_seen": datetime.fromtimestamp(record.last_seen, tz=timezone.utc).isoformat(),
            "recent_rate_per_sec": recent_rate,
            "baseline_rate_per_sec": base_rate,
            "frequency_change": change_ratio
        }

    def evaluate_service_patterns(
        self,
        tenant_id: str,
        service: str,
        current_time: Optional[float] = None
    ) -> Tuple[bool, float, List[Dict[str, Any]]]:
        """
        Evaluates whether any error patterns on the service are experiencing a sudden surge.
        Returns: (is_anomaly, error_pattern_score, anomalous_patterns)
        """
        now = current_time or time.time()
        tenant = tenant_id.lower()
        
        anomalous_patterns = []
        max_score = 0.0

        with self.lock:
            matching_keys = [k for k in self.patterns.keys() if k[0] == tenant and self.patterns[k].service == service]
            for k in matching_keys:
                rec = self.patterns[k]
                recent_rate, base_rate, change = rec.get_frequency_stats(now)
                
                # Check for surge: sudden spike in recent 30s
                # e.g. recent rate >= 0.1/s (3 errors in 30s) or frequency change >= 5x
                if recent_rate >= 0.10 or change >= 4.0:
                    # Calculate pattern anomaly score
                    score = min(1.0, (recent_rate * 2.0) + (min(5.0, change) / 10.0))
                    max_score = max(max_score, score)
                    anomalous_patterns.append({
                        "error_pattern_id": rec.pattern_id,
                        "template": rec.template,
                        "error_type": rec.error_type,
                        "count": rec.count,
                        "recent_rate": recent_rate,
                        "frequency_change": change,
                        "pattern_score": round(score, 3)
                    })

        is_anom = (len(anomalous_patterns) > 0 and max_score >= 0.35)
        return is_anom, round(max_score, 3), anomalous_patterns


error_pattern_detector = ErrorPatternDetector()
