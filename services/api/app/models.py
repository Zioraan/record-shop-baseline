"""Pydantic API models. frontends/storefront/src/api/types.ts mirrors these."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Format = Literal["vinyl", "cd", "digital"]


class ProductOut(BaseModel):
    id: int
    sku: str
    format: Format
    price_cents: int
    in_stock: Optional[int] = None  # None = digital (infinite)


class AlbumSummary(BaseModel):
    id: int
    title: str
    artist: str
    genre: str
    release_date: str
    from_price_cents: int


class TopSellerOut(AlbumSummary):
    units_sold: int
    # "stream": live Redis leaderboard maintained by the stream processor.
    # "sql": fallback aggregation over Postgres order history (cold start,
    #        before any orders have flowed through the stream path).
    source: Literal["stream", "sql"]


class AlbumDetail(BaseModel):
    id: int
    title: str
    artist: str
    genre: str
    release_date: str
    tracks: list[TrackOut]
    products: list[ProductOut]


class TrackOut(BaseModel):
    position: int
    title: str
    duration_s: int


class CartItemIn(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=10)


class CartOut(BaseModel):
    session_id: str
    items: list[CartLine]
    total_cents: int


class CartLine(BaseModel):
    product_id: int
    sku: str
    album_title: str
    format: Format
    quantity: int
    unit_price_cents: int


class OrderIn(BaseModel):
    customer_id: int
    items: list[CartItemIn] = Field(min_length=1)


class OrderOut(BaseModel):
    order_id: str
    event_id: str
    trace_id: str
    status: str
    total_cents: int


class ClickEventIn(BaseModel):
    event_type: Literal["page_view", "track_preview", "add_to_cart", "checkout_started"]
    album_id: Optional[int] = None
    customer_id: Optional[int] = None


AlbumDetail.model_rebuild()
CartOut.model_rebuild()
