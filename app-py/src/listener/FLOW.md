# Listener: end-to-end flow and behaviour

## Flow: DB change → ES update

1. **DB change**  
   Someone (or the app) does INSERT/UPDATE/DELETE on `foods` or `food_nutrients`.

2. **Trigger fires**  
   Postgres trigger (migration 004) runs and sends:
   ```text
   NOTIFY food_index_events, '{"table":"foods","op":"UPDATE","fdc_id":123}'
   ```

3. **Listener receives NOTIFY**  
   The listener process has a connection that did `LISTEN food_index_events`. Postgres pushes the payload to that connection. asyncpg invokes our callback with that payload.

4. **Callback enqueues (no await)**  
   The callback is synchronous. It only does: `queue.put_nowait((payload, 0))`. So the payload is **put in the in-memory queue** and the callback returns immediately. No DB or ES work here.

5. **Worker pulls from queue**  
   An async loop (the worker) is always waiting on `queue.get()`. When an item appears, it:
   - Parses the payload → `(table, op, fdc_id)`.
   - If `table == "foods"` and `op == "DELETE"`: calls `indexing_service.delete_food_from_index(fdc_id)`.
   - Otherwise: calls `indexing_service.upsert_food_by_fdc_id(fdc_id)`.
   - Those methods use the **same** Postgres/ES clients as ingest: they load the food (and nutrients) from DB, build the search doc, and index or delete in Elasticsearch.

6. **When the item leaves the queue**  
   - **Success:** After the worker finishes the indexing call, the item is done. It is not put back; it’s “dropped” in the sense that it’s consumed and not requeued.
   - **Invalid payload:** Worker parses it, sees it’s bad, logs and does not retry. Item is not put in the failed list.
   - **Processing error (e.g. ES down):** Worker catches the exception and appends `(payload, attempt+1)` to the **failed list**. The item is no longer in the main queue until the retry loop puts it back.

7. **Retries (failed list)**  
   - **How many retries:** We retry up to **3 times** after the first failure (so **4 attempts in total**: 1 initial + 3 retries).
   - **After how long:** Every **10 seconds** a retry loop runs. It takes everything in the failed list and puts it back on the main queue (if `attempt <= 3`). So a failed item gets its next attempt within about 10 seconds (then 20, then 30 for the next retries).
   - **After max retries:** If an item has already failed 3 retries (attempt 4), we do **not** put it back. We log an error and drop it permanently.

**How does the listener know there are failures?**  
The worker and the retry loop run in the **same process** and share the same object. When the worker catches an exception it does `self._failed.append((payload, attempt+1))`. So the failed list is just an in-memory list on that object; the retry loop doesn’t need to “find out” from anywhere else—it’s the same process that added them.

**What about work in between the 10s ticks?**  
New NOTIFYs go straight onto the **main queue** and are processed by the worker as soon as it’s free. The 10-second interval only controls **when we requeue items that already failed**. So:
- t=0: NOTIFY A fails → goes to `_failed`. NOTIFY B arrives → goes to main queue.
- t=1–9: Worker keeps draining the main queue (B and any others). A sits in `_failed`.
- t=10: Retry loop wakes up, sees `_failed` has A, puts A back on the main queue. Worker will pick A up on its next `queue.get()`.
So we don’t “check every 10s for work”; we check every 10s **only for failed items** to give them another try. Normal work is processed continuously from the main queue.

## Queue size

- **Main queue:** `asyncio.Queue()` with **no max size** by default → **unbounded**. So under heavy NOTIFY load the queue can grow until memory. If you want backpressure (e.g. drop or block when full), we can set `maxsize=` and handle `QueueFull` in the callback (we already handle it by logging and not putting the item in the failed list).
- **Failed list:** A list that is cleared each time the retry loop runs; items are either requeued or dropped. So its size is at most “number of distinct payloads that failed and haven’t been retried yet” (bounded by how many we process between retry intervals).

**Should it keep checking every 10s for items in the failed list?**  
Yes. The retry loop is a fixed-interval loop: `while True: sleep(10); if _failed: requeue(_failed)`. So every 10 seconds we look at `_failed` and move retriable items back to the main queue. We don’t need to “notify” the retry loop when something fails—the same process that appends to `_failed` is the one that runs the retry loop, so on the next 10s tick it will see whatever the worker added.

---

## Summary table

| Question | Answer |
|----------|--------|
| How many retries? | 3 retries (4 attempts total). |
| After how long? | Retry loop runs every 10 seconds and requeues failed items. |
| When is an item dropped from the queue? | When the worker finishes successfully (consumed); or when payload is invalid (no retry); or after 3 retries (logged and dropped). |
| Queue size? | Unbounded (no `maxsize`). |
| How does the listener know there are failures? | Same process: worker appends to `_failed`; retry loop reads `_failed` every 10s. |
| What about work between 10s ticks? | New NOTIFYs go to the main queue and are processed continuously. The 10s only controls when failed items get another chance. |
| How does the listener update ES? | Worker calls `FoodIndexingService.upsert_food_by_fdc_id(fdc_id)` or `delete_food_from_index(fdc_id)`; that service loads from Postgres and updates the Elasticsearch index (same logic as ingest). |
