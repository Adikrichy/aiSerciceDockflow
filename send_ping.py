import asyncio
import json
import aio_pika

async def main():
    conn = await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")
    ch = await conn.channel()
    q = await ch.declare_queue("ai_tasks", durable=True)

    msg = {"type": "PING", "payload": {}}
    await ch.default_exchange.publish(
        aio_pika.Message(body=json.dumps(msg).encode("utf-8")),
        routing_key=q.name,
    )
    await conn.close()

asyncio.run(main())
