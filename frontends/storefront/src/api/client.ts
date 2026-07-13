import type {
  AlbumDetail,
  AlbumSummary,
  CartOut,
  ClickEventType,
  OrderOut,
  TopSellerOut,
} from "./types";

const BASE = "/api";

/** Session id doubles as the cart key and the idempotency-key prefix. */
export const sessionId: string =
  window.crypto?.randomUUID?.() ?? `sess-${Date.now()}-${Math.random()}`;

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return (await res.json()) as T;
}

async function send<T>(
  method: "POST" | "DELETE",
  path: string,
  body?: unknown,
  headers?: Record<string, string>,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...headers },
    body: body === undefined ? null : JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${method} ${path} -> ${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export const api = {
  genres: (): Promise<string[]> => get("/genres"),

  albums: (params: { genre?: string; q?: string; offset?: number }): Promise<AlbumSummary[]> => {
    const search = new URLSearchParams();
    if (params.genre) search.set("genre", params.genre);
    if (params.q) search.set("q", params.q);
    if (params.offset) search.set("offset", String(params.offset));
    const qs = search.toString();
    return get(`/albums${qs ? `?${qs}` : ""}`);
  },

  album: (id: number): Promise<AlbumDetail> => get(`/albums/${id}`),

  topAlbums: (limit = 8): Promise<TopSellerOut[]> => get(`/albums/top?limit=${limit}`),

  cart: (): Promise<CartOut> => get(`/cart/${sessionId}`),

  addToCart: (productId: number, quantity = 1): Promise<CartOut> =>
    send("POST", `/cart/${sessionId}/items`, { product_id: productId, quantity }),

  clearCart: (): Promise<CartOut> => send("DELETE", `/cart/${sessionId}`),

  placeOrder: (customerId: number, items: { product_id: number; quantity: number }[]): Promise<OrderOut> =>
    send(
      "POST",
      "/orders",
      { customer_id: customerId, items },
      // one idempotency key per checkout attempt batch
      { "Idempotency-Key": `${sessionId}:${items.map((i) => `${i.product_id}x${i.quantity}`).join(",")}` },
    ),

  trackEvent: (eventType: ClickEventType, albumId?: number): Promise<void> =>
    send("POST", "/events", { event_type: eventType, album_id: albumId ?? null }).then(
      () => undefined,
    ),
};

export function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

/** Deterministic SVG album art from the album id (spec §4.9). */
export function albumArt(albumId: number, title: string): string {
  const hue1 = (albumId * 47) % 360;
  const hue2 = (albumId * 89 + 120) % 360;
  const shape = albumId % 3;
  const inner =
    shape === 0
      ? `<circle cx="60" cy="60" r="34" fill="hsl(${hue2},65%,55%)"/>`
      : shape === 1
        ? `<rect x="28" y="28" width="64" height="64" rx="8" fill="hsl(${hue2},65%,55%)" transform="rotate(${(albumId * 13) % 45} 60 60)"/>`
        : `<polygon points="60,22 96,90 24,90" fill="hsl(${hue2},65%,55%)"/>`;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120"><rect width="120" height="120" fill="hsl(${hue1},50%,30%)"/>${inner}<text x="60" y="112" font-size="9" fill="white" text-anchor="middle" font-family="sans-serif">${title.slice(0, 20).replace(/&/g, "&amp;").replace(/</g, "&lt;")}</text></svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}
