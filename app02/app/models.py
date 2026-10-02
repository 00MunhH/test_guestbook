"""ORM 모델 정의: 사용자, 방명록 항목, 반응, 댓글."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# 허용되는 반응 타입 (이모지 라벨은 템플릿/라우터에서 매핑)
REACTION_TYPES = ("like", "dislike", "thanks")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _count_reactions(reactions) -> dict[str, int]:
    counts = {t: 0 for t in REACTION_TYPES}
    for r in reactions:
        if r.reaction_type in counts:
            counts[r.reaction_type] += 1
    return counts


def _user_reaction(reactions, user_id):
    if user_id is None:
        return None
    for r in reactions:
        if r.user_id == user_id:
            return r.reaction_type
    return None


def _reactor_names(reactions) -> dict[str, list[str]]:
    """반응 타입별 참여자 표시 이름 목록."""
    result = {t: [] for t in REACTION_TYPES}
    for r in reactions:
        if r.reaction_type in result and r.user is not None:
            result[r.reaction_type].append(r.user.shown_name)
    return result


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

    @property
    def top_comments(self) -> list["Comment"]:
        """최상위 댓글만 (대댓글 제외), 작성순."""
        tops = [c for c in self.comments if c.parent_id is None]
        return sorted(tops, key=lambda c: c.created_at)

    @property
    def comment_total(self) -> int:
        """댓글 + 대댓글 전체 개수."""
        return len(self.comments)

    def reaction_counts(self) -> dict[str, int]:
        return _count_reactions(self.reactions)

    def user_reaction(self, user_id: int | None) -> str | None:
        return _user_reaction(self.reactions, user_id)

    def reactor_names(self) -> dict[str, list[str]]:
        return _reactor_names(self.reactions)


class Reaction(Base):
    """글 또는 댓글에 대한 사용자 반응.

    entry_id가 있으면 글 반응, comment_id가 있으면 댓글/대댓글 반응이다.
    사용자당 대상(글 또는 댓글)마다 1개(타입 변경 가능). 중복은 앱 레벨에서 제어한다.
    """

    __tablename__ = "reactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    reaction_type: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # 글 반응이면 entry_id, 댓글 반응이면 comment_id 사용 (하나만 채워짐)
    entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("guestbook_entries.id"), nullable=True, index=True
    )
    comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id"), nullable=True, index=True
    )

    user: Mapped["User"] = relationship()
    entry: Mapped["GuestbookEntry"] = relationship(back_populates="reactions")
    comment: Mapped["Comment | None"] = relationship(back_populates="reactions")


class Comment(Base):
    """방명록 글에 대한 댓글. parent_id가 있으면 대댓글(답글)이다."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    entry_id: Mapped[int] = mapped_column(ForeignKey("guestbook_entries.id"))
    # 대댓글이면 상위 댓글 id (최상위 댓글이면 None)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id"), nullable=True, index=True
    )

    author: Mapped["User"] = relationship()
    entry: Mapped["GuestbookEntry"] = relationship(back_populates="comments")

    # 자기참조: 답글 목록 / 부모 댓글
    replies: Mapped[list["Comment"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
        single_parent=True,
    )
    parent: Mapped["Comment | None"] = relationship(
        back_populates="replies", remote_side="Comment.id"
    )
    reactions: Mapped[list["Reaction"]] = relationship(
        back_populates="comment", cascade="all, delete-orphan"
    )

    def reaction_counts(self) -> dict[str, int]:
        return _count_reactions(self.reactions)

    def user_reaction(self, user_id: int | None) -> str | None:
        return _user_reaction(self.reactions, user_id)

    def reactor_names(self) -> dict[str, list[str]]:
        return _reactor_names(self.reactions)


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
    # 채팅 관련 알림용 (멘션/초대)
    room_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_rooms.id"), nullable=True
    )
    chat_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_messages.id"), nullable=True
    )
    # 클릭 시 이동할 URL (지정되면 우선 사용)
    link: Mapped[str] = mapped_column(String(255), default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship()


class Friendship(Base):
    """사이 맺기(친구) 관계. requester가 addressee에게 요청한다."""

    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friend_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    addressee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # pending | accepted
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # 관계 라벨 (친구/동료 등, 자유 입력)
    relation_label: Mapped[str] = mapped_column(String(32), default="친구")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    requester: Mapped["User"] = relationship(foreign_keys=[requester_id])
    addressee: Mapped["User"] = relationship(foreign_keys=[addressee_id])


class ChatRoom(Base):
    """그룹 채팅방."""

    __tablename__ = "chat_rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    owner: Mapped["User"] = relationship(foreign_keys=[owner_id])
    memberships: Mapped[list["ChatMembership"]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMembership(Base):
    """채팅방 멤버십. status: invited(초대 대기) / active(수락됨)."""

    __tablename__ = "chat_memberships"
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_room_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("chat_rooms.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    # 마지막으로 읽은 메시지 id (읽음 추적용)
    last_read_message_id: Mapped[int] = mapped_column(default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    room: Mapped["ChatRoom"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship()


class ChatMessage(Base):
    """채팅 메시지 (텍스트 또는 파일)."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("chat_rooms.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text, default="")
    # 파일 첨부가 있으면 저장 파일명/원본명 기록
    file_name: Mapped[str] = mapped_column(String(255), default="")
    original_name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    room: Mapped["ChatRoom"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship()

    @property
    def has_file(self) -> bool:
        return bool(self.file_name)
