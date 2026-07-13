# The Record Shop — Data Pipeline (Student Baseline)

This is the **starting point**, not the finished system. You will build a
complete data pipeline behind an online music store — OLTP writes,
transactional outbox, Kafka, stream processing into MongoDB + Redis, a
Prefect batch path, and end-to-end observability — one phase at a time,
with an AI coding agent, against a fixed spec and eval suite.

## Read first (in this order)

1. `docs/PROJECT_CONTEXT.md` — mission, principles, build order, and the
   **landmine list**: real bugs the reference build already paid for.
2. `docs/STACK_SPEC.md` — the concrete contract: services, ports, topics,
   keys, metrics. Treat its names as API.
3. `AGENT_HANDOFF.md` — the phase plan and eval IDs (E1.1–E6.6). **Evals are
   the definition of done.** Load it + the spec into your agent every session.
4. `docs/architecture-spec.md` — the authoritative architecture (wins all
   conflicts). `docs/stack-overview.md` is a narrative tour of where you'll
   end up.

## What is GIVEN vs. what YOU BUILD

**Given (do not rewrite):**
- All documentation and the eval fixtures (`evals/conftest.py`).
- The **storefront UI** — complete React + TypeScript pages. Its typed API
  client defines the endpoints your API must serve; `src/api/types.ts`
  mirrors `services/api/app/models.py` (also given — it is the contract).
- `libs/common/`: `ids.py`, `logging.py`, `metrics.py` (metric definitions
  are contract), `catalog_data.py` (name templates so every student's
  catalog matches lecture references).
- Infrastructure in `docker-compose.yml`: Postgres, Redis, Kafka (+ topic
  init), Mongo, Prometheus, Grafana — these run from day one.
- The storefront `nginx.conf` — it encodes landmine #3; leave it alone.

**You build (each with its phase and evals):**
- `infra/postgres/init.sql` (schema), `libs/common/seeding.py` (Phase 1)
- The FastAPI endpoints in `services/api/app/main.py` (Phase 1–2)
- `libs/common/checkpoints.py`, `services/outbox-relay/`,
  `services/audit-sink/` (Phase 2)
- `services/stream-processor/`, `frontends/dashboard/` tabs,
  `services/simulator/` (Phase 3)
- `services/flows/` (Phases 4–5)
- Grafana dashboards + OTel polish (Phase 6)
- The eval tests themselves, `evals/phaseN/test_phaseN.py` — written with
  or before each feature, never weakened to pass.

Each service directory contains a README stating its contract, metrics
ports, and the landmines that apply to it. Uncomment its block in
`docker-compose.yml` when the code exists.

## Day-one smoke test

```bash
docker compose up -d          # infra + api skeleton + storefront
curl http://localhost:8000/healthz          # {"ok": true}
# storefront at http://localhost:5173 — shows "Could not load albums"
# until you implement Phase 1. That error message is your starting line.
```

## Working rules (non-negotiable)

- One phase per branch (`phase-1-system-of-record`, …); commits reference
  eval IDs (`feat(api): idempotent orders [E1.4]`).
- A phase is done when `pytest evals/phase{n} -v` passes AND no earlier
  phase regresses. From the host, Kafka is `localhost:29092`.
- Spec conflicts and deliberate deviations go in `docs/DECISIONS.md` — never
  silently chosen. Fixes and verified milestones go in `progress.md`.
