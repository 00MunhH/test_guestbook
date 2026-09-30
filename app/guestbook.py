"""방명록 라우터: 조회는 공개, 작성은 로그인 필요."""
from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import require_user
from .database import get_db
from .models import GuestbookEntry, User

router = APIRouter(tags=["guestbook"])


# ----- 응답 스키마 -----
class AuthorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    profile_image: str


class EntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message: str
    created_at: object
    author: AuthorOut


# ----- JSON API -----
@router.get("/api/entries", response_model=list[EntryOut])
def list_entries(db: Session = Depends(get_db)) -> list[GuestbookEntry]:
    """방명록 전체 조회 (누구나 가능)."""
    stmt = select(GuestbookEntry).order_by(GuestbookEntry.created_at.desc())
    return list(db.scalars(stmt).all())


@router.get("/api/entries/{entry_id}", response_model=EntryOut)
def get_entry(entry_id: int, db: Session = Depends(get_db)) -> GuestbookEntry:
    """방명록 단건 조회 (누구나 가능)."""
    entry = db.get(GuestbookEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="방명록을 찾을 수 없습니다.")
    return entry


@router.post("/api/entries", response_model=EntryOut, status_code=201)
def create_entry_api(
    message: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> GuestbookEntry:
    """방명록 작성 (로그인 필요)."""
    text = message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="내용을 입력해주세요.")
    entry = GuestbookEntry(message=text, author_id=user.id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ----- 폼 제출 (HTML 페이지에서 사용) -----
@router.post("/entries")
def create_entry_form(
    message: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """HTML 폼에서 방명록 작성 후 홈으로 리다이렉트 (로그인 필요)."""
    text = message.strip()
    if text:
        entry = GuestbookEntry(message=text, author_id=user.id)
        db.add(entry)
        db.commit()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
