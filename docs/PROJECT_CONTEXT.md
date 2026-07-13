# Project Context — Everything Needed to Arrive at This Project

**Purpose of this file:** load it (plus `docs/STACK_SPEC.md`) into a fresh
agent session or hand it to a student, and the work that follows should
converge on this project — without rediscovering the bugs we already paid
for. It is the "start here" document.

**Document map (who is authoritative for what):**

| File | Role |
|---|---|
| `docs/PROJECT_CONTEXT.md` | This file — mission, principles, build order, conventions, landmines |
| `docs/STACK_SPEC.md` | The concrete stack: every service, version, port, topic, key, metric |
| `docs/architecture-spec.md` | The architecture contract (v1.3) — wins all conflicts |
| `AGENT_HANDOFF.md` | Phase plan + eval IDs E1.1–E6.6 — evals are the definition of done |
| `docs/stack-overview.md` | Narrative guided tour of the finished system |
| `docs/DECISIONS.md` | Deliberate deviations and scope additions, with rationale |
| `progress.md` | Chronological log of fixes and verified surface area |

---

## 1. Mission

Build a **classroom demonstration system for teaching data pipelines**: an
online music store ("the record shop") selling fictional artists' albums as
vinyl, CD, and digital downloads. The store is the pretext; the product is
the **pipeline behind it** and the ability to *watch* data move through it:

> OLTP writes → transactional outbox → Kafka → stream processing →
> MongoDB + Redis, alongside a Prefect-orchestrated batch path (DuckDB),
> with every hop observable via correlation IDs and audit checkpoints.

Constraints that shape everything:

- **Runs entirely in Docker Compose on a student laptop.** No cloud
  accounts, no cost, one command, ≤ ~4 GB RAM.
- **Python 3.12 everywhere on the back end**; the only non-Python code is
  the React + Vite storefront (TypeScript **strict**; `tsc --noEmit` is a
  build gate, treat type errors as build failures).
- **Deterministic data**: everything generated under `RANDOM_SEED=1138` is
  byte-identical on every machine. Lecture references and eval assertions
  depend on this.
- **Pedagogy over polish**: each component is the smallest tool that still
  teaches the industry pattern (hand-rolled Kafka consumer before Faust;
  hand-rolled outbox relay before Debezium). No auth, no payments, no
  Kubernetes, no schema registry — out-of-scope work is a review defect.

## 2. Non-negotiable design principles

Violating these is a defect even if features work:

1. Every business event carries an `event_id` (ULID) and OpenTelemetry
   `trace_id` from creation to final store; async hops propagate both via
   **Kafka headers**.
2. Order row + outbox row are written in the **same Postgres transaction**.
   Never publish to Kafka from the API request path.
3. Delivery is **at-least-once everywhere**; every consumer is **idempotent**
   (dedup by `event_id`).
4. Every stage emits a fire-and-forget **checkpoint** to `pipeline.audit`;
   checkpoints must never block or fail the business path (Kafka down ⇒
   orders still succeed).
5. All services log **structured JSON to stdout** with `event_id`/`trace_id`
   fields — `docker compose logs | grep <event_id>` is itself a trace.
6. Long-running consumers are Compose services; finite jobs are **Prefect
   flows**. Never wrap a Kafka consumer in a Prefect flow.

## 3. Build order

Six phases, one branch per phase (`phase-N-...`), commits reference eval IDs
(`[E2.4]`). A phase is done when **all its evals pass and no earlier eval
regresses** (`pytest evals/phase{n} -v`; evals ship in the same phase as the
feature and must not be weakened to pass).

1. **System of record** — Postgres schema + seeded catalog + FastAPI CRUD +
   storefront checkout; JSON logging with `event_id` from day one.
2. **Events** — Kafka + outbox relay + `pipeline.audit` topic + audit sink;
   first end-to-end trace visible.
3. **Stream path** — stream processor → Mongo `order_view` + Redis counters;
   DLQ; Streamlit dashboard with the Pipeline tab.
4. **Batch path** — Prefect server/worker; `daily_rollup_flow` (DuckDB over
   Postgres); stream-vs-batch comparison on the dashboard.
5. **Orchestration depth** — `backfill_flow`, `reconciliation_flow` (fails
   loudly on drift), `dlq_replay_flow`.
6. **Observability polish** — OTel trace continuity, Prometheus scrape of
   every service, provisioned Grafana dashboards, failure-injection drills.

## 4. Beyond the base spec (deliberate, recorded additions)

