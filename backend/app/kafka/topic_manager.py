"""
AegisOps AI - Enterprise Kafka Topic Architecture
Defines tenant-partitioned topics for streaming telemetry, normalization, anomalies,
correlations, incidents, remediation workflows, and operational audit trails.
"""

from typing import List, Dict, Any


class KafkaTopicManager:
    # Standard AegisOps Enterprise Topic Hierarchy
    TOPIC_LOGS = "aegisops.telemetry.logs"
    TOPIC_METRICS = "aegisops.telemetry.metrics"
    TOPIC_TRACES = "aegisops.telemetry.traces"
    TOPIC_EVENTS = "aegisops.telemetry.events"
    TOPIC_NORMALIZED = "aegisops.normalized.telemetry"
    TOPIC_ANOMALIES = "aegisops.anomalies"
    TOPIC_CORRELATIONS = "aegisops.correlations"
    TOPIC_INCIDENTS = "aegisops.incidents"
    TOPIC_REMEDIATION_ACTIONS = "aegisops.remediation.requests"
    TOPIC_REMEDIATION_RESULTS = "aegisops.remediation.results"
    TOPIC_AUDIT = "aegisops.audit"
    TOPIC_DEAD_LETTER = "aegisops.telemetry.deadletter"

    # Backward compatibility aliases
    TOPIC_RAW_TELEMETRY = TOPIC_NORMALIZED

    LEGACY_TOPICS = [
        "telemetry.raw",
        "telemetry.logs",
        "telemetry.metrics",
        "telemetry.traces",
        "telemetry.anomalies",
        "incidents",
        "remediation.actions",
        "remediation.results",
        "telemetry.deadletter",
    ]

    STANDARD_TOPICS = [
        TOPIC_LOGS,
        TOPIC_METRICS,
        TOPIC_TRACES,
        TOPIC_EVENTS,
        TOPIC_NORMALIZED,
        TOPIC_ANOMALIES,
        TOPIC_CORRELATIONS,
        TOPIC_INCIDENTS,
        TOPIC_REMEDIATION_ACTIONS,
        TOPIC_REMEDIATION_RESULTS,
        TOPIC_AUDIT,
        TOPIC_DEAD_LETTER
    ] + LEGACY_TOPICS

    @classmethod
    def get_standard_topics(cls) -> List[str]:
        return list(cls.STANDARD_TOPICS)

    @classmethod
    def get_topic_for_event_type(cls, event_type: str) -> str:
        t = (event_type or "").lower()
        if t in ["log", "logs"]:
            return cls.TOPIC_LOGS
        elif t in ["metric", "metrics"]:
            return cls.TOPIC_METRICS
        elif t in ["trace", "traces", "span"]:
            return cls.TOPIC_TRACES
        elif t in ["event", "events"]:
            return cls.TOPIC_EVENTS
        elif t in ["anomaly", "anomaly_signal", "anomalies"]:
            return cls.TOPIC_ANOMALIES
        elif t in ["correlation", "correlations"]:
            return cls.TOPIC_CORRELATIONS
        elif t in ["incident", "incidents"]:
            return cls.TOPIC_INCIDENTS
        elif t in ["remediation_action", "remediation.actions", "remediation_request"]:
            return cls.TOPIC_REMEDIATION_ACTIONS
        elif t in ["remediation_result", "remediation.results"]:
            return cls.TOPIC_REMEDIATION_RESULTS
        elif t in ["audit", "audit_log"]:
            return cls.TOPIC_AUDIT
        return cls.TOPIC_NORMALIZED

    @classmethod
    async def ensure_topics_exist(cls, bootstrap_servers: str = "localhost:9092", topics: List[str] = None) -> bool:
        """Safely creates standard Kafka topics if connected to a real broker and topics do not exist."""
        try:
            # Fast TCP probe to verify broker port is reachable before starting aiokafka
            host, port_str = bootstrap_servers.split(":") if ":" in bootstrap_servers else (bootstrap_servers, "9092")
            try:
                _, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port_str)), timeout=0.15)
                writer.close()
                await writer.wait_closed()
            except Exception:
                return False

            from aiokafka.admin import AIOKafkaAdminClient, NewTopic
            from aiokafka.errors import TopicAlreadyExistsError
            admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
            await admin.start()
            try:
                target_topics = topics or cls.STANDARD_TOPICS
                new_topics = [NewTopic(name=t, num_partitions=4, replication_factor=1) for t in target_topics]
                await admin.create_topics(new_topics)
            except TopicAlreadyExistsError:
                pass
            finally:
                await admin.close()
            return True
        except Exception:
            return False


topic_manager = KafkaTopicManager()
