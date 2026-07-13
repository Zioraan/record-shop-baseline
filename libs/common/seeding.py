"""Deterministic music-catalog seeder (spec §4.9).

Everything derives from RANDOM_SEED (default 1138), so every student machine
generates the IDENTICAL catalog: ~12 genres → ~150 artists → ~400 albums →
~4000 tracks; each album in 1–3 formats (distinct SKU products); vinyl/CD get
inventory rows, digital does not. Also seeds ~200 customers and ~30 days of
historical orders + clickstream so the batch path is interesting on day one.

Plain module in Phase 1 (invoked by `make seed` / seed_cli); wrapped by
Prefect's seed_flow in Phase 4.
"""
from __future__ import annotations

import logging
import math
import os
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from .catalog_data import FORMAT_MULTIPLIER, GENRES, WORDS
from .ids import new_event_id

logger = logging.getLogger("seeding")

DEFAULT_SEED = int(os.environ.get("RANDOM_SEED", "1138"))
ZIPF_S = 1.1  # skew: a few "hit" artists dominate a long tail


@dataclass
class Catalog:
    genres: list[str] = field(default_factory=list)
    artists: list[dict] = field(default_factory=list)     # name, genre, formed_year, popularity
    albums: list[dict] = field(default_factory=list)      # artist_idx, title, release_date
    tracks: list[dict] = field(default_factory=list)      # album_idx, title, position, duration_s
    products: list[dict] = field(default_factory=list)    # sku, album_idx, format, price_cents
    inventory: list[dict] = field(default_factory=list)   # product_idx, quantity
    customers: list[dict] = field(default_factory=list)   # email, name, signup_date


def _fill(rng: random.Random, pattern: str) -> str:
    out = pattern
    for key, options in WORDS.items():
        while "{" + key + "}" in out:
            out = out.replace("{" + key + "}", rng.choice(options), 1)
    out = out.replace("{n1}", str(rng.randint(1, 6))).replace("{n2}", str(rng.randint(7, 12)))
    return out


def _track_title(rng: random.Random) -> str:
    style = rng.random()
    if style < 0.4:
        return f"{rng.choice(WORDS['track_verb'])} in the {rng.choice(WORDS['track_noun'])}"
    if style < 0.7:
        return f"The {rng.choice(WORDS['track_noun'])}"
    return f"{rng.choice(WORDS['adj'])} {rng.choice(WORDS['track_noun'])}"


def _zipf_weights(n: int) -> list[float]:
    raw = [1.0 / (rank ** ZIPF_S) for rank in range(1, n + 1)]
    total = sum(raw)
    return [w / total for w in raw]


