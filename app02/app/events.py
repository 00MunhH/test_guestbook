"""실시간 이벤트용 간단한 in-memory pub/sub (SSE 브로드캐스트).

단일 프로세스 환경을 전제로 한다. 여러 워커/인스턴스로 확장할 경우
Redis Pub/Sub 등 외부 브로커로 교체해야 한다.
"""
import asyncio
import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse


class EventBroker:
    """구독자(asyncio.Queue)들에게 이벤트를 브로드캐스트한다."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(q)

    async def publish(self, event: dict[str, Any]) -> None:
        """모든 구독자에게 이벤트를 전달한다 (큐가 가득 차면 해당 이벤트는 생략)."""
        data = json.dumps(event, ensure_ascii=False)
        async with self._lock:
            targets = list(self._subscribers)
        for q in targets:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass


# 애플리케이션 전역 브로커
broker = EventBroker()


router = APIRouter(tags=["events"])


@router.get("/events/comments")
async def comment_stream(request: Request) -> StreamingResponse:
    """새 댓글 이벤트를 SSE로 전송 (조회는 누구나 가능).

    클라이언트는 EventSource('/events/comments')로 구독한다.
    """

    async def event_generator():
        queue = await broker.subscribe()
        try:
            # 연결 직후 주석 라인으로 스트림 오픈 알림
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # keep-alive (프록시 타임아웃 방지)
                    yield ": keep-alive\n\n"
        finally:
            await broker.unsubscribe(queue)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
    }
    return StreamingResponse(
        event_generator(), media_type="text/event-stream", headers=headers
    )
