"""In-memory event bus for local dev / testing when Redis is unavailable."""
import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from .bus import EventBus
from .types import MissionEvent


class InMemoryEventBus(EventBus):
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[MissionEvent]] = defaultdict(asyncio.Queue)
        self._history: dict[str, list[MissionEvent]] = defaultdict(list)

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def publish(self, event: MissionEvent) -> None:
        self._history[event.stream].append(event)
        queue = self._queues[event.stream]
        await queue.put(event)

    async def subscribe(
        self,
        stream: str,
        group: str = "default",
        consumer: str = "default",
        last_id: str = "0",
    ) -> AsyncIterator[MissionEvent]:
        queue = self._queues[stream]
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield event
            except asyncio.TimeoutError:
                continue

    def get_history(self, stream: str) -> list[MissionEvent]:
        return list(self._history[stream])
