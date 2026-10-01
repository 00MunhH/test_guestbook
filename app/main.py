"""FastAPI 진입점: 미들웨어, 라우터, 홈 페이지 구성."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from . import account, auth, events, guestbook
from .account import unread_count
from .auth import get_current_user
from .config import settings
from .database import get_db, init_db
from .models import GuestbookEntry, User

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 테이블 생성/자동 마이그레이션 + 기본 관리자 보장
    init_db()
    auth.ensure_local_admin()
    yield


app = FastAPI(title="카카오 로그인 방명록", lifespan=lifespan)

# 세션 미들웨어 (request.session 사용)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)

# 라우터 등록
app.include_router(auth.router)
app.include_router(guestbook.router)
app.include_router(account.router)
app.include_router(events.router)


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    """홈: 방명록 목록 + 작성 폼(로그인 시)."""
    stmt = select(GuestbookEntry).order_by(GuestbookEntry.created_at.desc())
    entries = list(db.scalars(stmt).all())
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "entries": entries,
            "user": user,
            "unread": unread_count(db, user),
            "current_user_id": user.id if user else None,
        },
    )