def build_catalog(seed: int = DEFAULT_SEED, artist_count: int = 150) -> Catalog:
    """Pure function: same seed → identical catalog. No I/O."""
    rng = random.Random(seed)
    cat = Catalog(genres=list(GENRES.keys()))

    # --- artists, spread across genres --------------------------------------
    seen_names: set[str] = set()
    for i in range(artist_count):
        genre = cat.genres[i % len(cat.genres)]
        spec = GENRES[genre]
        for _ in range(50):
            name = _fill(rng, rng.choice(spec["artist_patterns"]))
            if name not in seen_names:
                seen_names.add(name)
                break
        era = spec["era"]
        cat.artists.append({
            "name": name, "genre": genre,
            "formed_year": rng.randint(era[0], min(era[1], 2020)),
            "popularity": 0.0,  # assigned after shuffle below
        })

    # Zipf popularity assigned over a seeded shuffle so hits span genres.
    order = list(range(artist_count))
    rng.shuffle(order)
    for rank_pos, artist_idx in enumerate(order):
        cat.artists[artist_idx]["popularity"] = _zipf_weights(artist_count)[rank_pos]

    # --- albums & tracks ------------------------------------------------------
    seen_titles: set[str] = set()
    for artist_idx, artist in enumerate(cat.artists):
        spec = GENRES[artist["genre"]]
        for _ in range(rng.randint(1, 4)):  # ~2.5 albums/artist avg → ~375 albums
            for _ in range(50):
                title = _fill(rng, rng.choice(spec["album_patterns"]))
                if (artist["name"], title) not in seen_titles:
                    seen_titles.add((artist["name"], title))
                    break
            year = rng.randint(max(artist["formed_year"], spec["era"][0]), spec["era"][1])
            release = date(year, rng.randint(1, 12), rng.randint(1, 28))
            album_idx = len(cat.albums)
            cat.albums.append({"artist_idx": artist_idx, "title": title, "release_date": release})
            for pos in range(1, rng.randint(8, 14)):
                cat.tracks.append({
                    "album_idx": album_idx, "title": _track_title(rng),
                    "position": pos, "duration_s": rng.randint(120, 420),
                })

    # --- products (album × format) & inventory --------------------------------
    for album_idx, album in enumerate(cat.albums):
        genre = cat.artists[album["artist_idx"]]["genre"]
        mu = GENRES[genre]["price_mu"]
        base = int(rng.lognormvariate(math.log(mu), 0.25))
        formats = ["digital"]
        if rng.random() < 0.75:
            formats.append("cd")
        if rng.random() < 0.55:
            formats.append("vinyl")
        for fmt in formats:
            product_idx = len(cat.products)
            cat.products.append({
                "sku": f"SKU-{product_idx + 1:05d}",
                "album_idx": album_idx, "format": fmt,
                "price_cents": max(499, int(base * FORMAT_MULTIPLIER[fmt])),
            })
            if fmt != "digital":
                cat.inventory.append({"product_idx": product_idx,
                                      "quantity": rng.randint(5, 120)})

    # --- customers -------------------------------------------------------------
    seen_emails: set[str] = set()
    for i in range(200):
        first, last = rng.choice(WORDS["first"]), rng.choice(WORDS["last"])
        email = f"{first.lower()}.{last.lower()}{i}@example.com"
        if email in seen_emails:
            continue
        seen_emails.add(email)
        cat.customers.append({
            "email": email, "name": f"{first} {last}",
            "signup_date": date(2024, 1, 1) + timedelta(days=rng.randint(0, 850)),
        })

    logger.info("catalog built", extra={
        "genres": len(cat.genres), "artists": len(cat.artists),
        "albums": len(cat.albums), "tracks": len(cat.tracks),
        "products": len(cat.products),
    })
    return cat


# --------------------------------------------------------------------------- #
# Database loading
# --------------------------------------------------------------------------- #

class SeedLockTimeout(RuntimeError):
    """TRUNCATE could not acquire ACCESS EXCLUSIVE locks within lock_timeout."""


def load_catalog(conn, cat: Catalog) -> None:
    """Idempotent truncate-and-reload into Postgres (psycopg connection)."""
    with conn.cursor() as cur:
        cur.execute("SET lock_timeout = '5s'")
        try:
            cur.execute(
                "TRUNCATE order_items, orders, outbox, clickstream_archive, inventory,"
                " products, tracks, albums, artists, genres, customers"
                " RESTART IDENTITY CASCADE"
            )
        except Exception as exc:
            conn.rollback()
            raise SeedLockTimeout(
                "TRUNCATE timed out waiting for table locks. Another connection is "
                "holding locks (usually 'idle in transaction' — often the outbox "
                "relay after a non-autocommit SELECT). Inspect with: "
                "SELECT pid, state, wait_event_type, query FROM pg_stat_activity; "
                "Quick remedy: docker compose restart outbox-relay stream-processor "
                "then retry."
            ) from exc
        cur.execute("SET lock_timeout = 0")

        for name in cat.genres:
            cur.execute("INSERT INTO genres (name) VALUES (%s)", (name,))
        genre_ids = dict(_rows(cur, "SELECT name, id FROM genres"))
        logger.info("genres loaded", extra={"count": len(cat.genres)})

        cur.executemany(
            "INSERT INTO artists (name, genre_id, formed_year, popularity)"
            " VALUES (%s,%s,%s,%s)",
            [
                (a["name"], genre_ids[a["genre"]], a["formed_year"], a["popularity"])
                for a in cat.artists
            ],
        )
        logger.info("artists loaded", extra={"count": len(cat.artists)})

        cur.executemany(
            "INSERT INTO albums (artist_id, title, release_date) VALUES (%s,%s,%s)",
            [
                (al["artist_idx"] + 1, al["title"], al["release_date"])
                for al in cat.albums
            ],
        )
        cur.executemany(
            "INSERT INTO tracks (album_id, title, position, duration_s)"
            " VALUES (%s,%s,%s,%s)",
            [
                (t["album_idx"] + 1, t["title"], t["position"], t["duration_s"])
                for t in cat.tracks
            ],
        )
        logger.info(
            "albums+tracks loaded",
            extra={"albums": len(cat.albums), "tracks": len(cat.tracks)},
        )

        cur.executemany(
            "INSERT INTO products (sku, album_id, format, price_cents)"
            " VALUES (%s,%s,%s,%s)",
            [
                (p["sku"], p["album_idx"] + 1, p["format"], p["price_cents"])
                for p in cat.products
            ],
        )
        cur.executemany(
            "INSERT INTO inventory (product_id, quantity) VALUES (%s,%s)",
            [
                (inv["product_idx"] + 1, inv["quantity"])
                for inv in cat.inventory
            ],
        )
        cur.executemany(
            "INSERT INTO customers (email, name, signup_date) VALUES (%s,%s,%s)",
            [
                (c["email"], c["name"], c["signup_date"])
                for c in cat.customers
            ],
        )
        logger.info(
            "products+inventory+customers loaded",
            extra={
                "products": len(cat.products),
                "inventory": len(cat.inventory),
                "customers": len(cat.customers),
            },
        )
    conn.commit()


