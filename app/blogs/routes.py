from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Blog, User
from app.auth.jwt_utils import get_current_user, get_current_user_optional
from app.rabbitmq.publisher import publish_blog_published

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/blogs", response_class=HTMLResponse)
def list_blogs(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    # everyone can see everyone's blogs - no ownership filter here
    blogs = db.query(Blog).order_by(Blog.created_at.desc()).all()
    return templates.TemplateResponse(
        request, "blogs.html",
        {"blogs": blogs, "current_user": current_user},
    )


@router.get("/blogs/new", response_class=HTMLResponse)
def new_blog_page(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        request, "blog.html",
        {"current_user": current_user, "blog": None, "mode": "new"},
    )


@router.post("/blogs/new")
def create_blog(
    title: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    blog = Blog(title=title, content=content, owner_id=current_user.id)
    db.add(blog)
    db.commit()
    db.refresh(blog)

    # fire-and-forget event: API returns immediately, worker handles audit log/notify/etc.
    publish_blog_published(blog.id, blog.title, current_user.email)

    return RedirectResponse(url="/blogs", status_code=303)


@router.get("/blogs/{blog_id}", response_class=HTMLResponse)
def view_blog(
    blog_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    blog = db.query(Blog).filter(Blog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    return templates.TemplateResponse(
        request, "blog.html",
        {"blog": blog, "current_user": current_user, "mode": "view"},
    )


@router.get("/blogs/{blog_id}/edit", response_class=HTMLResponse)
def edit_blog_page(
    blog_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    blog = db.query(Blog).filter(Blog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    if blog.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own blogs")

    return templates.TemplateResponse(
        request, "blog.html",
        {"current_user": current_user, "blog": blog, "mode": "edit"},
    )


@router.post("/blogs/{blog_id}/edit")
def update_blog(
    blog_id: int,
    title: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    blog = db.query(Blog).filter(Blog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    if blog.owner_id != current_user.id:
        # <-- this is the "update only if he added it" rule from the spec
        raise HTTPException(status_code=403, detail="You can only edit your own blogs")

    blog.title = title
    blog.content = content
    db.commit()

    return RedirectResponse(url=f"/blogs/{blog_id}", status_code=303)