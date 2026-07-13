# CLAUDE.md — Record Shop Data Pipeline (student baseline)

## What this repo is
A student **baseline** for building a classroom data pipeline: an online
music store (fictional artists; vinyl/CD/digital) whose real subject is the
pipeline — FastAPI → PostgreSQL (transactional outbox) → Kafka → Python
stream processor → MongoDB + Redis, plus a Prefect batch path (DuckDB), all
in Docker Compose with end-to-end observability. The docs and scaffolding
are given; the pipeline itself is built phase by phase against evals.

**Authoritative docs, read before writing code:**
- `docs/PROJECT_CONTEXT.md` — start here: mission, build order, landmine list
- `docs/STACK_SPEC.md` — the concrete contract (services, topics, keys, metrics)
- `docs/architecture-spec.md` — the architecture contract (v1.3); wins conflicts
- `AGENT_HANDOFF.md` — phase plan + eval IDs; **evals are the definition of done**

## Hard rules
- Work on exactly ONE phase at a time; do not start phase N+1 with failing
  evals in phase N. One branch per phase; commits reference eval IDs.
- Evals ship in the same phase as the feature and must not be weakened.
- The six non-negotiable principles in PROJECT_CONTEXT §2 are defects to
  violate even if features work.
- GIVEN files (storefront UI, the COMPLETE dashboard in frontends/dashboard/,
  models.py, libs/common/{ids,logging,metrics,catalog_data,seeding,
  seed_cli}.py, nginx.conf, eval fixtures) are contract — extend the system
  around them, don't rewrite them. In particular, never touch
  `build_catalog` ordering/logic — E1.3 asserts byte-identical re-seeds.
  The dashboard defines the shapes your pipeline must produce (Mongo
  collections, Redis keys, checkpoint records) — build to what it reads.
  E3.7 is therefore read as: the given Pipeline tab renders a full timeline
  once YOUR stream path flows (see docs/DECISIONS.md).
- Encode the ten landmines (PROJECT_CONTEXT §6) from day one — they are
  requirements, not history.
- Deviations/ambiguities → `docs/DECISIONS.md`; verified milestones →
  `progress.md`.
