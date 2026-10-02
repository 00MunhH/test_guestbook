"""카카오 OAuth 2.0 로그인 라우터 및 인증 유틸리티."""
import secrets
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

router = APIRouter(prefix="/auth", tags=["auth"])

_BASE_DIR = Path(__file__).resolve().parent
_admin_templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))

KAKAO_AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"

# 카카오와 무관한 로컬 관리자 계정의 kakao_id 접두사
LOCAL_ADMIN_PREFIX = "local:"


def ensure_local_admin() -> None:
    """.env의 ADMIN_USERNAME/PASSWORD로 기본 관리자 계정을 DB에 보장한다.

    앱 시작 시 호출. 계정이 없으면 생성하고, 있으면 관리자 플래그를 유지한다.
    카카오 로그인 없이 /admin/login으로 접속하기 위한 계정이다.
    """
    from .database import SessionLocal

    username = settings.admin_username.strip()
    if not username:
        return

    kakao_id = f"{LOCAL_ADMIN_PREFIX}{username}"
    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.kakao_id == kakao_id))
        if admin is None:
            admin = User(
                kakao_id=kakao_id,
                nickname=username,
                display_name=username,
                is_admin=True,
            )
            db.add(admin)
        else:
            admin.is_admin = True  # 기본 관리자는 항상 관리자 유지
        db.commit()
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """세션에 저장된 user_id로 현재 로그인 사용자를 조회. 없으면 None."""
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return db.get(User, user_id)


def require_user(
    user: User | None = Depends(get_current_user),
) -> User:
    """로그인 필수 의존성. 미로그인 시 401."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다.",
        )
    return user


def require_admin(
    user: User = Depends(require_user),
) -> User:
    """관리자 필수 의존성. 비관리자 시 403."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )
    return user


@router.get("/kakao/login")
def kakao_login(request: Request) -> RedirectResponse:
    """카카오 인가 코드 요청 페이지로 리다이렉트."""
    # CSRF 방지를 위한 state 값
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state

    params = {
        "response_type": "code",
        "client_id": settings.kakao_rest_api_key,
        "redirect_uri": settings.kakao_redirect_uri,
        "state": state,
    }
    return RedirectResponse(url=f"{KAKAO_AUTHORIZE_URL}?{urlencode(params)}")


@router.get("/kakao/callback")
async def kakao_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """카카오 콜백: 인가 코드로 토큰 교환 후 사용자 정보를 세션에 저장."""
    if error:
        raise HTTPException(status_code=400, detail=f"카카오 인증 오류: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="인가 코드가 없습니다.")

    # state 검증 (CSRF 방지)
    saved_state = request.session.pop("oauth_state", None)
    if not state or state != saved_state:
        raise HTTPException(status_code=400, detail="유효하지 않은 state 값입니다.")

    # 1) 인가 코드로 액세스 토큰 발급
    token_data = {
        "grant_type": "authorization_code",
        "client_id": settings.kakao_rest_api_key,
        "redirect_uri": settings.kakao_redirect_uri,
        "code": code,
    }
    if settings.kakao_client_secret:
        token_data["client_secret"] = settings.kakao_client_secret

    async with httpx.AsyncClient(timeout=10) as client:
        token_res = await client.post(
            KAKAO_TOKEN_URL,
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_res.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"토큰 발급 실패: {token_res.text}",
            )
        access_token = token_res.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="액세스 토큰이 없습니다.")

        # 2) 액세스 토큰으로 사용자 정보 조회
        userinfo_res = await client.get(
            KAKAO_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_res.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"사용자 정보 조회 실패: {userinfo_res.text}",
            )
        info = userinfo_res.json()

    kakao_id = str(info.get("id"))
    profile = (info.get("kakao_account") or {}).get("profile") or {}
    nickname = profile.get("nickname") or f"사용자{kakao_id[-4:]}"
    profile_image = profile.get("profile_image_url") or ""

    # 3) 사용자 upsert
    is_bootstrap_admin = kakao_id in settings.admin_kakao_id_set
    user = db.scalar(select(User).where(User.kakao_id == kakao_id))
    if user is None:
        user = User(
            kakao_id=kakao_id,
            nickname=nickname,
            profile_image=profile_image,
            is_admin=is_bootstrap_admin,
        )
        db.add(user)
    else:
        user.nickname = nickname
        user.profile_image = profile_image
        # .env에 지정된 관리자는 로그인 시 자동 승격 (강등은 하지 않음)
        if is_bootstrap_admin:
            user.is_admin = True
    db.commit()
    db.refresh(user)

    # 4) 세션에 로그인 상태 저장
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
def logout(request: Request) -> RedirectResponse:
    """세션 로그아웃."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


# ----- 기본 관리자(ID/PW) 로그인: 카카오 무관 -----
@router.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request, error: str | None = None) -> HTMLResponse:
    """관리자 로컬 로그인 페이지."""
    enabled = bool(settings.admin_username and settings.admin_password)
    return _admin_templates.TemplateResponse(
        request,
        "admin_login.html",
        {"enabled": enabled, "error": error},
    )


@router.post("/admin/login")
def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """ID/비밀번호로 기본 관리자 로그인 (카카오 무관)."""
    cfg_user = settings.admin_username.strip()
    cfg_pw = settings.admin_password

    ok = bool(cfg_user) and bool(cfg_pw)
    ok = ok and secrets.compare_digest(username.strip(), cfg_user)
    ok = ok and secrets.compare_digest(password, cfg_pw)
    if not ok:
        return RedirectResponse(
            url="/auth/admin/login?error=1", status_code=status.HTTP_303_SEE_OTHER
        )

    admin = db.scalar(
        select(User).where(User.kakao_id == f"{LOCAL_ADMIN_PREFIX}{cfg_user}")
    )
    if admin is None:
        # 혹시 부트스트랩이 안 되어 있으면 생성
        admin = User(
            kakao_id=f"{LOCAL_ADMIN_PREFIX}{cfg_user}",
            nickname=cfg_user,
            display_name=cfg_user,
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

    request.session["user_id"] = admin.id
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
