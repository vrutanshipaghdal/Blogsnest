import os

# --- Database ---
DATABASE_URL = "sqlite:///./blogapp.db"

# --- JWT ---
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24  # 1 day

# --- OTP ---
OTP_EXPIRE_MINUTES = 5
OTP_LENGTH = 6

# --- RabbitMQ ---
# Set USE_RABBITMQ=false (env var) to skip RabbitMQ entirely - useful while
# you're still installing Erlang/RabbitMQ. When off, notifications run
# directly (synchronously) instead of going through a queue + worker.
USE_RABBITMQ = os.getenv("USE_RABBITMQ", "true").lower() != "false"
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
QUEUE_OTP = "otp_requested"
QUEUE_BLOG_PUBLISHED = "blog_published"
QUEUE_USER_REGISTERED = "user_registered"
QUEUE_COMMENT_POSTED = "comment_posted"

# --- Real email (SMTP) ---
# Fill these in to send REAL emails instead of writing to sent_emails.log.
# Gmail example: SMTP_USER is your gmail address, SMTP_PASSWORD is a
# Gmail "App Password" (NOT your normal password) - generate one at
# https://myaccount.google.com/apppasswords (needs 2-Step Verification on).
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)