The reference implementation grew four features beyond the spec, all recorded
in `docs/DECISIONS.md` / `progress.md` — include them in a rebuild *after*
the phases are green:

- **Dashboard auto-refresh** via `st.fragment(run_every=...)` — live sections
  poll (5 s KPIs, 3 s event timeline) while batch sections stay static, making
  the freshness contrast visible.
- **Pipeline flow diagram** — graphviz view of all stages with live
  throughput/latency/health from `pipeline_audit`, plus a recent-events
  picker feeding the per-event timeline.
- **Clickstream tab** — live events/min chart, live funnel with per-stage
  conversion beside the nightly batch funnel, album-level preview→cart
  insights.
- **Storefront Top Sellers rail** — the stream path's Redis leaderboard
  feeding back into the *product*: home-view rail, 15 s poll, SQL fallback
  for cold start, `source: "stream" | "sql"` labeling.

## 5. Working conventions

- Windows host quirks matter: see §"Environment notes" in `STACK_SPEC.md`
  (no `make` — use `.\make.ps1`; Kafka from the host is `localhost:29092`;
  rebuilds must come from the terminal, the Docker Desktop play button does
  NOT rebuild).
- Spec conflicts and ambiguities go in `docs/DECISIONS.md`, never silently
  chosen. The spec wins over every other doc.
- `src/api/types.ts` mirrors `services/api/app/models.py` — keep in sync;
  the storefront build runs `tsc --noEmit` and fails on drift.
- Fixes and newly verified surface area get a dated entry in `progress.md`.

## 6. Landmines — bugs already paid for (encode these from day one)

Each of these cost real debugging time. A rebuild that reintroduces them has
regressed:

1. **psycopg3 idle-in-transaction lock (outbox relay).** The relay's
   connection MUST be `autocommit=True`. A plain SELECT on a non-autocommit
   psycopg3 connection holds an implicit transaction (ACCESS SHARE on
   `outbox`) forever, deadlocking the seeder's TRUNCATE. Keep the publish
   pass atomic via explicit `conn.transaction()`.
2. **Seeder lock timeout.** `SET lock_timeout='5s'` before TRUNCATE and raise
   a `SeedLockTimeout` with a pg_stat_activity diagnosis. The seed must never
   hang silently.
3. **nginx stale DNS (storefront).** `resolver 127.0.0.11 valid=10s` +
   variable `proxy_pass` (`set $api_upstream http://api:8000`) + explicit
   `rewrite ^/api/(.*)$ /$1 break;`. A static `proxy_pass` pins the api
   container's IP at nginx startup → storefront 502s after any
   `--build api`. (Regressed once already; restored 2026-07-13.)
4. **pyarrow 25 segfault (dashboard).** Streamlit rendering a dataframe
   inside its script-runner thread with pyarrow 25.0.0 dies with SIGSEGV —
   exit 139, *no traceback in logs*, only reproducible with a real browser
   session. Pin `pyarrow<25`. Diagnose this class of crash with
   `PYTHONFAULTHANDLER=1`.
5. **FastAPI route order.** `/albums/top` must be declared before
   `/albums/{album_id}` or the router 422s trying to parse "top" as an int.
6. **Shared metrics registry exports zero-gauges.** Unlabeled Gauges defined
   in `libs/common/metrics.py` are exported (as 0) by *every* service that
   imports the module. Grafana queries over single-writer gauges
   (`batch_last_success_timestamp`, `stream_batch_drift_cents`) must
   aggregate with `max()`.
7. **Leaderboard keyed by title.** `ZINCRBY top:albums <qty> <title>` — the
   dashboard and eval E3.8 depend on this shape; consumers hydrate by title.
   Moving to album ids requires changing dashboard + E3.8 in one commit.
8. **Eval environmental interference.** E3.2 (replay idempotency) gives false
   failures while the simulator runs (global counters move between reads).
   E6.4 (e2e P95 < 2 s) gives false failures within ~10 min of the E3.5/E6.5
   kill-the-processor drills polluting the latency histogram. Run those
   evals on a quiet system / after the window clears before concluding
   anything is broken.
9. **Checkpoint arrival order ≠ stage order.** Checkpoints are fire-and-forget
   from concurrent services; `stream.consumed` regularly lands before
   `outbox.published`. Sort displays by stage rank, not naively by timestamp.
10. **Purchases can exceed checkouts in the funnel.** Orders placed straight
    through the API (evals, scripts) never emit browsing events. Label this
    in any funnel UI instead of "fixing" it.
