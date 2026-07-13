"""Record Shop — employee reporting dashboard — STUDENT SKELETON (Phase 3+).

The four-tab structure is given; every tab's content is a deliverable.
Connection setup and the stage vocabulary are given because they are
contract, not solution. See docs/architecture-spec.md §4.8 for what each
tab must show and docs/PROJECT_CONTEXT.md §4 for the polish added later
(auto-refresh via st.fragment, flow diagram, recent-events picker).

Landmines for this service (docs/PROJECT_CONTEXT.md §6):
- #4: requirements.txt pins pyarrow<25 — do not "clean it up".
- #9: checkpoint arrival order ≠ stage order; sort by stage rank.
"""
from __future__ import annotations

import os

import streamlit as st

st.set_page_config(page_title="Record Shop — Ops", layout="wide", page_icon="🎛️")

PG_DSN = os.environ["POSTGRES_DSN"]
MONGO_URI = os.environ["MONGO_URI"]
REDIS_URL = os.environ["REDIS_URL"]

# The checkpoint stage vocabulary (contract — docs/STACK_SPEC.md §5).
STAGE_ORDER = ["api.received", "db.committed", "outbox.published",
               "stream.consumed", "stream.mongo_upsert", "stream.redis_update",
               "batch.included", "dlq.captured"]

st.title("🎛️ Record Shop — Operations & Analytics")
tab_biz, tab_pipe, tab_click, tab_explore = st.tabs(
    ["📈 Business", "🔍 Pipeline", "👣 Clickstream", "🗄️ Data Explorer"])

with tab_biz:
    st.info("TODO Phase 3 [E4.8 later]: live Redis KPIs (stream) beside the "
            "latest Mongo daily_report (batch), each labeled with its "
            "freshness. Stream side should auto-refresh (st.fragment).")

with tab_pipe:
    st.info("TODO Phase 3 [E3.7] — the visibility centerpiece: paste an "
            "event_id, render its full checkpoint timeline from Mongo "
            "pipeline_audit with per-stage latency. Then: stage-health "
            "table, live flow diagram (st.graphviz_chart), recent-events "
            "picker.")

with tab_click:
    st.info("TODO after Phase 3: live events/min chart "
            "(clickstream_by_minute), browse→preview→cart→checkout funnel "
            "with conversion %, album preview→cart insights. Landmine #10: "
            "purchases can exceed checkouts — label it, don't 'fix' it.")

with tab_explore:
    st.info("TODO Phase 3: one order shown three ways — Postgres rows, "
            "Mongo order_view document, Redis keys it incremented.")
