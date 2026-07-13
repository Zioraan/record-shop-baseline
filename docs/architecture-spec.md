# E-Commerce Data Pipeline — Architecture Specification

**Purpose:** Classroom demonstration architecture for teaching data pipelines end-to-end: OLTP writes, change propagation, stream processing, batch processing, and multi-store persistence (SQL → NoSQL → key-value), with first-class observability so students can *watch* data move through every stage.

**Domain:** The example business is an **online music store** ("the record shop") selling albums and tracks in physical formats (vinyl, CD) and digital downloads. The domain gives the catalog a natural hierarchy (genre → artist → album → track), analytics questions students grasp instantly (top artists, vinyl vs. digital revenue), and a built-in modeling wrinkle: physical formats carry real inventory while digital products have infinite stock.

**Status:** v1.3 — approved direction (Python-centric back end, TypeScript storefront, Docker Compose, Kafka, Prefect for batch orchestration; online music store domain). July 2026.

---

## 1. Guiding Principles

1. **Every hop is observable.** Each record carries a correlation ID from the moment it's created in the storefront until it lands in its final store. Students can trace a single order across all systems.
2. **One command to run.** `docker compose up` brings up the entire platform on a student laptop. No cloud accounts, no cost.
3. **Simple enough to read, real enough to matter.** Each component uses the smallest tool that still teaches the industry-standard pattern (e.g., a hand-written Kafka consumer before introducing a framework).
4. **Stream and batch side by side.** The same source data feeds both a real-time path and a nightly batch path, so students can compare freshness, complexity, and failure modes directly.

---

## 2. High-Level Data Flow

```
[Storefront UI] ──REST──▶ [FastAPI Backend] ──SQL writes──▶ [PostgreSQL (OLTP + outbox)]
                                                                    │
                                                     [Outbox Relay (CDC-lite, Python)]
                                                                    │ publish
                                                                    ▼
                                                            [Kafka topics]
                                                        ┌───────┴────────┐
                                              (stream path)        (audit path)
                                                        │                │
                                        [Stream Processor (Python)]  [pipeline.audit topic]
                                             │            │                │
                                     ┌───────┘            └──────┐        │
                                     ▼                           ▼        ▼
                              [Redis (KV)]                [MongoDB (NoSQL)]◀── audit trail
                          live counters, cache,        denormalized order docs,
                          carts, leaderboards          real-time aggregates
                                                                 ▲
                                              (batch path)       │
                     [Batch Job (Python/DuckDB, nightly)] ───────┘
                     reads PostgreSQL → daily rollups → MongoDB + Redis

[Reporting Dashboard] ◀── reads MongoDB + Redis + Postgres (incl. pipeline trace views)
[Prometheus + Grafana] ◀── scrapes metrics from every service
```

---

## 3. Tech Stack

| Layer | Technology | Why this choice for a classroom |
|---|---|---|
| Consumer front-end | **React + Vite (TypeScript)** | Standard SPA storefront; kept deliberately small (catalog, cart, checkout). Typed API client mirrors the FastAPI Pydantic models. |
| Reporting front-end | **Streamlit** (Python) | Employees'/analysts' view. Pure Python — students extend it without learning a second front-end framework. |
| API backend | **FastAPI** (Python 3.12) + SQLAlchemy + Pydantic | Async, typed, auto-generated OpenAPI docs students can explore. |
| OLTP database | **PostgreSQL 16** | The system of record. Normalized relational schema + transactional outbox table. |
| Event backbone | **Apache Kafka** (single broker, KRaft mode — no ZooKeeper) | Industry standard. Redpanda is a documented drop-in substitute if laptop resources are tight. |
| Change capture | **Transactional outbox + Python relay** | Teaches the *pattern* behind CDC explicitly. Debezium is listed as a stretch extension. |
| Stream processing | **Python consumer services** (`confluent-kafka`) | Hand-rolled consumer first (visible mechanics: polling, offsets, commits); Faust/Flink noted as extensions. |
| Batch orchestration | **Prefect 3** (server + worker in Compose) | All batch-style work runs as Prefect flows: scheduling, retries, run history, and a UI students use as a second observability surface. |
| Batch processing | **Python + DuckDB** inside Prefect tasks | DuckDB reads Postgres directly and makes analytical SQL fast and legible. |
| NoSQL store | **MongoDB 7** | Denormalized order documents and analytics aggregates; shows document modeling vs. relational. |
| Key-value store | **Redis 7** | Live counters, product cache, session carts, top-sellers leaderboard, idempotency keys. |
| Telemetry | **OpenTelemetry SDK → Prometheus + Grafana**; structured JSON logs | Traces, metrics, and logs correlated by `trace_id`. Grafana ships with pre-built class dashboards. |
| Orchestration | **Docker Compose** | One file, one command, ~11 services. |

