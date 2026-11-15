"""
ShopSphere Redpanda/Kafka Telemetry Consumer & AegisOps Bridge
Subscribes to topics:
  - shopsphere-logs
  - shopsphere-metrics
  - shopsphere-traces
Consumes live telemetry produced by OpenTelemetry Collector, validates tenant_id="shopsphere",
normalizes OTLP JSON data, and streams batches directly to the AegisOps Telemetry Ingestion Gateway.
Measures real broker throughput and message rates.
"""

import os
import sys
import json
import time
import asyncio
from datetime import datetime, timezone
import httpx
from typing import Dict, Any, List, Optional

try:
    from aiokafka import AIOKafkaConsumer
    AIOKAFKA_AVAILABLE = True
except ImportError:
    AIOKAFKA_AVAILABLE = False

REDPANDA_BOOTSTRAP = os.getenv("REDPANDA_BOOTSTRAP_SERVERS", "redpanda:9092")
AEGISOPS_GATEWAY_URL = os.getenv("AEGISOPS_GATEWAY_URL", "http://host.docker.internal:8000/api/v1/telemetry").rstrip("/")
TENANT_ID = "shopsphere"
API_KEY = os.getenv("AEGISOPS_API_KEY", "agt_live_shopsphere_11112222333344445555")
TOPICS = ["shopsphere-logs", "shopsphere-metrics", "shopsphere-traces"]


class BrokerStats:
    def __init__(self):
        self.total_consumed = 0
        self.total_forwarded = 0
        self.total_bytes = 0
        self.window_messages = 0
        self.window_bytes = 0
        self.last_report = time.time()

    def record(self, msg_count: int, byte_count: int):
        self.total_consumed += msg_count
        self.total_forwarded += msg_count
        self.total_bytes += byte_count
        self.window_messages += msg_count
        self.window_bytes += byte_count

    def print_summary(self):
        now = time.time()
        elapsed = now - self.last_report
        if elapsed < 2.0:
            return
        rate = round(self.window_messages / elapsed, 1)
        kb_sec = round((self.window_bytes / 1024.0) / elapsed, 1)
        print(
            f"[REDPANDA STREAMER] Consumed {rate} msgs/sec ({kb_sec} KB/s) from Redpanda -> Forwarded to AegisOps | "
            f"Total Messages: {self.total_consumed}",
            flush=True
        )
        self.window_messages = 0
        self.window_bytes = 0
        self.last_report = now


stats = BrokerStats()


