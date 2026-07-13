# Decisions Log

Ambiguities, spec conflicts, and deliberate deviations — recorded here
instead of silently chosen. The spec wins; this file explains departures.

(empty — your first entry goes here)

## 2026-07-13 — The dashboard ships complete (deviation from the phase plan)

AGENT_HANDOFF Phase 3 lists the Streamlit dashboard as a deliverable
(E3.7). In this baseline the dashboard is GIVEN in full instead, because
this course teaches pipeline concepts through agent orchestration, not
Streamlit: the flow diagram's grey→green nodes make the pipeline visible
from day one and serve as the planning map for every phase
(docs/PIPELINE_CONCEPTS.md).

Consequences:
- E3.7 is reinterpreted: "querying a seeded event_id renders the full
  checkpoint timeline" is now an eval of YOUR pipeline feeding the given
  dashboard, not of dashboard code. The test is still written in Phase 3.
- The dashboard doubles as an executable spec: it reads exactly the Mongo
  collections, Redis keys, and checkpoint fields named in STACK_SPEC —
  if a tab stays empty, your pipeline isn't producing the contract shapes.
- Day-one behavior: Postgres-backed sections show a "schema doesn't exist
  yet" note until Phase 1 lands (graceful degradation is intentional —
  don't "fix" it into an error).
