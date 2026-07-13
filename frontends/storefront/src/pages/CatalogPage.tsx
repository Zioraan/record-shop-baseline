import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { albumArt, api, formatPrice } from "../api/client";
import type { AlbumSummary } from "../api/types";
import TopSellers from "../components/TopSellers";

export default function CatalogPage() {
  const [genres, setGenres] = useState<string[]>([]);
  const [albums, setAlbums] = useState<AlbumSummary[]>([]);
  const [activeGenre, setActiveGenre] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [params] = useSearchParams();
  const q = params.get("q") ?? undefined;

  useEffect(() => {
    api.genres().then(setGenres).catch(() => setError("API unreachable"));
  }, []);

  useEffect(() => {
    const query: { genre?: string; q?: string } = {};
    if (activeGenre) query.genre = activeGenre;
    if (q) query.q = q;
    api
      .albums(query)
      .then(setAlbums)
      .catch(() => setError("Could not load albums"));
  }, [activeGenre, q]);

  return (
    <>
      {activeGenre === null && !q && <TopSellers />}
      <div className="genre-row">
        <button className={activeGenre === null ? "active" : ""} onClick={() => setActiveGenre(null)}>
          All
        </button>
        {genres.map((g) => (
          <button
            key={g}
            className={activeGenre === g ? "active" : ""}
            onClick={() => setActiveGenre(g)}
          >
            {g}
          </button>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
      <div className="album-grid">
        {albums.map((a) => (
          <Link
            key={a.id}
            to={`/album/${a.id}`}
            className="album-card"
            onClick={() => void api.trackEvent("page_view", a.id)}
          >
            <img src={albumArt(a.id, a.title)} alt={a.title} />
            <h3>{a.title}</h3>
            <p>{a.artist}</p>
            <p>
              {a.genre} · {a.release_date.slice(0, 4)}
            </p>
            <p className="price">from {formatPrice(a.from_price_cents)}</p>
          </Link>
        ))}
      </div>
    </>
  );
}
