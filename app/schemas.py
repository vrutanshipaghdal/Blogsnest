from pydantic import BaseModel, EmailStr
from datetime import datetime


class RequestOTP(BaseModel):
    email: EmailStr


class VerifyOTP(BaseModel):
    email: EmailStr
    otp_code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class BlogCreate(BaseModel):
    title: str
    content: str


class BlogUpdate(BaseModel):
    title: str
    content: str


class BlogOut(BaseModel):
    id: int
    title: str
    content: str
    owner_id: int
    owner_email: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True