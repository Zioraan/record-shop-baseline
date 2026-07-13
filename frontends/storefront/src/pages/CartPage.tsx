import { useState } from "react";
import { api, formatPrice } from "../api/client";
import type { CartOut, OrderOut } from "../api/types";

interface Props {
  cart: CartOut | null;
  onCartChange: () => Promise<void>;
}

/** Demo store: checkout as a random seeded customer (1–200). */
const DEMO_CUSTOMER_ID = 1 + Math.floor(Math.random() * 200);

export default function CartPage({ cart, onCartChange }: Props) {
  const [order, setOrder] = useState<OrderOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (order) {
    return (
      <div className="confirm">
        <h2>Order placed 🎶</h2>
        <p>
          Total <strong>{formatPrice(order.total_cents)}</strong> — status {order.status}
        </p>
        <p>
          Trace this order through the pipeline with event id <code>{order.event_id}</code>
        </p>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>
          (Paste it into the reporting dashboard&apos;s Pipeline tab, or{" "}
          <code>docker compose logs | grep {order.event_id.slice(0, 12)}…</code>)
        </p>
      </div>
    );
  }

  if (!cart || cart.items.length === 0) return <p>Your cart is empty.</p>;

  const checkout = async () => {
    setBusy(true);
    setError(null);
    void api.trackEvent("checkout_started");
    try {
      const placed = await api.placeOrder(
        DEMO_CUSTOMER_ID,
        cart.items.map((l) => ({ product_id: l.product_id, quantity: l.quantity })),
      );
      await api.clearCart();
      await onCartChange();
      setOrder(placed);
    } catch (e) {
      setError(e instanceof Error ? e.message : "checkout failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="cart-page">
      <h2>Your cart</h2>
      <table>
        <thead>
          <tr>
            <th>Album</th>
            <th>Format</th>
            <th>Qty</th>
            <th>Price</th>
          </tr>
        </thead>
        <tbody>
          {cart.items.map((l) => (
            <tr key={l.product_id}>
              <td>{l.album_title}</td>
              <td>{l.format}</td>
              <td>{l.quantity}</td>
              <td>{formatPrice(l.unit_price_cents * l.quantity)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>Total: {formatPrice(cart.total_cents)}</h3>
      {error && <p className="error">{error}</p>}
      <button className="buy" disabled={busy} onClick={() => void checkout()}>
        {busy ? "Placing order…" : "Checkout"}
      </button>
    </div>
  );
}
