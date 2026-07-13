"""CLI entry point: `docker compose exec api python -m common.seed_cli`.

TODO Phase 1: call seeding.seed() with env config. Catch-all handler must
log `SEED FAILED` and exit 1 — never a silent hang or silent success.
(Prefect's seed_flow wraps the same function in Phase 4.)
"""
from __future__ import annotations

if __name__ == "__main__":
    raise SystemExit("TODO Phase 1: implement libs/common/seeding.py first")
