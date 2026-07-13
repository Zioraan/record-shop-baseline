# Evals — the definition of done

Fixtures (`conftest.py`) and dependencies (`requirements.txt`) are given.
The tests are YOUR deliverable, written with or before each feature:
one file per phase, `evals/phaseN/test_phaseN.py`, one test per eval ID
named `test_eN_M_<slug>` so `pytest -k e2_3` runs exactly one eval.
The assertion tables live in AGENT_HANDOFF.md §4.

Run from the host: `pip install -r evals/requirements.txt` then
`pytest evals/phase1 -v`. Kafka from the host is `localhost:29092`.
Landmine #8: run E3.2 with the simulator OFF, and E6.4 at least ~10 min
after any kill-the-processor drill.
