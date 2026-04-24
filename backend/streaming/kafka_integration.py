"""Kafka Integration Module.
========================

Real-time data streaming with Apache Kafka.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


logger = logging.getLogger(__name__)


@dataclass
class KafkaConfig:
    """Kafka connection configuration."""

    bootstrap_servers: str = "localhost:9092"
    client_id: str = "multi_omics_suite"
    group_id: str = "omics_consumers"
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = True
    max_poll_records: int = 500
    session_timeout_ms: int = 30000
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: str | None = None
    sasl_username: str | None = None
    sasl_password: str | None = None


class MessageType(str, Enum):
    """Types of streaming messages."""

    ANALYSIS_REQUEST = "analysis_request"
    ANALYSIS_RESULT = "analysis_result"
    DATA_UPDATE = "data_update"
    MUTATION_DETECTED = "mutation_detected"
    ALERT = "alert"
    STATUS_UPDATE = "status_update"


@dataclass
class StreamMessage:
    """A streaming message."""

    message_type: MessageType
    topic: str
    key: str | None
    value: dict[str, Any]
    timestamp: datetime = field(default_factory=utc_now)
    headers: dict[str, str] = field(default_factory=dict)


class KafkaProducer:
    """Kafka producer for publishing messages."""

    def __init__(self, config: KafkaConfig | None = None):
        """Initialize Kafka producer.

        Args:
            config: Kafka configuration

        """
        self.config = config or KafkaConfig()
        self._producer = None

    async def _get_producer(self):
        """Get or create producer."""
        if self._producer is None:
            try:
                from aiokafka import AIOKafkaProducer

                self._producer = AIOKafkaProducer(
                    bootstrap_servers=self.config.bootstrap_servers,
                    client_id=self.config.client_id,
                    value_serializer=lambda v: json.dumps(v).encode(),
                    key_serializer=lambda k: k.encode() if k else None,
                )
                await self._producer.start()

            except ImportError:
                raise ImportError("aiokafka not installed. Install with: pip install aiokafka")

        return self._producer

    async def send(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> bool:
        """Send a message to a topic.

        Args:
            topic: Topic name
            value: Message value
            key: Message key
            headers: Message headers

        Returns:
            Success status

        """
        producer = await self._get_producer()

        try:
            kafka_headers = [(k, v.encode()) for k, v in (headers or {}).items()]

            await producer.send_and_wait(
                topic,
                value=value,
                key=key,
                headers=kafka_headers,
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def send_analysis_request(
        self,
        analysis_type: str,
        parameters: dict[str, Any],
        request_id: str,
    ) -> bool:
        """Send an analysis request."""
        return await self.send(
            "analysis_requests",
            {
                "type": MessageType.ANALYSIS_REQUEST.value,
                "analysis_type": analysis_type,
                "parameters": parameters,
                "request_id": request_id,
                "timestamp": utc_now().isoformat(),
            },
            key=request_id,
        )

    async def send_analysis_result(
        self,
        request_id: str,
        results: dict[str, Any],
        status: str = "completed",
    ) -> bool:
        """Send analysis results."""
        return await self.send(
            "analysis_results",
            {
                "type": MessageType.ANALYSIS_RESULT.value,
                "request_id": request_id,
                "status": status,
                "results": results,
                "timestamp": utc_now().isoformat(),
            },
            key=request_id,
        )

    async def send_mutation_alert(
        self,
        gene: str,
        mutation: str,
        sample_id: str,
        clinical_significance: str,
    ) -> bool:
        """Send a mutation detection alert."""
        return await self.send(
            "mutation_alerts",
            {
                "type": MessageType.MUTATION_DETECTED.value,
                "gene": gene,
                "mutation": mutation,
                "sample_id": sample_id,
                "clinical_significance": clinical_significance,
                "timestamp": utc_now().isoformat(),
            },
            key=f"{gene}_{mutation}",
        )

    async def close(self):
        """Close the producer."""
        if self._producer:
            await self._producer.stop()
            self._producer = None


class KafkaConsumer:
    """Kafka consumer for receiving messages."""

    def __init__(
        self,
        topics: list[str],
        config: KafkaConfig | None = None,
    ):
        """Initialize Kafka consumer.

        Args:
            topics: Topics to subscribe to
            config: Kafka configuration

        """
        self.topics = topics
        self.config = config or KafkaConfig()
        self._consumer = None
        self._running = False

    async def _get_consumer(self):
        """Get or create consumer."""
        if self._consumer is None:
            try:
                from aiokafka import AIOKafkaConsumer

                self._consumer = AIOKafkaConsumer(
                    *self.topics,
                    bootstrap_servers=self.config.bootstrap_servers,
                    group_id=self.config.group_id,
                    auto_offset_reset=self.config.auto_offset_reset,
                    enable_auto_commit=self.config.enable_auto_commit,
                    max_poll_records=self.config.max_poll_records,
                    value_deserializer=lambda v: json.loads(v.decode()),
                    key_deserializer=lambda k: k.decode() if k else None,
                )
                await self._consumer.start()

            except ImportError:
                raise ImportError("aiokafka not installed. Install with: pip install aiokafka")

        return self._consumer

    async def consume(
        self,
        handler: Callable[[StreamMessage], None],
        batch_size: int = 100,
    ):
        """Start consuming messages.

        Args:
            handler: Message handler function
            batch_size: Number of messages per batch

        """
        consumer = await self._get_consumer()
        self._running = True

        try:
            async for msg in consumer:
                if not self._running:
                    break

                message = StreamMessage(
                    message_type=MessageType(msg.value.get("type", "status_update")),
                    topic=msg.topic,
                    key=msg.key,
                    value=msg.value,
                    timestamp=datetime.fromtimestamp(msg.timestamp / 1000),
                    headers={k: v.decode() for k, v in msg.headers} if msg.headers else {},
                )

                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"Message handler error: {e}")

        except Exception as e:
            logger.error(f"Consumer error: {e}")
        finally:
            self._running = False

    def stop(self):
        """Stop consuming."""
        self._running = False

    async def close(self):
        """Close the consumer."""
        self.stop()
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None


class StreamProcessor:
    """Stream processor for real-time data processing.

    Processes messages from input topics and produces
    results to output topics.
    """

    def __init__(
        self,
        input_topics: list[str],
        output_topic: str,
        config: KafkaConfig | None = None,
    ):
        """Initialize stream processor.

        Args:
            input_topics: Input topic names
            output_topic: Output topic name
            config: Kafka configuration

        """
        self.input_topics = input_topics
        self.output_topic = output_topic
        self.config = config or KafkaConfig()

        self.consumer = KafkaConsumer(input_topics, config)
        self.producer = KafkaProducer(config)

        self._processors: dict[MessageType, Callable] = {}
        self._running = False

    def register_processor(
        self,
        message_type: MessageType,
        processor: Callable[[dict], dict],
    ):
        """Register a processor for a message type.

        Args:
            message_type: Message type to process
            processor: Processing function

        """
        self._processors[message_type] = processor

    async def _handle_message(self, message: StreamMessage):
        """Handle an incoming message."""
        processor = self._processors.get(message.message_type)

        if processor:
            try:
                result = await processor(message.value)

                if result:
                    await self.producer.send(
                        self.output_topic,
                        result,
                        key=message.key,
                    )

            except Exception as e:
                logger.error(f"Processing error for {message.message_type}: {e}")

                # Send error to output
                await self.producer.send(
                    self.output_topic,
                    {
                        "type": "error",
                        "original_type": message.message_type.value,
                        "error": str(e),
                        "timestamp": utc_now().isoformat(),
                    },
                    key=message.key,
                )

    async def start(self):
        """Start the stream processor."""
        self._running = True
        logger.info(f"Starting stream processor: {self.input_topics} -> {self.output_topic}")

        await self.consumer.consume(self._handle_message)

    async def stop(self):
        """Stop the stream processor."""
        self._running = False
        self.consumer.stop()
        await self.consumer.close()
        await self.producer.close()


# Pre-built processors


async def mutation_detection_processor(message: dict) -> dict:
    """Process mutation detection messages."""
    # Check for actionable mutations
    gene = message.get("gene")
    mutation = message.get("mutation")

    # Simple actionability check
    actionable_genes = ["EGFR", "BRAF", "KRAS", "ALK", "ROS1", "BRCA1", "BRCA2"]

    return {
        "type": (
            MessageType.ALERT.value if gene in actionable_genes else MessageType.STATUS_UPDATE.value
        ),
        "gene": gene,
        "mutation": mutation,
        "actionable": gene in actionable_genes,
        "timestamp": utc_now().isoformat(),
    }


async def analysis_request_processor(message: dict) -> dict:
    """Process analysis requests."""
    analysis_type = message.get("analysis_type")
    request_id = message.get("request_id")

    # Route to appropriate analysis handler
    return {
        "type": MessageType.STATUS_UPDATE.value,
        "request_id": request_id,
        "status": "processing",
        "analysis_type": analysis_type,
        "timestamp": utc_now().isoformat(),
    }
