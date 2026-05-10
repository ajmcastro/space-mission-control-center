"""In-memory event bus for local dev / testing when Redis is unavailable."""
import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from .bus import EventBus
from .types import MissionEvent


class InMemoryEventBus(EventBus):
    """
    Pub-sub in-memory bus.

    Each call to `subscribe()` creates an independent queue so that multiple
    consumers of the same stream all receive every event (broadcast semantics).
    This matches Redis Streams consumer-group behaviour where each unique
    group name gets a full copy of the stream.
    """

    def __init__(self) -> None:
        # stream → list of per-subscriber queues (broadcast fan-out)
        self._queues: dict[str, list[asyncio.Queue[MissionEvent]]] = defaultdict(list)
        self._history: dict[str, list[MissionEvent]] = defaultdict(list)

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def publish(self, event: MissionEvent) -> None:
        self._history[event.stream].append(event)
        # Fan-out: deliver to every active subscriber.
        for queue in list(self._queues[event.stream]):
            await queue.put(event)

    async def subscribe(
        self,
        stream: str,
        group: str = "default",
        consumer: str = "default",
        last_id: str = "0",
    ) -> AsyncIterator[MissionEvent]:
        queue: asyncio.Queue[MissionEvent] = asyncio.Queue()
        self._queues[stream].append(queue)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event
                except asyncio.TimeoutError:
                    continue
        finally:
            # Clean up when the consumer exits or is cancelled.
            try:
                self._queues[stream].remove(queue)
            except ValueError:
                pass

    def get_history(self, stream: str) -> list[MissionEvent]:
        return list(self._history[stream])
