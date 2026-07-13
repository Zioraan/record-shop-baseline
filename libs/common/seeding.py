"""Deterministic catalog + history seeder — STUDENT SKELETON (Phase 1).

Contract (docs/STACK_SPEC.md §9, evals E1.2/E1.3):
- Everything derives from RANDOM_SEED (default 1138). Re-running produces a
  byte-identical catalog — E1.3 checksums ordered `products` rows.
- Targets: 12 genres · 140–160 artists · ~400 albums (1–3 products each,
  vinyl/CD/digital with distinct SKUs) · ~200 customers · ~30 days of order
  + clickstream history. Zipf-distributed artist popularity; log-normal
  pricing with vinyl > CD > digital for the same album.
- Inventory rows for physical formats ONLY [E1.6 depends on this].
- Genre/artist/album name templates are GIVEN in `catalog_data.py` so every
  student's catalog matches lecture references.

Landmines already paid for (docs/PROJECT_CONTEXT.md §6 — encode them NOW):
- `SET lock_timeout = '5s'` before TRUNCATE, and raise a clear error with a
  pg_stat_activity diagnosis instead of hanging silently (landmine #2).
- Bulk-insert with executemany; log structured progress so a slow seed is
  visibly alive.
"""
from __future__ import annotations


def seed(dsn: str, random_seed: int = 1138, history_days: int = 30) -> None:
    """TODO Phase 1 [E1.2, E1.3]: truncate-and-reload, deterministic."""
    raise NotImplementedError("Phase 1")
