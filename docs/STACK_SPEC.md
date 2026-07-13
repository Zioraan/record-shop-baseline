# Stack Spec — The Concrete Inventory

Companion to `docs/PROJECT_CONTEXT.md` (mission/principles) and
`docs/architecture-spec.md` (the contract). This file is the exact,
verifiable inventory of the running system: services, versions, ports,
topics, schemas, keys, and metrics. When rebuilding, treat these names as
API — evals, dashboards, and docs reference them literally.

---

## 1. Services (Docker Compose, project name `music-pipeline`)

| Service | Image / build | Ports (host) | Role |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | 5432 | System of record + outbox |
| `redis` | `redis:7-alpine` | 6379 | Carts, idempotency, counters, leaderboards, cache |
| `kafka` | `apache/kafka:3.8.0` (KRaft, single broker) | 9092, 29092 | Event backbone |
| `kafka-init` | `apache/kafka:3.8.0` (one-shot) | — | Creates topics, exits |
| `mongo` | `mongo:7` | 27017 | Documents: order views, reports, audit trail |
| `api` | build `python:3.12-slim` | 8000 | FastAPI edge; mints IDs; order+outbox tx |
| `outbox-relay` | build `python:3.12-slim` | 9101 (metrics) | Outbox → Kafka publisher (CDC-lite) |
| `stream-processor` | build `python:3.12-slim` | 9102 (metrics) | orders/clickstream → Mongo + Redis; DLQ |
| `audit-sink` | build `python:3.12-slim` | 9103 (metrics) | `pipeline.audit` → Mongo + stage metrics |
| `prefect-server` | `prefecthq/prefect:3-latest` | 4200 | Batch orchestration UI/API |
| `prefect-worker` | build `python:3.12-slim` | — | Runs the five flows |
| `storefront` | `node:22-alpine` build → `nginx:1.27-alpine` | 5173→80 | React SPA + `/api/` reverse proxy |
| `dashboard` | build `python:3.12-slim` (Streamlit) | 8501 | Ops/analytics UI (4 tabs) |
| `prometheus` | `prom/prometheus:v2.53.0` | 9090 | Scrapes all `/metrics` |
| `grafana` | `grafana/grafana:11.1.0` | 3000 | Provisioned dashboards (anonymous Admin) |
| `simulator` | build `python:3.12-slim` — **profile `traffic`** | — | Synthetic funnel-consistent load |

Start: `docker compose up -d` (simulator only via
`docker compose --profile traffic up -d simulator`).

## 2. Environment contract

Shared by every Python service (`x-python-env` in `docker-compose.yml`):

```
RANDOM_SEED=1138                                        # determinism anchor
POSTGRES_DSN=postgresql://shop:shop@postgres:5432/recordshop
KAFKA_BOOTSTRAP=kafka:9092                              # containers
MONGO_URI=mongodb://mongo:27017      MONGO_DB=recordshop
REDIS_URL=redis://redis:6379/0       LOG_LEVEL=INFO
```

Per-service extras: `OTEL_SERVICE_NAME` (all), `METRICS_PORT`
(9101/9102/9103 for relay / stream-processor / audit-sink),
`PREFECT_API_URL=http://prefect-server:4200/api` (worker, dashboard),
`API_URL` + `ORDERS_PER_MINUTE` (simulator).

**From the host** Kafka is the EXTERNAL listener `localhost:29092`
(evals use this); `kafka:9092` works only inside the Compose network.

## 3. Kafka topics

Created by `kafka-init` (auto-create disabled); 3 partitions, RF 1:

| Topic | Producer(s) | Consumer(s) |
|---|---|---|
| `orders.created` | outbox-relay | stream-processor |
| `orders.status` | outbox-relay | (reserved) |
| `clickstream.events` | api `/events` | stream-processor |
| `pipeline.audit` | every stage (fire-and-forget) | audit-sink |
| `orders.dlq` | stream-processor | `dlq_replay_flow` |

`event_id` and `trace_id` travel as **message headers** on every topic.

## 4. Data stores

**PostgreSQL** (`infra/postgres/init.sql`): `genres`, `artists`, `albums`,
`tracks`, `products` (album × format, unique SKU), `customers`, `orders`,
`order_items`, `inventory` (physical formats only), `outbox`
(`published_at NULL` = pending), `clickstream_archive`.

**MongoDB** (db `recordshop`): `order_view` (unique index `event_id` — the
idempotency gate), `sales_by_minute`, `clickstream_by_minute`,
`daily_reports` (one per day, from the rollup), `pipeline_audit`
(indexes `event_id+ts`, `stage+ts`).

**Redis key patterns:**

| Pattern | Type / TTL | Writer |
|---|---|---|
| `cart:{session_id}` | hash, 2 h | api |
| idempotency keys (SETNX) | 24 h | api |
| `cache:album:{id}` | string (JSON), 5 min | api (cache-aside) |
| `stats:{YYYYMMDD}:orders` / `:revenue_cents` / `:revenue:{format}` | counters | stream-processor |
| `top:albums`, `top:artists` | zset, member = **title/name** | stream-processor |
| `reconciliation:last_drift_cents`, `:last_run_ts` | string | reconciliation_flow |

