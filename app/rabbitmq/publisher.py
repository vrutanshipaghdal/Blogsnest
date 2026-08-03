import json
import pika
from app.config import RABBITMQ_HOST, QUEUE_OTP, QUEUE_BLOG_PUBLISHED, QUEUE_USER_REGISTERED


def get_connection():
    return pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))


def _publish(queue_name: str, message: dict):
    """Opens a short-lived connection, publishes, closes.
    Fine for low/medium traffic; for high throughput you'd keep a pooled connection instead."""
    connection = get_connection()
    channel = connection.channel()
    channel.queue_declare(queue=queue_name, durable=True)

    channel.basic_publish(
        exchange="",
        routing_key=queue_name,
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=2),  # persistent message
    )
    connection.close()


def publish_otp_requested(email: str, otp_code: str, purpose: str):
    _publish(QUEUE_OTP, {
        "email": email,
        "otp_code": otp_code,
        "purpose": purpose,
    })


def publish_user_registered(user_id: int, name: str, email: str):
    _publish(QUEUE_USER_REGISTERED, {
        "user_id": user_id,
        "name": name,
        "email": email,
    })


def publish_blog_published(blog_id: int, title: str, owner_email: str):
    _publish(QUEUE_BLOG_PUBLISHED, {
        "blog_id": blog_id,
        "title": title,
        "owner_email": owner_email,
    })