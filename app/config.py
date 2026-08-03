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