## 5. Checkpoint contract (`pipeline.audit`)

Shape: `{event_id, trace_id, stage, status, ts, latency_ms_from_prev,
service, detail}` with `status ∈ {ok, retried, failed}` and stages:

```
api.received → db.committed → outbox.published → stream.consumed
   → stream.mongo_upsert → stream.redis_update
side channels: batch.included (rollup manifest), dlq.captured (poison)
```

Arrival order is NOT guaranteed to match stage order (concurrent emitters).
IDs are ULIDs with type prefixes (see `libs/common/ids.py`), e.g.
`ord_01KXBR7BCF0KZ20J8JVCN4QYJ4`.

## 6. Prometheus metrics (all defined in `libs/common/metrics.py`)

| Metric | Type / labels | Exporter |
|---|---|---|
| `orders_created_total`, `order_create_failures_total`, `idempotency_conflicts_total` | counters | api |
| `http_request_duration_seconds` | histogram `{route}` | api |
| `outbox_unpublished_rows` | gauge | outbox-relay |
| `outbox_publish_latency_seconds` | histogram | outbox-relay |
| `events_processed_total`, `event_processing_duration_seconds` | `{topic}` | stream-processor, audit-sink |
| `processing_failures_total` | counter `{error_class}` (lazy — absent until a failure) | stream-processor |
| `dlq_messages_total` | counter | stream-processor |
| `pipeline_end_to_end_latency_seconds` | histogram (star metric, target P95 < 2 s) | stream-processor |
| `kafka_consumer_lag` | gauge `{topic}`, refreshed ~5 s | stream-processor |
| `pipeline_checkpoints_total` | counter `{stage,status}` | audit-sink |
| `pipeline_stage_latency_seconds` | histogram `{stage}` | audit-sink |
| `batch_last_success_timestamp` | gauge (query with `max()` — see landmine #6) | audit-sink |
| `stream_batch_drift_cents` | gauge (query with `max()`) | audit-sink (bridged from Redis) |

Grafana: provisioned Prometheus datasource (default) + dashboard uid
`pipeline-health`, **13 panels**, 10 s refresh.

## 7. Prefect deployments (`services/flows/serve.py`)

| Deployment | Schedule |
|---|---|
| `daily_rollup_flow/daily-rollup` | nightly cron |
| `reconciliation_flow/reconciliation` | `30 * * * *` (hourly) |
| `seed_flow/seed`, `backfill_flow/backfill`, `dlq_replay_flow/dlq-replay` | on demand |

Trigger manually: `docker compose exec prefect-worker prefect deployment run
'<flow>/<name>'` or the Prefect UI (localhost:4200).

## 8. Dependency pins (Python 3.12 in-container)

Common across services: `psycopg[binary]==3.2.*`, `confluent-kafka==2.5.*`,
`pymongo==4.8.*`, `redis==5.0.*`, `prometheus-client==0.20.*`.
Per service: api adds `fastapi==0.115.*`, `uvicorn[standard]==0.30.*`,
`pydantic==2.8.*`; flows add `duckdb==1.0.*`; dashboard uses
`streamlit==1.46.*`, `pandas==2.2.*`, and **`pyarrow<25`** (25.0.0 segfaults
under Streamlit's script-runner thread — landmine #4); evals (host) use
`pytest==8.*`, `httpx==0.27.*`.

Storefront: React + Vite, TypeScript strict; `npm run build` runs
`tsc --noEmit` first (type errors fail the image build). nginx config MUST
keep the resolver/variable-proxy_pass/rewrite trio (landmine #3).

## 9. Seeded data constants (RANDOM_SEED=1138)

12 genres · ~150 artists (eval bound: 140–160) · ~395 albums (1–3 products
each) · ~910 products · ~200 customers · ~30 days of order + clickstream
history. Zipf-distributed artist popularity (shared with the simulator);
log-normal pricing with vinyl > CD > digital for the same album; inventory
rows only for physical formats. Eval E1.3 asserts a checksum over ordered
`products` — do not touch `build_catalog` ordering casually.

## 10. Environment notes (Windows host)

- No `make`: use `.\make.ps1 <target>` or raw commands.
- Seed: `docker compose exec api python -m common.seed_cli`.
- Evals run on the host; on this machine deps live under Python 3.10
  (`py -3.10 -m pytest evals/phaseN -v`) — bare `python` is 3.13 without pip.
- Rebuilds must come from the terminal (`docker compose up -d --build <svc>`);
  the Docker Desktop play button does **not** rebuild images.
- URLs: storefront 5173 · API docs 8000/docs · dashboard 8501 · Prefect 4200 ·
  Prometheus 9090 · Grafana 3000.
