# Failure-Injection Runbook (Phase 6 exercises)

Each drill: predict → break → observe → recover → discuss. Students write
down their prediction *before* breaking anything.

## Drill 1 — Stream processor outage (consumer lag)
1. Open Grafana → Pipeline Health. Note "Events processed by topic".
2. `docker compose stop stream-processor`
3. Place 10+ orders (storefront or simulator).
4. **Observe:** Postgres order count grows; Redis "orders today" frozen on the
   dashboard; Kafka retains the messages.
5. `docker compose start stream-processor`
6. **Observe:** burst of processing; Redis catches up to SQL truth.
7. **Discuss:** why did nothing get lost? What would have been lost if the API
   published directly to Kafka with no outbox?

## Drill 2 — Relay outage (outbox backpressure)
1. `docker compose stop outbox-relay`
2. Place orders. **Observe:** `outbox_unpublished_rows` climbs (Grafana stat
   goes yellow → red); storefront unaffected — customers never notice.
3. `docker compose start outbox-relay` → backlog drains to 0 within seconds.
4. **Discuss:** the gauge as the single "pipeline is backing up" signal.

## Drill 3 — Poison message (DLQ)
1. Produce garbage:
   ```bash
   docker compose exec kafka /opt/kafka/bin/kafka-console-producer.sh \
     --bootstrap-server localhost:9092 --topic orders.created <<< '{"bad": true}'
   ```
2. **Observe:** processor logs `poison message dead-lettered`; DLQ stat
   increments; a `dlq.captured` checkpoint appears; processing CONTINUES.
3. Run `dlq_replay_flow` from the Prefect UI → `{recovered: 0, abandoned: 1}`.
4. **Discuss:** crash-loop vs dead-letter; who monitors the DLQ?

## Drill 4 — Corrupted stream state (reconciliation gating)
1. `docker compose exec redis redis-cli INCRBY stats:$(date -u +%Y%m%d):revenue_cents 500000`
2. Trigger `reconciliation_flow` (threshold 100) in the Prefect UI.
3. **Observe:** run FAILS; the error names stream vs SQL numbers and the day.
4. Fix: rerun with the counter corrected (or let the next day roll over).
5. **Discuss:** why gate on drift instead of silently trusting the fast path?

## Drill 5 — Kafka down entirely (checkpoint non-blocking)
1. `docker compose stop kafka`
2. Place an order. **Observe:** checkout still succeeds (order + outbox rows
   committed); API logs `checkpoint delivery failed (non-blocking)`.
3. `docker compose start kafka` → relay drains the accumulated outbox.
4. **Discuss:** which failures may block a sale, and which must never.
