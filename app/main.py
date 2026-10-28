from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import HTTPException
from fastapi.templating import Jinja2Templates

from app.database import Base, engine, SessionLocal
from app.auth.otp_utils import migrate_plaintext_otps
from app.auth.routes import router as auth_router
from app.blogs.routes import router as blog_router

Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    migrate_plaintext_otps(db)
finally:
    db.close()

app = FastAPI(title="BlogsNest")
templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth_router)
app.include_router(blog_router)

@app.get("/")
def root():
    return RedirectResponse(url="/blogs")

@app.exception_handler(HTTPException)
async def auth_redirect_handler(request: Request, exc: HTTPException):
    # not logged in and hit a protected page -> send to login instead of raw 401 JSON
    if exc.status_code == 401:
        return RedirectResponse(url="/login")
    return await http_exception_default(request, exc)

from fastapi.exception_handlers import http_exception_handler as http_exception_default