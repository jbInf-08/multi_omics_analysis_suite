"""Real-time Streaming Module.
==========================

Kafka-based real-time data processing.
"""

from backend.streaming.kafka_integration import (
    KafkaConfig,
    KafkaConsumer,
    KafkaProducer,
    StreamProcessor,
)

__all__ = [
    "KafkaConfig",
    "KafkaProducer",
    "KafkaConsumer",
    "StreamProcessor",
]
