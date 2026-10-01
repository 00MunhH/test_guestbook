"""내 정보 관리 및 관리자 페이지 라우터."""
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_admin, require_user
from .database import get_db
from .models import Notification, User


def unread_count(db: Session, user: User | None) -> int:
    """현재 사용자의 안 읽은 알림 개수 (미로그인 시 0)."""
    if user is None:
        return 0
    return db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read.is_(False)
    ).count()

router = APIRouter(tags=["account"])

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ----- 내 정보 -----
@router.get("/me", response_class=HTMLResponse)
def my_profile(
    request: Request,
    saved: int = 0,
    user: User = Depends(require_user),
) -> HTMLResponse:
    """내 정보 조회/수정 페이지 (로그인 필요)."""
    return templates.TemplateResponse(
        request, "me.html", {"user": user, "saved": bool(saved)}
    )


@router.post("/me")
def update_my_profile(
    display_name: str = Form(""),
    bio: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """내 정보 등록/변경 (로그인 필요)."""
    user.display_name = display_name.strip()[:128]
    user.bio = bio.strip()
    db.commit()
    return RedirectResponse(url="/me?saved=1", status_code=status.HTTP_303_SEE_OTHER)


# ----- 관리자 페이지 -----
@router.get("/admin", response_class=HTMLResponse)
def admin_members(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> HTMLResponse:
    """회원 목록 관리 페이지 (관리자 전용)."""
    members = list(db.scalars(select(User).order_by(User.created_at)).all())
    return templates.TemplateResponse(
        request,
        "admin.html",
        {"user": admin, "members": members},
    )


@router.post("/admin/members/{member_id}/role")
def set_admin_role(
    member_id: int,
    make_admin: str = Form(...),  # "1" 또는 "0"
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> RedirectResponse:
    """회원의 관리자 권한 부여/해제 (관리자 전용)."""
    member = db.get(User, member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")

    grant = make_admin == "1"
    # 본인 권한 해제 방지 (마지막 관리자 보호 + 실수 방지)
    if not grant and member.id == admin.id:
        raise HTTPException(status_code=400, detail="본인의 관리자 권한은 해제할 수 없습니다.")

    member.is_admin = grant
    db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/members/{member_id}/delete")
def delete_member(
    member_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> RedirectResponse:
    """회원 삭제 (관리자 전용). 해당 회원의 방명록/댓글/반응도 함께 삭제."""
    member = db.get(User, member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")
    if member.id == admin.id:
        raise HTTPException(status_code=400, detail="본인 계정은 삭제할 수 없습니다.")

    # 해당 회원이 남긴 반응/댓글 수동 정리 (글은 User.entries cascade로 삭제)
    from .models import Comment, Reaction

    db.query(Reaction).filter(Reaction.user_id == member.id).delete()
    db.query(Comment).filter(Comment.author_id == member.id).delete()
    db.delete(member)  # entries는 User-GuestbookEntry cascade로 삭제
    db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


# ----- 알림 -----
@router.get("/notifications", response_class=HTMLResponse)
def notifications_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> HTMLResponse:
    """내 알림 목록 (로그인 필요). 조회 시 모두 읽음 처리."""
    items = list(
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
        .all()
    )
    # 조회 시 읽음 처리
    db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read.is_(False)
    ).update({Notification.is_read: True})
    db.commit()
    return templates.TemplateResponse(
        request, "notifications.html", {"user": user, "items": items}
    )


@router.get("/api/notifications/unread_count")
def api_unread_count(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> dict:
    """안 읽은 알림 개수 (실시간 뱃지 갱신용)."""
    return {"count": unread_count(db, user)}
