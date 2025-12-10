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
    Atomically increment JWT (by jti) quota counter and compare to limit.
    Returns (allowed, new_count). If limit is None, returns (True, current+1).
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
    Atomically increment API Key quota counter and compare to limit.
    Returns (allowed, new_count). If limit is None, returns (True, current+1).
    """
    repo = AuthnzQuotasRepo(db_pool=db_pool)
    return await repo.increment_and_check_api_key_quota(
        api_key_id=api_key_id,
        counter_type=counter_type,
        limit=limit,
        bucket=bucket,
    )
