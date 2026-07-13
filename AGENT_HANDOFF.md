# Agent Hand-Off — E-Commerce Music Store Pipeline

**Audience:** AI coding agents (Cursor) and the students driving them.
**Companion doc:** `architecture-spec.md` (v1.2) — the authoritative architecture. This document tells an agent *how to build it, in what order, and how to prove each phase works*.
**How to use:** Load this file (and the spec) into the agent's context at the start of every session. Work on exactly one phase at a time. A phase is complete only when **all of its evals pass**. Do not start phase N+1 with failing evals in phase N.

---

## 1. Project Context (read first)

You are building a classroom demonstration system: an **online music store** ("the record shop") selling fictional artists' albums as vinyl, CD, and digital downloads. The pedagogical goal is not the store — it is the **data pipeline behind it**: OLTP writes → transactional outbox → Kafka → stream processing → MongoDB + Redis, alongside a Prefect-orchestrated batch path, with every hop observable via correlation IDs and audit checkpoints.

The system runs entirely in **Docker Compose** on a student laptop. There are no cloud dependencies. Everything backend is **Python 3.12**; the storefront is **React + Vite in TypeScript** (strict mode; `tsc --noEmit` must pass — treat type errors as build failures).

**Non-negotiable design principles** (violating these is a defect even if features work):

1. Every business event carries an `event_id` and OpenTelemetry `trace_id` from creation to final store; async hops propagate both via Kafka headers.
2. Order + outbox row are written in the **same Postgres transaction**. Never publish to Kafka directly from the API request path.
3. Consumers are **idempotent** (at-least-once delivery is assumed everywhere).
4. Every pipeline stage emits a fire-and-forget **checkpoint** to `pipeline.audit`; checkpoints must never block or fail the business path.
5. All services log **structured JSON to stdout** with `event_id`/`trace_id` fields.
6. Long-running consumers are Compose services; finite jobs are **Prefect flows**. Never wrap a Kafka consumer in a Prefect flow.

---

## 2. Architecture Contract (summary — spec is authoritative)

```
Storefront (React:5173) ──▶ FastAPI (:8000) ──tx──▶ PostgreSQL (:5432, + outbox)
                                 │                        │
                                 │ cart/idempotency   Outbox Relay
                                 ▼                        │
                            Redis (:6379) ◀─┐             ▼
                                            │      Kafka (:9092)
                                            │   topics: orders.created, orders.status,
                                            │   clickstream.events, pipeline.audit, orders.dlq
                                            │             │
                              Stream Processor ◀──────────┤
                                            │             └──▶ Audit Sink ──▶ MongoDB
                                            └──▶ MongoDB (:27017)
Prefect (:4200) ──schedules──▶ flows/ (daily_rollup, backfill, dlq_replay, reconciliation, seed)
Dashboard (Streamlit:8501) ◀── reads Postgres + MongoDB + Redis
Prometheus (:9090) ──▶ Grafana (:3000)
```

**Repository layout** (create exactly this; agents must not invent alternative structures):

```
ecommerce-pipeline/
├── docker-compose.yml
├── Makefile                      # make up / down / eval PHASE=n / logs / seed
├── AGENT_HANDOFF.md              # this file
├── docs/architecture-spec.md
├── services/
│   ├── api/                      # FastAPI
│   ├── outbox-relay/
│   ├── stream-processor/
│   ├── audit-sink/
│   ├── flows/                    # Prefect flows
│   └── simulator/
├── frontends/
│   ├── storefront/               # React + Vite (TypeScript, strict)
│   └── dashboard/                # Streamlit
├── infra/
│   ├── postgres/init.sql
│   ├── grafana/dashboards/
│   └── prometheus/prometheus.yml
├── libs/common/                  # shared: checkpoint emitter, JSON logger, models
└── evals/
    ├── conftest.py               # fixtures: db conns, kafka client, http client
    ├── phase1/ ... phase6/       # pytest suites, one directory per phase
    └── helpers.py
```

