"""ORM 모델 정의: 사용자, 방명록 항목, 반응, 댓글."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# 허용되는 반응 타입 (이모지 라벨은 템플릿/라우터에서 매핑)
REACTION_TYPES = ("like", "dislike", "thanks")


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
    # 사용자가 직접 등록/변경하는 정보
    display_name: Mapped[str] = mapped_column(String(128), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    # 관리자 여부
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    entries: Mapped[list["GuestbookEntry"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )

    @property
    def shown_name(self) -> str:
        """표시 이름: display_name이 있으면 우선, 없으면 닉네임."""
        return self.display_name or self.nickname


class GuestbookEntry(Base):
    """방명록 글."""

    __tablename__ = "guestbook_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author: Mapped["User"] = relationship(back_populates="entries")

    reactions: Mapped[list["Reaction"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )

    def reaction_counts(self) -> dict[str, int]:
        """반응 타입별 개수 집계."""
        counts = {t: 0 for t in REACTION_TYPES}
        for r in self.reactions:
            if r.reaction_type in counts:
                counts[r.reaction_type] += 1
        return counts

    def user_reaction(self, user_id: int | None) -> str | None:
        """해당 사용자가 이 글에 남긴 반응 타입 (없으면 None)."""
        if user_id is None:
            return None
        for r in self.reactions:
            if r.user_id == user_id:
                return r.reaction_type
        return None


class Reaction(Base):
    """방명록 글에 대한 사용자 반응. 사용자당 글마다 1개(타입 변경 가능)."""

    __tablename__ = "reactions"
    __table_args__ = (
        UniqueConstraint("user_id", "entry_id", name="uq_reaction_user_entry"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reaction_type: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    entry_id: Mapped[int] = mapped_column(ForeignKey("guestbook_entries.id"))

    user: Mapped["User"] = relationship()
    entry: Mapped["GuestbookEntry"] = relationship(back_populates="reactions")


class Comment(Base):
    """방명록 글에 대한 댓글."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    entry_id: Mapped[int] = mapped_column(ForeignKey("guestbook_entries.id"))

    author: Mapped["User"] = relationship()
    entry: Mapped["GuestbookEntry"] = relationship(back_populates="comments")


class Notification(Base):
    """인앱 알림 (예: 내 글에 댓글이 달림)."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 알림을 받는 사용자
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # 알림 종류 (현재는 'comment')
    kind: Mapped[str] = mapped_column(String(32), default="comment")
    # 알림 메시지 (렌더링용 요약)
    message: Mapped[str] = mapped_column(Text, default="")
    # 연결 대상
    entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("guestbook_entries.id"), nullable=True
    )
    comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id"), nullable=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship()
