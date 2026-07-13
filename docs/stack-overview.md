# Stack Overview — What Each Piece Is and Why It Exists

**Audience:** students meeting the record-shop pipeline for the first time, and
anyone who wants the "why" behind each container before diving into code.
The [architecture spec](architecture-spec.md) is the authoritative contract;
this document is the guided tour.

The business is deliberately boring: an online music store selling fictional
artists' albums as vinyl, CDs, and digital downloads. The *point* is what
happens after someone clicks "checkout" — one order fanning out through nine
systems, observable at every hop.

---

## The one-paragraph version

A React storefront calls a FastAPI backend, which writes an order **and** an
event row to PostgreSQL in a single transaction. A relay process publishes
those event rows to Kafka. From Kafka, a stream processor materializes the
order into MongoDB documents and Redis counters within seconds, while a
Prefect-orchestrated batch job recomputes the same numbers nightly with DuckDB.
Every stage drops a checkpoint onto an audit topic, an audit sink lands those
in MongoDB, and two dashboards (Streamlit for humans tracing events, Grafana
for aggregate health) make the whole journey visible. Docker Compose runs all
of it on one laptop.

```
Storefront ─▶ FastAPI ─▶ PostgreSQL (order + outbox, one tx)
                │              │
              Redis        Outbox Relay ─▶ Kafka ─┬─▶ Stream Processor ─▶ MongoDB + Redis
           (cart, idem.)                          ├─▶ Audit Sink ─▶ MongoDB (pipeline_audit)
                                                  └─▶ orders.dlq (poison messages)
        Prefect worker ── daily_rollup (DuckDB over Postgres) ─▶ MongoDB + Redis
        Streamlit dashboard ◀── Postgres + MongoDB + Redis
        Prometheus ◀── /metrics on every service ──▶ Grafana
```

---

## The stores — three shapes of the same fact

### PostgreSQL 16 — the system of record
Purpose: the one place data is *created*. Normalized relational schema
(`genres → artists → albums → tracks → products`, plus `customers`, `orders`,
`order_items`, `inventory`) with the constraints and transactions that make it
trustworthy. Two design details carry most of the teaching load:

- The **`outbox` table**: when the API creates an order, it inserts the order
  rows and an outbox row *in the same transaction*. Either both exist or
  neither does. This is the transactional outbox pattern — the answer to "why
  can't I just publish to Kafka after commit?" (a crash between commit and
  publish would silently lose the event).
- The **`inventory` table only has rows for physical formats**. Vinyl and CDs
  decrement stock; digital downloads are infinite. This asymmetry ripples
  through every downstream component and keeps the modeling honest.

### MongoDB 7 — the read-optimized document store
Purpose: hold data *shaped for reading*, not for integrity. The stream
processor writes `order_view` documents — order + customer + every item's
artist/album/format denormalized into one document, so rendering an order
needs zero joins. Batch writes `daily_reports`. The audit sink writes
`pipeline_audit` (every checkpoint, indexed by `event_id`) — the data behind
the dashboard's Pipeline tab. Same facts as Postgres, different shape,
different purpose: that contrast *is* the polyglot-persistence lesson.

### Redis 7 — the key-value edge
Purpose: everything that must be fast and is allowed to be ephemeral. Session
carts, idempotency keys (`SETNX` so a double-clicked checkout creates one
order), live counters (`INCR` orders/revenue today), and sorted-set
leaderboards (`ZINCRBY` top albums/artists). Redis is the "as of right now"
store; when the numbers matter historically, they belong elsewhere.

---

## The write path — from click to commit

### Storefront (React + Vite, TypeScript strict) — port 5173
Purpose: generate real user behavior. Catalog browsing, album pages, cart,
checkout, plus clickstream telemetry (`page_view`, `track_preview`,
`add_to_cart`) fired at the API's `/events` endpoint. It is deliberately
small — the only non-Python code in the repo. Its typed API client
(`src/api/types.ts`) mirrors the FastAPI Pydantic models one-to-one, so the
contract between front end and back end is checked by two compilers.

### FastAPI backend — port 8000
Purpose: the edge where events are *born*. Three responsibilities that define
the whole pipeline's semantics:

1. **Mints the correlation IDs.** Every order gets a ULID `event_id` and an
   OpenTelemetry `trace_id` at creation. These travel with the event through
   every subsequent system — they are what makes one order traceable across
   nine services.
