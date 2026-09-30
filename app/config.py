"""애플리케이션 설정 로딩 (.env 기반)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수/`.env`에서 읽어오는 설정 값."""

    # 카카오 OAuth
    kakao_rest_api_key: str
    kakao_client_secret: str = ""  # 카카오 앱에서 client_secret 미사용 시 빈 값
    kakao_redirect_uri: str = "http://localhost:8000/auth/kakao/callback"

    # 세션 서명 키
    session_secret_key: str = "change-me-to-a-long-random-secret"

    # 데이터베이스
    database_url: str = "sqlite:///./guestbook.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
