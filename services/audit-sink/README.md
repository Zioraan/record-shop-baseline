# audit-sink — STUDENT DELIVERABLE (Phase 2) [E2.4, E2.7]

Consumer (group `audit-sink`) over pipeline.audit → Mongo `pipeline_audit`
(indexes event_id+ts, stage+ts). Bad records are logged and skipped — the
audit trail is best-effort and must never crash-loop. METRICS_PORT 9103.

Phase 6 additions: re-export checkpoints as stage-health metrics
(pipeline_checkpoints_total, pipeline_stage_latency_seconds,
batch_last_success_timestamp) and bridge the reconciliation flow's drift
from Redis to Prometheus (stream_batch_drift_cents) — finite Prefect jobs
have no scrape target.
