"""
AegisOps AI - PII & Secret Redaction Engine
Detects and masks sensitive credentials, tokens, passwords, authorization headers,
and private keys before telemetry persistence or dashboard broadcast.
"""

import re
from typing import Any, Dict, List, Union

# Compiled regex patterns for high-performance streaming masking
SECRET_PATTERNS = [
    # Passwords in query strings or JSON
    (re.compile(r'(?i)(password|passwd|pwd|secret)\s*[:=]\s*["\']?([^"\'\s&]+)["\']?'), r'\1="[REDACTED]"'),
    # Bearer tokens & JWTs
    (re.compile(r'(?i)(bearer\s+)([A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+)'), r'\1[REDACTED_JWT]'),
    (re.compile(r'(?i)(authorization\s*[:=]\s*["\']?bearer\s+)([^"\'\s]+)["\']?'), r'\1[REDACTED_TOKEN]'),
    # API Keys & Tokens
    (re.compile(r'(?i)(api[_-]?key|access[_-]?token|auth[_-]?token|private[_-]?key)\s*[:=]\s*["\']?([A-Za-z0-9_\-]{8,})["\']?'), r'\1="[REDACTED_KEY]"'),
    # Database connection strings with credentials (postgres://user:pass@host)
    (re.compile(r'(?i)(postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|sqlite)://([^:]+):([^@]+)@'), r'\1://\2:[REDACTED]@'),
    # Generic Private Key headers
    (re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[^-]+-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', re.DOTALL), r'[REDACTED_PRIVATE_KEY]'),
    # Cloud provider credentials
    (re.compile(r'(?i)(aws_secret_access_key|cloud_client_secret|client_secret)\s*[:=]\s*["\']?([A-Za-z0-9/+=]{16,})["\']?'), r'\1="[REDACTED_CLOUD_SECRET]"'),
]

SENSITIVE_KEY_NAMES = {
    "password", "passwd", "pwd", "secret", "client_secret",
    "api_key", "apikey", "access_token", "auth_token", "token",
    "private_key", "authorization", "db_password", "connection_string"
}


class PIIMasker:
    """Masks secrets and PII from strings, dictionaries, and telemetry event payloads."""

    @classmethod
    def mask_text(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        
        result = text
        for pattern, replacement in SECRET_PATTERNS:
            result = pattern.sub(replacement, result)
        return result

    @classmethod
    def mask_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convenience method to scrub a dictionary payload of sensitive keys and strings."""
        return cls.mask_payload(data)

    @classmethod
    def mask_payload(cls, data: Union[Dict[str, Any], List[Any], str, Any]) -> Any:
        if isinstance(data, str):
            return cls.mask_text(data)
        elif isinstance(data, dict):
            cleaned = {}
            for k, v in data.items():
                k_lower = str(k).lower().replace("-", "_")
                if "api_key" in k_lower or "apikey" in k_lower or "auth_token" in k_lower:
                    cleaned[k] = "[REDACTED_API_KEY]"
                elif "password" in k_lower or "passwd" in k_lower or "secret" in k_lower:
                    cleaned[k] = "[REDACTED_SECRET]"
                elif any(sensitive in k_lower for sensitive in SENSITIVE_KEY_NAMES):
                    cleaned[k] = "[REDACTED]"
                else:
                    cleaned[k] = cls.mask_payload(v)
            return cleaned
        elif isinstance(data, list):
            return [cls.mask_payload(item) for item in data]
        return data


pii_masker = PIIMasker()
