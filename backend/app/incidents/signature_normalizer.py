"""
Error Signature Normalizer Engine
Normalizes disparate error messages into canonical signatures and tracks occurrences.
"""

import re
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


class ErrorSignatureNormalizer:
    def __init__(self):
        # In-memory fast cache of signatures: signature_key -> metadata dict
        self._signatures: Dict[str, Dict[str, Any]] = {}
        
        # Compiled normalization rules: (regex pattern, canonical signature, category)
        self.rules = [
            # Database Signatures
            (re.compile(r"(database|db).*?(connect|conn).*?(timeout|timed out|expired)", re.IGNORECASE), "DATABASE_CONNECTION_TIMEOUT", "DATABASE"),
            (re.compile(r"(connection pool|conn pool|connection slot|remaining connection).*?(exhaust|deplet|full|50/50|max|saturated|reserved)", re.IGNORECASE), "CONNECTION_POOL_EXHAUSTION", "DATABASE"),
            (re.compile(r"(deadlock|lock table|lock wait timeout|victim transaction)", re.IGNORECASE), "DATABASE_DEADLOCK", "DATABASE"),
            (re.compile(r"(database|db).*?(unreachable|refused|cannot connect|connection lost)", re.IGNORECASE), "DATABASE_UNREACHABLE", "DATABASE"),
            
            # Gateway & Proxy Signatures
            (re.compile(r"(502|bad gateway|upstream connection refused|upstream service error)", re.IGNORECASE), "GATEWAY_502_BAD_GATEWAY", "GATEWAY"),
            (re.compile(r"(504|gateway timeout|upstream response timed out)", re.IGNORECASE), "GATEWAY_504_TIMEOUT", "GATEWAY"),
            (re.compile(r"(upstream.*unreachable|cannot connect to upstream|upstream broken)", re.IGNORECASE), "GATEWAY_UPSTREAM_UNREACHABLE", "GATEWAY"),
            
            # Service & HTTP Status Signatures
            (re.compile(r"(503|service unavailable|circuit breaker open)", re.IGNORECASE), "HTTP_503_SERVICE_UNAVAILABLE", "SERVICE"),
            (re.compile(r"(500|internal server error|unhandled exception|null reference)", re.IGNORECASE), "HTTP_500_INTERNAL_SERVER_ERROR", "SERVICE"),
            (re.compile(r"(401|unauthorized|invalid token|token expired|signature mismatch)", re.IGNORECASE), "HTTP_401_UNAUTHORIZED", "AUTH"),
            (re.compile(r"(429|rate limit|too many requests|throttle)", re.IGNORECASE), "HTTP_429_TOO_MANY_REQUESTS", "RATE_LIMIT"),
            
            # Payment & Order Domain Signatures
            (re.compile(r"(payment.*failed|payment.*timeout|card.*declined|payment.*error)", re.IGNORECASE), "PAYMENT_PROCESSING_FAILED", "PAYMENT"),
            (re.compile(r"(order.*failed|order.*reconciliation|order.*crash)", re.IGNORECASE), "ORDER_CREATION_FAILED", "ORDER"),
            
            # Resource & Infrastructure Signatures
            (re.compile(r"(out of memory|oom|memory pressure|memory leak|heap dump)", re.IGNORECASE), "MEMORY_PRESSURE", "RESOURCE"),
            (re.compile(r"(cpu saturation|high cpu|thread starvation|cpu.*100%|cpu spike)", re.IGNORECASE), "CPU_SATURATION", "RESOURCE"),
            (re.compile(r"(disk full|storage full|storage exhaustion|tablespace.*capacity|disk space critical)", re.IGNORECASE), "STORAGE_EXHAUSTION", "STORAGE"),
            (re.compile(r"(crash|aborted|sigkill|process terminated|terminated unexpectedly)", re.IGNORECASE), "PROCESS_CRASH", "SYSTEM")
        ]

    def normalize(self, message: str, service: str = "unknown") -> Dict[str, Any]:
        """
        Normalizes a raw error log or telemetry message into a canonical signature.
        """
        cleaned_msg = str(message or "").strip()
        canonical_sig = "GENERIC_ERROR_SIGNAL"
        category = "UNKNOWN"

        for pattern, sig, cat in self.rules:
            if pattern.search(cleaned_msg):
                canonical_sig = sig
                category = cat
                break

        if canonical_sig == "GENERIC_ERROR_SIGNAL" and cleaned_msg:
            # Fallback heuristic: uppercase words without numbers/punctuation
            words = re.findall(r'[a-zA-Z]{3,}', cleaned_msg)
            if words:
                canonical_sig = f"ERROR_{'_'.join(words[:3]).upper()}"

        now_iso = datetime.now(timezone.utc).isoformat()
        key = f"{service}:{canonical_sig}"

        if key in self._signatures:
            sig_entry = self._signatures[key]
            sig_entry["frequency"] += 1
            sig_entry["last_seen"] = now_iso
            sig_entry["original_message"] = cleaned_msg
        else:
            sig_entry = {
                "signature": canonical_sig,
                "category": category,
                "service": service,
                "original_message": cleaned_msg,
                "frequency": 1,
                "first_seen": now_iso,
                "last_seen": now_iso
            }
            self._signatures[key] = sig_entry

        sev = "CRITICAL" if category in ["DATABASE", "SYSTEM"] or "EXHAUSTION" in canonical_sig or "CRASH" in canonical_sig else "HIGH" if category in ["GATEWAY", "PAYMENT"] else "MEDIUM"
        sig_id = "SIG-DB-CONN-001" if "CONNECTION_POOL" in canonical_sig else "SIG-GW-502-001" if "502" in canonical_sig else f"SIG-{canonical_sig[:12]}"

        return {
            "signature_id": sig_id,
            "signature": canonical_sig,
            "category": "DATABASE_CONNECTION_POOL" if "CONNECTION_POOL" in canonical_sig else "GATEWAY_UPSTREAM_502" if "502" in canonical_sig else category,
            "severity": sev,
            "service": service,
            "original_message": cleaned_msg,
            "is_cascade_compatible": True,
            "frequency": sig_entry["frequency"],
            "first_seen": sig_entry["first_seen"],
            "last_seen": sig_entry["last_seen"]
        }

    def are_signatures_cascade_compatible(self, root_sig: str, downstream_sig: str) -> bool:
        """
        Returns True if downstream_sig is a known causal consequence of root_sig.
        E.g. DATABASE_CONNECTION_TIMEOUT -> PAYMENT_PROCESSING_FAILED -> GATEWAY_502_BAD_GATEWAY.
        """
        cascade_chains = {
            "DATABASE_CONNECTION_TIMEOUT": {"PAYMENT_PROCESSING_FAILED", "GATEWAY_502_BAD_GATEWAY", "GATEWAY_504_TIMEOUT", "HTTP_500_INTERNAL_SERVER_ERROR", "HTTP_503_SERVICE_UNAVAILABLE"},
            "CONNECTION_POOL_EXHAUSTION": {"DATABASE_CONNECTION_TIMEOUT", "PAYMENT_PROCESSING_FAILED", "GATEWAY_502_BAD_GATEWAY", "GATEWAY_504_TIMEOUT", "HTTP_500_INTERNAL_SERVER_ERROR"},
            "DATABASE_DEADLOCK": {"PAYMENT_PROCESSING_FAILED", "GATEWAY_502_BAD_GATEWAY", "HTTP_500_INTERNAL_SERVER_ERROR"},
            "PAYMENT_PROCESSING_FAILED": {"ORDER_CREATION_FAILED", "GATEWAY_502_BAD_GATEWAY", "GATEWAY_504_TIMEOUT", "HTTP_500_INTERNAL_SERVER_ERROR"},
            "PROCESS_CRASH": {"GATEWAY_502_BAD_GATEWAY", "GATEWAY_504_TIMEOUT", "HTTP_503_SERVICE_UNAVAILABLE"},
            "MEMORY_PRESSURE": {"PROCESS_CRASH", "GATEWAY_502_BAD_GATEWAY", "HTTP_500_INTERNAL_SERVER_ERROR"},
            "CPU_SATURATION": {"GATEWAY_504_TIMEOUT", "PAYMENT_PROCESSING_FAILED", "HTTP_503_SERVICE_UNAVAILABLE"}
        }

        if root_sig == downstream_sig:
            return True
        allowed_downstream = cascade_chains.get(root_sig, set())
        return downstream_sig in allowed_downstream

    def get_all_signatures(self) -> List[Dict[str, Any]]:
        return list(self._signatures.values())


# Global singleton
signature_normalizer = ErrorSignatureNormalizer()
