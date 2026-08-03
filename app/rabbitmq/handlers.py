"""
The actual notification/audit-log work, pulled out into its own module so
it can be called two ways:
  1. Normally: consumer.py picks these up off a RabbitMQ queue (async, decoupled)
  2. USE_RABBITMQ=False fallback: publisher.py calls these directly, in-line,
     with no queue and no separate worker process needed - useful while
     you're still setting up RabbitMQ/Erlang.
"""
from datetime import datetime
from app.database import SessionLocal
from app.models import AuditLog

EMAIL_LOG_FILE = "sent_emails.log"


def send_email_mock(to: str, subject: str, body: str):
    """No real SMTP configured yet, so we 'send' by writing to a log file.
    Swap this out for smtplib / SendGrid / SES later - rest of the flow doesn't change."""
    with open(EMAIL_LOG_FILE, "a") as f:
        f.write(f"\n--- {datetime.utcnow().isoformat()} ---\n")
        f.write(f"To: {to}\nSubject: {subject}\n{body}\n")
    print(f"[email] sent to {to}: {subject}")


def do_otp(data: dict):
    email = data["email"]
    otp_code = data["otp_code"]
    purpose = data["purpose"]

    subject = "Your OTP Code" if purpose == "login" else "Verify your account"
    send_email_mock(email, subject, f"Your OTP is: {otp_code} (valid for a few minutes)")


def do_user_registered(data: dict):
    name = data.get("name") or "there"
    email = data["email"]
    user_id = data["user_id"]

    send_email_mock(email, "Welcome to BlogsNest!", f"Hi {name}, welcome aboard - your account has been created.")

    db = SessionLocal()
    try:
        db.add(AuditLog(action="user_registered", user_id=user_id, detail=f"{name} <{email}>"))
        db.commit()
        print(f"[analytics] would record signup event for user {user_id} ({email})")
    finally:
        db.close()


def do_blog_published(data: dict):
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