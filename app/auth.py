"""카카오 OAuth 2.0 로그인 라우터 및 인증 유틸리티."""
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

router = APIRouter(prefix="/auth", tags=["auth"])

KAKAO_AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"


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
    user = db.scalar(select(User).where(User.kakao_id == kakao_id))
    if user is None:
        user = User(
            kakao_id=kakao_id,
            nickname=nickname,
            profile_image=profile_image,
        )
        db.add(user)
    else:
        user.nickname = nickname
        user.profile_image = profile_image
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
