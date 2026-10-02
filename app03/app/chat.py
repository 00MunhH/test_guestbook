"""그룹 채팅방 라우터: 개설, 친구 초대(승인/거절), 메시지(텍스트/파일), 읽음, 멘션, 실시간 SSE."""
import asyncio
import re
import secrets
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from .account import unread_count
from .auth import require_user
from .config import settings
from .database import get_db
from .events import broker
from .friends import accepted_friend_ids, relation_label_between
from .models import ChatMembership, ChatMessage, ChatRoom, User
from .notify import create_notification
from .storage import presigned_download_url, upload_bytes
from .timeutils import to_kst

router = APIRouter(tags=["chat"])

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["kst"] = to_kst

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10MB
MENTION_RE = re.compile(r"@([^\s@]{1,32})")


def _membership(db: Session, room_id: int, user_id: int) -> ChatMembership | None:
    return db.scalar(
        select(ChatMembership).where(
            ChatMembership.room_id == room_id, ChatMembership.user_id == user_id
        )
    )


def _require_active_member(db: Session, room_id: int, user_id: int) -> ChatRoom:
    """방 존재 + 활성 멤버(수락 완료) 여부 확인."""
    room = db.get(ChatRoom, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
    mb = _membership(db, room_id, user_id)
    if mb is None or mb.status != "active":
        raise HTTPException(status_code=403, detail="이 채팅방의 멤버가 아닙니다.")
    return room


def _active_member_ids(db: Session, room_id: int) -> list[int]:
    return [
        m.user_id
        for m in db.scalars(
            select(ChatMembership).where(
                ChatMembership.room_id == room_id,
                ChatMembership.status == "active",
            )
        ).all()
    ]


def unread_chat_count(db: Session, user_id: int) -> int:
    """내가 속한 활성 방들에서 안 읽은 메시지 총합."""
    total = 0
    memberships = db.scalars(
        select(ChatMembership).where(
            ChatMembership.user_id == user_id, ChatMembership.status == "active"
        )
    ).all()
    for mb in memberships:
        cnt = db.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .where(
                ChatMessage.room_id == mb.room_id,
                ChatMessage.id > mb.last_read_message_id,
                ChatMessage.sender_id != user_id,
            )
        ) or 0
        total += cnt
    return total


@router.get("/chat", response_class=HTMLResponse)
def chat_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> HTMLResponse:
    """내 채팅방 목록(방별 미읽음 수) + 받은 초대."""
    memberships = db.scalars(
        select(ChatMembership).where(ChatMembership.user_id == user.id)
    ).all()

    rooms = []  # 활성 방 + 미읽음 수
    invites = []  # 받은 초대
    for mb in memberships:
        room = db.get(ChatRoom, mb.room_id)
        if room is None:
            continue
        if mb.status == "active":
            unread = db.scalar(
                select(func.count()).select_from(ChatMessage).where(
                    ChatMessage.room_id == room.id,
                    ChatMessage.id > mb.last_read_message_id,
                    ChatMessage.sender_id != user.id,
                )
            ) or 0
            rooms.append({"room": room, "unread": unread})
        elif mb.status == "invited":
            invites.append({"room": room, "membership": mb})

    rooms.sort(key=lambda r: r["room"].created_at, reverse=True)
    return templates.TemplateResponse(
        request,
        "chat_list.html",
        {
            "user": user,
            "rooms": rooms,
            "invites": invites,
            "unread": unread_count(db, user),
        },
    )


