"""
Run this as a SEPARATE process from the FastAPI app (only needed when
USE_RABBITMQ=true in config.py):
    python -m app.rabbitmq.consumer

This is the whole point of using RabbitMQ: the API just publishes a message
and returns instantly. This worker does the slow/unreliable stuff (sending
email, updating search index, etc.) without blocking the user's request.

If USE_RABBITMQ=false, this file isn't used at all - publisher.py calls the
same handler functions directly instead. See app/rabbitmq/handlers.py.
"""
import json
import pika

from app.config import RABBITMQ_HOST, QUEUE_OTP, QUEUE_BLOG_PUBLISHED, QUEUE_USER_REGISTERED, QUEUE_COMMENT_POSTED
from app.rabbitmq.handlers import do_otp, do_user_registered, do_blog_published, do_comment_posted

MAX_RETRIES = 3


def process_with_retry(ch, method, properties, body, queue_name, work_fn):
    """
    Runs work_fn(data). If it raises, retries by re-publishing the message
    with an incremented retry counter (stored in message headers) instead of
    just crashing or silently dropping it - that's the "retry on notification
    failure" requirement from the spec.

    After MAX_RETRIES failed attempts, the message is dropped and logged as
    dead-lettered (in a production system you'd route it to a real dead-letter
    queue instead of just printing).
    """
    retry_count = (properties.headers or {}).get("x-retry-count", 0) if properties else 0

    try:
        data = json.loads(body)
        work_fn(data)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        ch.basic_ack(delivery_tag=method.delivery_tag)  # remove the failed copy from the queue

        if retry_count < MAX_RETRIES:
            print(f"[retry] {queue_name} failed ({e}) - retry {retry_count + 1}/{MAX_RETRIES}")
            new_headers = dict(properties.headers or {}) if properties else {}
            new_headers["x-retry-count"] = retry_count + 1
            ch.basic_publish(
                exchange="",
                routing_key=queue_name,
                body=body,
                properties=pika.BasicProperties(delivery_mode=2, headers=new_headers),
            )
        else:
            print(f"[dead-letter] {queue_name} failed after {MAX_RETRIES} retries, giving up: {e}")


def handle_otp_message(ch, method, properties, body):
    process_with_retry(ch, method, properties, body, QUEUE_OTP, do_otp)


def handle_user_registered(ch, method, properties, body):
    process_with_retry(ch, method, properties, body, QUEUE_USER_REGISTERED, do_user_registered)


def handle_blog_published(ch, method, properties, body):
    process_with_retry(ch, method, properties, body, QUEUE_BLOG_PUBLISHED, do_blog_published)


def handle_comment_posted(ch, method, properties, body):
    process_with_retry(ch, method, properties, body, QUEUE_COMMENT_POSTED, do_comment_posted)


def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()

    channel.queue_declare(queue=QUEUE_OTP, durable=True)
    channel.queue_declare(queue=QUEUE_BLOG_PUBLISHED, durable=True)
    channel.queue_declare(queue=QUEUE_USER_REGISTERED, durable=True)
    channel.queue_declare(queue=QUEUE_COMMENT_POSTED, durable=True)

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(queue=QUEUE_OTP, on_message_callback=handle_otp_message)
    channel.basic_consume(queue=QUEUE_BLOG_PUBLISHED, on_message_callback=handle_blog_published)
    channel.basic_consume(queue=QUEUE_USER_REGISTERED, on_message_callback=handle_user_registered)
    channel.basic_consume(queue=QUEUE_COMMENT_POSTED, on_message_callback=handle_comment_posted)

    print("Worker started. Waiting for messages... (Ctrl+C to stop)")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()


if __name__ == "__main__":
    main()