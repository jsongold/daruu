"""Event publisher interface (Port).

This defines the contract for event publishing operations.
Implementations can be in-memory queues, Redis pub/sub, Kafka, etc.
"""

import asyncio
from typing import Any, Protocol


class EventPublisher(Protocol):
    """Interface for publishing events to subscribers.

    This protocol defines the contract for event publishing.
    It supports both async and sync publishing, and allows
    subscribers to receive events via async queues.

    Example:
        class RedisEventPublisher:
            def subscribe(self, job_id: str) -> asyncio.Queue: ...
            async def publish(self, job_id: str, event: dict) -> None: ...
            # etc.

        # Inject into orchestrator
        orchestrator = Orchestrator(event_publisher=RedisEventPublisher())
    """

    def subscribe(self, job_id: str) -> asyncio.Queue[dict[str, Any]]:
        """Subscribe to events for a job.

        Args:
            job_id: Job identifier to subscribe to.

        Returns:
            Async queue that will receive events.
        """
        ...

    def unsubscribe(self, job_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Unsubscribe from events for a job.

        Args:
            job_id: Job identifier.
            queue: Queue to unsubscribe.
        """
        ...

    async def publish(self, job_id: str, event: dict[str, Any]) -> None:
        """Publish an event to all subscribers.

        Args:
            job_id: Job identifier.
            event: Event data to publish.
        """
        ...

    def publish_sync(self, job_id: str, event: dict[str, Any]) -> None:
        """Synchronously publish an event (non-blocking).

        Args:
            job_id: Job identifier.
            event: Event data to publish.
        """
        ...