2. **Writes order + outbox atomically** (the pattern above).
3. **Enforces idempotency** at the door via Redis idempotency keys.

It never talks to Kafka on the request path. The user's checkout depends only
on Postgres and Redis being up.

---

## The event backbone — decoupling producers from consumers

### Outbox relay (CDC-lite, Python)
Purpose: move committed events from Postgres to Kafka, and teach what CDC
tools like Debezium do under the hood. A small loop:
`SELECT … WHERE published_at IS NULL FOR UPDATE SKIP LOCKED` → publish →
mark published. If it crashes between publish and mark, the event is published
*again* on restart — which is why the system guarantees **at-least-once**
delivery and why every consumer must be idempotent. That trade-off is chosen,
not accidental. (Operational scar tissue: the relay's connection must be
`autocommit=True`; see `progress.md` for the lock-contention story.)

### Apache Kafka (KRaft, single broker) — ports 9092 / 29092
Purpose: the buffer that decouples producers from consumers in time. Five
topics: `orders.created` and `orders.status` (business events),
`clickstream.events` (telemetry), `pipeline.audit` (checkpoints from every
stage), `orders.dlq` (poison messages). Because Kafka retains messages,
consumers can die and catch up — the classroom's favorite demo is stopping the
stream processor, placing orders, watching consumer lag grow on Grafana, then
restarting and watching it drain. Correlation IDs ride in **Kafka message
headers**, which is how traceability survives the async hop.

---

## The read paths — the same numbers, two ways

### Stream processor (hand-rolled Python consumer)
Purpose: freshness. Consumes `orders.created` + `clickstream.events` and,
within ~2 seconds of checkout, upserts the denormalized `order_view` into
MongoDB and increments Redis counters/leaderboards. Hand-written (no
framework) so the mechanics stay visible: polling, manual offset commits
*after* successful processing, consumer groups, and the two failure lanes —

- **Poison messages** (malformed payload, will never succeed) → produced to
  `orders.dlq` with a `dlq.captured` checkpoint; the consumer moves on.
- **Transient failures** (Mongo down) → no commit, back off, retry. Kafka
  redelivers.

Its idempotency gate — `$setOnInsert` upsert keyed by `event_id`, replays are
no-ops — is what makes at-least-once delivery safe. It also exports
`kafka_consumer_lag` from its own partition assignment, the single most
important stream-health number.

### Prefect 3 + DuckDB — the batch path (Prefect UI on port 4200)
Purpose: correctness on a schedule, and a second ops surface. All *finite*
work runs as Prefect flows on a worker container:

- **`daily_rollup_flow`** (nightly): DuckDB reads Postgres directly and
  computes revenue by day/genre/format, top artists, customer lifetime value,
  inventory turnover, and preview→purchase funnels into Mongo
  `daily_reports`. Watermarked, retried, idempotent to re-run.
- **`backfill_flow`**: re-runs rollups for a past date range (parameters +
  idempotent overwrite).
- **`reconciliation_flow`** (hourly): compares stream-computed Redis revenue
  to a direct SQL sum and **fails loudly past a drift threshold** — data
  quality as a gate, not a report.
- **`dlq_replay_flow`**: drains the DLQ, recovers what it can, reports the
  rest.
- **`seed_flow`**: even environment setup is orchestrated.

The rollup deliberately recomputes numbers the stream path already produced.
Stream says "now" and drifts under failure; batch says "as of last run" and
self-heals on re-run. Seeing them disagree intra-day — and understanding why —
is the lambda-architecture lesson in miniature.

**The dividing line** (a design rule, not a preference): long-running Kafka
consumers are Compose services supervised by restart policies and measured by
consumer lag; finite jobs are Prefect flows measured by run history. Wrapping
a Kafka consumer in a Prefect flow blurs that line and is called out in class
as an anti-pattern.

---

## The observability layer — designed in, not bolted on

### The audit trail (`pipeline.audit` topic + audit sink)
Purpose: make every hop a recorded fact. Every stage emits a checkpoint —
`{event_id, trace_id, stage, status, ts, latency_ms_from_prev, service}` —
fire-and-forget, so the audit trail can never block or fail the business path
(with Kafka down, orders still succeed; the API just logs a warning). The
**audit sink** consumer lands checkpoints in Mongo `pipeline_audit` and
re-exports them as Prometheus metrics (per-stage throughput and hop-latency
histograms, batch staleness, reconciliation drift). One data set feeds both
per-event tracing and aggregate health.

