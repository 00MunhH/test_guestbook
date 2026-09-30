"""SQLAlchemy 엔진/세션 및 Base 정의."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

# SQLite는 기본적으로 단일 스레드 체크를 하므로 FastAPI에서 사용하려면 옵션 해제
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """모든 ORM 모델의 기반 클래스."""


def get_db() -> Generator[Session, None, None]:
    """요청 단위 DB 세션 의존성."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """테이블 생성 (앱 시작 시 호출)."""
    # 모델이 Base에 등록되도록 import
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
