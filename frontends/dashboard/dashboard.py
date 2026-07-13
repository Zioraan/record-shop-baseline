"""Record Shop — employee reporting dashboard (spec §4.8). GIVEN in full.

This dashboard is deliberately complete on day one: it is your MAP of the
pipeline you are about to build. Every stage in the Pipeline tab's flow
diagram starts GREY (nothing exists yet) and turns GREEN as your phases
land. Use it while planning each phase with your agent — "we are building
this node next" — and to verify the phase actually flows afterwards.
See docs/PIPELINE_CONCEPTS.md for the concept ↔ node ↔ phase map.

Tabs:
  Business      — live KPIs (Redis/stream) vs. historical (Mongo/batch), labeled
  Pipeline      — the flow diagram + per-event checkpoint journeys
  Clickstream   — live browsing activity, funnel conversion, album insights
  Data Explorer — the same order as a Postgres row set, a Mongo doc, Redis keys
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import psycopg
import redis as redis_lib
import streamlit as st
from pymongo import MongoClient

st.set_page_config(page_title="Record Shop — Ops", layout="wide", page_icon="🎛️")

PG_DSN = os.environ["POSTGRES_DSN"]
MONGO = MongoClient(os.environ["MONGO_URI"])[os.environ.get("MONGO_DB", "recordshop")]
R = redis_lib.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

STAGE_ORDER = ["api.received", "db.committed", "outbox.published", "stream.consumed",
               "stream.mongo_upsert", "stream.redis_update", "batch.included",
               "dlq.captured"]


@st.cache_resource
def pg():
    return psycopg.connect(PG_DSN, autocommit=True)


def schema_missing_note(area: str) -> None:
    """Day-one graceful degradation: tables appear in Phase 1, data later."""
    st.info(f"{area}: the Postgres schema doesn't exist yet — this section "
            "lights up once Phase 1 (init.sql + seed) lands.")


st.title("🎛️ Record Shop — Operations & Analytics")
tab_biz, tab_pipe, tab_click, tab_explore = st.tabs(
    ["📈 Business", "🔍 Pipeline", "👣 Clickstream", "🗄️ Data Explorer"])

# --------------------------------------------------------------------------- #
with tab_biz:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("As of now — stream path")
        st.caption("Computed by the stream processor, stored in Redis. "
                   "Freshness: seconds. Auto-refreshes every 5 s.")

        @st.fragment(run_every="5s")
        def live_stream_kpis() -> None:
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            orders_today = int(R.get(f"stats:{today}:orders") or 0)
            revenue_today = int(R.get(f"stats:{today}:revenue_cents") or 0) / 100
            a, b = st.columns(2)
            a.metric("Orders today", orders_today)
            b.metric("Revenue today", f"${revenue_today:,.2f}")
            fmt_cols = st.columns(3)
            for i, fmt in enumerate(("vinyl", "cd", "digital")):
                cents = int(R.get(f"stats:{today}:revenue:{fmt}") or 0)
                fmt_cols[i].metric(f"{fmt.title()} revenue", f"${cents / 100:,.2f}")

            st.markdown("**Top albums (live leaderboard)**")
            top = R.zrevrange("top:albums", 0, 9, withscores=True)
            if top:
                st.dataframe(pd.DataFrame(top, columns=["Album", "Units"]),
                             hide_index=True, use_container_width=True)
            else:
                st.info("No stream data yet — place an order in the storefront.")

        live_stream_kpis()

    with col2:
        st.subheader("As of last batch run — batch path")
        report = MONGO["daily_reports"].find_one(sort=[("day", -1)])
        if report:
            st.caption(f"Computed by daily_rollup_flow. Watermark: {report['day']}"
                       f" · flow_run_id: `{report.get('flow_run_id', 'n/a')}`")
            a, b = st.columns(2)
            a.metric("Orders (last closed day)", report.get("orders", 0))
            b.metric("Revenue (last closed day)",
                     f"${report.get('revenue_cents', 0) / 100:,.2f}")
            by_genre = report.get("revenue_by_genre", {})
            if by_genre:
                df = pd.DataFrame(sorted(by_genre.items(), key=lambda kv: -kv[1]),
                                  columns=["Genre", "Revenue (cents)"])
                df["Revenue"] = df["Revenue (cents)"] / 100
                st.bar_chart(df.set_index("Genre")["Revenue"])
        else:
            st.info("No batch reports yet — trigger daily_rollup_flow in Prefect "
                    "(or wait for the nightly run).")

        funnel = MONGO["daily_reports"].find_one({"funnel": {"$exists": True}},
                                                 sort=[("day", -1)])
        if funnel:
            st.markdown("**Preview → purchase funnel (batch)**")
            st.dataframe(pd.DataFrame([funnel["funnel"]]), hide_index=True,
                         use_container_width=True)

# --------------------------------------------------------------------------- #
STREAM_STAGES = ["api.received", "db.committed", "outbox.published",
                 "stream.consumed", "stream.mongo_upsert", "stream.redis_update"]


def _flow_dot(stats: dict) -> str:
    """Build a graphviz DOT string of the pipeline with live per-stage stats."""
    lines = [
        "digraph pipeline {",
        "  rankdir=LR; bgcolor=transparent;",
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];',
        '  edge [fontname="Helvetica", fontsize=10, color="#94a3b8"];',
    ]
    for stage in STREAM_STAGES + ["dlq.captured", "batch.included"]:
        s = stats.get(stage, {})
        n, avg, failed = s.get("n", 0), s.get("avg"), s.get("failed", 0)
        if failed or (stage == "dlq.captured" and n):
            color = "#fca5a5"  # red: failures / DLQ traffic
        elif n:
            color = "#86efac"  # green: flowing
        else:
            color = "#e2e8f0"  # grey: idle
        label = f"{stage}\\n{n} evt / 5 min"
        if avg is not None and n:
            label += f"\\navg +{avg:.0f} ms"
        lines.append(f'  "{stage}" [label="{label}", fillcolor="{color}"];')
    for a, b in zip(STREAM_STAGES, STREAM_STAGES[1:]):
        lines.append(f'  "{a}" -> "{b}";')
    lines.append('  "stream.consumed" -> "dlq.captured" '
                 '[style=dashed, color="#f87171", label="poison"];')
    lines.append('  "db.committed" -> "batch.included" '
                 '[style=dashed, label="nightly batch"];')
    lines.append("}")
    return "\n".join(lines)


with tab_pipe:
    st.subheader("Pipeline flow — last 5 minutes")
    st.caption("Every hop an event takes, with live throughput and hop latency "
               "from `pipeline.audit` checkpoints. Green = flowing, grey = idle, "
               "red = failures/DLQ. Auto-refreshes every 5 s. **This is your "
               "build map**: on day one every node is grey; each phase you "
               "complete turns nodes green (see docs/PIPELINE_CONCEPTS.md).")

    @st.fragment(run_every="5s")
    def pipeline_flow() -> None:
        since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        agg = MONGO["pipeline_audit"].aggregate([
            {"$match": {"ts": {"$gte": since}}},
            {"$group": {"_id": "$stage", "n": {"$sum": 1},
                        "avg": {"$avg": "$latency_ms_from_prev"},
                        "failed": {"$sum": {"$cond": [
                            {"$eq": ["$status", "failed"]}, 1, 0]}}}},
        ])
        stats = {a["_id"]: a for a in agg}
        st.graphviz_chart(_flow_dot(stats), use_container_width=True)

    pipeline_flow()

    st.divider()
    st.subheader("Trace one event through every stage")
    recent = list(MONGO["pipeline_audit"].aggregate([
        {"$sort": {"ts": -1}},
        {"$group": {"_id": "$event_id", "last_ts": {"$first": "$ts"},
                    "stages": {"$sum": 1}}},
        {"$sort": {"last_ts": -1}},
        {"$limit": 15},
    ]))
    col_typed, col_pick = st.columns(2)
    col_typed.text_input("event_id (from an order confirmation or the logs)",
                         placeholder="ord_01J9XK…", key="pipe_event_id")
    labels = {r["_id"]: f"{r['_id']} · {r['stages']} stages" for r in recent}
    col_pick.selectbox(
        "…or pick a recent event", [""] + [r["_id"] for r in recent],
        key="pipe_recent_pick",
        format_func=lambda eid: labels.get(eid, eid) if eid else "(recent events)",
    )
    st.caption("The timeline below polls every 3 s — paste an event_id right "
               "after checkout and watch its checkpoints arrive. Typed input "
               "wins over the picker.")

    @st.fragment(run_every="3s")
    def event_journey() -> None:
        event_id = ((st.session_state.get("pipe_event_id") or "").strip()
                    or (st.session_state.get("pipe_recent_pick") or "").strip())
        if not event_id:
            return
        checkpoints = list(MONGO["pipeline_audit"]
                           .find({"event_id": event_id}, {"_id": 0})
                           .sort("ts", 1))
        if not checkpoints:
            st.warning("No checkpoints found for that event_id (yet).")
            return
        df = pd.DataFrame(checkpoints)
        df["stage_rank"] = df["stage"].map({s: i for i, s in enumerate(STAGE_ORDER)})
        df = df.sort_values(["ts", "stage_rank"])
        for _, row in df.iterrows():
            icon = "🟥" if row["status"] == "failed" else (
                "🟨" if row["status"] == "retried" else "🟩")
            latency = (f" · +{row['latency_ms_from_prev']:.0f} ms"
                       if pd.notna(row.get("latency_ms_from_prev")) else "")
            st.markdown(f"{icon} **{row['stage']}** — {row['service']}"
                        f" · {row['ts']}{latency}")
        st.dataframe(df.drop(columns=["stage_rank"]), hide_index=True,
                     use_container_width=True)

    event_journey()

    st.divider()
    st.subheader("Stage health (last hour)")

    @st.fragment(run_every="5s")
    def stage_health() -> None:
        hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        agg = list(MONGO["pipeline_audit"].aggregate([
            {"$match": {"ts": {"$gte": hour_ago}}},
            {"$group": {"_id": {"stage": "$stage", "status": "$status"},
                        "count": {"$sum": 1},
                        "avg_latency_ms": {"$avg": "$latency_ms_from_prev"}}},
            {"$sort": {"_id.stage": 1}},
        ]))
        if agg:
            rows = [{"stage": a["_id"]["stage"], "status": a["_id"]["status"],
                     "events": a["count"],
                     "avg +latency (ms)": round(a["avg_latency_ms"] or 0, 1)}
                    for a in agg]
            st.dataframe(pd.DataFrame(rows), hide_index=True,
                         use_container_width=True)
        else:
            st.info("No checkpoints in the last hour.")

        dlq_count = MONGO["pipeline_audit"].count_documents({"stage": "dlq.captured"})
        st.metric("DLQ captures (all time)", dlq_count)

    stage_health()

# --------------------------------------------------------------------------- #
FUNNEL_STAGES = [("page_view", "Page views"), ("track_preview", "Previews"),
                 ("add_to_cart", "Added to cart"), ("checkout_started", "Checkouts")]

with tab_click:
    st.subheader("Live activity — events per minute")
    st.caption("From Mongo `clickstream_by_minute`, written by the stream "
               "processor as events arrive. Auto-refreshes every 5 s.")

    @st.fragment(run_every="5s")
    def click_activity() -> None:
        since = datetime.now(timezone.utc) - timedelta(minutes=30)
        rows = list(MONGO["clickstream_by_minute"]
                    .find({"minute": {"$gte": since}}, {"_id": 0}))
        if not rows:
            st.info("No clickstream in the last 30 minutes — browse the "
                    "storefront or start the simulator.")
            return
        pivot = (pd.DataFrame(rows)
                 .pivot_table(index="minute", columns="event_type",
                              values="count", aggfunc="sum")
                 .fillna(0))
        st.area_chart(pivot)

    click_activity()

    st.divider()
    st.subheader("Funnel — browse → preview → cart → checkout")

    @st.fragment(run_every="10s")
    def funnel_live() -> None:
        try:
            with pg().cursor() as cur:
                cur.execute("SELECT event_type, count(*) FROM clickstream_archive"
                            " WHERE ts::date = now()::date GROUP BY event_type")
                counts = dict(cur.fetchall())
                cur.execute("SELECT count(*) FROM orders"
                            " WHERE created_at::date = now()::date")
                purchases = cur.fetchone()[0]
        except psycopg.errors.UndefinedTable:
            schema_missing_note("Funnel")
            return

        cols = st.columns(len(FUNNEL_STAGES) + 1)
        prev = None
        for col, (etype, label) in zip(cols, FUNNEL_STAGES):
            n = counts.get(etype, 0)
            conv = f"{n / prev * 100:.0f}% of prev" if prev else None
            col.metric(label, n, conv, delta_color="off")
            prev = n or None
        conv = f"{purchases / prev * 100:.0f}% of prev" if prev else None
        cols[-1].metric("Purchases", purchases, conv, delta_color="off")
        st.caption("Today so far (live, from `clickstream_archive` + `orders` "
                   "in Postgres). Each percentage is conversion from the "
                   "previous stage. Purchases can exceed checkouts: orders "
                   "placed straight through the API (evals, scripts) never "
                   "emit browsing events.")

        report = MONGO["daily_reports"].find_one({"funnel": {"$exists": True}},
                                                 sort=[("day", -1)])
        if report:
            f = report["funnel"]
            st.markdown(f"**Batch comparison** — `daily_rollup_flow` for "
                        f"{report['day']}: {f.get('previews', 0)} previews → "
                        f"{f.get('carts', 0)} carts → {f.get('checkouts', 0)} "
                        f"checkouts → {f.get('purchases', 0)} purchases. "
                        "Same funnel, computed nightly — the freshness gap "
                        "between these numbers is the stream-vs-batch lesson.")

    funnel_live()

    st.divider()
    st.subheader("Album insights — previewed vs. carted (today)")

    @st.fragment(run_every="30s")
    def album_insights() -> None:
        try:
            with pg().cursor() as cur:
                cur.execute("""
                SELECT al.title, ar.name,
                       count(*) FILTER (WHERE c.event_type='track_preview') AS previews,
                       count(*) FILTER (WHERE c.event_type='add_to_cart')   AS carts
                FROM clickstream_archive c
                JOIN albums al ON al.id = c.album_id
                JOIN artists ar ON ar.id = al.artist_id
                WHERE c.ts::date = now()::date
                GROUP BY al.title, ar.name
                HAVING count(*) FILTER (WHERE c.event_type='track_preview') > 0
                ORDER BY previews DESC LIMIT 10""")
                rows = cur.fetchall()
        except psycopg.errors.UndefinedTable:
            schema_missing_note("Album insights")
            return
        if not rows:
            st.info("No previews yet today.")
            return
        df = pd.DataFrame(rows, columns=["Album", "Artist", "Previews", "Carts"])
        df["Preview → cart"] = (df["Carts"] / df["Previews"] * 100).round(0)
        st.dataframe(
            df, hide_index=True, use_container_width=True,
            column_config={"Preview → cart": st.column_config.NumberColumn(
                format="%d%%")},
        )
        eligible = df[df["Previews"] >= 5]
        if len(eligible) >= 2:
            best = eligible.loc[eligible["Preview → cart"].idxmax()]
            worst = eligible.loc[eligible["Preview → cart"].idxmin()]
            st.markdown(
                f"🎯 **Converting:** *{best['Album']}* ({best['Artist']}) turns "
                f"{best['Preview → cart']:.0f}% of previews into carts. "
                f"🪟 **Window-shopped:** *{worst['Album']}* ({worst['Artist']}) "
                f"gets listened to but rarely carted "
                f"({worst['Preview → cart']:.0f}%).")
        st.caption("Zipf-distributed popularity means a few hit albums should "
                   "dominate previews — if this table looks flat, the "
                   "simulator's weighting is broken.")

    album_insights()

# --------------------------------------------------------------------------- #
with tab_explore:
    st.subheader("One fact, three shapes")
    st.caption("The same order as a normalized SQL row set, a denormalized Mongo "
               "document, and Redis keys it incremented — polyglot persistence, live.")
    order_id = st.text_input("order id", placeholder="ord_01J9XK…", key="explore")
    if order_id:
        order_id = order_id.strip()
        st.markdown("**PostgreSQL (system of record)**")
        try:
            with pg().cursor() as cur:
                cur.execute("SELECT id, customer_id, status, total_cents, created_at"
                            " FROM orders WHERE id=%s", (order_id,))
                order_row = cur.fetchone()
                if order_row:
                    st.code(str(order_row), language="text")
                    cur.execute("SELECT oi.product_id, p.sku, p.format, oi.quantity,"
                                " oi.unit_price_cents FROM order_items oi"
                                " JOIN products p ON p.id=oi.product_id"
                                " WHERE oi.order_id=%s", (order_id,))
                    st.dataframe(pd.DataFrame(
                        cur.fetchall(),
                        columns=["product_id", "sku", "format", "qty", "unit_price"],
                    ), hide_index=True)
                else:
                    st.warning("Not found in Postgres.")
        except psycopg.errors.UndefinedTable:
            schema_missing_note("Data explorer")

        st.markdown("**MongoDB (denormalized order_view)**")
        doc = MONGO["order_view"].find_one({"event_id": order_id}, {"_id": 0})
        st.json(doc if doc else {"found": False})

        st.markdown("**Redis (keys this order touched)**")
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        st.code("\n".join(
            f"{k} = {R.get(k)}"
            for k in [f"stats:{today}:orders", f"stats:{today}:revenue_cents"]
        ) or "no keys", language="text")