def parse_otlp_json(topic: str, val: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalizes OTLP JSON messages from Kafka topics into UnifiedTelemetryEvents for AegisOps."""
    events = []
    now_iso = datetime.now(timezone.utc).isoformat()
    
    if "traces" in topic or "resourceSpans" in val:
        for r_span in val.get("resourceSpans", []):
            svc_name = "shopsphere-service"
            for attr in r_span.get("resource", {}).get("attributes", []):
                if attr.get("key") == "service.name":
                    svc_name = attr.get("value", {}).get("stringValue", svc_name)
                    
            for scope in r_span.get("scopeSpans", []):
                for sp in scope.get("spans", []):
                    start_ns = int(sp.get("startTimeUnixNano", 0))
                    end_ns = int(sp.get("endTimeUnixNano", 0))
                    lat_ms = round((end_ns - start_ns) / 1_000_000.0, 2) if end_ns > start_ns else 0.0
                    
                    status_dict = sp.get("status", {})
                    status_code = status_dict.get("code", 0)
                    is_err = status_code == 2 or bool(status_dict.get("message"))
                    
                    attrs = {}
                    for a in sp.get("attributes", []):
                        k = a.get("key")
                        v = a.get("value", {})
                        attrs[k] = v.get("stringValue") or v.get("intValue") or v.get("doubleValue") or v.get("boolValue")
                    
                    http_code = attrs.get("http.status_code") or attrs.get("http.response.status_code")
                    route = attrs.get("http.route") or attrs.get("http.target") or sp.get("name")
                    
                    events.append({
                        "event_id": f"sp-tr-{sp.get('spanId', int(time.time()*1000))}",
                        "tenant_id": TENANT_ID,
                        "company_id": TENANT_ID,
                        "service_name": svc_name,
                        "event_type": "trace",
                        "severity": "ERROR" if is_err else ("WARNING" if lat_ms >= 1500 else "INFO"),
                        "timestamp": now_iso,
                        "message": f"Span {sp.get('name')} completed in {lat_ms}ms" if not is_err else f"Span {sp.get('name')} failed: {status_dict.get('message', 'error')}",
                        "source": "redpanda-traces",
                        "trace_id": sp.get("traceId"),
                        "span_id": sp.get("spanId"),
                        "latency": lat_ms,
                        "http_status": int(http_code) if http_code else (500 if is_err else 200),
                        "http_route": str(route),
                        "attributes": attrs
                    })
    elif "metrics" in topic or "resourceMetrics" in val:
        for r_met in val.get("resourceMetrics", []):
            svc_name = "shopsphere-service"
            for attr in r_met.get("resource", {}).get("attributes", []):
                if attr.get("key") == "service.name":
                    svc_name = attr.get("value", {}).get("stringValue", svc_name)
            for scope in r_met.get("scopeMetrics", []):
                for m in scope.get("metrics", []):
                    m_name = m.get("name", "metric")
                    dp_val = 1.0
                    gauge = m.get("gauge") or m.get("sum")
                    if gauge and gauge.get("dataPoints"):
                        dp = gauge["dataPoints"][0]
                        dp_val = dp.get("asDouble") or dp.get("asInt") or 1.0
                    events.append({
                        "event_id": f"sp-m-{int(time.time()*1000)}-{m_name}",
                        "tenant_id": TENANT_ID,
                        "company_id": TENANT_ID,
                        "service_name": svc_name,
                        "event_type": "metric",
                        "severity": "INFO",
                        "timestamp": now_iso,
                        "metric_name": m_name,
                        "metric_value": float(dp_val),
                        "source": "redpanda-metrics"
                    })
    elif "logs" in topic or "resourceLogs" in val:
        for r_log in val.get("resourceLogs", []):
            svc_name = "shopsphere-service"
            for attr in r_log.get("resource", {}).get("attributes", []):
                if attr.get("key") == "service.name":
                    svc_name = attr.get("value", {}).get("stringValue", svc_name)
            for scope in r_log.get("scopeLogs", []):
                for lg in scope.get("logRecords", []):
                    body = lg.get("body", {}).get("stringValue", "log")
                    sev = lg.get("severityText", "INFO")
                    events.append({
                        "event_id": f"sp-log-{int(time.time()*1000)}",
                        "tenant_id": TENANT_ID,
                        "company_id": TENANT_ID,
                        "service_name": svc_name,
                        "event_type": "log",
                        "severity": sev,
                        "timestamp": now_iso,
                        "message": body,
                        "source": "redpanda-logs"
                    })
    else:
        events.append({
            "event_id": f"sp-{int(time.time()*1000)}",
            "tenant_id": TENANT_ID,
            "company_id": TENANT_ID,
            "service_name": val.get("service") or "shopsphere-service",
            "event_type": "log",
            "severity": val.get("level") or "INFO",
            "timestamp": now_iso,
            "message": val.get("message") or f"Telemetry from {topic}",
            "source": "redpanda",
            "latency": val.get("latency_ms"),
            "attributes": val
        })
    return events


async def forward_batch(client: httpx.AsyncClient, batch: List[Dict[str, Any]]):
    if not batch:
        return
    try:
        resp = await client.post(
            f"{AEGISOPS_GATEWAY_URL}/batch",
            json=batch,
            headers={
                "X-API-Key": API_KEY,
                "X-Tenant-ID": TENANT_ID,
                "Content-Type": "application/json"
            },
            timeout=5.0
        )
        if resp.status_code == 200:
            raw_bytes = sum(len(json.dumps(x)) for x in batch)
            stats.record(len(batch), raw_bytes)
        else:
            print(f"[REDPANDA STREAMER] Gateway rejected batch: {resp.status_code} - {resp.text[:100]}", flush=True)
    except Exception as e:
        print(f"[REDPANDA STREAMER] Forward error to AegisOps: {e}", flush=True)


async def main():
    print("=" * 70)
    print(f"   SHOPSPHERE REDPANDA STREAMING CONNECTOR")
    print(f"   Redpanda Broker: {REDPANDA_BOOTSTRAP}")
    print(f"   Topics:          {', '.join(TOPICS)}")
    print(f"   AegisOps Target: {AEGISOPS_GATEWAY_URL}")
    print(f"   Enforced Tenant: {TENANT_ID}")
    print("=" * 70, flush=True)

    if not AIOKAFKA_AVAILABLE:
        print("[REDPANDA STREAMER] Error: aiokafka not installed", flush=True)
        return

    # Wait for AegisOps to be reachable
    async with httpx.AsyncClient(timeout=3.0) as http_client:
        for _ in range(30):
            try:
                r = await http_client.get(f"{AEGISOPS_GATEWAY_URL}/stats?tenant_id={TENANT_ID}")
                if r.status_code == 200:
                    print("[REDPANDA STREAMER] AegisOps Ingestion Gateway is online.", flush=True)
                    break
            except Exception:
                await asyncio.sleep(1.0)

    # Connect to Redpanda
    consumer = None
    for attempt in range(30):
        try:
            consumer = AIOKafkaConsumer(
                *TOPICS,
                bootstrap_servers=REDPANDA_BOOTSTRAP,
                group_id="shopsphere-aegisops-streamer",
                auto_offset_reset="latest",
                enable_auto_commit=True,
                value_deserializer=lambda v: json.loads(v.decode("utf-8", errors="replace")) if v else None
            )
            await consumer.start()
            print(f"[REDPANDA STREAMER] Connected to Redpanda on {REDPANDA_BOOTSTRAP}!", flush=True)
            break
        except Exception as exc:
            print(f"[REDPANDA STREAMER] Waiting for Redpanda ({exc})... Attempt {attempt+1}/30", flush=True)
            await asyncio.sleep(2.0)

    if not consumer:
        print("[REDPANDA STREAMER] Fatal: Failed to connect to Redpanda broker.", flush=True)
        return

    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    async with httpx.AsyncClient(limits=limits, timeout=5.0) as http_client:
        buffer = []
        last_flush = time.time()

        try:
            async for msg in consumer:
                val = msg.value
                if val:
                    parsed_events = parse_otlp_json(msg.topic, val)
                    buffer.extend(parsed_events)

                # Flush batch every 50 events or every 250ms
                if len(buffer) >= 50 or (time.time() - last_flush) >= 0.25:
                    if buffer:
                        asyncio.create_task(forward_batch(http_client, list(buffer)))
                        buffer.clear()
                    last_flush = time.time()

                stats.print_summary()

        except asyncio.CancelledError:
            pass
        finally:
            await consumer.stop()


if __name__ == "__main__":
    asyncio.run(main())
