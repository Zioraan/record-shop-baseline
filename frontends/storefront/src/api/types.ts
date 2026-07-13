/** Mirrors services/api/app/models.py — keep in sync. */

export type Format = "vinyl" | "cd" | "digital";

export interface ProductOut {
  id: number;
  sku: string;
  format: Format;
  price_cents: number;
  in_stock: number | null; // null = digital (infinite)
}

export interface AlbumSummary {
  id: number;
  title: string;
  artist: string;
  genre: string;
  release_date: string;
  from_price_cents: number;
}

export interface TopSellerOut extends AlbumSummary {
  units_sold: number;
  /** "stream" = live Redis leaderboard; "sql" = Postgres history fallback. */
  source: "stream" | "sql";
}

export interface TrackOut {
  position: number;
  title: string;
  duration_s: number;
}

export interface AlbumDetail {
  id: number;
  title: string;
  artist: string;
  genre: string;
  release_date: string;
  tracks: TrackOut[];
  products: ProductOut[];
}

export interface CartLine {
  product_id: number;
  sku: string;
  album_title: string;
  format: Format;
  quantity: number;
  unit_price_cents: number;
}

export interface CartOut {
  session_id: string;
  items: CartLine[];
  total_cents: number;
}

export interface OrderOut {
  order_id: string;
  event_id: string;
  trace_id: string;
  status: string;
  total_cents: number;
}

export type ClickEventType =
  | "page_view"
  | "track_preview"
  | "add_to_cart"
  | "checkout_started";
