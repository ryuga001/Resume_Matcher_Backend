"""
RabbitMQ pub/sub helpers.

Publisher:  call publish(queue, message_dict) from any view.
Consumer:   call consume(queue, callback) in a worker script — blocks forever
            with automatic reconnect on connection loss.
"""
import json
import os
import time

import pika


def _connection_params() -> pika.URLParameters:
    url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    params = pika.URLParameters(url)
    # Disable heartbeat so long-running callbacks (Gemini API, PDF parsing)
    # never cause RabbitMQ to close the connection mid-task.
    params.heartbeat = 0
    params.blocked_connection_timeout = 300
    return params


def _open_channel(queue: str) -> tuple[pika.BlockingConnection, pika.adapters.blocking_connection.BlockingChannel]:
    conn = pika.BlockingConnection(_connection_params())
    ch = conn.channel()
    ch.queue_declare(queue=queue, durable=True)
    return conn, ch


def publish(queue: str, message: dict) -> None:
    """Publish a JSON-serialisable message to a durable queue. Fire-and-forget."""
    conn, ch = _open_channel(queue)
    try:
        ch.basic_publish(
            exchange="",
            routing_key=queue,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2),  # persistent
        )
    finally:
        conn.close()


def consume(queue: str, callback) -> None:
    """
    Start a blocking consumer with automatic reconnect on connection loss.
    `callback(ch, method, properties, body)` is responsible for acking/nacking.
    """
    retry_delay = 5
    while True:
        try:
            conn, ch = _open_channel(queue)
            ch.basic_qos(prefetch_count=1)
            ch.basic_consume(queue=queue, on_message_callback=callback)
            print(f"[rabbitmq] listening on queue='{queue}'  CTRL+C to stop")
            retry_delay = 5  # reset on successful connect
            ch.start_consuming()
        except KeyboardInterrupt:
            print(f"[rabbitmq] shutting down queue='{queue}'")
            try:
                ch.stop_consuming()
                conn.close()
            except Exception:
                pass
            return
        except pika.exceptions.AMQPConnectionError as exc:
            print(f"[rabbitmq] connection lost ({exc}), retrying in {retry_delay}s…")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)
        except Exception as exc:
            print(f"[rabbitmq] unexpected error ({exc}), retrying in {retry_delay}s…")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)