### Streamlit dashboard — port 8501
Purpose: the *human* view, in pure Python so students can extend it.
- **Business tab**: live Redis KPIs ("as of now — stream") beside Mongo batch
  reports ("as of last run — batch"), auto-refreshing so the stream side
  visibly moves while the batch side visibly doesn't.
- **Pipeline tab** — the visibility centerpiece: a live flow diagram of every
  stage (throughput, hop latency, green/grey/red health) plus per-event
  tracing — pick a recent event or paste an `event_id` right after checkout
  and watch its checkpoints arrive stage by stage.
- **Data explorer tab**: one order shown simultaneously as Postgres rows, a
  Mongo document, and Redis keys — polyglot persistence, live.

### Prometheus + Grafana — ports 9090 / 3000
Purpose: the *aggregate* view. Prometheus scrapes `/metrics` on every Python
service; Grafana ships pre-provisioned with 13 panels: order rate, outbox
backlog (the "pipeline is backing up" gauge), consumer lag, DLQ depth,
per-stage throughput and latency from the audit trail, batch staleness,
stream-vs-batch drift, and the star metric — **end-to-end latency, checkout
click to Mongo document, target < 2s**.

### Structured JSON logs
Every service logs JSON to stdout with `event_id`/`trace_id` on every line, so
`docker compose logs | grep <event_id>` is itself a distributed trace — the
zero-tooling fallback that always works.

---

## The supporting cast

- **Traffic simulator** (opt-in: `docker compose --profile traffic up -d simulator`)
  places synthetic orders using the same Zipf popularity weights as the seeded
  catalog, so leaderboards and funnels show recognizable patterns during demos.
- **Seeded catalog** (`libs/common/seeding.py`, `RANDOM_SEED=1138`): ~12
  genres, ~150 fictional artists, ~400 albums, ~900 products — byte-identical
  on every machine, so lecture references and eval assertions match what every
  student sees.
- **`libs/common/`**: the shared vocabulary — checkpoint emitter, JSON logger,
  Prometheus metric definitions, ID minting, seeding — imported by every
  service so cross-cutting behavior stays consistent.
- **Evals** (`evals/phase1..6`, ~36 pytest assertions): the definition of
  done. Each phase's evals assert observable behavior — atomicity by failure
  injection, idempotency by replay, catch-up by killing the processor —
  against the *running* stack, not mocks.
- **Docker Compose**: 16 services, one command, no cloud accounts. Healthcheck
  ordering makes cold start deterministic.

---

## How it combines into a pipeline

Follow one checkout and every component appears in order:

1. **Storefront** POSTs the order; **FastAPI** mints `event_id`/`trace_id`,
   checks the Redis idempotency key, and commits order + outbox row to
   **Postgres** in one transaction. Checkpoints: `api.received`,
   `db.committed`. The user has their confirmation — nothing downstream can
   take that away.
2. The **outbox relay** publishes the row to **Kafka** with the IDs in
   headers (`outbox.published`). At-least-once from here on.
3. The **stream processor** consumes it, denormalizes into Mongo `order_view`,
   increments Redis counters (`stream.consumed`, `stream.mongo_upsert`,
   `stream.redis_update`) — duplicates are no-ops, garbage goes to the DLQ.
   Elapsed: about a second.
4. That night (or on demand), the **Prefect rollup** recomputes the day from
   Postgres via DuckDB into `daily_reports` (`batch.included`), and the
   **reconciliation flow** checks that stream and SQL still agree.
5. Throughout, every checkpoint has landed in **Mongo** via the audit sink and
   in **Prometheus** as metrics — so the **Streamlit** Pipeline tab can replay
   this exact order's journey, and **Grafana** shows its dot on the
   end-to-end latency panel.

The architecture holds together because of four decisions applied everywhere,
which is why the system stays comprehensible at 16 services:

1. **Correlation IDs are minted once, at the edge, and never dropped** —
   traceability is a property of the data, not of any tool.
2. **State changes and event publication are atomic** (outbox) — downstream
   systems can trust that every committed order eventually becomes an event.
3. **Delivery is at-least-once and every consumer is idempotent** — the
   pragmatic distributed-systems trade, made explicitly and handled uniformly.
4. **Observability rides sidecar** — checkpoints are fire-and-forget, so the
   thing watching the pipeline can never break the pipeline.

Remove any one component and a specific, nameable capability dies with it —
which is the best evidence each one is earning its place.
