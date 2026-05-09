from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from .types import MissionEvent


class EventBus(ABC):
    """Abstract event bus. Swap Redis ↔ Kafka ↔ in-memory without changing callers."""

    @abstractmethod
    async def publish(self, event: MissionEvent) -> None:
        """Publish an event to its stream."""

    @abstractmethod
    async def subscribe(
        self,
        stream: str,
        group: str,
        consumer: str,
        last_id: str = "0",
    ) -> AsyncIterator[MissionEvent]:
        """Yield events from a stream consumer group."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish the underlying connection."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the underlying connection."""
