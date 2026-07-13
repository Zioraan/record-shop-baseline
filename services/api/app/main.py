"""Record Shop API — STUDENT SKELETON (Phase 1+).

You will grow this file across the phases. The response models in
`models.py` are GIVEN — they are the contract the TypeScript storefront
already compiles against (`frontends/storefront/src/api/types.ts` mirrors
them; keep the two in sync).

Teaching moments this service must end up implementing:
- event_id + trace_id minted at the edge (principle #1)          [E1.7]
- order + outbox row in ONE transaction (principle #2)           [E1.5]
- idempotent order creation via Redis SETNX                      [E1.4]
- inventory decrement for physical formats only                  [E1.6]
- checkpoints api.received / db.committed (principle #4)         [E2.4]
- /events producing clickstream to Kafka                         [Phase 2]

Read `docs/PROJECT_CONTEXT.md` §6 (landmines) BEFORE you start.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "/app/libs")  # container layout; harmless elsewhere

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# from .models import (AlbumDetail, AlbumSummary, CartItemIn, CartOut,
#                      ClickEventIn, OrderIn, OrderOut, TopSellerOut)

app = FastAPI(title="Record Shop API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

# TODO [E6.2]: mount prometheus_client's ASGI app at /metrics.
# TODO [E1.7]: JSON logging with event_id/trace_id on every order-related line
#              (use libs/common/logging.py — it is given).
# TODO [E1.1]: lifespan that opens a psycopg_pool ConnectionPool and a Redis
#              client (see docs/STACK_SPEC.md §2 for the env contract).


@app.get("/healthz")
def healthz():
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Phase 1 — catalog, cart, orders                                             #
# --------------------------------------------------------------------------- #

@app.get("/genres")
def list_genres():
    raise HTTPException(501, "TODO Phase 1: list genre names from Postgres")


@app.get("/albums")
def list_albums(genre: str | None = None, q: str | None = None,
                limit: int = 24, offset: int = 0):
    raise HTTPException(501, "TODO Phase 1 [E1.2]: album summaries "
                             "(filter by genre / search, min product price)")


# NOTE (landmine #5): /albums/top must be declared BEFORE /albums/{album_id}
# or FastAPI tries to parse "top" as an int. The Top Sellers rail is a
# post-Phase-3 exercise — the storefront hides it while this 501s.
@app.get("/albums/top")
def top_albums(limit: int = 8):
    raise HTTPException(501, "TODO after Phase 3: Redis leaderboard + "
                             "Postgres hydration, SQL fallback for cold start")


@app.get("/albums/{album_id}")
def get_album(album_id: int):
    raise HTTPException(501, "TODO Phase 1: album detail with tracks and "
                             "products; Redis cache-aside (5 min TTL)")


@app.get("/cart/{session_id}")
def get_cart(session_id: str):
    raise HTTPException(501, "TODO Phase 1: Redis-backed session cart")


@app.post("/cart/{session_id}/items")
def add_to_cart(session_id: str):
    raise HTTPException(501, "TODO Phase 1: add item; cart is a Redis hash "
                             "with a 2 h TTL")


@app.delete("/cart/{session_id}")
def clear_cart(session_id: str):
    raise HTTPException(501, "TODO Phase 1: clear cart")


@app.post("/orders")
def create_order():
    raise HTTPException(501, "TODO Phase 1 [E1.4, E1.5, E1.6]: THE endpoint. "
                             "Mint event_id/trace_id; Idempotency-Key via "
                             "Redis SETNX; order + order_items + outbox row "
                             "in ONE transaction; 409 on insufficient stock")


@app.post("/events")
def track_event():
    raise HTTPException(501, "TODO Phase 1 stub, Phase 2 real: archive to "
                             "Postgres, produce to clickstream.events")
