import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { albumArt, api, formatPrice } from "../api/client";
import type { AlbumDetail } from "../api/types";

interface Props {
  onCartChange: () => Promise<void>;
}

function duration(s: number): string {
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export default function AlbumPage({ onCartChange }: Props) {
  const { id } = useParams<{ id: string }>();
  const albumId = Number(id);
  const [album, setAlbum] = useState<AlbumDetail | null>(null);
  const [added, setAdded] = useState<number | null>(null);
  const [previewing, setPreviewing] = useState<number | null>(null);

  useEffect(() => {
    if (!Number.isFinite(albumId)) return;
    api.album(albumId).then(setAlbum).catch(() => setAlbum(null));
  }, [albumId]);

  if (!album) return <p>Loading…</p>;

  const addToCart = async (productId: number) => {
    await api.addToCart(productId);
    void api.trackEvent("add_to_cart", album.id);
    setAdded(productId);
    await onCartChange();
    window.setTimeout(() => setAdded(null), 1200);
  };

  const preview = (position: number) => {
    setPreviewing(position);
    void api.trackEvent("track_preview", album.id);
    window.setTimeout(() => setPreviewing(null), 1500);
  };

  return (
    <div className="album-page">
      <div>
        <img src={albumArt(album.id, album.title)} alt={album.title} />
        <div className="formats">
          {album.products.map((p) => (
            <div key={p.id} className="format-row">
              <div>
                <div className="fmt">{p.format}</div>
                <div className="stock">
                  {p.in_stock === null
                    ? "instant download"
                    : p.in_stock > 0
                      ? `${p.in_stock} in stock`
                      : "out of stock"}
                </div>
              </div>
              <div>
                <span className="price" style={{ marginRight: 12 }}>
                  {formatPrice(p.price_cents)}
                </span>
                <button
                  className="buy"
                  disabled={p.in_stock !== null && p.in_stock <= 0}
                  onClick={() => void addToCart(p.id)}
                >
                  {added === p.id ? "Added ✓" : "Add to cart"}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div>
        <h2>{album.title}</h2>
        <p>
          {album.artist} · {album.genre} · {album.release_date.slice(0, 4)}
        </p>
        <ol className="tracklist">
          {album.tracks.map((t) => (
            <li key={t.position}>
              <span>{t.position}.</span>
              <span>{t.title}</span>
              <button className="preview" onClick={() => preview(t.position)}>
                {previewing === t.position ? "playing…" : "▶ preview"}
              </button>
              <span className="dur">{duration(t.duration_s)}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
