# Listener: queue, worker, and who owns what

## Why a queue at all?

Postgres NOTIFY is delivered via **asyncpg** as a **synchronous callback**: `add_listener(channel, callback)`. When a NOTIFY arrives, asyncpg calls `callback(connection, pid, channel, payload)` from the driver’s context. That callback **must not** do long work or `await` anything — it would block the connection and break the event loop.

We need to:

1. **React immediately** in the callback (so we don’t drop notifications).
2. **Do the real work asynchronously** (DB + ES calls), which is slow and must run in the async event loop.

So the callback only **enqueues** the payload; a separate **async worker** runs in the event loop and **consumes the queue** and does the indexing. The queue is the bridge between “sync notification” and “async processing”.

## What the worker does

- **Worker** = an async loop that:
  - Takes one item from the queue (payload + attempt).
  - Parses it, calls `FoodIndexingService` (upsert or delete by `fdc_id`).
  - On success: done. On failure: append to a “failed” list with `attempt + 1`.
- **Retry loop** = another async loop that every N seconds takes items from the failed list and puts them back on the queue (up to `max_retries`), so the worker will try again.

So there are two queues in spirit:

1. **Main queue**: “things to process”. Producer = NOTIFY callback. Consumer = worker.
2. **Failed list**: “things that failed, to be retried”. Producer = worker (on exception). Consumer = retry loop, which re-enqueues into the main queue.

## Who has the queue? Subscriber.

**Subscriber** = the process that subscribes to the channel (our listener process). It is the one that LISTENs and decides what to do with each notification.

The queue lives **inside the subscriber**: the subscriber (our `FoodIndexNotifyListener`) owns the queue. So:

- Postgres (publisher) sends NOTIFY.
- Subscriber (listener process) receives it and **immediately** puts the payload on **its own** queue.
- The same subscriber runs the worker that drains that queue and calls the indexing service.

So yes — the queue is something the **subscriber** has, not the publisher. The publisher (Postgres) has no queue; it just fires NOTIFY. Our listener is the subscriber and it has the in-memory queue (and the failed list) to decouple “received event” from “process event” and to support retries.