def seed_history(conn, cat: Catalog, seed: int = DEFAULT_SEED, days: int = 30) -> int:
    """~30 days of historical orders + clickstream, popularity-weighted.

    Historical rows are marked published in the outbox so the relay does not
    replay a month of history through the stream path on first boot.
    """
    rng = random.Random(seed + 1)
    product_weights = [cat.artists[cat.albums[p["album_idx"]]["artist_idx"]]["popularity"]
                       for p in cat.products]
    n_orders = 0
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        for day_offset in range(days, 0, -1):
            day = now - timedelta(days=day_offset)
            for _ in range(rng.randint(15, 45)):
                customer_id = rng.randint(1, len(cat.customers))
                items = rng.choices(range(len(cat.products)),
                                    weights=product_weights, k=rng.randint(1, 3))
                order_id = new_event_id("ord")
                trace_id = f"{rng.getrandbits(128):032x}"
                ts = day + timedelta(seconds=rng.randint(0, 86_399))
                total = 0
                rows = []
                for pi in set(items):
                    qty = rng.randint(1, 2)
                    price = cat.products[pi]["price_cents"]
                    total += qty * price
                    rows.append((pi + 1, qty, price))
                    # clickstream leading up to the purchase (funnel-consistent)
                    album_id = cat.products[pi]["album_idx"] + 1
                    for etype in ("page_view", "track_preview", "add_to_cart"):
                        if etype == "page_view" or rng.random() < 0.8:
                            cur.execute(
                                "INSERT INTO clickstream_archive"
                                " (event_id, trace_id, event_type, customer_id, album_id, ts)"
                                " VALUES (%s,%s,%s,%s,%s,%s)",
                                (new_event_id("clk"), trace_id, etype, customer_id,
                                 album_id, ts - timedelta(minutes=rng.randint(1, 30))),
                            )
                cur.execute(
                    "INSERT INTO orders (id, event_id, trace_id, customer_id, status,"
                    " total_cents, created_at) VALUES (%s,%s,%s,%s,'paid',%s,%s)",
                    (order_id, order_id, trace_id, customer_id, total, ts),
                )
                for product_id, qty, price in rows:
                    cur.execute(
                        "INSERT INTO order_items (order_id, product_id, quantity,"
                        " unit_price_cents) VALUES (%s,%s,%s,%s)",
                        (order_id, product_id, qty, price),
                    )
                cur.execute(
                    "INSERT INTO outbox (aggregate_type, aggregate_id, event_type,"
                    " payload, trace_id, created_at, published_at)"
                    " VALUES ('order', %s, 'orders.created', '{}'::jsonb, %s, %s, %s)",
                    (order_id, trace_id, ts, ts),
                )
                n_orders += 1
            if day_offset % 10 == 0:
                logger.info(
                    "history day progress",
                    extra={"days_remaining": day_offset, "orders_so_far": n_orders},
                )
    conn.commit()
    logger.info("history seeded", extra={"orders": n_orders, "days": days})
    return n_orders


def catalog_checksum(conn) -> str:
    """Golden checksum over ordered product rows — used by eval E1.3."""
    import hashlib
    with conn.cursor() as cur:
        cur.execute("SELECT sku, album_id, format, price_cents FROM products ORDER BY sku")
        digest = hashlib.sha256()
        for row in cur.fetchall():
            digest.update(repr(row).encode())
    return digest.hexdigest()


def _rows(cur, sql: str):
    cur.execute(sql)
    return cur.fetchall()
