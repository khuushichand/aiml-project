"""Shared backend SQL helper utilities.

These helpers consolidate placeholder conversion, parameter normalisation, and
SQLite → PostgreSQL query rewrites so individual database adapters do not need
bespoke implementations.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .base import BackendType

ParamsType = Optional[Union[Tuple[Any, ...], List[Any], Dict[str, Any], Any]]


def normalise_params(params: ParamsType) -> Optional[Union[Tuple[Any, ...], Dict[str, Any]]]:
    """Normalize parameter containers for backend execution."""
    if params is None:
        return None
    if isinstance(params, dict):
        return params
    if isinstance(params, tuple):
        return params
    if isinstance(params, list):
        return tuple(params)
    return (params,)


def convert_sqlite_placeholders_to_postgres(query: str) -> str:
    """Convert SQLite positional placeholders (`?`) to PostgreSQL (`%s`)."""
    if "?" not in query:
        return query

    result: List[str] = []
    in_single = False
    in_double = False
    i = 0
    length = len(query)

    while i < length:
        ch = query[i]

        if ch == "'" and not in_double:
            if in_single:
                if i + 1 < length and query[i + 1] == "'":
                    result.append("''")
                    i += 2
                    continue
                in_single = False
                result.append(ch)
                i += 1
                continue
            in_single = True
            result.append(ch)
            i += 1
            continue

        if ch == '"' and not in_single:
            if in_double:
                if i + 1 < length and query[i + 1] == '"':
                    result.append('""')
                    i += 2
                    continue
                in_double = False
                result.append(ch)
                i += 1
                continue
            in_double = True
            result.append(ch)
            i += 1
            continue

        if ch == "?" and not in_single and not in_double:
            result.append("%s")
            i += 1
            continue

        result.append(ch)
        i += 1

    return ''.join(result)


def replace_insert_or_ignore(query: str) -> str:
    """Translate SQLite `INSERT OR IGNORE` statements into Postgres-compatible form."""
    if 'INSERT OR IGNORE' not in query.upper():
        return query

    pattern = re.compile(r'INSERT\s+OR\s+IGNORE\s+INTO', re.IGNORECASE)
    replaced = pattern.sub('INSERT INTO', query)
    stripped = replaced.rstrip()
    suffix = ''
    if stripped.endswith(';'):
        stripped = stripped[:-1]
        suffix = ';'
    if 'ON CONFLICT' in stripped.upper():
        return stripped + suffix
    return f"{stripped} ON CONFLICT DO NOTHING{suffix}"


def replace_collate_nocase(query: str) -> str:
    """Remove SQLite-specific `COLLATE NOCASE` directives."""
    return re.sub(r'COLLATE\s+NOCASE', '', query, flags=re.IGNORECASE)


_RANDOMBLOB_PATTERN = re.compile(r"lower\s*\(\s*hex\s*\(\s*randomblob\s*\(\s*(\d+)\s*\)\s*\)\s*\)", re.IGNORECASE)
_HEX_RANDOMBLOB_PATTERN = re.compile(r"hex\s*\(\s*randomblob\s*\(\s*(\d+)\s*\)\s*\)", re.IGNORECASE)
_JSON_EXTRACT_PATTERN = re.compile(
    r"json_extract\s*\(\s*([A-Za-z0-9_\.]+)\s*,\s*'\$\.([A-Za-z0-9_]+)'\s*\)",
    re.IGNORECASE,
)
_BOOLEAN_EQ_FALSE_PATTERN = re.compile(
    r"\b((?:is_[A-Za-z0-9_]+)|(?:has_[A-Za-z0-9_]+)|(?:deleted)|(?:enabled))\s*=\s*0\b",
    re.IGNORECASE,
)
_BOOLEAN_EQ_TRUE_PATTERN = re.compile(
    r"\b((?:is_[A-Za-z0-9_]+)|(?:has_[A-Za-z0-9_]+)|(?:deleted)|(?:enabled))\s*=\s*1\b",
    re.IGNORECASE,
)
_RETURNING_PATTERN = re.compile(r"\bRETURNING\b", re.IGNORECASE)


def _replace_randomblob_calls(query: str) -> str:
    """Translate SQLite randomblob-based UUID helpers to PostgreSQL."""

    def _lower_hex_sub(match: re.Match[str]) -> str:
        length = match.group(1)
        return f"lower(encode(gen_random_bytes({length}), 'hex'))"

    def _hex_sub(match: re.Match[str]) -> str:
        length = match.group(1)
        return f"encode(gen_random_bytes({length}), 'hex')"

    query = _RANDOMBLOB_PATTERN.sub(_lower_hex_sub, query)
    return _HEX_RANDOMBLOB_PATTERN.sub(_hex_sub, query)


def _replace_json_extract_calls(query: str) -> str:
    """Replace SQLite json_extract usages with PostgreSQL jsonb accessors."""

    def _json_extract_sub(match: re.Match[str]) -> str:
        column = match.group(1)
        path = match.group(2)
        return f"({column} ->> '{path}')"

    return _JSON_EXTRACT_PATTERN.sub(_json_extract_sub, query)


def _ensure_returning_id(query: str) -> str:
    """Append a RETURNING id clause to INSERT statements when missing."""

    if _RETURNING_PATTERN.search(query):
        return query

    match = re.match(r"\s*INSERT\s+INTO\s+", query, flags=re.IGNORECASE)
    if not match:
        return query

    trailing_semicolon = ''
    stripped = query.rstrip()
    if stripped.endswith(';'):
        trailing_semicolon = ';'
        stripped = stripped[:-1].rstrip()

    return f"{stripped} RETURNING id{trailing_semicolon}"


def _replace_boolean_comparisons(query: str) -> str:
    """Convert common boolean equality checks to TRUE/FALSE literals."""

    def _false_sub(match: re.Match[str]) -> str:
        column = match.group(1)
        return f"{column} = FALSE"

    def _true_sub(match: re.Match[str]) -> str:
        column = match.group(1)
        return f"{column} = TRUE"

    query = _BOOLEAN_EQ_FALSE_PATTERN.sub(_false_sub, query)
    return _BOOLEAN_EQ_TRUE_PATTERN.sub(_true_sub, query)


def transform_sqlite_query_for_postgres(
    query: str,
    *,
    replace_insert: bool = True,
    replace_collate: bool = True,
    ensure_returning: bool = False,
) -> str:
    """Apply common SQLite→Postgres rewrites expected across adapters."""
    transformed = query
    if replace_insert:
        transformed = replace_insert_or_ignore(transformed)
    if replace_collate:
        transformed = replace_collate_nocase(transformed)
    transformed = _replace_randomblob_calls(transformed)
    transformed = _replace_json_extract_calls(transformed)
    transformed = _replace_boolean_comparisons(transformed)
    if ensure_returning:
        transformed = _ensure_returning_id(transformed)
    return transformed


def prepare_backend_statement(
    backend_type: BackendType,
    query: str,
    params: ParamsType = None,
    *,
    transformer: Optional[Any] = None,
    apply_default_transform: bool = False,
    ensure_returning: bool = False,
) -> Tuple[str, Optional[Union[Tuple[Any, ...], Dict[str, Any]]]]:
    """Prepare a query/params pair for execution on the configured backend."""
    if backend_type != BackendType.POSTGRESQL:
        return query, params

    returning_requested = ensure_returning
    if transformer is not None:
        query = transformer(query)
        if returning_requested:
            query = _ensure_returning_id(query)
    elif apply_default_transform:
        query = transform_sqlite_query_for_postgres(
            query,
            ensure_returning=returning_requested,
        )
    elif returning_requested:
        query = _ensure_returning_id(query)

    converted_query = convert_sqlite_placeholders_to_postgres(query)
    prepared_params = normalise_params(params)
    return converted_query, prepared_params


def prepare_backend_many_statement(
    backend_type: BackendType,
    query: str,
    params_list: Sequence[ParamsType],
    *,
    transformer: Optional[Any] = None,
    apply_default_transform: bool = False,
    ensure_returning: bool = False,
) -> Tuple[str, List[Optional[Union[Tuple[Any, ...], Dict[str, Any]]]]]:
    """Prepare a batch query/params list for execution on the configured backend."""
    if backend_type != BackendType.POSTGRESQL:
        return query, list(params_list)

    if transformer is not None:
        query = transformer(query)
    elif apply_default_transform:
        query = transform_sqlite_query_for_postgres(
            query,
            ensure_returning=ensure_returning,
        )
    elif ensure_returning:
        query = _ensure_returning_id(query)

    converted_query = convert_sqlite_placeholders_to_postgres(query)
    prepared_params = [normalise_params(params) for params in params_list]
    return converted_query, prepared_params
