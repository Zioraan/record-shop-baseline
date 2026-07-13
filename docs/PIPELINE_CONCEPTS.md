# Pipeline Concepts — Your Map of the Territory

**Audience: you, the student.** Do not load this into your agent — it needs
the specs; you need the mental model. Read this before planning each phase,
with the dashboard's Pipeline tab open beside it (localhost:8501 — it is
given, complete, and starts all-grey. It is your build map: every phase you
finish turns nodes green).

The point of this course is not this record shop. It is that after building
this once, you can walk into *any* data system — a hospital's records flow,
a bank's transaction feed, an ad platform — and recognize the same seven
aspects, ask where each one lives, and know what breaks when it's missing.

---

## The seven aspects of every data pipeline

### 1. COLLECT — data enters the world
*Here:* the storefront + FastAPI. A human clicks "checkout"; an API turns
that into a fact with an identity (`event_id`) and a birth certificate
(`trace_id`).
*Generalize:* every pipeline starts with an edge that turns messy reality
into identified records. If records aren't given identity **at the edge**,
nothing downstream can ever be traced.
*You'll see it:* the `api.received` node; an order confirmation showing its
`event_id`.

### 2. STORE (system of record) — one place is the truth
*Here:* PostgreSQL. Normalized tables, constraints, transactions. Everything
else in the system is a *derivative* of this.
*Generalize:* every pipeline has (or desperately needs) exactly one place
where a fact is authoritative. All disagreements are settled here.
*You'll see it:* the `db.committed` node; the Data Explorer tab's "one fact,
three shapes" — this is shape #1.

### 3. CAPTURE — changes become events
*Here:* the transactional outbox + relay. The order and the announcement of
the order are written in ONE transaction; a separate process publishes the
announcement.
*Generalize:* this is the hardest idea in the course. Systems that "save,
then publish" silently lose events when they crash in between. Real-world
names: CDC, Debezium, binlog tailing — all solve this same problem.
*You'll see it:* the `outbox.published` node turning green in Phase 2; the
outbox-backlog gauge climbing when you stop the relay.

### 4. TRANSPORT — events travel, buffered
*Here:* Kafka topics. Producers and consumers are decoupled *in time* — a
dead consumer misses nothing; it catches up.
*Generalize:* queues/logs/buses exist so that parts of a system can fail
independently. The key health question is always "how far behind?" —
consumer lag.
*You'll see it:* stop the stream processor, place orders, watch lag grow on
Grafana, restart, watch it drain. The signature demo of the course.

### 5. TRANSFORM — facts reshaped for their audience
*Here, twice (on purpose):*
- **Stream** (seconds): the processor denormalizes orders into Mongo
  documents and Redis counters as they happen.
- **Batch** (nightly): DuckDB recomputes the same numbers from the system
  of record.
*Generalize:* the same fact usually needs several shapes — normalized for
integrity, denormalized for reading, aggregated for dashboards. Stream is
fresh but drifts under failure; batch is stale but self-healing. Almost
every real pipeline runs both and must explain why they disagree.
*You'll see it:* `stream.mongo_upsert` / `stream.redis_update` /
`batch.included` nodes; the Business tab's side-by-side "as of now" vs
"as of last run" numbers disagreeing intra-day.

### 6. ORCHESTRATE — someone must supervise the finite work
*Here:* Prefect — schedules, retries, run history, backfills, and a
reconciliation job that FAILS LOUDLY when stream and truth drift apart.
*Generalize:* infinite work (consumers) gets supervised by restart policies
and lag metrics; finite work (nightly jobs) gets an orchestrator. Confusing
the two is a classic architecture smell.
*You'll see it:* the Prefect UI's DAG (localhost:4200); the drift stat on
Grafana going red when you corrupt a counter.

### 7. OBSERVE — the pipeline must be watchable
*Here:* checkpoints on every hop → the flow diagram and per-event journey
timeline; metrics → Grafana; JSON logs greppable by `event_id`.
*Generalize:* observability is a property of the data (IDs minted once,
carried everywhere), not a tool you bolt on later. If you can't follow one
record end-to-end, you don't have a pipeline — you have hope.
*You'll see it:* paste any order's `event_id` into the Pipeline tab and
watch its checkpoints arrive, stage by stage, seconds after checkout.

---

## Phase ↔ concept ↔ what turns green

| Phase | Concept you're learning | Nodes that turn green | Prove it to yourself by… |
|---|---|---|---|
| 1 | Collect + Store | `api.received`, `db.committed` | placing an order; grepping logs for its event_id |
| 2 | Capture + Transport (+ Observe begins) | `outbox.published` | stopping the relay → backlog climbs → restart → drains |
| 3 | Transform (stream) | `stream.consumed`, `stream.mongo_upsert`, `stream.redis_update`; `dlq.captured` on poison | kill/catch-up demo; Data Explorer's three shapes |
| 4 | Transform (batch) | `batch.included` | comparing stream vs batch numbers on the Business tab |
| 5 | Orchestrate | (no new nodes — watch Prefect run history instead) | corrupting a counter → reconciliation fails loudly, naming it |
| 6 | Observe, completed | all nodes annotated with latency; Grafana fills | tracing one order from checkout click to its dot on the latency panel |

## How to use this while planning with your agent

Before each phase, look at the flow diagram and answer three questions out
loud — *before* the agent writes anything:

1. **Which grey node(s) am I building, and which concept is that?**
2. **What will I look at afterwards to see it working?** (a node turning
   green, a metric moving, a number appearing)
3. **What should happen when it breaks?** (every aspect here has a designed
   failure behavior — backlog, lag, DLQ, loud reconciliation. If your plan
   has no answer, the plan isn't done.)

If you can answer those three for all seven aspects by the end of the
course, the record shop did its job — and you'll never look at a data
system the same way again.
