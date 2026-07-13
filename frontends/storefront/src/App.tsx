import { useCallback, useEffect, useState } from "react";
import { Link, Route, Routes, useNavigate } from "react-router-dom";
import { api } from "./api/client";
import type { CartOut } from "./api/types";
import AlbumPage from "./pages/AlbumPage";
import CartPage from "./pages/CartPage";
import CatalogPage from "./pages/CatalogPage";

export default function App() {
  const [cart, setCart] = useState<CartOut | null>(null);
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  const refreshCart = useCallback(async () => {
    try {
      setCart(await api.cart());
    } catch {
      setCart(null);
    }
  }, []);

  useEffect(() => {
    void refreshCart();
  }, [refreshCart]);

  const itemCount = cart?.items.reduce((n, l) => n + l.quantity, 0) ?? 0;

  return (
    <>
      <header className="site">
        <h1>
          <Link to="/">
            THE <span>RECORD</span> SHOP
          </Link>
        </h1>
        <nav>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              navigate(`/?q=${encodeURIComponent(search)}`);
            }}
          >
            <input
              placeholder="Search albums or artists…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </form>
        </nav>
        <Link to="/cart" className="cart-chip">
          Cart ({itemCount})
        </Link>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<CatalogPage />} />
          <Route path="/album/:id" element={<AlbumPage onCartChange={refreshCart} />} />
          <Route path="/cart" element={<CartPage cart={cart} onCartChange={refreshCart} />} />
        </Routes>
      </main>
    </>
  );
}
