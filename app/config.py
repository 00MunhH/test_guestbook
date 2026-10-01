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

    # 최초 관리자로 부트스트랩할 카카오 ID 목록 (쉼표 구분)
    admin_kakao_ids: str = ""

    # 카카오와 무관한 기본 관리자 계정 (ID/비밀번호 로그인)
    admin_username: str = ""
    admin_password: str = ""

    # 채팅 파일 업로드 저장 디렉터리
    upload_dir: str = "./uploads"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def admin_kakao_id_set(self) -> set[str]:
        """ADMIN_KAKAO_IDS를 파싱한 집합."""
        return {x.strip() for x in self.admin_kakao_ids.split(",") if x.strip()}


settings = Settings()
