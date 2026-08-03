"""
Run this as a SEPARATE process from the FastAPI app:
    python -m app.rabbitmq.consumer

This is the whole point of using RabbitMQ: the API just publishes a message
and returns instantly. This worker does the slow/unreliable stuff (sending
email, updating search index, etc.) without blocking the user's request.
"""
import json
from datetime import datetime
import pika

from app.config import RABBITMQ_HOST, QUEUE_OTP, QUEUE_BLOG_PUBLISHED, QUEUE_USER_REGISTERED
from app.database import SessionLocal
from app.models import AuditLog

EMAIL_LOG_FILE = "sent_emails.log"  # stand-in for a real email provider
MAX_RETRIES = 3


def send_email_mock(to: str, subject: str, body: str):
    """No real SMTP configured yet, so we 'send' by writing to a log file.
    Swap this out for smtplib / SendGrid / SES later - rest of the flow doesn't change."""
    with open(EMAIL_LOG_FILE, "a") as f:
        f.write(f"\n--- {datetime.utcnow().isoformat()} ---\n")
        f.write(f"To: {to}\nSubject: {subject}\n{body}\n")
    print(f"[email] sent to {to}: {subject}")


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


def _do_otp(data):
    email = data["email"]
    otp_code = data["otp_code"]
    purpose = data["purpose"]

    subject = "Your OTP Code" if purpose == "login" else "Verify your account"
    send_email_mock(email, subject, f"Your OTP is: {otp_code} (valid for a few minutes)")


def _do_user_registered(data):
    name = data.get("name") or "there"
    email = data["email"]
    user_id = data["user_id"]

    send_email_mock(email, "Welcome to BlogsNest!", f"Hi {name}, welcome aboard - your account has been created.")

    db = SessionLocal()
    try:
        db.add(AuditLog(action="user_registered", user_id=user_id, detail=f"{name} <{email}>"))
        db.commit()
        # simulated downstream tasks from the spec
        print(f"[analytics] would record signup event for user {user_id} ({email})")
    finally:
        db.close()


def _do_blog_published(data):
    blog_id = data["blog_id"]
    title = data["title"]
    owner_email = data["owner_email"]

    db = SessionLocal()
    try:
        db.add(AuditLog(action="blog_created", blog_id=blog_id, detail=f"'{title}' by {owner_email}"))
        db.commit()

        print(f"[search-index] would index blog {blog_id}: '{title}'")
        print(f"[cache] would clear blog-list cache")
        print(f"[notify] would notify subscribers about new blog '{title}'")
    finally:
        db.close()


def handle_otp_message(ch, method, properties, body):
    process_with_retry(ch, method, properties, body, QUEUE_OTP, _do_otp)


def handle_user_registered(ch, method, properties, body):
    process_with_retry(ch, method, properties, body, QUEUE_USER_REGISTERED, _do_user_registered)


def handle_blog_published(ch, method, properties, body):
    process_with_retry(ch, method, properties, body, QUEUE_BLOG_PUBLISHED, _do_blog_published)


def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()

    channel.queue_declare(queue=QUEUE_OTP, durable=True)
    channel.queue_declare(queue=QUEUE_BLOG_PUBLISHED, durable=True)
    channel.queue_declare(queue=QUEUE_USER_REGISTERED, durable=True)

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(queue=QUEUE_OTP, on_message_callback=handle_otp_message)
    channel.basic_consume(queue=QUEUE_BLOG_PUBLISHED, on_message_callback=handle_blog_published)
    channel.basic_consume(queue=QUEUE_USER_REGISTERED, on_message_callback=handle_user_registered)

    print("Worker started. Waiting for messages... (Ctrl+C to stop)")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
        connection.close()


if __name__ == "__main__":
    main()