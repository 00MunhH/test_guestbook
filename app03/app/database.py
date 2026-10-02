"""SQLAlchemy 엔진/세션 및 Base 정의 — app03: 스키마는 Alembic으로 관리."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

# SQLite일 때만 단일 스레드 체크 해제 (로컬 개발 편의)
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
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
    """스키마 준비.

    - 운영(PostgreSQL): 스키마는 **Alembic 마이그레이션**으로 관리한다
      (`alembic upgrade head`). 여기서는 아무것도 하지 않는다.
    - 로컬 개발(SQLite): 편의를 위해 모델 기준으로 테이블을 생성한다.
    """
    from . import models  # noqa: F401

    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
