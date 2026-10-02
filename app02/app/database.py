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
    """테이블 생성 + 간단한 자동 마이그레이션 (앱 시작 시 호출)."""
    # 모델이 Base에 등록되도록 import
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _auto_migrate()


def _auto_migrate() -> None:
    """모델에는 있으나 기존 테이블에 없는 컬럼을 자동으로 추가한다 (SQLite).

    버전 업그레이드 시 기존 DB에서 발생하는 'no such column' 오류를 방지한다.
    새 컬럼은 NOT NULL + 기본값으로 추가하므로 기존 행에도 안전하게 적용된다.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all이 이미 생성함
            db_columns = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in db_columns:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                default_sql = _default_clause(column)
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}{default_sql}'
                conn.execute(text(ddl))

    # reactions.entry_id가 기존 NOT NULL이면 댓글 반응(entry_id=NULL) 삽입이 막힌다.
    # SQLite는 컬럼 NULL 제약 변경이 안 되므로 테이블을 재생성한다.
    _relax_reactions_entry_nullable(inspector)


def _relax_reactions_entry_nullable(inspector) -> None:
    """reactions.entry_id를 nullable로 완화 (댓글 반응 지원)."""
    from sqlalchemy import inspect as _inspect
    from sqlalchemy import text

    inspector = _inspect(engine)
    if "reactions" not in inspector.get_table_names():
        return
    cols = {c["name"]: c for c in inspector.get_columns("reactions")}
    # comment_id가 있고 entry_id가 NOT NULL인 경우에만 재구성
    if "comment_id" not in cols:
        return
    entry_col = cols.get("entry_id")
    if entry_col is None or entry_col.get("nullable", True):
        return  # 이미 nullable이면 할 일 없음

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE reactions RENAME TO reactions_old"))
        conn.execute(
            text(
                "CREATE TABLE reactions ("
                "id INTEGER PRIMARY KEY, "
                "reaction_type VARCHAR(16), "
                "created_at DATETIME, "
                "user_id INTEGER NOT NULL REFERENCES users(id), "
                "entry_id INTEGER REFERENCES guestbook_entries(id), "
                "comment_id INTEGER REFERENCES comments(id)"
                ")"
            )
        )
        conn.execute(
            text(
                "INSERT INTO reactions (id, reaction_type, created_at, user_id, entry_id, comment_id) "
                "SELECT id, reaction_type, created_at, user_id, entry_id, "
                "       CASE WHEN comment_id IS NULL THEN NULL ELSE comment_id END "
                "FROM reactions_old"
            )
        )
        conn.execute(text("DROP TABLE reactions_old"))


def _default_clause(column) -> str:
    """ALTER TABLE ADD COLUMN에 사용할 NOT NULL/DEFAULT 절 생성."""
    import datetime

    from sqlalchemy import Boolean, DateTime, Integer, Numeric

    if column.nullable:
        return ""

    py_type = None
    try:
        py_type = column.type.python_type
    except (NotImplementedError, AttributeError):
        pass

    if isinstance(column.type, Boolean):
        default = "0"
    elif isinstance(column.type, (Integer, Numeric)):
        default = "0"
    elif isinstance(column.type, DateTime) or py_type is datetime.datetime:
        default = "CURRENT_TIMESTAMP"
    else:
        default = "''"
    return f" NOT NULL DEFAULT {default}"
