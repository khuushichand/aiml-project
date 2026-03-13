from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatAuthenticationError


@dataclass
class _FakeValidationRunsRepo:
    run: dict[str, object]
    running_calls: list[tuple[str, str | None]] = field(default_factory=list)
    complete_calls: list[dict[str, int]] = field(default_factory=list)
    failed_calls: list[tuple[str, str]] = field(default_factory=list)

    async def get_run(self, run_id: str):
        if self.run.get("id") != run_id:
            return None
        return dict(self.run)

    async def mark_running(self, run_id: str, *, job_id: str | None):
        self.running_calls.append((run_id, job_id))
        updated = dict(self.run)
        updated["status"] = "running"
        updated["job_id"] = job_id
        return updated

    async def mark_complete(
        self,
        run_id: str,
        *,
        keys_checked: int,
        valid_count: int,
        invalid_count: int,
        error_count: int,
    ):
        self.complete_calls.append(
            {
                "keys_checked": keys_checked,
                "valid_count": valid_count,
                "invalid_count": invalid_count,
                "error_count": error_count,
            }
        )
        updated = dict(self.run)
        updated["status"] = "complete"
        updated["keys_checked"] = keys_checked
        updated["valid_count"] = valid_count
        updated["invalid_count"] = invalid_count
        updated["error_count"] = error_count
        return updated

    async def mark_failed(self, run_id: str, *, error_message: str):
        self.failed_calls.append((run_id, error_message))
        updated = dict(self.run)
        updated["status"] = "failed"
        updated["error_message"] = error_message
        return updated


@pytest.mark.asyncio
async def test_handle_byok_validation_job_marks_running_and_complete() -> None:
    from tldw_Server_API.app.services.admin_byok_validation_jobs_worker import (
        handle_byok_validation_job,
    )

    repo = _FakeValidationRunsRepo(
        run={
            "id": "run-1",
            "status": "queued",
            "org_id": 42,
            "provider": None,
        }
    )

    async def _load_candidates(run: dict[str, object]) -> list[dict[str, object]]:
        assert run["id"] == "run-1"
        return [
            {"provider": "openai", "api_key": "valid-openai-1", "credential_fields": None},
            {"provider": "openai", "api_key": "invalid-openai-2", "credential_fields": None},
            {"provider": "anthropic", "api_key": "valid-anthropic-1", "credential_fields": None},
        ]

    async def _validate(*, provider: str, api_key: str, credential_fields=None, model=None):
        if api_key.startswith("invalid-"):
            raise ChatAuthenticationError(message="rejected", provider=provider)
        return "ok"

    result = await handle_byok_validation_job(
        {"id": "job-1", "payload": {"run_id": "run-1"}},
        repo=repo,
        candidate_loader=_load_candidates,
        test_provider_credentials_fn=_validate,
    )

    assert repo.running_calls == [("run-1", "job-1")]
    assert repo.complete_calls == [
        {
            "keys_checked": 3,
            "valid_count": 2,
            "invalid_count": 1,
            "error_count": 0,
        }
    ]
    assert repo.failed_calls == []
    assert result["status"] == "complete"
    assert result["keys_checked"] == 3
    assert result["valid_count"] == 2


@pytest.mark.asyncio
async def test_handle_byok_validation_job_marks_failed_with_redacted_summary() -> None:
    from tldw_Server_API.app.services.admin_byok_validation_jobs_worker import (
        handle_byok_validation_job,
    )

    repo = _FakeValidationRunsRepo(
        run={
            "id": "run-1",
            "status": "queued",
            "org_id": None,
            "provider": "openai",
        }
    )

    async def _load_candidates(run: dict[str, object]) -> list[dict[str, object]]:
        return [{"provider": "openai", "api_key": "valid-openai-1", "credential_fields": None}]

    async def _validate(*, provider: str, api_key: str, credential_fields=None, model=None):
        raise RuntimeError("openai returned 503 with secret-like raw payload")

    with pytest.raises(RuntimeError):
        await handle_byok_validation_job(
            {"id": "job-9", "payload": {"run_id": "run-1"}},
            repo=repo,
            candidate_loader=_load_candidates,
            test_provider_credentials_fn=_validate,
        )

    assert repo.complete_calls == []
    assert repo.failed_calls == [("run-1", "provider_validation_failed")]


@pytest.mark.asyncio
async def test_run_validation_scan_uses_bounded_per_provider_concurrency() -> None:
    from tldw_Server_API.app.services.admin_byok_validation_jobs_worker import _run_validation_scan

    current_by_provider: dict[str, int] = {}
    max_by_provider: dict[str, int] = {}

    async def _validate(*, provider: str, api_key: str, credential_fields=None, model=None):
        current_by_provider[provider] = current_by_provider.get(provider, 0) + 1
        max_by_provider[provider] = max(max_by_provider.get(provider, 0), current_by_provider[provider])
        await asyncio.sleep(0.01)
        current_by_provider[provider] -= 1
        return "ok"

    candidates = [
        {"provider": "openai", "api_key": "valid-1", "credential_fields": None},
        {"provider": "openai", "api_key": "valid-2", "credential_fields": None},
        {"provider": "openai", "api_key": "valid-3", "credential_fields": None},
        {"provider": "anthropic", "api_key": "valid-4", "credential_fields": None},
    ]

    summary = await _run_validation_scan(
        candidates,
        test_provider_credentials_fn=_validate,
        per_provider_limit=2,
    )

    assert summary["keys_checked"] == 4
    assert summary["valid_count"] == 4
    assert summary["invalid_count"] == 0
    assert summary["error_count"] == 0
    assert max_by_provider["openai"] <= 2


@pytest.mark.asyncio
async def test_handle_byok_validation_job_raises_for_missing_run() -> None:
    from tldw_Server_API.app.services.admin_byok_validation_jobs_worker import (
        handle_byok_validation_job,
    )

    repo = _FakeValidationRunsRepo(run={"id": "other-run"})

    with pytest.raises(ValueError, match="missing_run"):
        await handle_byok_validation_job(
            {"id": "job-7", "payload": {"run_id": "run-1"}},
            repo=repo,
        )
