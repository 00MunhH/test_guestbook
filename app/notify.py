"""알림 생성 공용 헬퍼."""
from sqlalchemy.orm import Session

from .models import Notification


def create_notification(
    db: Session,
    user_id: int,
    kind: str,
    message: str,
    *,
    link: str = "",
    entry_id: int | None = None,
    comment_id: int | None = None,
    room_id: int | None = None,
    chat_message_id: int | None = None,
    commit: bool = True,
) -> Notification:
    """알림을 생성한다. link가 있으면 클릭 시 그 URL로 이동한다."""
    n = Notification(
        user_id=user_id,
        kind=kind,
        message=message,
        link=link,
        entry_id=entry_id,
        comment_id=comment_id,
        room_id=room_id,
        chat_message_id=chat_message_id,
    )
    db.add(n)
    if commit:
        db.commit()
    return n


def notification_url(n: Notification) -> str:
    """알림 클릭 시 이동할 URL 계산."""
    if n.link:
        return n.link
    if n.comment_id:
        return f"/?focus={n.comment_id}#comment-{n.comment_id}"
    if n.entry_id:
        return f"/#entry-{n.entry_id}"
    if n.room_id:
        base = f"/chat/{n.room_id}"
        if n.chat_message_id:
            return f"{base}?focus={n.chat_message_id}#msg-{n.chat_message_id}"
        return base
    return "#"
