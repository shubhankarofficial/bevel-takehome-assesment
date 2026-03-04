## Design Options Considered

This document records the main architectural options we considered for the assignment, along with pros and cons, and the chosen approach. It is meant as talking material to explain tradeoffs and future extensibility.

---

### Option 1: Layered OO with Facade + Observer-style (baseline)

**Description**

- Use a classic layered design:
  - FastAPI routes (presentation layer)
  - Service layer (`SearchService`, `IngestService` / `IngestPipeline`)
  - Repository layer (`FoodRepository`, `FoodNutrientRepository`, etc.)
  - Infrastructure layer (Postgres pool, Elasticsearch client)
- Add a **Facade** over Elasticsearch for the food index (e.g. `FoodSearchIndex`) that hides all index operations (create, bulk index, search, delete).
- Use **Observer-style** behavior via Postgres `NOTIFY/LISTEN`:
  - Database triggers emit `NOTIFY` when food data changes.
  - An async listener in the app (`FoodChangeListener`) reacts and updates Elasticsearch.

**Pros**

- Clear separation of concerns:
  - Routes are thin: parse HTTP, call a service, return response.
  - Services implement use cases.
  - Repositories own SQL and data mapping.
  - Elasticsearch details are isolated behind the Facade.
- Easy to reason about and explain in an interview.
- Good foundation for extension:
  - New endpoints → new services, reuse repositories and Facade.
  - New consumers of DB changes can hook into the same NOTIFY mechanism.

**Cons**

- Requires a bit more structure (several modules/classes) compared to a very minimal implementation.
- Search behavior is still baked into a single implementation inside the Facade; changing it is possible but not pluggable by design.

---

### Option 2: Layered OO + Facade + Observer-style + Strategy for search (chosen)

**Description**

- Start from Option 1 (layered, Facade, Observer-style) and add a **Strategy pattern** for search behavior:
  - Define a `SearchStrategy` interface/protocol with a method like `search(query: str, size: int)`.
  - Implement concrete strategies, e.g.:
    - `SimpleTextSearchStrategy` — basic BM25 match with optional fuzziness on the food name.
    - Future strategies (not required now) such as `NutrientAwareSearchStrategy`, `PrefixSearchStrategy`, etc.
  - `SearchService` depends on a `SearchStrategy` (injected), which internally uses the `FoodSearchIndex` Facade to talk to Elasticsearch.
- Keep **Observer-style** reindexing via Postgres `NOTIFY/LISTEN` and a `FoodChangeListener`.

**Pros**

- All the benefits of Option 1 (clear layering, Facade, Observer-style sync).
- Search behavior is explicitly pluggable:
  - Easy to change how ranking works without touching routes or DB code.
  - Easy to A/B test or configure different strategies (e.g. strict vs fuzzy search).
- Very nice story for future extensibility:
  - New search features or ranking algorithms can be added as new strategies.

**Cons**

- Slightly more indirection: one more abstraction layer around search.
- For a simple assignment, only one concrete strategy is strictly needed (others remain conceptual/extensions).

---

### Option 3: Minimalistic / direct usage (no Facade, minimal patterns)

**Description**

- Keep the project very simple:
  - Routes might directly use the Postgres pool and Elasticsearch client.
  - A small helper or two, but no explicit repository/service layers.
  - Elasticsearch is used directly in `/search` and the ingestion script, without a dedicated Facade.
- Dynamic reindexing, if implemented, calls the Elasticsearch client directly from the `LISTEN` loop.

**Pros**

- Fastest to implement with the fewest files and classes.
- Less indirection; beginners may find it easier to follow small scripts.

**Cons**

- Harder to extend:
  - Search logic and ES queries can end up scattered in multiple places.
  - Changes to ES mappings or queries may require touching routes and ingest code.
- Less clearly structured for a production-like system:
  - No obvious place to plug in new features.
  - Harder to test in isolation (e.g. no clear repository or service boundaries).
- Not aligned with the assignment’s emphasis on design, maintainability, and extensibility.

---

### Option 4: Event-first / explicit Event Bus (strong Observer flavor)

**Description**

- Make events a first-class concept inside the application, not just rely on Postgres NOTIFY:
  - Define `DomainEvent` types, such as `FoodCreated`, `FoodUpdated`, `FoodDeleted`.
  - Implement an `EventBus` that lets components publish events and subscribe listeners.
  - Repositories or services publish domain events whenever they modify food data.
  - `FoodSearchIndexUpdater` subscribes to these events and updates Elasticsearch.
- Optionally integrate Postgres `NOTIFY/LISTEN` with the event bus:
  - Postgres emits `NOTIFY`.
  - The listener pushes corresponding domain events into the internal bus.

**Pros**

- Very extensible and scalable architectural style:
  - New features that react to changes simply subscribe to relevant events (e.g. metrics, audit logs, cache invalidation, downstream queues).
- Clear conceptual model for moving towards event-driven or microservice architectures.

**Cons**

- Higher complexity and more plumbing (EventBus, event definitions, registrations) than needed for a single-service take-home.
- Can feel over-engineered given the assignment scope and time constraints.
- More moving parts to explain in a walkthrough.

---

### Why Option 2 Was Chosen

**Chosen design:** Option 2 — Layered OO design with:

- **Repository** layer for data access (Postgres).
- **Service** layer for use-case logic (ingest and search).
- **Facade** (`FoodSearchIndex`) over Elasticsearch for index operations.
- **Observer-style** sync between Postgres and Elasticsearch using `NOTIFY/LISTEN` and a listener component.
- **Strategy** pattern for search behavior, with at least one concrete strategy implemented now and the possibility of adding more in the future.

**Rationale:**

- **Extensibility:** Adding new search behaviors, endpoints, or consumers of DB changes is straightforward within this structure.
- **Clarity:** Each layer and component has a well-defined responsibility that is easy to explain during a code walkthrough.
- **Pragmatism:** It uses a few well-known patterns (Facade, Strategy, Observer-style, Repository/Service layering) without introducing a full event bus or other heavy infrastructure that would be disproportionate to the assignment.