Everything back-end is Python; the only non-Python code is the TypeScript storefront UI.

---

## 4. Components & Features

### 4.1 Storefront (consumer front-end)
- Music catalog browsing and search: by genre, artist, album, and format (vinyl / CD / digital), with reads via FastAPI from Postgres and Redis cache-aside for hot album pages.
- Cart (stored in Redis, keyed by session — demonstrates KV as ephemeral state). A cart can mix physical and digital items.
- Checkout → creates an order (the canonical "event" that flows through the whole pipeline). Physical items decrement inventory; digital items don't.
- Emits client telemetry events (`page_view`, `track_preview`, `add_to_cart`, `checkout_started`) via a `/events` endpoint — feeds the clickstream topic. `track_preview` (30-second sample plays) gives the funnel an extra, music-specific stage: browse → preview → cart → purchase.

### 4.2 FastAPI backend
- REST endpoints: `products`, `cart`, `orders`, `events`.
- Writes orders to Postgres **in the same transaction** as an outbox row (the transactional outbox pattern — the key teaching moment for reliable event publishing).
- Generates the **correlation ID** (`event_id` + OpenTelemetry `trace_id`) at the edge; it travels in Kafka headers thereafter.
- Idempotent order creation using Redis `SETNX` idempotency keys.

### 4.3 PostgreSQL (system of record)
- Normalized music-domain schema: `artists`, `albums`, `tracks`, `genres`, `products` (an album/track in a specific format — vinyl, CD, digital — each with its own SKU and price), `customers`, `orders`, `order_items`, `inventory` (physical formats only).
- `outbox` table: `(id, aggregate_type, aggregate_id, event_type, payload jsonb, trace_id, created_at, published_at)`.
- Schema created by `infra/postgres/init.sql`; data population is done by Prefect's `seed_flow` (see §4.9), keeping DDL and data loading separate.
- A **traffic simulator** container continuously places synthetic orders so the pipeline is always alive during demos.

### 4.4 Outbox relay (CDC-lite)
- Small Python loop: `SELECT ... FROM outbox WHERE published_at IS NULL FOR UPDATE SKIP LOCKED` → publish to Kafka → mark published.
- Teaches at-least-once delivery and why consumers must be idempotent.

### 4.5 Kafka topics
| Topic | Producer | Contents |
|---|---|---|
| `orders.created` | outbox relay | Full order payload |
| `orders.status` | backend/relay | Status transitions (paid, shipped…) |
| `clickstream.events` | FastAPI `/events` | Page views, cart events |
| `pipeline.audit` | **every stage** | Checkpoint records (see §6) |
| `orders.dlq` | stream processor | Poison messages — teaches dead-letter handling |

### 4.6 Stream processor (real-time path)
- Consumes `orders.created` + `clickstream.events`.
- Writes to **MongoDB**: denormalized `order_view` documents (order + customer + items with artist/album/format in one doc) and rolling `sales_by_minute` aggregates.
- Writes to **Redis**: `INCR` live counters (orders today, revenue today, revenue by format), `ZINCRBY` sorted sets for top-selling albums and top artists, cache invalidation for changed album pages.
- Demonstrates: consumer groups, offset commits, idempotent upserts, DLQ on bad payloads, backpressure via consumer lag.

