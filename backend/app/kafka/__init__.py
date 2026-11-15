"""
AegisOps AI - Kafka Streaming Integration Module
"""

from backend.app.kafka.topic_manager import topic_manager, KafkaTopicManager
from backend.app.kafka.health import kafka_health_tracker, KafkaHealthTracker
from backend.app.kafka.dead_letter import dead_letter_handler, DeadLetterHandler
from backend.app.kafka.producer import kafka_producer, AegisKafkaProducer
from backend.app.kafka.consumer import kafka_consumer, AegisKafkaConsumer
from backend.app.kafka.event_bus import event_bus, AegisEventBus

__all__ = [
    "topic_manager",
    "KafkaTopicManager",
    "kafka_health_tracker",
    "KafkaHealthTracker",
    "dead_letter_handler",
    "DeadLetterHandler",
    "kafka_producer",
    "AegisKafkaProducer",
    "kafka_consumer",
    "AegisKafkaConsumer",
    "event_bus",
    "AegisEventBus"
]