**Canonical schema (Postgres):** `genres`, `artists`, `albums`, `tracks`, `products` (album/track × format, unique SKU), `customers`, `orders`, `order_items`, `inventory` (physical formats only), `outbox`.

**Checkpoint record shape** (JSON, on `pipeline.audit` and in logs):
`{event_id, trace_id, stage, status, ts, latency_ms_from_prev, service, detail}`
Stage vocabulary: `api.received`, `db.committed`, `outbox.published`, `stream.consumed`, `stream.mongo_upsert`, `stream.redis_update`, `batch.included`, `dlq.captured`.

---

## 3. Working Rules for Agents

- **One phase per branch:** `phase-1-system-of-record`, `phase-2-events`, etc. Commit small; commit messages reference eval IDs they satisfy (e.g., `feat(api): order creation with idempotency [E1.4]`).
- **Evals are the definition of done.** Each phase ships its pytest suite under `evals/phaseN/` *in the same phase* — building the eval is part of the work, and eval code must not be weakened to pass (tests assert on behavior, not implementation details).
- **Run evals via** `make eval PHASE=n` (wraps `pytest evals/phase{n} -v`). All prior phases' evals must also still pass (`make eval-all`) — regressions block completion.
- **Determinism:** all generated data uses the fixed seed `RANDOM_SEED=1138` from env. Evals may assert on exact seeded values.
- **Don't gold-plate:** no auth, no payments integration, no Kubernetes, no schema registry unless a phase explicitly asks. Out-of-scope work is a review defect.
- **When blocked or when the spec and this doc disagree,** the spec wins; note the discrepancy in `docs/DECISIONS.md` rather than silently choosing.

---

## 4. Phase Plan with Traceable Evals

Eval IDs are stable and traceable: **E<phase>.<n>**. Each maps 1:1 to a pytest test named `test_e{phase}_{n}_*` so `pytest -k e2_3` runs exactly one eval.

---

### Phase 1 — System of Record (spec M1)

**Objective:** Postgres schema + seeded music catalog + FastAPI CRUD + storefront checkout. JSON logging with `event_id` from day one. Compose runs: `postgres`, `api`, `storefront`.

**In scope:** schema (`infra/postgres/init.sql`), seed logic as a plain Python module in `libs/common/seeding.py` (Prefect wrapping comes in Phase 4; a `make seed` CLI entry point calls it directly for now), API endpoints (`/products`, `/albums`, `/cart`, `/orders`, `/events` stub, `/healthz`), Redis for cart + idempotency keys, React + TypeScript storefront (catalog, album page, cart, checkout) with a typed API client (`src/api/types.ts` mirrors the Pydantic response models).
**Out of scope:** Kafka, outbox relay (the `outbox` *table* is created and written, but nothing reads it), Mongo, dashboards.

| Eval | Assertion |
|---|---|
| **E1.1** | `docker compose up -d` then all Phase-1 services report healthy within 90s; `GET /healthz` returns 200. |
| **E1.2** | Seeded catalog matches the fixed seed: exactly 12 genres; artist count in [140,160]; every album has 1–3 product rows; every vinyl/CD product has an `inventory` row and no digital product does. |
| **E1.3** | Determinism: dropping and re-seeding yields byte-identical catalog (checksum over ordered `products` rows matches recorded golden value). |
| **E1.4** | `POST /orders` twice with the same `Idempotency-Key` creates exactly one order row and returns the same `order_id`. |
| **E1.5** | Order + outbox atomicity: a successful order write produces exactly one `outbox` row with matching `aggregate_id` and non-null `trace_id`, in the same transaction (verified by failure injection: forced error after order insert leaves zero rows in both tables). |
| **E1.6** | Physical order items decrement `inventory`; digital items do not; ordering more than available stock returns 409 and changes nothing. |
| **E1.7** | Every API log line is valid JSON and order-related lines contain `event_id` and `trace_id`. |
| **E1.8** | Storefront E2E (Playwright): browse a genre → open an album → add vinyl to cart → checkout → order confirmation shows an `event_id`. |

**Demo moment:** place an order in the UI, then `docker compose logs api | grep <event_id>` shows its JSON trail.

---

