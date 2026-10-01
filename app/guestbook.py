"""방명록 라우터: 조회는 공개, 작성은 로그인 필요."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import require_user
from .database import get_db
from .events import broker
from .models import REACTION_TYPES, Comment, GuestbookEntry, Notification, Reaction, User
from .timeutils import to_kst


def _wants_json(request: Request) -> bool:
    """AJAX(fetch) 요청인지 판별."""
    return request.headers.get("x-requested-with") == "fetch" or (
        "application/json" in request.headers.get("accept", "")
    )


def _reaction_state(obj, user_id: int | None) -> dict:
    """반응 버튼 갱신용 상태 (집계/내 반응/참여자)."""
    return {
        "counts": obj.reaction_counts(),
        "my_reaction": obj.user_reaction(user_id),
        "reactors": obj.reactor_names(),
    }

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


@router.post("/entries/{entry_id}/edit")
def edit_entry(
    request: Request,
    entry_id: int,
    message: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """게시글 수정 (본인 글만)."""
    entry = db.get(GuestbookEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="방명록을 찾을 수 없습니다.")
    if entry.author_id != user.id:
        raise HTTPException(status_code=403, detail="본인 글만 수정할 수 있습니다.")
    text = message.strip()
    if text:
        entry.message = text
        db.commit()
        db.refresh(entry)
    if _wants_json(request):
        return JSONResponse({"id": entry.id, "message": entry.message})
    return RedirectResponse(url=f"/#entry-{entry_id}", status_code=status.HTTP_303_SEE_OTHER)


# 반응 타입 → 한글 라벨 (알림 메시지용)
REACTION_LABELS = {"like": "좋아요", "dislike": "싫어요", "thanks": "감사해요"}


def _notify_reaction(db, target_id, actor_name, label, entry_id, comment_id, where):
    """반응을 받은 글/댓글 작성자에게 알림 생성 (본인 제외, 새로 추가될 때만)."""
    db.add(
        Notification(
            user_id=target_id,
            kind="reaction",
            message=f"{actor_name}님이 회원님의 {where}에 '{label}' 반응을 남겼습니다.",
            entry_id=entry_id,
            comment_id=comment_id,
        )
    )


# ----- 글 반응 (좋아요/싫어요/감사해요) -----
@router.post("/entries/{entry_id}/react")
def react_entry(
    request: Request,
    entry_id: int,
    reaction_type: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """글 반응 토글 (로그인 필요). 새 반응이면 글 작성자에게 알림.

    AJAX 요청이면 JSON(집계/내 반응/참여자) 반환, 아니면 리다이렉트(JS 미사용 fallback).
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
    notify = False
    if existing is None:
        db.add(Reaction(user_id=user.id, entry_id=entry_id, reaction_type=reaction_type))
        notify = True
    elif existing.reaction_type == reaction_type:
        db.delete(existing)  # 같은 반응 재클릭 → 취소 (알림 없음)
    else:
        existing.reaction_type = reaction_type  # 변경 → 알림
        notify = True

    if notify and entry.author_id != user.id:
        _notify_reaction(
            db, entry.author_id, user.shown_name,
            REACTION_LABELS.get(reaction_type, reaction_type),
            entry_id, None, "글",
        )
    db.commit()
    db.refresh(entry)
    if _wants_json(request):
        return JSONResponse(_reaction_state(entry, user.id))
    return RedirectResponse(url=f"/#entry-{entry_id}", status_code=status.HTTP_303_SEE_OTHER)


