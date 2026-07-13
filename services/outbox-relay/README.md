# outbox-relay — STUDENT DELIVERABLE (Phase 2) [E2.1–E2.3, E2.6]

CDC-lite: `SELECT … FROM outbox WHERE published_at IS NULL FOR UPDATE SKIP
LOCKED` → publish to Kafka with event_id/trace_id HEADERS → mark published.
Emits `outbox.published` checkpoints and the `outbox_unpublished_rows` gauge
(METRICS_PORT 9101). At-least-once by design — a crash between publish and
mark re-publishes on restart; downstream dedups.

LANDMINE #1 (docs/PROJECT_CONTEXT.md §6): the connection MUST be
`autocommit=True`, with the publish pass atomic via explicit
`conn.transaction()`. A plain SELECT on a non-autocommit psycopg3 connection
holds table locks forever and deadlocks the seeder's TRUNCATE.
