import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from app.config import settings

logger = logging.getLogger("prodllm.queue")
T = TypeVar("T")


class BackpressureQueueFullError(Exception):
    """Raised when the priority queue reaches max capacity."""


@dataclass(order=True)
class PrioritizedItem:
    priority_num: int  # 0 for high, 1 for normal, 2 for low
    timestamp: float = field(default_factory=time.time)
    future: asyncio.Future = field(compare=False, default=None)
    task_fn: Callable[[], Awaitable[Any]] = field(compare=False, default=None)


class PriorityScheduler:
    """
    Asynchronous Priority Queue & Concurrency Limiter with Backpressure.
    Ensures high-priority requests execute first and bounds maximum active concurrency.
    """

    PRIORITY_LEVELS = {
        "high": 0,
        "urgent": 0,
        "normal": 1,
        "medium": 1,
        "low": 2,
    }

    def __init__(
        self,
        max_concurrency: int | None = None,
        max_queue_size: int | None = None,
    ):
        self.max_concurrency = max_concurrency or settings.MAX_CONCURRENT_REQUESTS
        self.max_queue_size = max_queue_size or settings.PRIORITY_QUEUE_CAPACITY
        self._queue = asyncio.PriorityQueue(maxsize=self.max_queue_size)
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._active_workers: list[asyncio.Task] = []
        self._is_running = False

    async def start_workers(self, num_workers: int = 50):
        if self._is_running:
            return
        self._is_running = True
        for i in range(num_workers):
            task = asyncio.create_task(self._worker_loop(i), name=f"prio-worker-{i}")
            self._active_workers.append(task)
        logger.info(f"Started {num_workers} priority scheduler workers.")

    async def stop_workers(self):
        self._is_running = False
        for task in self._active_workers:
            task.cancel()
        self._active_workers.clear()

    async def _worker_loop(self, worker_id: int):
        while self._is_running:
            try:
                item: PrioritizedItem = await self._queue.get()
                async with self._semaphore:
                    if item.future and not item.future.cancelled():
                        try:
                            result = await item.task_fn()
                            item.future.set_result(result)
                        except Exception as e:
                            item.future.set_exception(e)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} unexpected error: {e}")

    async def schedule(
        self,
        task_fn: Callable[[], Awaitable[T]],
        priority: str = "normal",
    ) -> T:
        """
        Enqueue a task according to priority. If queue is full, raise BackpressureQueueFullError.
        """
        priority_num = self.PRIORITY_LEVELS.get(priority.lower(), 1)
        loop = asyncio.get_running_loop()
        fut = loop.create_future()

        item = PrioritizedItem(
            priority_num=priority_num,
            timestamp=time.time(),
            future=fut,
            task_fn=task_fn,
        )

        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            logger.warning("Priority queue capacity reached! Shedding load (Backpressure 429/503).")
            raise BackpressureQueueFullError("Gateway is currently overloaded. Please retry shortly.")

        return await fut


scheduler = PriorityScheduler()