### Phase 2 — Events: Outbox → Kafka → Audit Trail (spec M2)

**Objective:** Kafka joins Compose; outbox relay publishes; `pipeline.audit` topic + audit sink land checkpoints in MongoDB. First end-to-end trace is visible.

**In scope:** `kafka` (KRaft single broker), `outbox-relay` (SELECT … FOR UPDATE SKIP LOCKED loop), topic creation (`orders.created`, `orders.status`, `clickstream.events`, `pipeline.audit`, `orders.dlq`), shared checkpoint emitter in `libs/common/`, `audit-sink` consumer → Mongo `pipeline_audit` collection, API `/events` now produces clickstream to Kafka, checkpoints emitted at `api.received`, `db.committed`, `outbox.published`.
**Out of scope:** stream processor business logic, Redis analytics, batch.

| Eval | Assertion |
|---|---|
| **E2.1** | Placing an order results in a message on `orders.created` within 5s, with Kafka headers `event_id` and `trace_id` equal to the outbox row's values. |
| **E2.2** | The outbox row is marked `published_at` and is never re-published (relay restarted mid-run publishes no duplicates to `orders.created` for already-published rows). |
| **E2.3** | At-least-once tolerance: killing the relay after publish but before marking published, then restarting, yields a duplicate on the topic — and the eval asserts the *system defines this as acceptable* by verifying downstream idempotency in Phase 3 (here: the duplicate carries the same `event_id`). |
| **E2.4** | For one order, Mongo `pipeline_audit` contains checkpoints `api.received` → `db.committed` → `outbox.published` with monotonically increasing timestamps and matching `event_id`. |
| **E2.5** | Checkpoint emission is non-blocking: with Kafka stopped, `POST /orders` still succeeds (order + outbox rows written) and the API logs a checkpoint-delivery warning rather than erroring. |
| **E2.6** | Backpressure visibility: with the relay stopped, the `outbox_unpublished_rows` gauge (exposed at `/metrics`) grows as orders are placed, and drains to 0 within 30s of restart. |
| **E2.7** | `docker compose logs \| grep <event_id>` surfaces lines from ≥ 2 different services for one order. |

**Demo moment:** stop the relay, place 20 orders, watch the outbox backlog metric climb, restart, watch it drain.

---

### Phase 3 — Stream Path (spec M3)

**Objective:** Real-time processing into MongoDB and Redis; DLQ; dashboard's Pipeline tab. Compose adds `stream-processor`, `dashboard`, `simulator`.

**In scope:** stream processor (consumer group over `orders.created` + `clickstream.events`) → Mongo `order_view` + `sales_by_minute`, Redis counters/leaderboards (`ZINCRBY` top albums & artists, revenue by format), DLQ routing for poison messages, checkpoints `stream.consumed`, `stream.mongo_upsert`, `stream.redis_update`, `dlq.captured`; Streamlit dashboard with Business tab (live KPIs) and Pipeline tab (event-journey lookup by `event_id`); traffic simulator using seeded popularity weights.
**Out of scope:** batch numbers on the dashboard, Grafana.

| Eval | Assertion |
|---|---|
| **E3.1** | End-to-end latency: checkout → `order_view` document in Mongo in < 2s (P95 over 50 simulated orders). |
| **E3.2** | Idempotency: replaying the same `orders.created` message 3× leaves exactly one `order_view` doc and increments Redis revenue counters exactly once (dedup by `event_id`). |
| **E3.3** | `order_view` is correctly denormalized: contains customer, items, and each item's artist/album/format — no further lookups needed to render it. |
| **E3.4** | Poison message (malformed payload injected onto `orders.created`) lands on `orders.dlq` with a `dlq.captured` checkpoint; the processor keeps consuming subsequent messages (no crash-loop). |
| **E3.5** | Catch-up: with the processor stopped, 30 orders are placed (consumer lag > 0); after restart, lag returns to 0 and Redis daily-revenue equals the Postgres sum for those orders. |
| **E3.6** | Format asymmetry: digital-only orders update revenue counters but never touch inventory-related state. |
| **E3.7** | Pipeline tab: querying a seeded `event_id` renders the full checkpoint timeline (all stages present, per-stage latency shown). |
| **E3.8** | Top-sellers integrity: after 500 simulated orders, the Redis top-10 album leaderboard matches a direct SQL aggregation over the same orders (Zipf head is visible: top artist share > uniform expectation). |

