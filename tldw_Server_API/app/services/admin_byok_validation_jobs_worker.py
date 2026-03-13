from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.repos.users_repo import AuthnzUsersRepo
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    decrypt_byok_payload,
    loads_envelope,
)
from tldw_Server_API.app.core.Chat.Chat_Deps import (
    ChatAuthenticationError,
    ChatBadRequestError,
    ChatProviderError,
)
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK
from tldw_Server_API.app.core.testing import env_flag_enabled
from tldw_Server_API.app.services import admin_byok_service, admin_orgs_service
from tldw_Server_API.app.services.admin_byok_validation_service import (
    AdminByokValidationService,
)


BYOK_VALIDATION_DOMAIN = "byok"
BYOK_VALIDATION_JOB_TYPE = "validation_sweep"


def byok_validation_queue() -> str:
    """Return the Jobs queue used for authoritative BYOK validation runs."""
    return (os.getenv("ADMIN_BYOK_VALIDATION_JOBS_QUEUE") or "default").strip() or "default"


def byok_validation_worker_enabled() -> bool:
    """Return True when the authoritative BYOK validation worker is enabled."""
    return env_flag_enabled("ADMIN_BYOK_VALIDATION_JOBS_WORKER_ENABLED")


def build_byok_validation_job_payload(*, run_id: str) -> dict[str, Any]:
    """Build the opaque Jobs payload for one BYOK validation run."""
    return {"run_id": str(run_id)}


def build_byok_validation_idempotency_key(*, run_id: str) -> str:
    """Return the Jobs idempotency key for one BYOK validation run enqueue."""
    return f"byok-validation:{run_id}"


async def _get_repo():
    """Build the BYOK validation run repository for worker execution."""
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.core.AuthNZ.repos.byok_validation_runs_repo import (
        AuthnzByokValidationRunsRepo,
    )

    pool = await get_db_pool()
    repo = AuthnzByokValidationRunsRepo(pool)
    await repo.ensure_schema()
    return repo


def _per_provider_limit() -> int:
    """Return the max concurrent validation calls per provider."""
    raw_value = (os.getenv("ADMIN_BYOK_VALIDATION_PER_PROVIDER_CONCURRENCY") or "2").strip()
    try:
        return max(1, int(raw_value))
    except ValueError:
        return 2


def _redact_validation_failure(exc: Exception) -> str:
    """Return a bounded redacted summary for a failed validation run."""
    if isinstance(exc, ChatAuthenticationError | ChatBadRequestError):
        return "invalid_credentials"
    if isinstance(exc, ChatProviderError):
        return "provider_validation_failed"
    return "provider_validation_failed"


async def enqueue_byok_validation_run(
    run: dict[str, Any],
    *,
    job_manager: JobManager | None = None,
) -> str:
    """Enqueue one authoritative BYOK validation run into Jobs."""
    jobs = job_manager or JobManager()
    job = jobs.create_job(
        domain=BYOK_VALIDATION_DOMAIN,
        queue=byok_validation_queue(),
        job_type=BYOK_VALIDATION_JOB_TYPE,
        payload=build_byok_validation_job_payload(run_id=str(run["id"])),
        owner_user_id=(
            str(run["requested_by_user_id"]) if run.get("requested_by_user_id") is not None else None
        ),
        idempotency_key=build_byok_validation_idempotency_key(run_id=str(run["id"])),
    )
    return str(job.get("id"))


async def _load_team_scoped_shared_candidates(
    *,
    org_id: int,
    provider: str | None,
    shared_repo,
) -> list[dict[str, Any]]:
    """Load team-scoped shared key candidates for one organization."""
    items: list[dict[str, Any]] = []
    offset = 0
    limit = 200
    while True:
        teams = await admin_orgs_service.list_teams_by_org(org_id, limit=limit, offset=offset)
        if not teams:
            break
        for team in teams:
            team_id = int(team["id"])
            team_rows = await shared_repo.list_secrets(
                scope_type="team",
                scope_id=team_id,
                provider=provider,
            )
            for row in team_rows:
                full_row = await shared_repo.fetch_secret("team", team_id, str(row["provider"]))
                if not full_row or not full_row.get("encrypted_blob"):
                    continue
                payload = decrypt_byok_payload(loads_envelope(str(full_row["encrypted_blob"])))
                items.append(
                    {
                        "provider": str(row["provider"]),
                        "api_key": payload["api_key"],
                        "credential_fields": payload.get("credential_fields"),
                        "source": "shared",
                        "scope_type": "team",
                        "scope_id": team_id,
                    }
                )
        if len(teams) < limit:
            break
        offset += limit
    return items


