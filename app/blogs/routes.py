from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Blog, User, Comment, Like
from app.auth.jwt_utils import get_current_user, get_current_user_optional
from app.rabbitmq.publisher import publish_blog_published, publish_comment_posted

router = APIRouter()
templates = Jinja2Templates(directory="templates")
from app.template_filters import to_ist
templates.env.filters["to_ist"] = to_ist


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_blogs = db.query(Blog).count()
    total_users = db.query(User).count()
    my_blogs = db.query(Blog).filter(Blog.owner_id == current_user.id).order_by(Blog.created_at.desc()).all()
    recent_blogs = db.query(Blog).order_by(Blog.created_at.desc()).limit(5).all()

    return templates.TemplateResponse(
        request, "dashboard.html",
        {
            "current_user": current_user,
            "total_blogs": total_blogs,
            "total_users": total_users,
            "my_blogs": my_blogs,
            "my_blog_count": len(my_blogs),
            "recent_blogs": recent_blogs,
        },
    )


@router.get("/blogs", response_class=HTMLResponse)
def list_blogs(
    request: Request,
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    query = db.query(Blog)
    if q:
        like = f"%{q}%"
        query = query.filter((Blog.title.ilike(like)) | (Blog.content.ilike(like)))
    blogs = query.order_by(Blog.created_at.desc()).all()
    return templates.TemplateResponse(
        request, "blogs.html",
        {"blogs": blogs, "current_user": current_user, "q": q or ""},
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

    comments = db.query(Comment).filter(Comment.blog_id == blog_id).order_by(Comment.created_at.asc()).all()

    # Calculate likes count & check if current user liked it
    like_count = db.query(Like).filter(Like.blog_id == blog_id).count()
    is_liked = False
    if current_user:
        is_liked = db.query(Like).filter(Like.blog_id == blog_id, Like.user_id == current_user.id).first() is not None

    return templates.TemplateResponse(
        request, "blog.html",
        {
            "blog": blog,
            "current_user": current_user,
            "mode": "view",
            "comments": comments,
            "like_count": like_count,
            "is_liked": is_liked,
        },
    )


@router.post("/blogs/{blog_id}/like")
def toggle_like(
    blog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    blog = db.query(Blog).filter(Blog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")

    existing_like = db.query(Like).filter(Like.blog_id == blog_id, Like.user_id == current_user.id).first()

    if existing_like:
        db.delete(existing_like)
    else:
        new_like = Like(blog_id=blog_id, user_id=current_user.id)
        db.add(new_like)

    db.commit()
    return RedirectResponse(url=f"/blogs/{blog_id}", status_code=303)


@router.post("/blogs/{blog_id}/comment")
def add_comment(
    blog_id: int,
    content: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    blog = db.query(Blog).filter(Blog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")

    comment = Comment(content=content, blog_id=blog_id, user_id=current_user.id)
    db.add(comment)
    db.commit()

    publish_comment_posted(
        blog_id, blog.title, blog.owner.email, current_user.name or current_user.email
    )

    return RedirectResponse(url=f"/blogs/{blog_id}#comments", status_code=303)


@router.post("/blogs/{blog_id}/comment/{comment_id}/delete")
def delete_comment(
    blog_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = db.query(Comment).filter(Comment.id == comment_id, Comment.blog_id == blog_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    blog = db.query(Blog).filter(Blog.id == blog_id).first()

    # comment author OR the blog owner can remove a comment
    if comment.user_id != current_user.id and blog.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed to delete this comment")

    db.delete(comment)
    db.commit()
    return RedirectResponse(url=f"/blogs/{blog_id}#comments", status_code=303)


@router.post("/blogs/{blog_id}/delete")
def delete_blog(
    blog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    blog = db.query(Blog).filter(Blog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    if blog.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own blogs")

    db.delete(blog)
    db.commit()
    return RedirectResponse(url="/blogs", status_code=303)


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
        raise HTTPException(status_code=403, detail="You can only edit your own blogs")

    blog.title = title
    blog.content = content
    db.commit()

    return RedirectResponse(url=f"/blogs/{blog_id}", status_code=303)