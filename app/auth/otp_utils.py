import random
import string
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models import OTP
from app.config import OTP_EXPIRE_MINUTES, OTP_LENGTH


def generate_otp_code() -> str:
    return "".join(random.choices(string.digits, k=OTP_LENGTH))


def create_otp(db: Session, email: str, purpose: str = "login") -> OTP:
    """Invalidate any older unused OTPs for this email+purpose, then create a fresh one."""
    db.query(OTP).filter(
        OTP.email == email, OTP.purpose == purpose, OTP.is_used == False
    ).update({"is_used": True})

    otp = OTP(
        email=email,
        otp_code=generate_otp_code(),
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
    )
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return otp


def verify_otp(db: Session, email: str, otp_code: str, purpose: str = "login") -> bool:
    otp = (
        db.query(OTP)
        .filter(
            OTP.email == email,
            OTP.otp_code == otp_code,
            OTP.purpose == purpose,
            OTP.is_used == False,
        )
        .order_by(OTP.created_at.desc())
        .first()
    )

    if not otp:
        return False

    expires_at = otp.expires_at
    if expires_at.tzinfo is not None:
        now = datetime.now(timezone.utc)
    else:
        now = datetime.utcnow()

    if expires_at < now:
        return False

    otp.is_used = True
    db.commit()
    return True