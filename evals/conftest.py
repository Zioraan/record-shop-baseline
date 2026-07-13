"""Shared fixtures for all eval phases.

Evals run on the HOST against the composed stack (localhost ports).
Requires: pip install pytest httpx psycopg[binary] pymongo redis confluent-kafka
"""
from __future__ import annotations

import os
import subprocess
import time

import httpx
import pytest

API = os.environ.get("EVAL_API_URL", "http://localhost:8000")
PG_DSN = os.environ.get("EVAL_PG_DSN",
                        "postgresql://shop:shop@localhost:5432/recordshop")
MONGO_URI = os.environ.get("EVAL_MONGO_URI", "mongodb://localhost:27017")
REDIS_URL = os.environ.get("EVAL_REDIS_URL", "redis://localhost:6379/0")
KAFKA = os.environ.get("EVAL_KAFKA", "localhost:29092")


@pytest.fixture(scope="session")
def api() -> httpx.Client:
    client = httpx.Client(base_url=API, timeout=15)
    yield client
    client.close()


@pytest.fixture(scope="session")
def pg():
    import psycopg
    conn = psycopg.connect(PG_DSN, autocommit=True)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def mongo():
    from pymongo import MongoClient
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    yield client["recordshop"]
    client.close()


@pytest.fixture(scope="session")
def redis_client():
    import redis as redis_lib
    r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
    yield r
    r.close()


@pytest.fixture()
def kafka_consumer_factory():
    from confluent_kafka import Consumer

    consumers = []

    def make(topic: str, group: str | None = None) -> "Consumer":
        c = Consumer({
            "bootstrap.servers": KAFKA,
            "group.id": group or f"eval-{time.time_ns()}",
            "auto.offset.reset": "earliest",
        })
        c.subscribe([topic])
        consumers.append(c)
        return c

    yield make
    for c in consumers:
        c.close()


def compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", *args], capture_output=True,
                          text=True, cwd=os.path.dirname(os.path.dirname(__file__)))


def place_order(api: httpx.Client, product_ids: list[int],
                idempotency_key: str | None = None) -> dict:
    headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
    resp = api.post("/orders", json={
        "customer_id": 1,
        "items": [{"product_id": p, "quantity": 1} for p in product_ids],
    }, headers=headers)
    resp.raise_for_status()
    return resp.json()


def wait_for(predicate, timeout_s: float = 10, interval_s: float = 0.25):
    """Poll until predicate() is truthy; return its value or raise."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval_s)
    raise TimeoutError(f"condition not met within {timeout_s}s")
