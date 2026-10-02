"""애플리케이션 설정 로딩 (.env 기반) — app03: RDS(Postgres) + S3 + Redis."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수/`.env`에서 읽어오는 설정 값."""

    # 카카오 OAuth
    kakao_rest_api_key: str
    kakao_client_secret: str = ""
    kakao_redirect_uri: str = "http://localhost:8000/auth/kakao/callback"

    # 세션 서명 키
    session_secret_key: str = "change-me-to-a-long-random-secret"

    # 데이터베이스: 운영은 RDS PostgreSQL. 로컬 개발은 sqlite 로도 가능.
    #   예) postgresql+psycopg://user:pass@host:5432/guestbook
    database_url: str = "postgresql+psycopg://guestbook:guestbook@localhost:5432/guestbook"

    # 최초 관리자 카카오 ID (쉼표 구분)
    admin_kakao_ids: str = ""

    # 기본 관리자 계정
    admin_username: str = ""
    admin_password: str = ""

    # 파일 업로드: S3
    s3_bucket: str = ""
    aws_region: str = "ap-northeast-2"
    # 로컬 테스트용 S3 호환 엔드포인트(MinIO 등). 비우면 실제 AWS S3 사용.
    s3_endpoint_url: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # 실시간(SSE) 브로커: Redis
    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def admin_kakao_id_set(self) -> set[str]:
        return {x.strip() for x in self.admin_kakao_ids.split(",") if x.strip()}


settings = Settings()
