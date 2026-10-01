"""그룹 채팅방 라우터: 개설, 친구 초대, 메시지(텍스트/파일), 실시간 SSE."""
import asyncio
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
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .auth import require_user
from .config import settings
from .database import get_db
from .events import broker
from .friends import accepted_friend_ids
from .models import ChatMembership, ChatMessage, ChatRoom, User
from .timeutils import to_kst

router = APIRouter(tags=["chat"])

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["kst"] = to_kst

UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10MB


def _require_member(db: Session, room_id: int, user_id: int) -> ChatRoom:
    """방 존재 + 멤버 여부 확인."""
    room = db.get(ChatRoom, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
    is_member = db.scalar(
        select(ChatMembership).where(
            ChatMembership.room_id == room_id, ChatMembership.user_id == user_id
        )
    )
    if is_member is None:
        raise HTTPException(status_code=403, detail="이 채팅방의 멤버가 아닙니다.")
    return room


@router.get("/chat", response_class=HTMLResponse)
def chat_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> HTMLResponse:
    """내가 속한 채팅방 목록 + 방 개설 폼."""
    rooms = db.scalars(
        select(ChatRoom)
        .join(ChatMembership, ChatMembership.room_id == ChatRoom.id)
        .where(ChatMembership.user_id == user.id)
        .order_by(ChatRoom.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        request, "chat_list.html", {"user": user, "rooms": list(rooms)}
    )


@router.post("/chat/rooms")
def create_room(
    name: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """채팅방 개설 (개설자는 자동 멤버)."""
    room_name = name.strip()[:128] or "새 채팅방"
    room = ChatRoom(name=room_name, owner_id=user.id)
    db.add(room)
    db.commit()
    db.refresh(room)
    db.add(ChatMembership(room_id=room.id, user_id=user.id))
    db.commit()
    return RedirectResponse(url=f"/chat/{room.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/chat/{room_id}", response_class=HTMLResponse)
def chat_room(
    room_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> HTMLResponse:
    """채팅방 상세: 메시지 목록 + 입력 + 초대 가능한 친구."""
    room = _require_member(db, room_id, user.id)

    member_ids = {
        m.user_id
        for m in db.scalars(
            select(ChatMembership).where(ChatMembership.room_id == room_id)
        ).all()
    }
    # 초대 가능한 친구 = 내 친구 중 아직 멤버가 아닌 사람
    invitable = []
    for fid in accepted_friend_ids(db, user.id):
        if fid not in member_ids:
            u = db.get(User, fid)
            if u:
                invitable.append(u)

    members = [db.get(User, mid) for mid in member_ids]

    return templates.TemplateResponse(
        request,
        "chat_room.html",
        {
            "user": user,
            "room": room,
            "messages": room.messages,
            "members": members,
            "invitable": invitable,
            "is_owner": room.owner_id == user.id,
        },
    )


@router.post("/chat/{room_id}/invite")
def invite_member(
    room_id: int,
    friend_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """사이 맺은 친구를 방에 초대 (멤버만 초대 가능)."""
    _require_member(db, room_id, user.id)

    # 초대 대상이 실제 내 친구인지 확인
    if friend_id not in accepted_friend_ids(db, user.id):
        raise HTTPException(status_code=400, detail="사이 맺은 친구만 초대할 수 있습니다.")

    already = db.scalar(
        select(ChatMembership).where(
            ChatMembership.room_id == room_id, ChatMembership.user_id == friend_id
        )
    )
    if already is None:
        db.add(ChatMembership(room_id=room_id, user_id=friend_id))
        db.commit()
    return RedirectResponse(url=f"/chat/{room_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/chat/{room_id}/leave")
def leave_room(
    room_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> RedirectResponse:
    """방 나가기. 방장이 나가면 방 삭제."""
    room = _require_member(db, room_id, user.id)
    if room.owner_id == user.id:
        db.delete(room)  # cascade로 멤버십/메시지 삭제
    else:
        membership = db.scalar(
            select(ChatMembership).where(
                ChatMembership.room_id == room_id, ChatMembership.user_id == user.id
            )
        )
        if membership:
            db.delete(membership)
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
    """메시지 전송 (텍스트 또는 파일). 멤버만 가능."""
    _require_member(db, room_id, user.id)

    text = body.strip()
    stored_name = ""
    original_name = ""

    if file is not None and file.filename:
        content = await file.read()
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(status_code=400, detail="파일은 최대 10MB까지 가능합니다.")
        suffix = Path(file.filename).suffix[:16]
        stored_name = f"{secrets.token_hex(16)}{suffix}"
        original_name = Path(file.filename).name[:255]
        (UPLOAD_DIR / stored_name).write_bytes(content)

    if not text and not stored_name:
        return RedirectResponse(
            url=f"/chat/{room_id}", status_code=status.HTTP_303_SEE_OTHER
        )

    msg = ChatMessage(
        room_id=room_id,
        sender_id=user.id,
        body=text,
        file_name=stored_name,
        original_name=original_name,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

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
) -> FileResponse:
    """첨부 파일 다운로드 (방 멤버만)."""
    _require_member(db, room_id, user.id)
    msg = db.get(ChatMessage, message_id)
    if msg is None or msg.room_id != room_id or not msg.file_name:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    path = UPLOAD_DIR / msg.file_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다.")
    return FileResponse(
        path, filename=msg.original_name or msg.file_name, media_type="application/octet-stream"
    )


@router.get("/chat/{room_id}/events")
async def chat_events(
    room_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> StreamingResponse:
    """방별 실시간 메시지 스트림 (멤버만)."""
    _require_member(db, room_id, user.id)

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
                    # 이 방의 chat 이벤트만 전달
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
