"""
Phase 3: LISTEN on food_index_events, update search index per notification.

Payload: JSON {"table": "foods"|"food_nutrients", "op": "INSERT"|"UPDATE"|"DELETE", "fdc_id": <int>}.
- table=foods and op=DELETE → delete_food_from_index(fdc_id).
- Otherwise → upsert_food_by_fdc_id(fdc_id).

Failures go to an in-memory queue and are retried up to max_retries; then logged and dropped.
Multiple listener processes can run (Postgres broadcasts NOTIFY to all); updates are idempotent.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

from ...config import NOTIFY_CHANNEL_FOOD_INDEX
from ...services.food_indexing_service import FoodIndexingService

from ..base import NotifyListener

logger = logging.getLogger(__name__)

# Retry: up to this many retries after first failure (4 attempts total).
DEFAULT_MAX_RETRIES = 3
# How often the retry loop runs and requeues failed items (seconds).
RETRY_INTERVAL_SEC = 10.0
# Main queue max size; 0 or None = unbounded (no backpressure).
QUEUE_MAX_SIZE: Optional[int] = None  # 0 means infinite in asyncio.Queue


def _parse_payload(payload: str) -> Optional[Tuple[str, str, int]]:
    """Parse JSON payload; return (table, op, fdc_id) or None if invalid."""
    try:
        data: Dict[str, Any] = json.loads(payload)
        table = data.get("table")
        op = data.get("op")
        fdc_id = data.get("fdc_id")
        if not table or not op or fdc_id is None:
            return None
        return (str(table).strip(), str(op).strip(), int(fdc_id))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


class FoodIndexNotifyListener(NotifyListener):
    """
    Listener for channel NOTIFY_CHANNEL_FOOD_INDEX: syncs search index per event.

    Uses a dedicated DB connection for LISTEN. The NOTIFY callback (sync) only
    enqueues payloads; an async worker drains the queue and calls FoodIndexingService.
    Failures are retried up to max_retries, then dropped. The queue is owned by
    this subscriber to decouple receipt from processing and to support retries.
    """

    @property
    def channel(self) -> str:
        return NOTIFY_CHANNEL_FOOD_INDEX

    def __init__(
        self,
        indexing_service: FoodIndexingService,
        listen_conn: asyncpg.Connection,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_interval_sec: float = RETRY_INTERVAL_SEC,
    ) -> None:
        self._indexing = indexing_service
        self._listen_conn = listen_conn
        self._max_retries = max_retries
        self._retry_interval_sec = retry_interval_sec
        self._queue: asyncio.Queue[Tuple[str, int]] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE if QUEUE_MAX_SIZE is not None else 0)
        self._failed: List[Tuple[str, int]] = []  # (payload, attempt); requeued every retry_interval_sec, dropped after max_retries
        self._shutdown = asyncio.Event()

    def _on_notify(
        self,
        connection: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: Optional[str],
    ) -> None:
        """Sync callback from asyncpg: enqueue payload for async processing (attempt=0)."""
        if payload:
            try:
                self._queue.put_nowait((payload, 0))
            except asyncio.QueueFull:
                logger.warning("FoodIndexNotifyListener: queue full, dropping payload")

    async def _process_one(self, payload: str, attempt: int) -> bool:
        """Process one payload; return True if successful, False to retry."""
        parsed = _parse_payload(payload)
        if not parsed:
            logger.warning("FoodIndexNotifyListener: invalid payload (attempt=%s): %r", attempt, payload)
            return True  # don't retry invalid payloads

        table, op, fdc_id = parsed
        try:
            if table == "foods" and op == "DELETE":
                await self._indexing.delete_food_from_index(fdc_id)
            else:
                await self._indexing.upsert_food_by_fdc_id(fdc_id)
            return True
        except Exception as e:
            logger.warning(
                "FoodIndexNotifyListener: failed (attempt=%s) table=%s op=%s fdc_id=%s: %s",
                attempt,
                table,
                op,
                fdc_id,
                e,
            )
            return False

    async def _worker(self) -> None:
        """Consume queue and process (payload, attempt); put failures in _failed with attempt+1."""
        while not self._shutdown.is_set():
            try:
                payload, attempt = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                continue
            ok = await self._process_one(payload, attempt)
            if not ok:
                self._failed.append((payload, attempt + 1))

    def _requeue_failures(self) -> None:
        """Re-put retriable failed items back on the queue; drop rest after max_retries."""
        current, self._failed = self._failed, []
        retriable: List[Tuple[str, int]] = []
        for payload, attempt in current:
            if attempt <= self._max_retries:
                try:
                    self._queue.put_nowait((payload, attempt))
                except asyncio.QueueFull:
                    retriable.append((payload, attempt))
            else:
                logger.error(
                    "FoodIndexNotifyListener: giving up after %s retries: %r",
                    self._max_retries,
                    payload[:200],
                )
        self._failed = retriable

    async def _retry_loop(self) -> None:
        """Every retry_interval_sec, requeue items in _failed so the worker retries them.
        Same process as the worker, so we see whatever the worker appended to _failed."""
        while not self._shutdown.is_set():
            await asyncio.sleep(self._retry_interval_sec)
            if not self._failed:
                continue
            self._requeue_failures()

    async def run(self) -> None:
        """Start LISTEN and worker/retry loops; blocks until shutdown."""
        await self._listen_conn.add_listener(self.channel, self._on_notify)
        logger.info("FoodIndexNotifyListener: LISTEN on channel %s", self.channel)

        worker = asyncio.create_task(self._worker())
        retry_task = asyncio.create_task(self._retry_loop())

        try:
            await self._shutdown.wait()
        finally:
            worker.cancel()
            retry_task.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
            try:
                await retry_task
            except asyncio.CancelledError:
                pass

    def stop(self) -> None:
        """Signal the run loop to exit (idempotent)."""
        self._shutdown.set()