**Demo moment:** the E3.5 kill/catch-up sequence live, narrated with the consumer-lag number.

---

### Phase 4 — Batch Path with Prefect (spec M4)

**Objective:** Prefect server + worker in Compose; `daily_rollup_flow` (DuckDB over Postgres → Mongo `daily_reports`, Redis reference keys) with schedule, retries, and run manifests; `seed_flow` wraps the Phase-1 seeder; stream-vs-batch comparison on the dashboard.

**In scope:** `prefect-server`, `prefect-worker` services; deployments with nightly cron; `daily_rollup_flow` task graph (`extract_watermark → extract → transform → load_mongo → refresh_redis → emit_audit_manifest → data_quality_checks`); rollups: revenue by day/genre/format, top artists, CLV, vinyl inventory turnover, preview→purchase funnel; manifest checkpoint (`batch.included`, includes `flow_run_id`); dashboard Business tab shows "stream (now)" vs "batch (as of last run)" side by side; "Run batch now" button.
**Out of scope:** backfill/reconciliation/dlq_replay flows (Phase 5).

| Eval | Assertion |
|---|---|
| **E4.1** | `prefect deployment ls` (in the worker container) shows `daily_rollup_flow` and `seed_flow` deployments; the rollup has a cron schedule. |
| **E4.2** | Triggering `daily_rollup_flow` completes with state COMPLETED and writes one `daily_reports` doc per day of seeded history (~30 docs on first run). |
| **E4.3** | Correctness: batch revenue-by-genre for a closed day equals a direct SQL aggregation over Postgres for that day (exact match). |
| **E4.4** | Idempotent re-run: running the flow twice for the same date range yields identical `daily_reports` (no duplicates, same checksums). |
| **E4.5** | Retry behavior: with Mongo paused, the `load_mongo` task retries (visible in run logs) and the flow succeeds once Mongo resumes — or fails cleanly after max retries with state FAILED, never half-written (staging + atomic swap or upsert). |
| **E4.6** | Run manifest: a `batch.included` checkpoint exists on `pipeline.audit` carrying rows_read, rows_written, watermark, and a `flow_run_id` that resolves in the Prefect API. |
| **E4.7** | Preview funnel report exists and is internally consistent: previews ≥ carts ≥ purchases for every album row. |
| **E4.8** | Dashboard shows stream and batch revenue for today side by side, labeled with their freshness. |

**Demo moment:** open the Prefect UI DAG mid-run; then compare stream vs. batch numbers on the dashboard and discuss why they differ intra-day.

---

### Phase 5 — Orchestration Depth (spec M5)

**Objective:** the three remaining flows, each a self-contained orchestration lesson.

**In scope:** `backfill_flow(start_date, end_date)`; `reconciliation_flow` (stream vs. batch revenue drift; fails past threshold); `dlq_replay_flow` (drain DLQ, reprocess, report recovered/abandoned counts).
**Out of scope:** new business features.

| Eval | Assertion |
|---|---|
| **E5.1** | Backfill: after deleting 5 days of `daily_reports`, `backfill_flow` for that range restores them byte-identical to the originals (golden checksums). |
| **E5.2** | Backfill is parameterized and bounded: it touches only the requested date range (docs outside the range keep their original `_id`/timestamps). |
| **E5.3** | Reconciliation passes on a healthy system: drift < threshold → flow COMPLETED, drift metric exported. |
| **E5.4** | Reconciliation gates on corruption: after artificially inflating a Redis revenue counter, the flow FAILS with a drift report naming the offending day — and the failure is visible in Prefect UI run history. |
| **E5.5** | DLQ replay: with 3 poison + 2 transiently-failed messages on the DLQ, `dlq_replay_flow` recovers the 2, re-dead-letters the 3, and reports `{recovered: 2, abandoned: 3}`; recovered orders appear in `order_view` exactly once. |
| **E5.6** | All flows emit audit checkpoints and appear in the same Pipeline-tab timeline as stream events. |

