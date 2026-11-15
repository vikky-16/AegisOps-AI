"""
Syslog (RFC 5424 / RFC 3164) Protocol Ingestion Connector
Parses standard syslog messages from Linux/Windows servers and network appliances.
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.app.integrations.base import BaseConnector
from backend.app.integrations.models import NormalizedTelemetryEvent, TelemetryType, TelemetrySeverity


class SyslogConnector(BaseConnector):
    def __init__(self):
        super().__init__(
            connector_id="syslog-receiver",
            name="Syslog Ingestion Gateway",
            connector_type="SYSLOG",
            description="RFC 5424 / 3164 standardized log stream ingestion from OS servers, daemons, and appliances.",
            auth_required=False,
            enabled=True
        )

    def normalize(self, raw_payload: Any, headers: Optional[Dict[str, str]] = None) -> List[NormalizedTelemetryEvent]:
        events: List[NormalizedTelemetryEvent] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        raw_text = str(raw_payload)
        lines = raw_text.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Standard Syslog regex matching <priority>timestamp host process: message
            prio_match = re.match(r"^<(\d+)>", line)
            prio = int(prio_match.group(1)) if prio_match else 13
            clean_msg = re.sub(r"^<\d+>", "", line).strip()

            facility = prio >> 3
            severity_num = prio & 7

            if severity_num in [0, 1, 2]: # Emergency, Alert, Critical
                sev = TelemetrySeverity.CRITICAL
            elif severity_num == 3:       # Error
                sev = TelemetrySeverity.ERROR
            elif severity_num == 4:       # Warning
                sev = TelemetrySeverity.WARNING
            else:
                sev = TelemetrySeverity.INFO

            parts = clean_msg.split(maxsplit=6)
            # Detect RFC 5424: <PRI>1 TIMESTAMP HOSTNAME APP-NAME PROCID MSGID MSG
            if len(parts) >= 4 and parts[0] == "1":
                timestamp_str = parts[1]
                host = parts[2]
                service = parts[3].rstrip(":")
                msg = parts[6] if len(parts) > 6 else (" ".join(parts[4:]))
            elif len(parts) >= 3:
                host = parts[0]
                service = parts[1].rstrip(":")
                msg = " ".join(parts[2:])
            else:
                host = "syslog-host"
                service = "system"
                msg = clean_msg

            events.append(NormalizedTelemetryEvent(
                timestamp=now_iso,
                source=f"syslog-{host}",
                environment="demo",
                service=service.lower(),
                type=TelemetryType.LOG,
                severity=sev,
                event_type="SYSLOG_EVENT",
                message=msg,
                host=host,
                metadata={"facility": facility, "syslog_priority": prio}
            ))

        self.record_ingest(len(events))
        return events
