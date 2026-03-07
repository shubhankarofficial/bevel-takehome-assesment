# Backend Take-Home: Food Search

This repository contains a backend take-home assignment: a service that ingests USDA Foundation Foods data into PostgreSQL and Elasticsearch and exposes search over foods (with nutrients). Two implementations are provided; the **Python (FastAPI)** app in `app-py/` is the primary one and is fully implemented (ingest, search, live sync via Postgres NOTIFY). The TypeScript (Express) version in `app-ts/` is boilerplate—see `app-ts/README.md` for setup.

---

## Prerequisites

- **Docker** (and Docker Compose) — to run PostgreSQL, Elasticsearch, and Kibana.
- **Python 3.9–3.12** — for the `app-py` implementation. Use this range when creating the venv; Python 3.13 is not yet supported by some dependencies. **Most users:** if your default `python` or `python3` is already in this range, run `python -m venv venv` (or `python3 -m venv venv`) as in the steps below. **Only if** your default is 3.13, create the venv with an explicit interpreter, e.g. `python3.11 -m venv venv`.
- **Data (CSVs)** — The repository (or submission zip) includes sample CSVs in `csv/` at the repo root. Required files: `food.csv`, `food_nutrient.csv`, `nutrient.csv`. To use a different directory, set the `CSV_DIR` environment variable when running from `app-py` (e.g. `CSV_DIR=/path/to/csv`).

---

## Implementation steps (Python app)

Follow these in order.

### 1. Virtual environment

From the repo root:

```bash
cd app-py
python -m venv venv
```

Activate it:

- **macOS/Linux:** `source venv/bin/activate`
- **Windows:** `venv\Scripts\activate`

Then install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Start services (Docker Compose)

From the **repo root** (where `docker-compose.yml` is):

```bash
docker-compose up -d
```

(or `docker compose up -d` on newer Docker CLI). This starts PostgreSQL (port 54328), Elasticsearch (9200), and Kibana (5601).

**Note:** The Compose file uses `postgres:16` (not `latest`) for compatibility with the default data directory layout; Postgres 18+ images use a different volume layout and can cause startup issues.

### 3. Migrations

Migrations run automatically as part of ingest—there is no separate migration step.

### 4. Start the application

From `app-py` (with venv activated):

```bash
uvicorn src.main:app --reload --port 3000
```

On startup, the app runs the **ingest pipeline once** (migrations, CSV load, Elasticsearch index creation and bulk index), then starts the **NOTIFY listener** in the background to keep the search index in sync with DB changes. No separate ingest step is needed for a normal run.

**Standalone ingest (optional)** — To only (re)load data without starting the API (e.g. after a reset or to repopulate the index):

```bash
cd app-py
python -m src.ingest.scripts.run_ingest
```

This runs migrations, CSV load, and ES indexing only; it does not start the listener or the HTTP server.

### 5. Test the API

With the app running, you can hit the endpoints directly:

**Health** (checks DB and Elasticsearch):

```bash
curl -s http://localhost:3000/health
```

**Search** (required query, optional size, default 20, max 100):

```bash
curl -s "http://localhost:3000/search?query=apple&size=10"
```

### 6. Demonstrations and reset

- **Run food demos** (add/update/delete sample data; requires ingest done and listener running):  
  From `app-py` **with venv activated:** `python -m src.demonstrations.run_food_demos`
- **Reset:** From `app-py` **with venv activated:** `python -m src.reset.run_reset`  
  Reset truncates Postgres tables (foods, food_nutrients, nutrients), deletes the Elasticsearch food index, then **runs the full ingest pipeline** (migrations, CSV load, ES reindex). So data is repopulated automatically; no separate ingest step after reset. The reset script does not start the listener or the HTTP server—start the app again if you want the API and listener running.  
  If you get `ModuleNotFoundError: No module named 'asyncpg'` (or similar), either the venv is missing dependencies (run `pip install -r requirements.txt`) or the venv’s `python` is not the interpreter you installed into (e.g. it’s 3.13 while packages are in 3.11). Check with `python --version` in the venv; if it shows 3.13, run the command with your 3.9–3.12 interpreter, e.g. `python3.11 -m src.reset.run_reset`, or recreate the venv with that interpreter (`python3.11 -m venv venv`, then activate and `pip install -r requirements.txt`).

### 7. Demo endpoints (DB → index sync)

With the app running, DB changes trigger `NOTIFY`; the listener updates Elasticsearch. Example calls:

**Add a food** (trigger NOTIFY → listener indexes it):

```bash
curl -s -X POST http://localhost:3000/demo/foods \
  -H "Content-Type: application/json" \
  -d '{"fdc_id": 999999, "data_type": "foundation_food", "description": "Test food"}'
```

**Update a food** (e.g. change description):

```bash
curl -s -X PUT http://localhost:3000/demo/foods/999999 \
  -H "Content-Type: application/json" \
  -d '{"description": "Updated test food"}'
```

**Delete a food:**

```bash
curl -s -X DELETE http://localhost:3000/demo/foods/999999
```

**Food nutrients** — add, update, delete (body fields: `fdc_id`, `nutrient_id`, `amount` for add; any subset for update). The food must exist first: use the same `fdc_id` (e.g. 999999) as in “Add a food” above. If you already ran “Delete a food”, add the food again before adding a food-nutrient; otherwise the add returns **500** (foreign key violation). For update and delete, use the **`id` returned in the add response** in the URL (not a placeholder like `1`); otherwise you get **404** (no food_nutrient found).