**Demo moment:** corrupt a counter live, run reconciliation, watch it fail loudly with the culprit named.

---

### Phase 6 — Observability Polish (spec M6)

**Objective:** OpenTelemetry traces, Prometheus + Grafana provisioned dashboards, failure-injection exercise pack.

**In scope:** OTel spans across storefront request → API → Postgres commit, `trace_id` continuity through Kafka headers into stream-processor spans; Prometheus scrape of every service; provisioned Grafana dashboards (pipeline health: per-stage throughput/latency heatmap from audit data, consumer lag, outbox backlog, DLQ depth, end-to-end latency, batch staleness, stream-vs-batch drift); `docs/exercises/` failure-injection runbook.
**Out of scope:** alerting/paging integrations.

| Eval | Assertion |
|---|---|
| **E6.1** | One `trace_id` links spans from ≥ 3 services (api, relay-published hop, stream processor) for a single order. |
| **E6.2** | Every Python service exposes `/metrics`; Prometheus reports all targets UP. |
| **E6.3** | Grafana provisioning: dashboards exist via API on a fresh `docker compose up` (no manual import), and the end-to-end latency panel returns data after 20 simulated orders. |
| **E6.4** | `pipeline_end_to_end_latency_seconds` P95 < 2s under simulator load; the metric is derived from audit checkpoints (spot-check one order's value against its checkpoint timestamps, within tolerance). |
| **E6.5** | Failure drill (scripted): stop stream processor → lag alert panel goes red → restart → recovers; the runbook's expected observations match reality. |
| **E6.6** | `make eval-all` passes: Phases 1–6 green on a fresh clone + `docker compose up`, on a machine with only Docker + Git. |

**Demo moment:** the full end-to-end story on Grafana — one order's dot on the latency panel, traced back to its checkpoints.

---

## 5. Eval Traceability Matrix

| Phase | Evals | Verifies spec sections |
|---|---|---|
| 1 | E1.1–E1.8 | §4.1–4.3, §4.9 (seed determinism), outbox pattern (write side) |
| 2 | E2.1–E2.7 | §4.4–4.5, §6 (checkpoints, non-blocking rule) |
| 3 | E3.1–E3.8 | §4.6, §4.8 (Pipeline tab), §7 stream column |
| 4 | E4.1–E4.8 | §4.7 (rollup flow), §7 batch column |
| 5 | E5.1–E5.6 | §4.7 (supporting flows) |
| 6 | E6.1–E6.6 | §5 (telemetry points), §6 (Grafana views) |

---

## 6. Session Bootstrap Prompt (paste into Cursor at the start of a phase)

> You are implementing Phase {N} of the music-store data pipeline. Read `AGENT_HANDOFF.md` and `docs/architecture-spec.md` before writing code. Work only within Phase {N} scope; do not modify prior phases except to fix regressions surfaced by `make eval-all`. Definition of done: all E{N}.* evals pass and no earlier eval regresses. Write the eval tests first or alongside the feature, never after the fact as a formality. Commit messages must reference the eval IDs they address. If you believe a spec requirement is wrong or ambiguous, stop and record the question in `docs/DECISIONS.md` instead of improvising.

---

## 7. Glossary for Agents

- **event_id** — ULID minted by the API at order/event creation; the business correlation key.
- **trace_id** — OpenTelemetry trace ID; the request-level correlation key; stored on the outbox row, propagated via Kafka headers.
- **checkpoint** — fire-and-forget audit record on `pipeline.audit`; never on the critical path.
- **outbox pattern** — event row written in the same DB transaction as the business row; a relay publishes it later. The reason: a crash between "commit" and "publish" must not lose events.
- **poison message** — a message that deterministically fails processing; must go to the DLQ, not crash-loop the consumer.
- **watermark** — the timestamp boundary a batch run covers; stored in the run manifest so re-runs and backfills are well-defined.
