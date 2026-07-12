"""Canonical JSON encoding shared by envelopes, log entries and STHs.

Sorted keys, no whitespace, UTF-8 — byte-stable across processes so
signatures and hashes are reproducible.
"""
import json
from typing import Any


def canonical_json(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
