# stream-processor — STUDENT DELIVERABLE (Phase 3) [E3.1–E3.6, E3.8]

Hand-rolled confluent-kafka consumer (group `stream-processor`) over
orders.created + clickstream.events. Writes Mongo `order_view` (denormalized,
unique index on event_id = the idempotency gate) + `sales_by_minute` +
`clickstream_by_minute`; Redis counters + `top:albums`/`top:artists`
leaderboards. Manual offset commits AFTER successful handling.

Two failure lanes: poison messages → orders.dlq + `dlq.captured` checkpoint,
keep consuming; transient failures → no commit, back off, Kafka redelivers.
Exports events_processed/event-duration/DLQ/e2e-latency metrics and (Phase 6)
kafka_consumer_lag from its own assignment (METRICS_PORT 9102).
Landmine #7: leaderboard members are album TITLES — consumers depend on it.
