from __future__ import annotations

from typing import Optional, Tuple

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.repos.quotas_repo import AuthnzQuotasRepo


async def increment_and_check_jwt_quota(
    db_pool: DatabasePool,
    jti: str,
    counter_type: str,
    limit: Optional[int],
    bucket: Optional[str] = None,
) -> Tuple[bool, int]:
    """
    Atomically increment JWT (by jti) quota counter and compare to ``limit``.

    Returns ``(allowed, new_count)`` as provided by
    ``AuthnzQuotasRepo.increment_and_check_jwt_quota``. When ``limit`` is
    ``None`` or ``jti`` is empty, this is treated as a no-op and
    ``(True, -1)`` is returned (no persistent increment / not tracked).
    """
    repo = AuthnzQuotasRepo(db_pool=db_pool)
    return await repo.increment_and_check_jwt_quota(
        jti=jti,
        counter_type=counter_type,
        limit=limit,
        bucket=bucket,
    )


async def increment_and_check_api_key_quota(
    db_pool: DatabasePool,
    api_key_id: int,
    counter_type: str,
    limit: Optional[int],
    bucket: Optional[str] = None,
) -> Tuple[bool, int]:
    """
    Atomically increment API Key quota counter and compare to ``limit``.

    Returns ``(allowed, new_count)`` as provided by
    ``AuthnzQuotasRepo.increment_and_check_api_key_quota``. When ``limit`` is
    ``None`` or ``api_key_id`` is ``None``, this is treated as a no-op and
    ``(True, -1)`` is returned (no persistent increment / not tracked).
    """
    repo = AuthnzQuotasRepo(db_pool=db_pool)
    return await repo.increment_and_check_api_key_quota(
        api_key_id=api_key_id,
        counter_type=counter_type,
        limit=limit,
        bucket=bucket,
    )
