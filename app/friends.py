"""사이 맺기(친구) 라우터: 요청/수락/거절/삭제, 관계 라벨 지정."""
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .auth import require_user
from .database import get_db
from .models import Friendship, User
from .timeutils import to_kst

router = APIRouter(tags=["friends"])

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["kst"] = to_kst


def accepted_friend_ids(db: Session, user_id: int) -> set[int]:
    """수락된 친구들의 user_id 집합."""
    rows = db.scalars(
        select(Friendship).where(
            Friendship.status == "accepted",
            or_(
                Friendship.requester_id == user_id,
                Friendship.addressee_id == user_id,
            ),
        )
    ).all()
    ids: set[int] = set()
    for f in rows:
        ids.add(f.addressee_id if f.requester_id == user_id else f.requester_id)
    return ids


@router.get("/friends", response_class=HTMLResponse)
def friends_page(
    request: Request,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> HTMLResponse:
    """친구 목록 + 받은/보낸 요청 + 사용자 검색."""
    all_links = db.scalars(
        select(Friendship).where(
            or_(
                Friendship.requester_id == user.id,
                Friendship.addressee_id == user.id,
            )
        )
    ).all()

    friends = []  # (friendship, 상대 User)
    incoming = []  # 받은 요청
    outgoing = []  # 보낸 요청
    related_ids = {user.id}
    for f in all_links:
        other_id = f.addressee_id if f.requester_id == user.id else f.requester_id
        related_ids.add(other_id)
        other = db.get(User, other_id)
        if f.status == "accepted":
            friends.append((f, other))
        elif f.requester_id == user.id:
            outgoing.append((f, other))
        else:
            incoming.append((f, other))

    # 사용자 검색 (닉네임/표시이름), 이미 관계 있는 사람과 본인 제외
    search_results = []
    if q and q.strip():
        term = f"%{q.strip()}%"
        candidates = db.scalars(
            select(User).where(
                or_(User.nickname.like(term), User.display_name.like(term))
            ).limit(20)
        ).all()
        search_results = [u for u in candidates if u.id not in related_ids]

    return templates.TemplateResponse(
        request,
        "friends.html",
        {
            "user": user,
            "friends": friends,
            "incoming": incoming,
            "outgoing": outgoing,
            "q": q or "",
            "search_results": search_results,
        },
    )


@router.post("/friends/request")
def send_request(
    addressee_id: int = Form(...),
    relation_label: str = Form("친구"),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """친구 요청 보내기."""
    if addressee_id == user.id:
        raise HTTPException(status_code=400, detail="자기 자신에게는 요청할 수 없습니다.")
    target = db.get(User, addressee_id)
    if target is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    # 이미 어떤 방향으로든 관계가 있으면 무시
    existing = db.scalar(
        select(Friendship).where(
            or_(
                (Friendship.requester_id == user.id)
                & (Friendship.addressee_id == addressee_id),
                (Friendship.requester_id == addressee_id)
                & (Friendship.addressee_id == user.id),
            )
        )
    )
    if existing is None:
        db.add(
            Friendship(
                requester_id=user.id,
                addressee_id=addressee_id,
                status="pending",
                relation_label=(relation_label.strip() or "친구")[:32],
            )
        )
        db.commit()
    return RedirectResponse(url="/friends", status_code=status.HTTP_303_SEE_OTHER)


def _get_link_for_user(db: Session, link_id: int, user_id: int) -> Friendship:
    link = db.get(Friendship, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="관계를 찾을 수 없습니다.")
    if user_id not in (link.requester_id, link.addressee_id):
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    return link


@router.post("/friends/{link_id}/accept")
def accept_request(
    link_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """받은 친구 요청 수락 (수신자만)."""
    link = _get_link_for_user(db, link_id, user.id)
    if link.addressee_id != user.id:
        raise HTTPException(status_code=403, detail="받은 요청만 수락할 수 있습니다.")
    link.status = "accepted"
    db.commit()
    return RedirectResponse(url="/friends", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/friends/{link_id}/delete")
def delete_link(
    link_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """친구 끊기 / 요청 거절 / 요청 취소 (양쪽 당사자 가능)."""
    link = _get_link_for_user(db, link_id, user.id)
    db.delete(link)
    db.commit()
    return RedirectResponse(url="/friends", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/friends/{link_id}/label")
def update_label(
    link_id: int,
    relation_label: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """관계 라벨 변경 (친구/동료/custom)."""
    link = _get_link_for_user(db, link_id, user.id)
    link.relation_label = (relation_label.strip() or "친구")[:32]
    db.commit()
    return RedirectResponse(url="/friends", status_code=status.HTTP_303_SEE_OTHER)
