"""`make seed` entry point (Phase 1). Phase 4 wraps the same functions in Prefect."""
from __future__ import annotations

import argparse
import os

import psycopg

from .logging import configure_logging
from .seeding import DEFAULT_SEED, build_catalog, catalog_checksum, load_catalog, seed_history


def main() -> None:
    logger = configure_logging("seed-cli")
    parser = argparse.ArgumentParser()
    parser.add_argument("--artists", type=int, default=150)
    parser.add_argument("--history-days", type=int, default=30)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    dsn = os.environ["POSTGRES_DSN"]
    catalog = build_catalog(seed=args.seed, artist_count=args.artists)
    try:
        with psycopg.connect(dsn) as conn:
            load_catalog(conn, catalog)
            seed_history(conn, catalog, seed=args.seed, days=args.history_days)
            logger.info("seed complete", extra={"checksum": catalog_checksum(conn)})
    except Exception as exc:
        logger.error(f"SEED FAILED: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
