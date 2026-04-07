from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import Any

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.errors import InputError


pytestmark = pytest.mark.unit


def _load_email_backfill_ops_module():
    return importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.media_db.runtime.email_backfill_ops"
    )


class _EmailBackfillWorkerStub:
    def __init__(
        self,
        batch_results: Sequence[dict[str, Any]],
        *,
        resolved_tenant: str = "resolved-tenant",
        resolved_key: str = "normalized-key",
        state_result: dict[str, Any] | None = None,
    ) -> None:
        self._batch_results = list(batch_results)
        self._resolved_tenant = resolved_tenant
        self._resolved_key = resolved_key
        self._state_result = state_result or {
            "tenant_id": resolved_tenant,
            "backfill_key": resolved_key,
            "status": "running",
        }
        self.batch_calls: list[dict[str, Any]] = []
        self.state_calls: list[dict[str, Any]] = []

    def _resolve_email_tenant_id(self, tenant_id: str | None = None) -> str:
        return self._resolved_tenant if tenant_id is None else str(tenant_id)

    def _normalize_email_backfill_key(self, backfill_key: Any) -> str:
        return self._resolved_key if str(backfill_key or "").strip() else "normalized-key"

    def run_email_legacy_backfill_batch(
        self,
        *,
        batch_size: int = 500,
        tenant_id: str | None = None,
        backfill_key: str = "legacy_media_email",
    ) -> dict[str, Any]:
        self.batch_calls.append(
            {
                "batch_size": batch_size,
                "tenant_id": tenant_id,
                "backfill_key": backfill_key,
            }
        )
        if not self._batch_results:
            raise AssertionError("No batch results remaining for stub.")
        return dict(self._batch_results.pop(0))

    def get_email_legacy_backfill_state(
        self,
        *,
        tenant_id: str | None = None,
        backfill_key: str = "legacy_media_email",
    ) -> dict[str, Any]:
        self.state_calls.append(
            {
                "tenant_id": tenant_id,
                "backfill_key": backfill_key,
            }
        )
        return dict(self._state_result)


@pytest.mark.parametrize("invalid_batch_size", [0, -1, "not-an-int"])
def test_run_email_legacy_backfill_batch_rejects_invalid_batch_size(
    invalid_batch_size: object,
) -> None:
    email_backfill_ops = _load_email_backfill_ops_module()

    with pytest.raises(InputError):
        email_backfill_ops.run_email_legacy_backfill_batch(
            object(),
            batch_size=invalid_batch_size,
        )


@pytest.mark.parametrize("invalid_max_batches", [0, -1, "not-an-int"])
def test_run_email_legacy_backfill_worker_rejects_invalid_max_batches(
    invalid_max_batches: object,
) -> None:
    email_backfill_ops = _load_email_backfill_ops_module()

    worker_stub = _EmailBackfillWorkerStub([])

    with pytest.raises(InputError):
        email_backfill_ops.run_email_legacy_backfill_worker(
            worker_stub,
            max_batches=invalid_max_batches,
        )


def test_run_email_legacy_backfill_worker_stops_on_no_progress() -> None:
    email_backfill_ops = _load_email_backfill_ops_module()

    worker_stub = _EmailBackfillWorkerStub(
        [
            {
                "scanned": 0,
                "ingested": 0,
                "skipped": 0,
                "failed": 0,
                "completed": False,
                "status": "running",
                "state": {"status": "running"},
            }
        ],
        resolved_tenant="user:42",
        resolved_key="legacy-worker",
        state_result={
            "tenant_id": "user:42",
            "backfill_key": "legacy-worker",
            "status": "running",
        },
    )

    result = email_backfill_ops.run_email_legacy_backfill_worker(
        worker_stub,
        batch_size=25,
        tenant_id="explicit-tenant",
        backfill_key="input-key",
        max_batches=3,
    )

    assert result["completed"] is True
    assert result["stop_reason"] == "no_progress"
    assert result["batches_run"] == 1
    assert result["scanned"] == 0
    assert result["ingested"] == 0
    assert result["skipped"] == 0
    assert result["failed"] == 0
    assert result["last_batch"]["status"] == "running"
    assert worker_stub.batch_calls == [
        {
            "batch_size": 25,
            "tenant_id": "explicit-tenant",
            "backfill_key": "legacy-worker",
        }
    ]
    assert worker_stub.state_calls == [
        {
            "tenant_id": "explicit-tenant",
            "backfill_key": "legacy-worker",
        }
    ]


def test_run_email_legacy_backfill_worker_aggregates_batch_totals_until_completion() -> None:
    email_backfill_ops = _load_email_backfill_ops_module()

    worker_stub = _EmailBackfillWorkerStub(
        [
            {
                "scanned": 2,
                "ingested": 1,
                "skipped": 1,
                "failed": 0,
                "completed": False,
                "status": "running",
                "state": {"status": "running"},
            },
            {
                "scanned": 3,
                "ingested": 2,
                "skipped": 0,
                "failed": 1,
                "completed": True,
                "status": "completed_with_errors",
                "state": {"status": "completed_with_errors"},
            },
        ],
        resolved_tenant="user:84",
        resolved_key="legacy-bulk",
        state_result={
            "tenant_id": "user:84",
            "backfill_key": "legacy-bulk",
            "status": "completed_with_errors",
        },
    )

    result = email_backfill_ops.run_email_legacy_backfill_worker(
        worker_stub,
        batch_size=50,
        tenant_id="tenant-input",
        backfill_key="input-key",
        max_batches=5,
    )

    assert result["completed"] is True
    assert result["stop_reason"] == "completed"
    assert result["batches_run"] == 2
    assert result["scanned"] == 5
    assert result["ingested"] == 3
    assert result["skipped"] == 1
    assert result["failed"] == 1
    assert result["last_batch"]["status"] == "completed_with_errors"
    assert result["state"]["status"] == "completed_with_errors"
    assert worker_stub.batch_calls == [
        {
            "batch_size": 50,
            "tenant_id": "tenant-input",
            "backfill_key": "legacy-bulk",
        },
        {
            "batch_size": 50,
            "tenant_id": "tenant-input",
            "backfill_key": "legacy-bulk",
        },
    ]
    assert worker_stub.state_calls == [
        {
            "tenant_id": "tenant-input",
            "backfill_key": "legacy-bulk",
        }
    ]
