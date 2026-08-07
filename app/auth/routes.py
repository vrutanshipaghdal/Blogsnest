from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.models import User
from app.auth.otp_utils import create_otp, verify_otp
from app.auth.jwt_utils import create_access_token, get_current_user
from app.config import JWT_EXPIRE_MINUTES
from app.rabbitmq.publisher import publish_otp_requested, publish_user_registered

router = APIRouter()
templates = Jinja2Templates(directory="templates")
from app.template_filters import to_ist
templates.env.filters["to_ist"] = to_ist


# ---------- SIGN UP (new account: name + email + optional dob/gender) ----------

@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse(request, "auth.html", {"stage": "signup"})


@router.post("/auth/register")
def register(
    name: str = Form(...),
    email: str = Form(...),
    date_of_birth: str = Form(""),
    gender: str = Form(""),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return RedirectResponse(url=f"/login?msg=account_exists&email={email}", status_code=303)

    user = User(
        name=name,
        email=email,
        date_of_birth=date.fromisoformat(date_of_birth) if date_of_birth else None,
        gender=gender or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # distinct "user_registered" event -> worker sends a welcome email + writes audit log
    publish_user_registered(user.id, name, email)

    # also kick off an OTP straight away so they can verify + log in immediately
    otp = create_otp(db, email, purpose="signup")
    publish_otp_requested(email, otp.otp_code, "signup")

    return RedirectResponse(url=f"/verify?email={email}&purpose=signup", status_code=303)


# ---------- LOGIN (existing account, email only) ----------

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, msg: str | None = None, email: str | None = None):
    return templates.TemplateResponse(request, "auth.html", {"stage": "login", "msg": msg, "email": email})


@router.post("/auth/request-otp")
def request_otp(email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return RedirectResponse(url=f"/signup?msg=no_account&email={email}", status_code=303)

    otp = create_otp(db, email, purpose="login")
    publish_otp_requested(email, otp.otp_code, "login")

    return RedirectResponse(url=f"/verify?email={email}&purpose=login", status_code=303)

# ---------- OTP VERIFY (shared by both flows) ----------

@router.get("/verify", response_class=HTMLResponse)
def verify_page(request: Request, email: str, purpose: str = "login"):
    return templates.TemplateResponse(request, "auth.html", {"stage": "verify", "email": email, "purpose": purpose})


@router.post("/auth/verify-otp")
def verify_otp_route(
    email: str = Form(...),
    otp_code: str = Form(...),
    purpose: str = Form("login"),
    db: Session = Depends(get_db),
):
    if not verify_otp(db, email, otp_code, purpose=purpose):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    user = db.query(User).filter(User.email == email).first()
    user.is_verified = True
    db.commit()

    if purpose == "signup":
        # account created + verified, but don't auto-login -> send them to
        # the login page to sign in properly, like a normal signup flow
        return RedirectResponse(url=f"/login?msg=verified&email={email}", status_code=303)

    # login flow -> actually log them in
    token = create_access_token(user.id, user.email)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=JWT_EXPIRE_MINUTES * 60,
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response


# ---------- PROFILE (view + update) ----------

@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, current_user: User = Depends(get_current_user), msg: str | None = None):
    return templates.TemplateResponse(
        request, "profile.html", {"current_user": current_user, "msg": msg}
    )


@router.post("/profile/update")
def update_profile(
    name: str = Form(...),
    date_of_birth: str = Form(""),
    gender: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.name = name
    current_user.date_of_birth = date.fromisoformat(date_of_birth) if date_of_birth else None
    current_user.gender = gender or None
    db.commit()
    return RedirectResponse(url="/profile?msg=updated", status_code=303)