@router.post("/chat/rooms")
def create_room(
    name: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """채팅방 개설 (개설자는 자동 활성 멤버)."""
    room_name = name.strip()[:128] or "새 채팅방"
    room = ChatRoom(name=room_name, owner_id=user.id)
    db.add(room)
    db.commit()
    db.refresh(room)
    db.add(ChatMembership(room_id=room.id, user_id=user.id, status="active"))
    db.commit()
    return RedirectResponse(url=f"/chat/{room.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/chat/{room_id}", response_class=HTMLResponse)
def chat_room(
    room_id: int,
    request: Request,
    focus: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> HTMLResponse:
    """채팅방 상세. 진입 시 읽음 처리."""
    room = _require_active_member(db, room_id, user.id)
    mb = _membership(db, room_id, user.id)

    active_ids = _active_member_ids(db, room_id)
    invitable = [
        db.get(User, fid)
        for fid in accepted_friend_ids(db, user.id)
        if fid not in {m.user_id for m in db.scalars(
            select(ChatMembership).where(ChatMembership.room_id == room_id)
        ).all()}
    ]
    invitable = [u for u in invitable if u]

    members = []
    for mid in active_ids:
        u = db.get(User, mid)
        if u:
            members.append({"user": u, "relation": relation_label_between(db, user.id, mid)})

    messages = list(room.messages)

    # 메시지별 읽은 사람 수: last_read_message_id >= 메시지id 인 활성 멤버 수
    memberships = db.scalars(
        select(ChatMembership).where(
            ChatMembership.room_id == room_id, ChatMembership.status == "active"
        )
    ).all()
    read_counts = {}
    for msg in messages:
        read_counts[msg.id] = sum(
            1 for m in memberships if m.last_read_message_id >= msg.id
        )

    # 멘션 자동완성용 멤버 이름
    member_names = [m["user"].shown_name for m in members]

    # 읽음 처리: 마지막 메시지까지 읽은 것으로
    if messages:
        last_id = messages[-1].id
        if mb.last_read_message_id < last_id:
            mb.last_read_message_id = last_id
            db.commit()

    return templates.TemplateResponse(
        request,
        "chat_room.html",
        {
            "user": user,
            "room": room,
            "messages": messages,
            "members": members,
            "member_names": member_names,
            "read_counts": read_counts,
            "member_total": len(active_ids),
            "invitable": invitable,
            "is_owner": room.owner_id == user.id,
            "focus": focus,
        },
    )


@router.post("/chat/{room_id}/invite")
def invite_member(
    room_id: int,
    friend_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """사이 맺은 친구를 초대 (invited 상태 + 알림). 활성 멤버만 초대 가능."""
    room = _require_active_member(db, room_id, user.id)

    if friend_id not in accepted_friend_ids(db, user.id):
        raise HTTPException(status_code=400, detail="사이 맺은 친구만 초대할 수 있습니다.")

    existing = _membership(db, room_id, friend_id)
    if existing is None:
        db.add(ChatMembership(room_id=room_id, user_id=friend_id, status="invited"))
        db.commit()
        create_notification(
            db, friend_id, "chat_invite",
            f"{user.shown_name}님이 '{room.name}' 채팅방에 초대했습니다.",
            link="/chat", room_id=room_id,
        )
    return RedirectResponse(url=f"/chat/{room_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/chat/{room_id}/invite/accept")
def accept_invite(
    room_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """채팅방 초대 수락."""
    mb = _membership(db, room_id, user.id)
    if mb is None or mb.status != "invited":
        raise HTTPException(status_code=404, detail="초대를 찾을 수 없습니다.")
    mb.status = "active"
    db.commit()
    return RedirectResponse(url=f"/chat/{room_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/chat/{room_id}/invite/decline")
def decline_invite(
    room_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """채팅방 초대 거절."""
    mb = _membership(db, room_id, user.id)
    if mb is None or mb.status != "invited":
        raise HTTPException(status_code=404, detail="초대를 찾을 수 없습니다.")
    db.delete(mb)
    db.commit()
    return RedirectResponse(url="/chat", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/chat/{room_id}/leave")
def leave_room(
    room_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """방 나가기. 방장이 나가면 방 삭제."""
    room = _require_active_member(db, room_id, user.id)
    if room.owner_id == user.id:
        db.delete(room)
    else:
        mb = _membership(db, room_id, user.id)
        if mb:
            db.delete(mb)
    db.commit()
    return RedirectResponse(url="/chat", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/chat/{room_id}/messages")
async def send_message(
    room_id: int,
    body: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """메시지 전송 (텍스트/파일). 활성 멤버만. 멘션 시 알림."""
    room = _require_active_member(db, room_id, user.id)

    text = body.strip()
    stored_name = ""
    original_name = ""

    if file is not None and file.filename:
        content = await file.read()
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(status_code=400, detail="파일은 최대 10MB까지 가능합니다.")
        suffix = Path(file.filename).suffix[:16]
        stored_name = f"chat/{room_id}/{secrets.token_hex(16)}{suffix}"  # S3 key
        original_name = Path(file.filename).name[:255]
        upload_bytes(stored_name, content, content_type=file.content_type or "application/octet-stream")

    if not text and not stored_name:
        return RedirectResponse(
            url=f"/chat/{room_id}", status_code=status.HTTP_303_SEE_OTHER
        )

    msg = ChatMessage(
        room_id=room_id, sender_id=user.id, body=text,
        file_name=stored_name, original_name=original_name,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # 보낸 사람은 자기 메시지를 읽은 것으로
    mb = _membership(db, room_id, user.id)
    if mb and mb.last_read_message_id < msg.id:
        mb.last_read_message_id = msg.id
        db.commit()

    # 멘션 처리: @이름 → 활성 멤버 중 일치하는 사람에게 알림
    if text:
        mentioned = {m.group(1) for m in MENTION_RE.finditer(text)}
        if mentioned:
            for mid in _active_member_ids(db, room_id):
                if mid == user.id:
                    continue
                mu = db.get(User, mid)
                if mu and mu.shown_name in mentioned:
                    create_notification(
                        db, mid, "mention",
                        f"{user.shown_name}님이 '{room.name}'에서 회원님을 언급했습니다: {text[:40]}",
                        room_id=room_id, chat_message_id=msg.id,
                    )

    await broker.publish(
        {
            "type": "chat",
            "room_id": room_id,
            "message_id": msg.id,
            "sender": user.shown_name,
            "sender_id": user.id,
            "sender_image": user.profile_image,
            "body": text,
            "file_url": f"/chat/{room_id}/files/{msg.id}" if stored_name else None,
            "file_name": original_name,
            "created_at": to_kst(msg.created_at),
        }
    )
    return RedirectResponse(url=f"/chat/{room_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/chat/{room_id}/files/{message_id}")
def download_file(
    room_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """첨부 파일 다운로드 (활성 멤버만). S3 presigned URL로 리다이렉트."""
    _require_active_member(db, room_id, user.id)
    msg = db.get(ChatMessage, message_id)
    if msg is None or msg.room_id != room_id or not msg.file_name:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    url = presigned_download_url(msg.file_name, msg.original_name or "download")
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/chat/{room_id}/events")
async def chat_events(
    room_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> StreamingResponse:
    """방별 실시간 메시지 스트림 (활성 멤버만)."""
    _require_active_member(db, room_id, user.id)

    async def gen():
        import json

        queue = await broker.subscribe()
        try:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15)
                    try:
                        ev = json.loads(data)
                    except ValueError:
                        continue
                    if ev.get("type") == "chat" and ev.get("room_id") == room_id:
                        yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            await broker.unsubscribe(queue)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
