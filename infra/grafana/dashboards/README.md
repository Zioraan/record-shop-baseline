# Grafana dashboards — STUDENT DELIVERABLE (Phase 6) [E6.3]

Provisioning is wired: any `*.json` dashboard dropped in this directory
appears in Grafana (localhost:3000, anonymous Admin) on a fresh
`docker compose up` — no manual import allowed by the eval.

The reference `pipeline-health` dashboard has 13 panels; the metric names
and required panels are inventoried in `docs/STACK_SPEC.md` §6. Remember
landmine #6: single-writer gauges (`batch_last_success_timestamp`,
`stream_batch_drift_cents`) must be queried with `max()`.
