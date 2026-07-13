"""Checkpoint emitter — STUDENT SKELETON (Phase 2) [E2.4, E2.5].

Every pipeline stage calls this to drop an audit record onto the
`pipeline.audit` Kafka topic. The contract (docs/STACK_SPEC.md §5):

    {event_id, trace_id, stage, status, ts, latency_ms_from_prev,
     service, detail}

Rules that the evals enforce:
- FIRE AND FORGET. Emitting a checkpoint must never block or fail the
  business path — with Kafka down, POST /orders still succeeds and the
  API logs a delivery warning instead of erroring [E2.5].
- Also log every checkpoint as a structured JSON line (the audit trail
  doubles as grep-able logs) [E2.7].
"""
from __future__ import annotations


class CheckpointEmitter:
    """TODO Phase 2: wrap a confluent_kafka.Producer.

    Suggested surface (the reference implementation uses exactly this):

        emit(event_id, trace_id, stage, status="ok", detail=None) -> None
        flush() -> None   # called on service shutdown only
    """

    def emit(self, event_id: str, trace_id: str, stage: str,
             status: str = "ok", detail: dict | None = None) -> None:
        raise NotImplementedError("Phase 2 [E2.4]")

    def flush(self) -> None:
        raise NotImplementedError("Phase 2")
