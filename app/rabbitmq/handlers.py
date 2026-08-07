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
from app.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM

EMAIL_LOG_FILE = "sent_emails.log"


def send_email_mock(to: str, subject: str, body: str):
    """
    Sends a REAL email via SMTP if SMTP_HOST/SMTP_USER/SMTP_PASSWORD are set
    (see app/config.py). Otherwise falls back to writing the message to
    sent_emails.log so the flow still works for testing.

    Gmail setup:
      1. Turn on 2-Step Verification: myaccount.google.com/security
      2. Create an App Password: myaccount.google.com/apppasswords
      3. Set env vars (same terminal, before running uvicorn):
           $env:SMTP_HOST = "smtp.gmail.com"
           $env:SMTP_USER = "youraddress@gmail.com"
           $env:SMTP_PASSWORD = "the 16-character app password"
    """
    if SMTP_HOST and SMTP_USER and SMTP_PASSWORD:
        try:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM
            msg["To"] = to

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM, to, msg.as_string())

            print(f"[email] REAL email sent to {to}: {subject}")
            return
        except Exception as e:
            print(f"[email] SMTP send failed ({e}), falling back to log file")

    with open(EMAIL_LOG_FILE, "a") as f:
        f.write(f"\n--- {datetime.utcnow().isoformat()} ---\n")
        f.write(f"To: {to}\nSubject: {subject}\n{body}\n")
    print(f"[email-mock] sent to {to}: {subject}")


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


def do_comment_posted(data: dict):
    blog_id = data["blog_id"]
    blog_title = data["blog_title"]
    blog_owner_email = data["blog_owner_email"]
    commenter_name = data["commenter_name"]

    # don't email yourself when you comment on your own post
    if blog_owner_email and commenter_name != blog_owner_email:
        send_email_mock(
            blog_owner_email,
            f"New comment on '{blog_title}'",
            f"{commenter_name} commented on your post '{blog_title}'.",
        )

    db = SessionLocal()
    try:
        db.add(AuditLog(action="comment_posted", blog_id=blog_id, detail=f"by {commenter_name}"))
        db.commit()
    finally:
        db.close()