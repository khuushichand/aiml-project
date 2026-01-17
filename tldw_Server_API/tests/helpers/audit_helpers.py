import asyncio
import time
from pathlib import Path

import aiosqlite
from fastapi.testclient import TestClient


async def await_audit_action(audit_db: Path, action: str, timeout_s: float = 5.0) -> int:
    """
    Poll the audit database until at least one event with the specified action is found.

    Args:
        audit_db: Path to the audit database file.
        action: The action name to search for (e.g., "team_member.add").
        timeout_s: Maximum time to wait in seconds.

    Returns:
        The count of matching audit events found.
    """
    deadline = time.monotonic() + timeout_s
    count = 0
    while time.monotonic() < deadline:
        async with aiosqlite.connect(str(audit_db)) as con:
            async with con.execute(
                "SELECT COUNT(*) FROM audit_events WHERE action = ?",
                (action,),
            ) as cur:
                row = await cur.fetchone()
                count = int(row[0]) if row else 0
        if count >= 1:
            break
        await asyncio.sleep(0.05)
    return count


def flush_audit_events(client: TestClient, user_id: int) -> None:
    """
    Flush pending audit events for a user via the audit service.

    Args:
        client: The FastAPI TestClient instance.
        user_id: The user ID whose audit events should be flushed.
    """

    async def _flush(uid: int) -> None:
        from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_or_create_audit_service_for_user_id

        svc = await get_or_create_audit_service_for_user_id(uid)
        await svc.flush()

    if getattr(client, "portal", None) is not None:
        client.portal.call(_flush, int(user_id))
