"""Correlation identifiers.

event_id : ULID-style, minted once at the edge (API), business correlation key.
trace_id : OpenTelemetry trace id of the originating request; stored on the
           outbox row and propagated through Kafka headers.
"""
from __future__ import annotations

import os
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def new_event_id(prefix: str = "evt") -> str:
    """Sortable ULID with a readable prefix, e.g. ord_01J9XK...."""
    ts_ms = int(time.time() * 1000)
    randomness = int.from_bytes(os.urandom(10), "big")
    return f"{prefix}_{_encode(ts_ms, 10)}{_encode(randomness, 16)}"


def new_order_id() -> str:
    return new_event_id("ord")
