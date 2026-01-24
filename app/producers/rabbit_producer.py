import json
import aio_pika
from aio_pika import DeliveryMode
from app.config import settings
from app.schemas.messages import AiResult


class RabbitProducer:
    def __init__(self):
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def start(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=50)

        # default direct exchange is fine for queues by routing_key
        self._exchange = self._channel.default_exchange

        # Ensure output queue exists
        await self._channel.declare_queue(settings.rabbitmq_queue_out, durable=True)

    async def stop(self) -> None:
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
        if self._connection and not self._connection.is_closed:
            await self._connection.close()

    async def publish_result(self, message: AiResult, reply_to: str | None = None) -> None:
        if not self._exchange:
            raise RuntimeError("RabbitProducer is not started")

        target = reply_to or settings.rabbitmq_queue_out

        body = json.dumps(message.model_dump(), ensure_ascii=False).encode("utf-8")

        await self._exchange.publish(
            aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT,
                correlation_id=message.correlation_id,  # AMQP property
            ),
            routing_key=target,
        )

