"""
AegisOps AI - Real Async Kafka Consumer
Subscribes to standard AegisOps Kafka topics (default: telemetry.raw) and routes normalized
events to the AegisOps intelligence layer (Detection, Correlation, RCA, and Self-Healing).
Uses aiokafka for true network streaming with connection retry and graceful shutdown.
"""

import os
import json
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone

try:
    from aiokafka import AIOKafkaConsumer
    AIOKAFKA_AVAILABLE = True
except ImportError:
    AIOKAFKA_AVAILABLE = False

from backend.app.core.config import settings
from backend.app.schemas.telemetry_contract import UnifiedTelemetryEvent
from backend.app.integrations.normalizer import telemetry_normalizer
from backend.app.kafka.topic_manager import topic_manager
from backend.app.kafka.health import kafka_health_tracker
from backend.app.kafka.dead_letter import dead_letter_handler

logger = logging.getLogger("aegisops.kafka.consumer")


class AegisKafkaConsumer:
    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        group_id: Optional[str] = None,
        topic: Optional[str] = None
    ):
        self.bootstrap_servers = bootstrap_servers or getattr(settings, "KAFKA_BOOTSTRAP_SERVERS", os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
        self.group_id = group_id or getattr(settings, "KAFKA_CONSUMER_GROUP", os.getenv("KAFKA_CONSUMER_GROUP", "aegisops-telemetry-consumer"))
        self.topic = topic or getattr(settings, "KAFKA_TELEMETRY_TOPIC", os.getenv("KAFKA_TELEMETRY_TOPIC", "telemetry.raw"))
        self.is_running = False
        self.is_connected = False
        self.subscribed_topics = [self.topic]
        self._callbacks: List[Callable[[UnifiedTelemetryEvent], None]] = []
        self._worker_task: Optional[asyncio.Task] = None
        self._kafka_consumer: Optional[Any] = None

    def register_event_handler(self, callback: Callable[[UnifiedTelemetryEvent], None]):
        """Registers a callback for processing normalized telemetry consumed from Kafka."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    async def start(self):
        """Starts the background Kafka consumption worker task."""
        if self.is_running:
            return
        self.is_running = True
        self._worker_task = asyncio.create_task(self._consume_loop())

    async def stop(self):
        """Gracefully stops the Kafka consumer and worker task."""
        self.is_running = False
        self.is_connected = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except (asyncio.CancelledError, Exception):
                pass
            self._worker_task = None

        if self._kafka_consumer:
            try:
                await self._kafka_consumer.stop()
            except Exception:
                pass
            self._kafka_consumer = None

        kafka_health_tracker.set_connection_status(False, self.bootstrap_servers)

    async def _consume_loop(self):
        """Main streaming loop: connects to broker, consumes messages, and handles retries."""
        if not AIOKAFKA_AVAILABLE:
            logger.warning("[AEGISOPS KAFKA CONSUMER] aiokafka is not installed. Network consumer inactive.")
            return

        retry_count = 0
        while self.is_running:
            try:
                # Fast TCP probe to verify broker port is reachable before starting aiokafka
                host, port_str = self.bootstrap_servers.split(":") if ":" in self.bootstrap_servers else (self.bootstrap_servers, "9092")
                try:
                    _, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port_str)), timeout=0.15)
                    writer.close()
                    await writer.wait_closed()
                except Exception as probe_err:
                    raise ConnectionRefusedError(f"Kafka broker {self.bootstrap_servers} port unreachable") from probe_err

                # Ensure topic exists on broker
                await topic_manager.ensure_topics_exist(self.bootstrap_servers, [self.topic])

                self._kafka_consumer = AIOKafkaConsumer(
                    self.topic,
                    bootstrap_servers=self.bootstrap_servers,
                    group_id=self.group_id,
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                    value_deserializer=lambda v: json.loads(v.decode("utf-8", errors="replace")) if v else None
                )
                await self._kafka_consumer.start()
                self.is_connected = True
                kafka_health_tracker.set_connection_status(True, self.bootstrap_servers)
                print(f"[AEGISOPS KAFKA CONSUMER] Connected to Kafka broker {self.bootstrap_servers} [Group: {self.group_id}, Topic: {self.topic}].")
                retry_count = 0

                async for msg in self._kafka_consumer:
                    if not self.is_running:
                        break
                    print(f"[AEGISOPS KAFKA CONSUMER] Message received from topic '{msg.topic}' [Partition {msg.partition}, Offset {msg.offset}].")
                    await self.dispatch_incoming_message(msg.value, topic=msg.topic)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.is_connected = False
                kafka_health_tracker.set_connection_status(False, self.bootstrap_servers)
                kafka_health_tracker.record_failed(1)
                retry_count += 1
                backoff = min(30.0, 5.0 * min(retry_count, 6))
                if retry_count <= 2 or retry_count % 10 == 0:
                    print(f"[AEGISOPS KAFKA CONSUMER] Broker {self.bootstrap_servers} unavailable ({type(exc).__name__}). Reconnecting in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
            finally:
                if self._kafka_consumer:
                    try:
                        await self._kafka_consumer.stop()
                    except Exception:
                        pass
                    self._kafka_consumer = None

    async def dispatch_incoming_message(self, raw_message: Any, topic: str = "telemetry.raw"):
        """Dispatches an incoming message from Kafka or the streaming bridge through normalizers."""
        if raw_message is None:
            return

        start_t = time.time()
        kafka_health_tracker.record_received(1)
        
        try:
            events = telemetry_normalizer.normalize_event(raw_message, source="kafka")
            print(f"[AEGISOPS NORMALIZER] Normalized {len(events)} UnifiedTelemetryEvent(s) from Kafka payload.")
            for ev in events:
                for cb in self._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(cb):
                            await cb(ev)
                        else:
                            cb(ev)
                    except Exception as handler_exc:
                        dead_letter_handler.route_to_dlq(ev.model_dump(), f"Handler failed: {str(handler_exc)}", topic)
                        kafka_health_tracker.record_failed(1)
            
            elapsed_ms = (time.time() - start_t) * 1000
            kafka_health_tracker.record_processed(len(events), elapsed_ms)
        except Exception as exc:
            dead_letter_handler.route_to_dlq(raw_message, f"Normalization error: {str(exc)}", topic)
            kafka_health_tracker.record_failed(1)


kafka_consumer = AegisKafkaConsumer()
