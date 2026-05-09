"""Redis Streams event bus implementation."""
import json
from collections.abc import AsyncIterator
import redis.asyncio as aioredis
from .bus import EventBus
from .types import MissionEvent, EventType
from ..config import settings


class RedisStreamBus(EventBus):
    def __init__(self, url: str | None = None) -> None:
        self._url = url or settings.redis_url
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._client = aioredis.from_url(self._url, decode_responses=True)
        await self._client.ping()

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def _redis(self) -> aioredis.Redis:
        if not self._client:
            raise RuntimeError("RedisStreamBus not connected — call connect() first.")
        return self._client

    async def publish(self, event: MissionEvent) -> None:
        data = event.to_dict()
        await self._redis.xadd(
            event.stream,
            data,
            maxlen=settings.redis_stream_maxlen,
            approximate=True,
        )

    async def _ensure_group(self, stream: str, group: str) -> None:
        try:
            await self._redis.xgroup_create(stream, group, id="0", mkstream=True)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def subscribe(
        self,
        stream: str,
        group: str = "control",
        consumer: str = "worker-1",
        last_id: str = ">",
    ) -> AsyncIterator[MissionEvent]:
        await self._ensure_group(stream, group)
        while True:
            results = await self._redis.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: last_id},
                count=10,
                block=1000,
            )
            if not results:
                continue
            for _stream, messages in results:
                for msg_id, fields in messages:
                    try:
                        event = MissionEvent(
                            id=fields.get("id", msg_id),
                            type=EventType(fields["type"]),
                            stream=stream,
                            mission_id=fields.get("mission_id") or None,
                            rover_id=fields.get("rover_id") or None,
                            payload={
                                k.removeprefix("payload_"): v
                                for k, v in fields.items()
                                if k.startswith("payload_")
                            },
                        )
                        yield event
                        await self._redis.xack(stream, group, msg_id)
                    except Exception:
                        pass
