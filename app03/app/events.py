"""실시간 이벤트 pub/sub — Redis Pub/Sub 기반 (여러 태스크/워커 간 공유).

여러 ECS 태스크로 확장해도 실시간 이벤트가 공유되도록 Redis를 메시지 브로커로 사용한다.
각 프로세스는 Redis 채널 하나를 구독하는 리스너를 1개 돌리고, 수신한 메시지를
해당 프로세스의 로컬 구독자(asyncio.Queue)들에게 분배한다.

인터페이스(broker.subscribe/unsubscribe/publish, router)는 in-memory 버전과 동일하여
guestbook.py / chat.py 등 호출부 코드는 수정 없이 그대로 사용한다.
"""
import asyncio
import json
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .config import settings

CHANNEL = "events"


class RedisEventBroker:
    """Redis Pub/Sub 기반 브로커. 프로세스별 로컬 큐에 재분배한다."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._redis: aioredis.Redis | None = None
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        self._listener_task: asyncio.Task | None = None

    async def _ensure_listener(self) -> None:
        """프로세스당 하나의 Redis 구독 리스너를 보장한다."""
        if self._listener_task is not None:
            return
        self._redis = aioredis.from_url(self._url, decode_responses=True)
        self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        assert self._redis is not None
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(CHANNEL)
        async for message in pubsub.listen():
            if message is None or message.get("type") != "message":
                continue
            data = message["data"]
            async with self._lock:
                targets = list(self._subscribers)
            for q in targets:
                try:
                    q.put_nowait(data)
                except asyncio.QueueFull:
                    pass

    async def subscribe(self) -> asyncio.Queue:
        await self._ensure_listener()
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers.add(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(q)

    async def publish(self, event: dict[str, Any]) -> None:
        """Redis 채널로 이벤트를 발행한다 (모든 프로세스의 구독자에게 전달됨)."""
        await self._ensure_listener()
        assert self._redis is not None
        await self._redis.publish(CHANNEL, json.dumps(event, ensure_ascii=False))


broker = RedisEventBroker(settings.redis_url)


router = APIRouter(tags=["events"])


@router.get("/events/comments")
async def comment_stream(request: Request) -> StreamingResponse:
    """새 댓글 이벤트를 SSE로 전송 (조회는 누구나 가능)."""

    async def event_generator():
        queue = await broker.subscribe()
        try:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15)
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
    return StreamingResponse(
        event_generator(), media_type="text/event-stream", headers=headers
    )