async def load_default_validation_candidates(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Load shared and per-user BYOK validation candidates for one run scope."""
    provider = str(run.get("provider") or "").strip() or None
    org_id = int(run["org_id"]) if run.get("org_id") is not None else None

    shared_repo = await admin_byok_service.get_shared_byok_repo()
    user_repo = await admin_byok_service.get_user_byok_repo()
    users_repo = await AuthnzUsersRepo.from_pool()

    candidates: list[dict[str, Any]] = []

    if org_id is not None:
        shared_rows = await shared_repo.list_secrets(
            scope_type="org",
            scope_id=org_id,
            provider=provider,
        )
        team_rows = await _load_team_scoped_shared_candidates(
            org_id=org_id,
            provider=provider,
            shared_repo=shared_repo,
        )
    else:
        shared_rows = await shared_repo.list_secrets(provider=provider)
        team_rows = []

    for row in shared_rows:
        scope_type = str(row["scope_type"])
        scope_id = int(row["scope_id"])
        full_row = await shared_repo.fetch_secret(scope_type, scope_id, str(row["provider"]))
        if not full_row or not full_row.get("encrypted_blob"):
            continue
        payload = decrypt_byok_payload(loads_envelope(str(full_row["encrypted_blob"])))
        candidates.append(
            {
                "provider": str(row["provider"]),
                "api_key": payload["api_key"],
                "credential_fields": payload.get("credential_fields"),
                "source": "shared",
                "scope_type": scope_type,
                "scope_id": scope_id,
            }
        )
    candidates.extend(team_rows)

    offset = 0
    limit = 200
    while True:
        users, total = await users_repo.list_users(
            offset=offset,
            limit=limit,
            org_ids=[org_id] if org_id is not None else None,
        )
        if not users:
            break
        for user in users:
            user_id = int(user["id"])
            user_rows = await user_repo.list_secrets_for_user(user_id)
            for row in user_rows:
                row_provider = str(row["provider"])
                if provider is not None and row_provider != provider:
                    continue
                full_row = await user_repo.fetch_secret_for_user(user_id, row_provider)
                if not full_row or not full_row.get("encrypted_blob"):
                    continue
                payload = decrypt_byok_payload(loads_envelope(str(full_row["encrypted_blob"])))
                candidates.append(
                    {
                        "provider": row_provider,
                        "api_key": payload["api_key"],
                        "credential_fields": payload.get("credential_fields"),
                        "source": "user",
                        "user_id": user_id,
                    }
                )
        offset += limit
        if offset >= total:
            break

    return candidates


async def _run_validation_scan(
    candidates: list[dict[str, Any]],
    *,
    test_provider_credentials_fn: Callable[..., Awaitable[Any]],
    per_provider_limit: int | None = None,
) -> dict[str, int]:
    """Validate candidate credentials with bounded concurrency per provider."""
    provider_limit = per_provider_limit or _per_provider_limit()
    semaphores: dict[str, asyncio.Semaphore] = {}

    async def _validate_candidate(candidate: dict[str, Any]) -> str:
        provider = str(candidate["provider"])
        semaphore = semaphores.setdefault(provider, asyncio.Semaphore(provider_limit))
        async with semaphore:
            try:
                await test_provider_credentials_fn(
                    provider=provider,
                    api_key=str(candidate["api_key"]),
                    credential_fields=candidate.get("credential_fields"),
                    model=None,
                )
                return "valid"
            except (ChatAuthenticationError, ChatBadRequestError):
                return "invalid"

    results = await asyncio.gather(*[_validate_candidate(candidate) for candidate in candidates])
    return {
        "keys_checked": len(candidates),
        "valid_count": sum(1 for status in results if status == "valid"),
        "invalid_count": sum(1 for status in results if status == "invalid"),
        "error_count": 0,
    }


async def handle_byok_validation_job(
    job: dict[str, Any],
    *,
    repo=None,
    candidate_loader: Callable[[dict[str, Any]], Awaitable[list[dict[str, Any]]]] | None = None,
    test_provider_credentials_fn: Callable[..., Awaitable[Any]] | None = None,
) -> dict[str, Any]:
    """Execute one authoritative BYOK validation run from the Jobs queue."""
    from tldw_Server_API.app.core.AuthNZ.byok_testing import test_provider_credentials

    payload = job.get("payload") or {}
    run_id = str(payload.get("run_id") or "").strip()
    if not run_id:
        raise ValueError("missing_run_id")

    repo = repo or await _get_repo()
    run = await repo.get_run(run_id)
    if not run:
        raise ValueError("missing_run")

    job_id = str(job.get("id")) if job.get("id") is not None else None
    await repo.mark_running(run_id, job_id=job_id)

    loader = candidate_loader or load_default_validation_candidates
    validator = test_provider_credentials_fn or test_provider_credentials

    try:
        candidates = await loader(run)
        summary = await _run_validation_scan(
            candidates,
            test_provider_credentials_fn=validator,
        )
    except Exception as exc:
        await repo.mark_failed(run_id, error_message=_redact_validation_failure(exc))
        raise

    await repo.mark_complete(
        run_id,
        keys_checked=int(summary["keys_checked"]),
        valid_count=int(summary["valid_count"]),
        invalid_count=int(summary["invalid_count"]),
        error_count=int(summary["error_count"]),
    )

    logger.info(
        "BYOK validation job completed: run_id={} job_id={} keys_checked={} valid={} invalid={} errors={}",
        run_id,
        job_id,
        summary["keys_checked"],
        summary["valid_count"],
        summary["invalid_count"],
        summary["error_count"],
    )
    return {
        "status": "complete",
        "run_id": run_id,
        "job_id": job_id,
        "keys_checked": int(summary["keys_checked"]),
        "valid_count": int(summary["valid_count"]),
        "invalid_count": int(summary["invalid_count"]),
        "error_count": int(summary["error_count"]),
    }


async def run_admin_byok_validation_jobs_worker() -> None:
    """Run the WorkerSDK loop for authoritative BYOK validation jobs."""
    worker_id = (
        os.getenv("ADMIN_BYOK_VALIDATION_JOBS_WORKER_ID") or f"admin-byok-validation-{os.getpid()}"
    ).strip()
    cfg = WorkerConfig(
        domain=BYOK_VALIDATION_DOMAIN,
        queue=byok_validation_queue(),
        worker_id=worker_id,
    )
    jm = JobManager()
    sdk = WorkerSDK(jm, cfg)
    logger.info(
        "Admin BYOK validation Jobs worker starting: queue={} worker_id={}",
        cfg.queue,
        worker_id,
    )
    await sdk.run(handler=handle_byok_validation_job)


async def start_admin_byok_validation_jobs_worker() -> asyncio.Task | None:
    """Start the BYOK validation Jobs worker when explicitly enabled."""
    if not byok_validation_worker_enabled():
        return None
    return asyncio.create_task(
        run_admin_byok_validation_jobs_worker(),
        name="admin_byok_validation_jobs_worker",
    )


__all__ = [
    "BYOK_VALIDATION_DOMAIN",
    "BYOK_VALIDATION_JOB_TYPE",
    "_run_validation_scan",
    "build_byok_validation_idempotency_key",
    "build_byok_validation_job_payload",
    "byok_validation_queue",
    "byok_validation_worker_enabled",
    "enqueue_byok_validation_run",
    "handle_byok_validation_job",
    "load_default_validation_candidates",
    "run_admin_byok_validation_jobs_worker",
    "start_admin_byok_validation_jobs_worker",
]