### 4.7 Batch path (Prefect-orchestrated)
The nightly rollup is a **Prefect flow** (`daily_rollup_flow`) with one task per logical step, so the DAG students see in the Prefect UI mirrors the data flow:

```
extract_watermark → extract_from_postgres (DuckDB) → transform_rollups
    → load_mongo_reports → refresh_redis_keys → emit_audit_manifest → data_quality_checks
```

- DuckDB work (revenue by day/genre/format, top artists, customer lifetime value, vinyl inventory turnover, preview→purchase funnels) lives inside Prefect tasks with retries + exponential backoff configured declaratively.
- Scheduled via a Prefect deployment (nightly cron) and runnable on demand from the Prefect UI or a "Run batch now" button in the reporting dashboard.
- `emit_audit_manifest` writes the run manifest (rows read/written, duration, watermark, `flow_run_id`) to `pipeline.audit` — batch runs appear in the same trace timeline as stream events, and the checkpoint links back to the Prefect flow-run URL.
- Deliberately re-computes some numbers the stream path also produces, so students can compare stream vs. batch answers and discuss consistency/lateness.

**Other Prefect flows** (each is a self-contained exercise):
- `backfill_flow` — parameterized by date range; re-runs rollups idempotently for past days (teaches parameters + idempotent overwrite).
- `dlq_replay_flow` — drains `orders.dlq`, attempts reprocessing, reports what was recovered (manual trigger).
- `reconciliation_flow` — compares stream-computed vs. batch-computed revenue and emits the drift metric; fails loudly past a threshold (teaches data-quality gating).
- `seed_flow` — one-shot database seeding, so even environment setup demonstrates orchestration.

**Where Prefect deliberately does *not* go:** the FastAPI backend, outbox relay, and stream processor stay as always-on services. A key lesson of the architecture is the distinction between long-running stream consumers (supervised by Compose, measured by consumer lag) and finite scheduled jobs (orchestrated by Prefect, measured by run history) — putting a Kafka consumer inside a Prefect flow blurs that line and is called out in class as an anti-pattern.

### 4.8 Reporting dashboard (employee front-end, Streamlit)
- **Business tab:** sales KPIs from Redis (live) and MongoDB (historical) side by side — labeled "as of now (stream)" vs "as of last batch".
- **Pipeline tab (the visibility centerpiece):** paste any `event_id` and see its full journey — every checkpoint, per-stage latency, and current location. Plus stage health: events/min per stage, DLQ depth, consumer lag.
- **Data explorer tab:** raw peeks into Postgres rows, Mongo documents, and Redis keys for the same order — shows how one fact is shaped differently per store.

### 4.9 Catalog & seed data strategy (music store)
Catalog data is **generated, deterministic, and expansive**, produced by Prefect's `seed_flow`. All artists, albums, and tracks are *fictional* — generated from genre-specific name templates — so there are no licensing questions and the data is stable forever.

