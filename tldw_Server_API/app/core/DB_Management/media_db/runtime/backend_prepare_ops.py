"""Backend-preparation helpers for the package-native Media DB runtime."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.query_utils import (
    normalise_params,
    prepare_backend_many_statement,
    prepare_backend_statement,
)


def _prepare_backend_statement(
    self: Any,
    query: str,
    params: tuple | list | dict | None = None,
) -> tuple[str, tuple | dict | None]:
    return prepare_backend_statement(
        self.backend_type,
        query,
        params,
        apply_default_transform=True,
        ensure_returning=False,
    )


def _prepare_backend_many_statement(
    self: Any,
    query: str,
    params_list: list[tuple | list | dict],
) -> tuple[str, list[tuple | dict]]:
    converted_query, prepared_params = prepare_backend_many_statement(
        self.backend_type,
        query,
        params_list,
        apply_default_transform=True,
        ensure_returning=False,
    )
    return converted_query, prepared_params


def _normalise_params(
    self: Any,
    params: Any | None,
) -> tuple | dict | None:
    return normalise_params(params)


__all__ = [
    "_normalise_params",
    "_prepare_backend_many_statement",
    "_prepare_backend_statement",
]
