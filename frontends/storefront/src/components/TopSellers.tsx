import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { albumArt, api, formatPrice } from "../api/client";
import type { TopSellerOut } from "../api/types";

const POLL_MS = 15_000;

/** Top-sellers rail: the stream path's Redis leaderboard feeding back into
 *  the product. Polls so the rail visibly reorders as orders flow. */
export default function TopSellers() {
  const [sellers, setSellers] = useState<TopSellerOut[]>([]);

  useEffect(() => {
    const load = () => void api.topAlbums(8).then(setSellers).catch(() => {});
    load();
    const timer = window.setInterval(load, POLL_MS);
    return () => window.clearInterval(timer);
  }, []);

  if (sellers.length === 0) return null;

  const live = sellers[0].source === "stream";
  return (
    <section className="top-sellers">
      <div className="top-sellers-head">
        <h2>🔥 Top sellers</h2>
        <span className="top-sellers-src">
          {live ? "live — as orders happen" : "from order history"}
        </span>
      </div>
      <div className="top-sellers-rail">
        {sellers.map((a, i) => (
          <Link
            key={a.id}
            to={`/album/${a.id}`}
            className="album-card seller-card"
            onClick={() => void api.trackEvent("page_view", a.id)}
          >
            <span className="rank-badge">#{i + 1}</span>
            <img src={albumArt(a.id, a.title)} alt={a.title} />
            <h3>{a.title}</h3>
            <p>{a.artist}</p>
            <p className="units">{a.units_sold} sold</p>
            <p className="price">from {formatPrice(a.from_price_cents)}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
