"""
Pydantic compatibility helpers shared across the codebase.

Provides utilities to work with both Pydantic v1 and v2 models without relying
on deprecated APIs such as ``BaseModel.dict``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Optional, Set

from fastapi.encoders import jsonable_encoder


def model_dump_compat(
    obj: Any,
    *,
    exclude_none: bool = False,
    exclude: Optional[Iterable[Any]] = None,
    exclude_unset: bool = False,
) -> Dict[str, Any]:
    """
    Convert a Pydantic model or dict-like object into a plain dictionary.

    Prefers ``model_dump`` when available (Pydantic v2), falls back to
    ``model_dump_json`` or ``jsonable_encoder`` to maintain compatibility with
    Pydantic v1 models as well as dataclass-like inputs.
    """
    if obj is None:
        return {}

    exclude_set: Optional[Set[Any]] = set(exclude) if exclude is not None else None

    dump_method = getattr(obj, "model_dump", None)
    if callable(dump_method):
        try:
            kwargs: Dict[str, Any] = {"exclude_none": exclude_none}
            if exclude_set is not None:
                kwargs["exclude"] = exclude_set
            if exclude_unset:
                kwargs["exclude_unset"] = True
            return dump_method(**kwargs)
        except TypeError:
            return dump_method()

    dump_json_method = getattr(obj, "model_dump_json", None)
    if callable(dump_json_method):
        try:
            kwargs: Dict[str, Any] = {}
            if exclude_set is not None:
                kwargs["exclude"] = list(exclude_set)
            if exclude_unset:
                kwargs["exclude_unset"] = True
            payload = json.loads(dump_json_method(**kwargs))
            if isinstance(payload, dict):
                if exclude_set:
                    for key in exclude_set:
                        payload.pop(key, None)
                if exclude_none:
                    return {k: v for k, v in payload.items() if v is not None}
                return payload
        except Exception:
            # Continue to encoder-based handling if JSON dump fails
            pass

    if isinstance(obj, dict):
        data = dict(obj)
        if exclude_set:
            for key in exclude_set:
                data.pop(key, None)
        if exclude_none:
            return {k: v for k, v in data.items() if v is not None}
        return data

    encoded = jsonable_encoder(obj)
    if isinstance(encoded, dict):
        if exclude_set:
            for key in exclude_set:
                encoded.pop(key, None)
        if exclude_none:
            return {k: v for k, v in encoded.items() if v is not None}
        return encoded

    if hasattr(obj, "__dict__"):
        data = {k: v for k, v in vars(obj).items() if not k.startswith("_")}
        if exclude_set:
            for key in exclude_set:
                data.pop(key, None)
        if exclude_none:
            return {k: v for k, v in data.items() if v is not None}
        return data

    raise TypeError(f"Unsupported object for model_dump_compat: {type(obj)}")
