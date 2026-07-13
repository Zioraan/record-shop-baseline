"""Prometheus metrics helpers shared by the worker services.

FastAPI mounts prometheus_client's ASGI app; standalone consumers call
start_metrics_server() to expose /metrics on METRICS_PORT.
"""
from __future__ import annotations

import os

from prometheus_client import Counter, Gauge, Histogram, start_http_server


def start_metrics_server() -> None:
    start_http_server(int(os.environ.get("METRICS_PORT", "9100")))


# Shared metric definitions (each service uses the subset it needs).
ORDERS_CREATED = Counter("orders_created_total", "Orders successfully created")
ORDER_FAILURES = Counter("order_create_failures_total", "Order creation failures")
IDEMPOTENCY_CONFLICTS = Counter("idempotency_conflicts_total", "Duplicate idempotency keys")
HTTP_LATENCY = Histogram("http_request_duration_seconds", "API latency", ["route"])

OUTBOX_UNPUBLISHED = Gauge("outbox_unpublished_rows", "Outbox rows awaiting publish")
OUTBOX_PUBLISH_LATENCY = Histogram("outbox_publish_latency_seconds",
                                   "DB commit to Kafka ack")

EVENTS_PROCESSED = Counter("events_processed_total", "Stream events processed", ["topic"])
EVENT_DURATION = Histogram("event_processing_duration_seconds",
                           "Per-event processing time", ["topic"])
PROCESSING_FAILURES = Counter("processing_failures_total",
                              "Stream processing failures", ["error_class"])
DLQ_MESSAGES = Counter("dlq_messages_total", "Messages routed to the DLQ")

E2E_LATENCY = Histogram(
    "pipeline_end_to_end_latency_seconds",
    "Checkout to MongoDB order_view visibility",
    buckets=[0.1, 0.25, 0.5, 1, 2, 5, 10, 30],
)

CONSUMER_LAG = Gauge("kafka_consumer_lag",
                     "Messages behind the latest offset, per topic",
                     ["topic"])

# Exported by the audit sink, which sees every checkpoint on pipeline.audit —
# this is what turns the audit trail into Grafana-visible stage health.
STAGE_CHECKPOINTS = Counter("pipeline_checkpoints_total",
                            "Audit checkpoints ingested", ["stage", "status"])
STAGE_LATENCY = Histogram("pipeline_stage_latency_seconds",
                          "Hop latency from the previous stage", ["stage"],
                          buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5,
                                   1, 2, 5, 10, 30])
BATCH_LAST_SUCCESS = Gauge("batch_last_success_timestamp",
                           "Unix time of the last batch.included manifest")
STREAM_BATCH_DRIFT = Gauge("stream_batch_drift_cents",
                           "Reconciliation drift: |stream revenue - SQL revenue|")
