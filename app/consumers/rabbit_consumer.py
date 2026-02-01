import asyncio
import json
import aio_pika

from app.config import settings
from app.schemas.messages import AiTask, AiResult
from app.producers.rabbit_producer import RabbitProducer


class RabbitConsumer:
    def __init__(self, producer: RabbitProducer, router):
        self._producer = producer
        self._router = router

        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None

        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=20)

        # MAIN queue (in)
        await self._channel.declare_queue(settings.rabbitmq_queue_in, durable=True)

        # DLQ
        await self._channel.declare_queue(settings.rabbitmq_dlq, durable=True)

        # RETRY queue (TTL -> dead-letter back to MAIN)
        await self._channel.declare_queue(
            settings.rabbitmq_retry_queue,
            durable=True,
            arguments={
                "x-message-ttl": settings.rabbitmq_retry_delay_ms,
                "x-dead-letter-exchange": "",  # default exchange
                "x-dead-letter-routing-key": settings.rabbitmq_queue_in,
            },
        )

        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping.set()

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._channel and not self._channel.is_closed:
            await self._channel.close()
        if self._connection and not self._connection.is_closed:
            await self._connection.close()

    async def _run(self) -> None:
        assert self._channel is not None
        queue = await self._channel.get_queue(settings.rabbitmq_queue_in)

        async with queue.iterator() as it:
            async for message in it:
                if self._stopping.is_set():
                    break

                try:
                    await self._handle_message(message)
                    await message.ack()
                except Exception:
                    # Любая ошибка -> retry/DLQ, и ACK исходное сообщение,
                    # чтобы оно не крутилось бесконечно в main queue
                    await self._send_to_retry_or_dlq(message)
                    await message.ack()

    async def _handle_message(self, message: aio_pika.IncomingMessage) -> None:
        try:
            # 1) Parse входного сообщения
            data = json.loads(message.body.decode("utf-8"))
            task = AiTask.model_validate(data)
        except Exception as e:
            # Если не смогли даже распарсить задачу - логируем и выходим (сообщение уйдет в retry/DLQ)
            import logging
            logging.getLogger(__name__).error(f"Failed to parse AI task: {str(e)}")
            raise

        processing_result = AiResult(
            task_id=task.task_id,
            status="PROCESSING",
            result={},
            correlation_id=task.correlation_id,
            schema_version=task.schema_version,
        )
        await self._producer.publish_result(processing_result, reply_to=task.reply_to)

        try:
            # 2) Обработка бизнес-логики
            result_payload = await self._router.handle(task)

            # 3) Формируем ответ (с корреляцией/версией)
            status = "SUCCESS"
            if task.type == "CHAT":
                status = "CHAT_RESPONSE"

            result = AiResult(
                task_id=task.task_id,
                status=status,
                result=result_payload,
                correlation_id=task.correlation_id,
                schema_version=task.schema_version,
            )
        except Exception as e:
            result = AiResult(
                task_id=task.task_id,
                status="ERROR",
                result={},
                error=str(e),
                correlation_id=task.correlation_id,
                schema_version=task.schema_version,
            )

        # 4) Публикуем туда, куда указал отправитель, иначе default
        try:
            await self._producer.publish_result(result, reply_to=task.reply_to)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to publish result for task {task.task_id}: {e}")
            raise

    async def _send_to_retry_or_dlq(self, message: aio_pika.IncomingMessage) -> None:
        assert self._channel is not None

        headers = dict(message.headers or {})
        retry_count = int(headers.get("x-retry-count", 0)) + 1
        headers["x-retry-count"] = retry_count

        target = (
            settings.rabbitmq_retry_queue
            if retry_count <= settings.rabbitmq_max_retries
            else settings.rabbitmq_dlq
        )

        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=message.body,
                headers=headers,
                content_type=message.content_type or "application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                correlation_id=message.correlation_id,
            ),
            routing_key=target,
        )
