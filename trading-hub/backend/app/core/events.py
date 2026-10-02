"""Async in-process EventBus (§5 EventBus, §81).

A tiny publish/subscribe hub. The engine publishes typed events; the API's
WebSocket layer and the AlertEngine subscribe. Keeping this in-process (no
broker) honours the "works fully local, no server required" rule (§3).

Design notes for scalability (§72): publishing never blocks on slow
subscribers - each subscriber owns a bounded queue and a dropped-message
counter, so one stuck consumer can never stall the trading engine.
"""
from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from typing import Any

from .enums import EventType


@dataclass(slots=True)
class Event:
    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def as_dict(self) -> dict[str, Any]:
        return {"type": self.type.value, "payload": self.payload, "ts": self.ts}


class _Subscription:
    def __init__(self, maxsize: int = 1000) -> None:
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)
        self.dropped = 0


class EventBus:
    def __init__(self) -> None:
        self._subs: set[_Subscription] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> None:
        # Snapshot to avoid holding the lock while touching queues.
        async with self._lock:
            subs = list(self._subs)
        for sub in subs:
            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                sub.dropped += 1  # never block the publisher (§72)

    def publish_soon(self, event: Event) -> None:
        """Fire-and-forget from sync code running inside the event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.publish(event))

    @contextlib.asynccontextmanager
    async def subscribe(self, maxsize: int = 1000):
        sub = _Subscription(maxsize)
        async with self._lock:
            self._subs.add(sub)
        try:
            yield sub.queue
        finally:
            async with self._lock:
                self._subs.discard(sub)


# One shared bus for the process.
bus = EventBus()