```bash
# Add (requires food 999999 to exist; response includes "id")
curl -s -X POST http://localhost:3000/demo/food-nutrients \
  -H "Content-Type: application/json" \
  -d '{"fdc_id": 999999, "nutrient_id": 1008, "amount": 0.5}'

# Update (replace 1 with the id from the add response)
curl -s -X PUT http://localhost:3000/demo/food-nutrients/1 \
  -H "Content-Type: application/json" \
  -d '{"amount": 1.0}'

# Delete (replace 1 with the id from the add response)
curl -s -X DELETE http://localhost:3000/demo/food-nutrients/1
```

Then call `/search?query=test` to see the new or updated food in search results (listener must be running).

### 8. Kibana

Open **http://localhost:5601** to inspect Elasticsearch indices and run queries (e.g. against the food index).

### 9. Tests

Run all tests from the **`app-py`** directory with your virtual environment activated. From inside `app-py`:

```bash
pytest
```

This discovers and runs every test in `tests/` (test_main, test_search, test_ingest, test_listener). No running Docker or app is required—tests use mocks for DB and Elasticsearch. For verbose output use `pytest -v`; to run only one file use e.g. `pytest tests/test_main.py`.

**What the tests cover:**

- **`test_main.py`** — HTTP endpoints: `/health`, `/search` (success, missing/empty query 400, invalid size 400, search failure 503), demo endpoints for foods and food-nutrients (add/update/delete, 200 and 404).
- **`test_search.py`** — Query sanitization, search strategy (ES params, size, hits), search service and response DTOs (nutrient mapping, empty/multiple hits).
- **`test_ingest.py`** — USDA nutrient mapping (valid/invalid amounts, keys, edge cases), reindex (batches, skip invalid rows), upsert (foundation vs non-foundation, delete vs index).
- **`test_listener.py`** — NOTIFY payload parsing (valid/invalid JSON, table, op, fdc_id), processing (foods/food_nutrients insert/update/delete → correct index calls).

All tests use mocks for DB and Elasticsearch where needed, so no running services are required for the test suite.

---

## Design decisions

**Layered architecture.** I follow a layered architecture approach more generally so that services and functionality are easy to debug and scalable in their own sense. I did consider an alternative **more monolithic architecture**, with functionalities bunched together in fewer, coarser modules that would fit the scope of this project and would offer the benefits of simplicity at this scale—easier navigation and fewer files to follow. However, that structure would leave very little room for extension (e.g. adding new search behaviours or new consumers of data changes without touching core flows), so I rejected it in favour of the layered design.

**Specific functionality: Facade, Strategy, and Observer.** The app has two main functional areas: **(1) indexing and search** — getting data into Elasticsearch and querying it; **(2) keeping the search index in sync with the database** — when food data changes in Postgres, the index should reflect that. For each I chose specific design patterns; below are the alternatives I considered, their pros and cons, and why I chose what I did.

**Indexing and search.** For **indexing**, I use a **Facade** (`FoodSearchIndex`) over Elasticsearch so that all index operations (create, bulk index, search, delete) live in one place. For **search**, I use a **Strategy** so that if search needs change later (e.g. different ranking or query behaviour), I can switch the strategy without changing routes or ingest. The **alternative** I considered was a **transaction-script-style** (or direct-usage) design: routes and ingest scripts call the Elasticsearch client directly, with no Facade or strategy abstraction. That approach offers quicker implementation, fewer files, and less indirection; but index and query logic would live in multiple places, making it harder to extend (e.g. new search strategies or indices) and to test in isolation, which did not match my goal of maintainability and extensibility. I chose the Facade and Strategy over it because I wanted one place for all Elasticsearch operations, clear boundaries for testing, and the ability to add or swap search behaviours without touching the rest of the app. Other options I did not adopt: **Template Method** (inheritance-based variation of search logic) is less flexible than Strategy when swapping the whole algorithm; **Decorator** is better for adding behaviour to one implementation than for swapping implementations.

**Keeping the index in sync with the database.** I use an **Observer-style** setup for the **listener**: Postgres triggers emit `NOTIFY` when food or food_nutrient rows change, and an async listener in the app (`FoodChangeListener`) subscribes and updates Elasticsearch. Because the notification mechanism is decoupled, I can add more listeners later (e.g. to update a cache or emit metrics) without changing the write path. The **alternative** I considered was an **explicit in-app Event Bus**: domain events such as `FoodCreated`, `FoodUpdated`, with an event bus and publishers/subscribers inside the app (optionally driven by NOTIFY). The event bus offers greater extensibility and fits event-driven or microservice evolution when many consumers need to subscribe; but it adds more moving parts (event types, bus, registrations) than I need for a single-service app and is heavier to implement at this scope. I chose the Observer-style NOTIFY/LISTEN plus a single listener over the event bus because it gives me live sync with minimal complexity and no extra infrastructure; for this scope its pros outweighed the cons. Other options I did not adopt: **polling** (a scheduled job that periodically syncs DB to ES) would be simpler to reason about but not real-time and would add unnecessary load; **dual write** (every write to the DB also writes to ES in the same request) would avoid NOTIFY but would duplicate write logic and risk inconsistency if one write fails.

---

## Troubleshooting

- **“Cannot connect to the Docker daemon”** — Ensure Docker Desktop (Mac/Windows) or the Docker service (Linux) is running.
- **“role … does not exist”** — Another process may be using the same Postgres port. The Compose file uses port **54328**. Restart clean: `docker compose down --volumes` then `docker compose up -d`.
- **CSV not found** — Ensure `food.csv`, `food_nutrient.csv`, and `nutrient.csv` are in `csv/` at the repo root (or set `CSV_DIR` when running from `app-py`).

---

## Further reading

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)
