"""방명록 라우터: 조회는 공개, 작성은 로그인 필요."""
from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import require_user
from .database import get_db
from .events import broker
from .models import REACTION_TYPES, Comment, GuestbookEntry, Notification, Reaction, User

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


@router.post("/entries/{entry_id}/delete")
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """방명록 글 삭제 (본인 글만 가능). 관련 반응/댓글도 함께 삭제된다."""
    entry = db.get(GuestbookEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="방명록을 찾을 수 없습니다.")
    if entry.author_id != user.id:
        raise HTTPException(status_code=403, detail="본인 글만 삭제할 수 있습니다.")
    db.delete(entry)  # cascade로 반응/댓글도 삭제
    db.commit()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


# ----- 반응 (좋아요/싫어요/감사해요) -----
@router.post("/entries/{entry_id}/react")
def react_entry(
    entry_id: int,
    reaction_type: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """반응 토글 (로그인 필요).

    - 같은 타입을 다시 누르면 취소
    - 다른 타입을 누르면 변경
    - 없으면 새로 추가
    사용자당 글마다 하나의 반응만 유지한다.
    """
    if reaction_type not in REACTION_TYPES:
        raise HTTPException(status_code=400, detail="알 수 없는 반응 타입입니다.")

    entry = db.get(GuestbookEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="방명록을 찾을 수 없습니다.")

    existing = db.scalar(
        select(Reaction).where(
            Reaction.user_id == user.id, Reaction.entry_id == entry_id
        )
    )
    if existing is None:
        db.add(Reaction(user_id=user.id, entry_id=entry_id, reaction_type=reaction_type))
    elif existing.reaction_type == reaction_type:
        db.delete(existing)  # 같은 반응 재클릭 → 취소
    else:
        existing.reaction_type = reaction_type  # 다른 반응 → 변경
    db.commit()
    return RedirectResponse(url=f"/#entry-{entry_id}", status_code=status.HTTP_303_SEE_OTHER)


# ----- 댓글 -----
@router.post("/entries/{entry_id}/comments")
async def create_comment(
    entry_id: int,
    message: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """댓글 작성 (로그인 필요).

    - 글 작성자(본인 제외)에게 인앱 알림 생성
    - SSE로 실시간 댓글 이벤트 브로드캐스트
    """
    entry = db.get(GuestbookEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="방명록을 찾을 수 없습니다.")
    text = message.strip()
    if text:
        comment = Comment(message=text, author_id=user.id, entry_id=entry_id)
        db.add(comment)
        db.commit()
        db.refresh(comment)

        author_name = user.shown_name

        # 글 작성자에게 알림 (본인 댓글은 제외)
        if entry.author_id != user.id:
            db.add(
                Notification(
                    user_id=entry.author_id,
                    kind="comment",
                    message=f"{author_name}님이 회원님의 글에 댓글을 남겼습니다: {text[:40]}",
                    entry_id=entry_id,
                    comment_id=comment.id,
                )
            )
            db.commit()

        # 실시간 브로드캐스트 (같은 글을 보고 있는 모든 사용자에게)
        await broker.publish(
            {
                "type": "comment",
                "entry_id": entry_id,
                "comment_id": comment.id,
                "author": author_name,
                "author_image": user.profile_image,
                "message": text,
                "created_at": comment.created_at.strftime("%Y-%m-%d %H:%M"),
                "target_user_id": entry.author_id if entry.author_id != user.id else None,
            }
        )
    return RedirectResponse(url=f"/#entry-{entry_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/comments/{comment_id}/delete")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """댓글 삭제 (본인 댓글만 가능)."""
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    if comment.author_id != user.id:
        raise HTTPException(status_code=403, detail="본인 댓글만 삭제할 수 있습니다.")
    entry_id = comment.entry_id
    db.delete(comment)
    db.commit()
    return RedirectResponse(url=f"/#entry-{entry_id}", status_code=status.HTTP_303_SEE_OTHER)
