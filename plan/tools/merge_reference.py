"""Small, pure three-way feature merge oracle for tests, NOT a production engine.

None means a deleted/nonexistent FEATURE. A field value may itself be None.
Geometry is an opaque atomic value under the key `geometry`; canonical EWKB,
schema/rules, attachments, permissions, transactions and durable history are NOT
implemented here. This deliberately exposes rather than conceals those gaps.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

_MISSING = object()


@dataclass(frozen=True)
class MergeResult:
    candidate: dict[str, Any] | None
    conflicts: tuple[str, ...]


def merge_feature(base: dict[str, Any] | None, ours: dict[str, Any] | None,
                  target: dict[str, Any] | None) -> MergeResult:
    """Return a candidate only when conflict-free; never silently prefer a side."""
    for value in (base, ours, target):
        if value is not None and not isinstance(value, dict):
            raise TypeError("Feature state must be a dictionary or None.")
    if ours == base:
        return MergeResult(deepcopy(target), ())
    if target == base or ours == target:
        return MergeResult(deepcopy(ours), ())
    if base is None:
        # Two distinct insertions under one logical UUID are an identity conflict.
        return MergeResult(None, ("insert/insert",))
    if ours is None or target is None:
        return MergeResult(None, ("delete/update",))
    candidate: dict[str, Any] = {}
    conflicts: list[str] = []
    for key in sorted(set(base) | set(ours) | set(target)):
        b, o, t = base.get(key, _MISSING), ours.get(key, _MISSING), target.get(key, _MISSING)
        if o == b:
            value = t
        elif t == b or o == t:
            value = o
        else:
            conflicts.append(key)
            continue
        if value is not _MISSING:
            candidate[key] = deepcopy(value)
    return MergeResult(None if conflicts else candidate, tuple(conflicts))