# ----- 댓글/대댓글 반응 -----
@router.post("/comments/{comment_id}/react")
def react_comment(
    request: Request,
    comment_id: int,
    reaction_type: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """댓글/대댓글 반응 토글 (로그인 필요). 새 반응이면 댓글 작성자에게 알림.

    AJAX 요청이면 JSON 반환, 아니면 리다이렉트(fallback).
    """
    if reaction_type not in REACTION_TYPES:
        raise HTTPException(status_code=400, detail="알 수 없는 반응 타입입니다.")

    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")

    existing = db.scalar(
        select(Reaction).where(
            Reaction.user_id == user.id, Reaction.comment_id == comment_id
        )
    )
    notify = False
    if existing is None:
        db.add(Reaction(user_id=user.id, comment_id=comment_id, reaction_type=reaction_type))
        notify = True
    elif existing.reaction_type == reaction_type:
        db.delete(existing)
    else:
        existing.reaction_type = reaction_type
        notify = True

    if notify and comment.author_id != user.id:
        _notify_reaction(
            db, comment.author_id, user.shown_name,
            REACTION_LABELS.get(reaction_type, reaction_type),
            comment.entry_id, comment_id, "댓글",
        )
    db.commit()
    db.refresh(comment)
    if _wants_json(request):
        return JSONResponse(_reaction_state(comment, user.id))
    return RedirectResponse(
        url=f"/#comment-{comment_id}", status_code=status.HTTP_303_SEE_OTHER
    )


# ----- 댓글 / 대댓글 -----
@router.post("/entries/{entry_id}/comments")
async def create_comment(
    request: Request,
    entry_id: int,
    message: str = Form(...),
    parent_id: int | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """댓글/대댓글 작성 (로그인 필요).

    - parent_id가 없으면 최상위 댓글 → 글 작성자에게 알림
    - parent_id가 있으면 대댓글 → 원 댓글 작성자에게 알림
    - 본인에게는 알림을 보내지 않음
    - SSE로 실시간 이벤트 브로드캐스트
    """
    entry = db.get(GuestbookEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="방명록을 찾을 수 없습니다.")

    parent = None
    if parent_id is not None:
        parent = db.get(Comment, parent_id)
        if parent is None or parent.entry_id != entry_id:
            raise HTTPException(status_code=400, detail="원 댓글을 찾을 수 없습니다.")
        # 대댓글의 대댓글은 최상위 댓글에 묶음 (1단계 깊이 유지)
        if parent.parent_id is not None:
            parent = db.get(Comment, parent.parent_id)

    text = message.strip()
    if not text:
        if _wants_json(request):
            return JSONResponse({"error": "empty"}, status_code=400)
        return RedirectResponse(
            url=f"/#entry-{entry_id}", status_code=status.HTTP_303_SEE_OTHER
        )

    comment = Comment(
        message=text,
        author_id=user.id,
        entry_id=entry_id,
        parent_id=parent.id if parent else None,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    author_name = user.shown_name

    # 알림 대상 결정
    if parent is not None:
        # 대댓글 → 원 댓글 작성자에게
        target_id = parent.author_id
        notif_msg = f"{author_name}님이 회원님의 댓글에 답글을 남겼습니다: {text[:40]}"
    else:
        # 최상위 댓글 → 글 작성자에게
        target_id = entry.author_id
        notif_msg = f"{author_name}님이 회원님의 글에 댓글을 남겼습니다: {text[:40]}"

    if target_id != user.id:
        db.add(
            Notification(
                user_id=target_id,
                kind="reply" if parent else "comment",
                message=notif_msg,
                entry_id=entry_id,
                comment_id=comment.id,
            )
        )
        db.commit()

    # 실시간 브로드캐스트
    payload = {
        "type": "comment",
        "entry_id": entry_id,
        "comment_id": comment.id,
        "parent_id": parent.id if parent else None,
        "author": author_name,
        "author_image": user.profile_image,
        "message": text,
        "created_at": to_kst(comment.created_at),
        "target_user_id": target_id if target_id != user.id else None,
    }
    await broker.publish(payload)

    if _wants_json(request):
        # 작성자 본인 화면에서 바로 삽입할 수 있도록 데이터 반환
        data = dict(payload)
        data["is_mine"] = True
        data["author_id"] = user.id
        return JSONResponse(data)
    return RedirectResponse(url=f"/#entry-{entry_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/comments/{comment_id}/edit")
def edit_comment(
    request: Request,
    comment_id: int,
    message: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """댓글/대댓글 수정 (본인만)."""
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    if comment.author_id != user.id:
        raise HTTPException(status_code=403, detail="본인 댓글만 수정할 수 있습니다.")
    text = message.strip()
    if text:
        comment.message = text
        db.commit()
        db.refresh(comment)
    if _wants_json(request):
        return JSONResponse({"id": comment.id, "message": comment.message})
    return RedirectResponse(
        url=f"/#comment-{comment_id}", status_code=status.HTTP_303_SEE_OTHER
    )


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