- **Generator:** Faker + hand-curated genre templates. Default catalog: ~12 genres → ~150 fictional artists → ~400 albums → ~4,000 tracks. Each album exists in 1–3 formats (vinyl / CD / digital), each format a distinct SKU-bearing `product` row — so the sellable catalog lands around 700–900 products. Plus ~200 customers with varied signup dates and ~30 days of historical orders + clickstream so the batch path is interesting on day one.
- **Fixed random seed:** every student's machine generates the *identical* catalog. Lecture references ("look up `SKU-00042`" or "the top-selling vinyl in Jazz") and exercise-sheet expected answers match what students see.
- **Realistic distributions:** genre-appropriate log-normal pricing (vinyl > CD > digital for the same album); Zipf-distributed artist popularity so a handful of fictional "hit" artists dominate sales over a long tail. Release dates spread over decades, enabling catalog-vs-new-release analytics. The traffic simulator consumes the *same* popularity weights when placing orders and previewing tracks, so leaderboards, preview→purchase funnels, and CLV produce recognizable patterns instead of flat noise.
- **Physical vs. digital:** only vinyl/CD rows get `inventory` records; digital SKUs are infinite-stock. This asymmetry feeds distinct lessons — inventory turnover applies to a subset of the catalog, and the stream processor's stock-decrement logic branches by format.
- **Parameterized:** `seed_flow` accepts scale knobs (`--artists 1000`, `--history-days 90`) for load-testing exercises. Re-running is idempotent (truncate-and-reload or upsert by SKU).
- **Album art:** SVG covers generated deterministically from the album ID (color/pattern hash) — the storefront looks alive with no binary assets in the repo.
- **Stretch exercise:** swap the generated catalog for a real open dataset — the classic **Chinook** music-store database is a natural fit, or MusicBrainz / Spotify chart data — and handle the messiness: schema mapping, cleaning, and volume become the lesson.

---

## 5. Telemetry Points

Instrument with OpenTelemetry (metrics + traces) and structured JSON logs. Prometheus scrapes; Grafana dashboards ship pre-built.

**Edge / API**
- `http_request_duration_seconds` (per route, P50/P95/P99)
- `orders_created_total`, `order_create_failures_total`
- `idempotency_conflicts_total`

**Outbox / Kafka**
- `outbox_unpublished_rows` (gauge — the "pipeline is backing up" signal)
- `outbox_publish_latency_seconds` (DB commit → Kafka ack)
- `kafka_consumer_lag` per consumer group (the single most important stream-health metric)
- `dlq_messages_total`

**Stream processor**
- `events_processed_total` / `event_processing_duration_seconds` per topic
- `mongo_upsert_duration_seconds`, `redis_write_duration_seconds`
- `processing_failures_total` by error class

**Batch job**
- `batch_job_duration_seconds`, `batch_rows_read/written`
- `batch_last_success_timestamp` (staleness alerting)
- Stream-vs-batch drift: |stream revenue − batch revenue| for the same day

**Stores**
- Redis cache hit ratio; Postgres connection pool saturation; Mongo write latency

**End-to-end (the star metric)**
- `pipeline_end_to_end_latency_seconds`: checkout click → document visible in MongoDB. Derived from audit checkpoints; graphed in Grafana. Target < 2s on the stream path.

**Traces:** one OpenTelemetry trace spans storefront request → FastAPI → Postgres commit; the `trace_id` is stored in the outbox row and propagated through Kafka headers so the async hops are linked to the originating request.

---

## 6. Pipeline Logging & Visibility (the teaching layer)

Every stage emits a **checkpoint record** to the `pipeline.audit` Kafka topic (and to its own structured log):

```json
{
  "event_id": "ord_01J9XK...",
  "trace_id": "4bf92f35...",
  "stage": "stream.mongo_upsert",        // api.received | db.committed | outbox.published |
                                          // stream.consumed | stream.mongo_upsert |
                                          // stream.redis_update | batch.included | dlq.captured
  "status": "ok",                         // ok | retried | failed
  "ts": "2026-07-10T14:03:22.114Z",
  "latency_ms_from_prev": 41,
  "service": "stream-processor",
  "detail": {"collection": "order_view"}
}
```

A tiny **audit sink** consumer writes these into MongoDB (`pipeline_audit` collection, indexed by `event_id`). The Streamlit Pipeline tab queries it to render the per-event journey timeline; Grafana aggregates it for stage-level throughput and latency heatmaps.

