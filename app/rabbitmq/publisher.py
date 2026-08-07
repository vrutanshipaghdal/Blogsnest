import json
from app.config import RABBITMQ_HOST, QUEUE_OTP, QUEUE_BLOG_PUBLISHED, QUEUE_USER_REGISTERED, QUEUE_COMMENT_POSTED, USE_RABBITMQ
from app.rabbitmq.handlers import do_otp, do_user_registered, do_blog_published, do_comment_posted


def get_connection():
    import pika
    return pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))


def _publish(queue_name: str, message: dict):
    """Opens a short-lived connection, publishes, closes.
    Fine for low/medium traffic; for high throughput you'd keep a pooled connection instead."""
    import pika
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
    message = {"email": email, "otp_code": otp_code, "purpose": purpose}
    if USE_RABBITMQ:
        _publish(QUEUE_OTP, message)
    else:
        # no RabbitMQ - just do the work right here, synchronously
        do_otp(message)


def publish_user_registered(user_id: int, name: str, email: str):
    message = {"user_id": user_id, "name": name, "email": email}
    if USE_RABBITMQ:
        _publish(QUEUE_USER_REGISTERED, message)
    else:
        do_user_registered(message)


def publish_blog_published(blog_id: int, title: str, owner_email: str):
    message = {"blog_id": blog_id, "title": title, "owner_email": owner_email}
    if USE_RABBITMQ:
        _publish(QUEUE_BLOG_PUBLISHED, message)
    else:
        do_blog_published(message)


def publish_comment_posted(blog_id: int, blog_title: str, blog_owner_email: str, commenter_name: str):
    message = {
        "blog_id": blog_id,
        "blog_title": blog_title,
        "blog_owner_email": blog_owner_email,
        "commenter_name": commenter_name,
    }
    if USE_RABBITMQ:
        _publish(QUEUE_COMMENT_POSTED, message)
    else:
        do_comment_posted(message)