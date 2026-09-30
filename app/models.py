"""ORM 모델 정의: 사용자와 방명록 항목."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """카카오 로그인 사용자."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 카카오 고유 사용자 ID
    kakao_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(128), default="")
    profile_image: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    entries: Mapped[list["GuestbookEntry"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )


class GuestbookEntry(Base):
    """방명록 글."""

    __tablename__ = "guestbook_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped["User"] = relationship(back_populates="entries")