Rules:
- Checkpoints are fire-and-forget (must never block or fail the business path).
- All services log JSON to stdout with `event_id`/`trace_id` fields; `docker compose logs` is therefore itself a grep-able trace: `docker compose logs | grep ord_01J9XK`.
- Failures emit `status: "failed"` checkpoints *and* route the message to the DLQ, so lost data is visible, not silent.

---

## 7. Stream vs. Batch — the explicit comparison

| | Stream path | Batch path |
|---|---|---|
| Trigger | Every event, immediately | Prefect schedule (nightly) or on-demand run |
| Engine | Python Kafka consumer | Prefect flow: Python + DuckDB over Postgres |
| Ops surface | Grafana consumer lag | Prefect UI run history + retries |
| Freshness | ~seconds | Up to 24h stale |
| Output | Redis counters, Mongo `order_view` + `sales_by_minute` | Mongo `daily_reports`, CLV, funnels |
| Teaches | Offsets, consumer groups, idempotency, DLQ, lag | Watermarks, full-recompute vs incremental, run manifests |
| Failure mode demo | Kill the processor → watch lag grow → restart → catch-up | Corrupt a run → re-run job → idempotent overwrite |

Classroom exercise: stop the stream processor mid-demo, place orders, show Redis frozen while Postgres grows, then restart and watch it catch up — consumer lag on Grafana tells the whole story.

---

## 8. Repository & Deployment Layout

```
ecommerce-pipeline/
├── docker-compose.yml            # postgres, kafka, mongo, redis, api, relay,
│                                 # stream-processor, prefect-server, prefect-worker,
│                                 # audit-sink, storefront, dashboard,
│                                 # prometheus, grafana, simulator
├── services/
│   ├── api/                      # FastAPI
│   ├── outbox-relay/
│   ├── stream-processor/
│   ├── flows/                    # Prefect flows: daily_rollup, backfill,
│   │                             # dlq_replay, reconciliation, seed
│   ├── audit-sink/
│   └── simulator/                # synthetic traffic generator
├── frontends/
│   ├── storefront/               # React + Vite (TypeScript)
│   └── dashboard/                # Streamlit
├── infra/
│   ├── postgres/init.sql         # schema + seed
│   ├── grafana/dashboards/       # pre-provisioned JSON dashboards
│   └── prometheus/prometheus.yml
└── docs/                         # this spec, exercise sheets, runbooks
```

Resource note: full stack targets ≤ ~4 GB RAM. If student laptops struggle, swap Kafka → Redpanda (compose override file provided).

---

## 9. Suggested Build Milestones

1. **M1 — System of record:** Postgres schema + FastAPI CRUD + storefront checkout; JSON logging with `event_id` from day one.
2. **M2 — Events:** outbox table + relay + Kafka; audit topic and audit sink; first end-to-end trace visible.
3. **M3 — Stream path:** stream processor → Mongo + Redis; DLQ; dashboard Pipeline tab.
4. **M4 — Batch path with Prefect:** Prefect server/worker in Compose; `daily_rollup_flow` with retries + schedule + run manifests; stream-vs-batch comparison views.
5. **M5 — Orchestration depth:** `backfill_flow`, `reconciliation_flow` (data-quality gating), `dlq_replay_flow`.
6. **M6 — Observability polish:** OpenTelemetry traces, Grafana dashboards, failure-injection exercises.

**Stretch extensions:** Debezium instead of the hand-rolled relay; Faust or Flink for windowed aggregations; schema registry + Avro; Prefect work pools with multiple workers; Kubernetes deployment.

---

## 10. Key Teaching Moments Baked Into the Design

- **Transactional outbox** — why you can't "just publish to Kafka after commit."
- **At-least-once + idempotency** — duplicates are a feature of the design, handled explicitly.
- **Polyglot persistence** — the same order as a normalized row set, a denormalized document, and a set of counters.
- **Lambda-style duality** — stream and batch computing the same numbers, disagreeing, and why.
- **Observability as architecture** — correlation IDs and checkpoints designed in, not bolted on.
