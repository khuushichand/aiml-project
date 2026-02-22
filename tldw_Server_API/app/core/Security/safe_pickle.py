"""Restricted pickle deserialization helpers.

Use this module only for legacy compatibility paths where pickle is unavoidable.
It intentionally permits a narrow set of built-in value container types.
"""

from __future__ import annotations

import builtins
import io
import pickle
from collections import OrderedDict
from typing import Any

_ALLOWED_GLOBALS: dict[tuple[str, str], Any] = {
    ("builtins", "dict"): builtins.dict,
    ("builtins", "list"): builtins.list,
    ("builtins", "set"): builtins.set,
    ("builtins", "tuple"): builtins.tuple,
    ("builtins", "str"): builtins.str,
    ("builtins", "bytes"): builtins.bytes,
    ("builtins", "bytearray"): builtins.bytearray,
    ("builtins", "int"): builtins.int,
    ("builtins", "float"): builtins.float,
    ("builtins", "bool"): builtins.bool,
    ("collections", "OrderedDict"): OrderedDict,
}


class RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that blocks arbitrary global class/function resolution."""

    def find_class(self, module: str, name: str) -> Any:  # type: ignore[override]
        key = (module, name)
        if key in _ALLOWED_GLOBALS:
            return _ALLOWED_GLOBALS[key]
        raise pickle.UnpicklingError(f"Disallowed pickle class/function: {module}.{name}")


def safe_pickle_loads(data: bytes) -> Any:
    """Deserialize trusted legacy pickle data with a restricted allowlist."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("pickle payload must be bytes")
    try:
        return RestrictedUnpickler(io.BytesIO(bytes(data))).load()
    except pickle.PickleError as exc:
        raise ValueError(f"Unsafe pickle payload: {exc}") from exc
