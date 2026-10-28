import hashlib
import hmac
import secrets
import string
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models import OTP
from app.config import OTP_EXPIRE_MINUTES, OTP_LENGTH

OTP_HASH_ITERATIONS = 200_000


def generate_otp_code() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(OTP_LENGTH))


def _hash_otp(otp_code: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", otp_code.encode(), bytes.fromhex(salt), OTP_HASH_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${OTP_HASH_ITERATIONS}${salt}${digest}"


def _verify_otp_hash(otp_code: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected_digest = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            otp_code.encode(),
            bytes.fromhex(salt),
            int(iterations),
        ).hex()
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(digest, expected_digest)


def migrate_plaintext_otps(db: Session) -> None:
    """Hash OTP values left in the database by versions before hashed storage."""
    legacy_otps = (
        db.query(OTP)
        .filter(~OTP.otp_code.startswith("pbkdf2_sha256$"))
        .all()
    )
    for otp in legacy_otps:
        otp.otp_code = _hash_otp(otp.otp_code)
    if legacy_otps:
        db.commit()


def create_otp(db: Session, email: str, purpose: str = "login") -> str:
    """Invalidate older OTPs, store a salted hash, and return the code for email delivery."""
    db.query(OTP).filter(
        OTP.email == email, OTP.purpose == purpose, OTP.is_used == False
    ).update({"is_used": True})

    otp_code = generate_otp_code()
    otp = OTP(
        email=email,
        otp_code=_hash_otp(otp_code),
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
    )
    db.add(otp)
    db.commit()
    return otp_code


def verify_otp(db: Session, email: str, otp_code: str, purpose: str = "login") -> bool:
    otp = (
        db.query(OTP)
        .filter(
            OTP.email == email,
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

    if not _verify_otp_hash(otp_code, otp.otp_code):
        return False

    otp.is_used = True
    db.commit()
    return True