# flows — STUDENT DELIVERABLE (Phases 4–5) [E4.*, E5.*]

Prefect 3 flows, served as deployments (see docs/STACK_SPEC.md §7):
- daily_rollup_flow (nightly): DuckDB over Postgres → Mongo daily_reports +
  Redis reference keys; watermarked, retried, idempotent re-runs; emits a
  batch.included manifest checkpoint carrying flow_run_id.
- seed_flow: wraps libs/common/seeding.seed (Phase 4).
- backfill_flow(start,end): bounded, idempotent (Phase 5).
- reconciliation_flow: stream-vs-SQL revenue drift; FAILS loudly past
  threshold; parks drift in Redis for the audit-sink bridge (Phase 5).
- dlq_replay_flow: drain DLQ, reprocess, report recovered/abandoned (Phase 5).

Rule: NEVER wrap a Kafka consumer in a Prefect flow (principle #6).
