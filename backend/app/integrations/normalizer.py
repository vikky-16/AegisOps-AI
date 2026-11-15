"""
Universal Telemetry Normalization Layer
Converts heterogeneous input formats (OTel, Kafka, REST, Webhook, Prometheus, Docker, Cloud)
into normalized UnifiedTelemetryEvent instances.
"""

import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.schemas.telemetry_contract import UnifiedTelemetryEvent, TelemetrySeverityLevel


class UniversalTelemetryNormalizer:
    @staticmethod
    def _parse_attributes(raw_attrs: Any) -> Dict[str, Any]:
        """Safely normalizes both dict attributes and OTLP list-of-KeyValue attributes."""
        if isinstance(raw_attrs, dict):
            return raw_attrs
        if isinstance(raw_attrs, list):
            result = {}
            for item in raw_attrs:
                if isinstance(item, dict):
                    k = item.get("key") or item.get("name")
                    v_obj = item.get("value")
                    if isinstance(v_obj, dict):
                        v = v_obj.get("stringValue", v_obj.get("intValue", v_obj.get("doubleValue", v_obj.get("boolValue", v_obj.get("arrayValue", str(v_obj))))))
                    else:
                        v = v_obj if v_obj is not None else item.get("val")
                    if k:
                        result[str(k)] = v
            return result
        return {}

    @classmethod
    def normalize_event(cls, payload: Any, source: str = "generic", headers: Optional[Dict[str, str]] = None) -> List[UnifiedTelemetryEvent]:
        """Normalizes any incoming raw payload into a list of UnifiedTelemetryEvent instances."""
        now_iso = datetime.now(timezone.utc).isoformat()
        results: List[UnifiedTelemetryEvent] = []

        if isinstance(payload, UnifiedTelemetryEvent):
            return [payload]

        if isinstance(payload, list):
            for item in payload:
                results.extend(cls.normalize_event(item, source=source, headers=headers))
            return results

        if not isinstance(payload, dict):
            # Wrap primitive/string
            return [
                UnifiedTelemetryEvent(
                    event_id=f"evt-{uuid.uuid4().hex[:12]}",
                    timestamp=now_iso,
                    source=source,
                    event_type="log",
                    message=str(payload),
                    severity="INFO"
                )
            ]

        # 1. OpenTelemetry ResourceSpans / ScopeSpans
        if "resourceSpans" in payload or "resource_spans" in payload:
            spans_list = payload.get("resourceSpans") or payload.get("resource_spans") or []
            for rs in spans_list:
                res_attrs = cls._parse_attributes(rs.get("resource", {}).get("attributes", []))
                svc_name = str(res_attrs.get("service.name") or "otel-service")

                for scope in rs.get("scopeSpans", rs.get("scope_spans", [])):
                    for span in scope.get("spans", []):
                        name = span.get("name", "span")
                        trace_id = span.get("traceId", span.get("trace_id", ""))
                        span_id = span.get("spanId", span.get("span_id", ""))
                        status_code = span.get("status", {}).get("code", 0)
                        is_err = status_code == 2 or "error" in name.lower() or span.get("status", {}).get("message")
                        sev = "ERROR" if is_err else "INFO"
                        
                        duration_ns = int(span.get("endTimeUnixNano", 0)) - int(span.get("startTimeUnixNano", 0))
                        duration_ms = duration_ns / 1_000_000 if duration_ns > 0 else None
                        span_attrs = cls._parse_attributes(span.get("attributes", {}))

                        results.append(UnifiedTelemetryEvent(
                            event_id=f"evt-{uuid.uuid4().hex[:12]}",
                            timestamp=now_iso,
                            tenant_id=res_attrs.get("tenant.id", "demo-tenant"),
                            source="otel",
                            event_type="trace",
                            service_name=svc_name,
                            environment=res_attrs.get("environment", "development"),
                            host=res_attrs.get("host.name", "localhost"),
                            trace_id=trace_id,
                            span_id=span_id,
                            severity=sev,
                            metric_name="span_duration_ms" if duration_ms else None,
                            metric_value=duration_ms,
                            http_status=500 if is_err else 200,
                            message=f"Span '{name}' completed with status {status_code}" + (f": {span.get('status',{}).get('message')}" if span.get('status',{}).get('message') else ""),
                            attributes={**res_attrs, **span_attrs},
                            dependencies=[]
                        ))
            return results

        # 2. OpenTelemetry ResourceMetrics / ScopeMetrics
        if "resourceMetrics" in payload or "resource_metrics" in payload:
            metrics_list = payload.get("resourceMetrics") or payload.get("resource_metrics") or []
            for rm in metrics_list:
                res_attrs = cls._parse_attributes(rm.get("resource", {}).get("attributes", []))
                svc_name = str(res_attrs.get("service.name") or "otel-service")

                for scope in rm.get("scopeMetrics", rm.get("scope_metrics", [])):
                    for m in scope.get("metrics", []):
                        m_name = m.get("name", "metric")
                        gauge = m.get("gauge", {}).get("dataPoints", [])
                        sum_data = m.get("sum", {}).get("dataPoints", [])
                        hist_data = m.get("histogram", {}).get("dataPoints", [])
                        
                        points = gauge or sum_data or hist_data or [{}]
                        for dp in points:
                            val = dp.get("asDouble") or dp.get("asInt") or dp.get("value") or 0.0
                            dp_attrs = cls._parse_attributes(dp.get("attributes", {}))
                            results.append(UnifiedTelemetryEvent(
                                event_id=f"evt-{uuid.uuid4().hex[:12]}",
                                timestamp=now_iso,
                                tenant_id=res_attrs.get("tenant.id", "demo-tenant"),
                                source="otel",
                                event_type="metric",
                                service_name=svc_name,
                                environment=res_attrs.get("environment", "development"),
                                severity="INFO",
                                metric_name=m_name,
                                metric_value=float(val),
                                message=f"Metric {m_name} = {val}",
                                attributes={**res_attrs, **dp_attrs}
                            ))
            return results

        # 3. OpenTelemetry ResourceLogs / ScopeLogs
        if "resourceLogs" in payload or "resource_logs" in payload:
            logs_list = payload.get("resourceLogs") or payload.get("resource_logs") or []
            for rl in logs_list:
                res_attrs = cls._parse_attributes(rl.get("resource", {}).get("attributes", []))
                svc_name = str(res_attrs.get("service.name") or "otel-service")

                for scope in rl.get("scopeLogs", rl.get("scope_logs", [])):
                    for log_rec in scope.get("logRecords", scope.get("log_records", [])):
                        body = log_rec.get("body", {})
                        msg_str = body.get("stringValue", body) if isinstance(body, dict) else str(body)
                        sev_text = str(log_rec.get("severityText") or log_rec.get("severity_text") or "INFO").upper()
                        if sev_text not in ["INFO", "WARN", "WARNING", "ERROR", "CRITICAL"]:
                            sev_text = "INFO"
                        if sev_text == "WARN":
                            sev_text = "WARNING"
                        
                        trace_id = log_rec.get("traceId", log_rec.get("trace_id", ""))
                        span_id = log_rec.get("spanId", log_rec.get("span_id", ""))
                        log_attrs = cls._parse_attributes(log_rec.get("attributes", []))

                        results.append(UnifiedTelemetryEvent(
                            event_id=f"evt-{uuid.uuid4().hex[:12]}",
                            timestamp=now_iso,
                            tenant_id=res_attrs.get("tenant.id", "demo-tenant"),
                            source="otel",
                            event_type="log",
                            service_name=svc_name,
                            environment=res_attrs.get("environment", "development"),
                            host=res_attrs.get("host.name", "localhost"),
                            trace_id=trace_id if trace_id else None,
                            span_id=span_id if span_id else None,
                            severity=sev_text,
                            message=msg_str,
                            attributes={**res_attrs, **log_attrs}
                        ))
            return results

        # 4. Standard JSON Log or Kafka Event
        svc = payload.get("service_name") or payload.get("service") or payload.get("app") or "unknown-service"
        evt_type = payload.get("event_type") or payload.get("type") or "log"
        severity = str(payload.get("severity") or payload.get("level") or "INFO").upper()
        if severity not in ["INFO", "WARN", "WARNING", "ERROR", "CRITICAL"]:
            severity = "INFO"
        if severity == "WARN":
            severity = "WARNING"

        msg = str(payload.get("message") or payload.get("msg") or payload.get("event") or payload.get("description") or "")
        trace_id = payload.get("trace_id") or payload.get("traceId")
        span_id = payload.get("span_id") or payload.get("spanId")
        req_id = payload.get("request_id") or payload.get("requestId")

        metric_name = payload.get("metric_name") or payload.get("metric")
        metric_val = payload.get("metric_value") or payload.get("value")
        if metric_val is not None:
            try:
                metric_val = float(metric_val)
            except (ValueError, TypeError):
                metric_val = None

        http_status = payload.get("http_status") or payload.get("status_code")
        if http_status is not None:
            try:
                http_status = int(http_status)
            except (ValueError, TypeError):
                http_status = None

        results.append(UnifiedTelemetryEvent(
            event_id=payload.get("event_id") or f"evt-{uuid.uuid4().hex[:12]}",
            timestamp=payload.get("timestamp") or now_iso,
            tenant_id=payload.get("tenant_id") or "demo-tenant",
            source=payload.get("source") or source,
            event_type=evt_type,
            service_name=svc,
            environment=payload.get("environment") or "development",
            host=payload.get("host") or "localhost",
            trace_id=trace_id,
            span_id=span_id,
            request_id=req_id,
            severity=severity,
            metric_name=metric_name,
            metric_value=metric_val,
            http_status=http_status,
            message=msg,
            attributes=payload.get("attributes") or payload.get("metadata") or {},
            dependencies=payload.get("dependencies") or []
        ))

        return results


    @classmethod
    def normalize(cls, payload: Any, source_type: str = "generic", source: str = "generic", headers: Optional[Dict[str, str]] = None) -> Any:
        src = source_type if source_type != "generic" else source
        res = cls.normalize_event(payload, source=src, headers=headers)
        if isinstance(payload, dict) and not isinstance(payload, list) and len(res) == 1:
            return res[0]
        return res


telemetry_normalizer = UniversalTelemetryNormalizer()
universal_normalizer = telemetry_normalizer
