"""
admin_billing_service.py

Service layer for admin billing management operations.
Provides functions for listing all subscriptions, overriding plans,
granting credits, and retrieving billing overview/events.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.billing_repo import AuthnzBillingRepo
from tldw_Server_API.app.core.Billing.stripe_client import is_billing_enabled
from tldw_Server_API.app.core.Billing.subscription_service import get_subscription_service


async def _get_billing_repo() -> AuthnzBillingRepo:
    """Get a billing repo backed by the current DB pool."""
    pool = await get_db_pool()
    return AuthnzBillingRepo(db_pool=pool)


async def list_all_subscriptions(
    *,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """
    List all org subscriptions with optional status filtering.

    Returns a dict with ``items`` (list of subscription dicts) and ``total``.
    """
    repo = await _get_billing_repo()

    # Query org_subscriptions joined with plans
    pool = await get_db_pool()
    is_pg = getattr(pool, "pool", None) is not None

    conditions: list[str] = []
    params: list[Any] = []

    if status_filter:
        if is_pg:
            conditions.append(f"os.status = ${len(params) + 1}")
        else:
            conditions.append("os.status = ?")
        params.append(status_filter)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    try:
        async with pool.acquire() as conn:
            if is_pg:
                # Count query
                count_sql = f"""
                    SELECT COUNT(*) FROM org_subscriptions os {where_clause}
                """
                total = await conn.fetchval(count_sql, *params)

                # Data query
                data_sql = f"""
                    SELECT os.id, os.org_id, os.plan_id, os.stripe_customer_id,
                           os.stripe_subscription_id, os.status, os.billing_cycle,
                           os.current_period_start, os.current_period_end,
                           os.trial_end, os.cancel_at_period_end,
                           os.created_at,
                           sp.name as plan_name, sp.display_name as plan_display_name
                    FROM org_subscriptions os
                    JOIN subscription_plans sp ON os.plan_id = sp.id
                    {where_clause}
                    ORDER BY os.created_at DESC
                    LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
                """
                rows = await conn.fetch(data_sql, *params, limit, offset)
                items = [dict(r) for r in rows]
            else:
                # SQLite path
                count_sql = f"SELECT COUNT(*) FROM org_subscriptions os {where_clause}"
                cur = await conn.execute(count_sql, tuple(params))
                row = await cur.fetchone()
                total = row[0] if row else 0

                data_sql = f"""
                    SELECT os.id, os.org_id, os.plan_id, os.stripe_customer_id,
                           os.stripe_subscription_id, os.status, os.billing_cycle,
                           os.current_period_start, os.current_period_end,
                           os.trial_end, os.cancel_at_period_end,
                           os.created_at,
                           sp.name as plan_name, sp.display_name as plan_display_name
                    FROM org_subscriptions os
                    JOIN subscription_plans sp ON os.plan_id = sp.id
                    {where_clause}
                    ORDER BY os.created_at DESC
                    LIMIT ? OFFSET ?
                """
                cur = await conn.execute(data_sql, tuple(params) + (limit, offset))
                rows = await cur.fetchall()
                columns = [col[0] for col in cur.description]
                items = [{columns[i]: val for i, val in enumerate(r)} for r in rows]

        return {"items": items, "total": total}
    except Exception as exc:
        logger.error("admin_billing_service.list_all_subscriptions failed: {}", exc)
        raise


async def get_user_subscription_details(user_id: int) -> dict[str, Any] | None:
    """
    Get detailed subscription info for a specific user/org.

    In the current model, user_id maps to an org_id for subscription lookup.
    Returns the subscription dict or None if not found.
    """
    repo = await _get_billing_repo()
    sub = await repo.get_org_subscription(user_id)
    if not sub:
        return None
    return sub


async def override_user_plan(
    user_id: int,
    *,
    plan_id: str,
    reason: str,
    admin_user_id: int | None = None,
) -> dict[str, Any]:
    """
    Override a user's subscription plan (admin action).

    Changes the plan in the local database. Does not modify Stripe directly.
    """
    repo = await _get_billing_repo()
    service = await get_subscription_service()

    # Resolve plan
    plan = await repo.get_plan_by_name(plan_id)
    if not plan:
        raise ValueError(f"Plan '{plan_id}' not found")

    # Get or create subscription
    existing = await repo.get_org_subscription(user_id)
    if existing:
        await repo.update_org_subscription(
            user_id,
            plan_id=plan["id"],
            status="active",
        )
    else:
        await repo.create_org_subscription(
            org_id=user_id,
            plan_id=plan["id"],
            status="active",
        )

    # Log the admin action
    await repo.log_billing_action(
        org_id=user_id,
        user_id=admin_user_id,
        action="admin.plan_override",
        details={
            "new_plan": plan_id,
            "reason": reason,
            "previous_plan": existing.get("plan_name") if existing else None,
        },
    )

    logger.info(
        "Admin override plan for user/org {}: plan={}, reason={}",
        user_id, plan_id, reason,
    )

    updated = await repo.get_org_subscription(user_id)
    return updated or {"org_id": user_id, "plan_name": plan_id, "status": "active"}


async def grant_credits(
    user_id: int,
    *,
    amount: int,
    reason: str,
    expires_at: str | None = None,
    admin_user_id: int | None = None,
) -> dict[str, Any]:
    """
    Grant usage credits to a user/org.

    Credits are recorded as a billing audit log entry. The actual credit
    tracking depends on the enforcement layer reading these entries.
    """
    if amount <= 0:
        raise ValueError("Credit amount must be positive")

    repo = await _get_billing_repo()

    details: dict[str, Any] = {
        "amount": amount,
        "reason": reason,
    }
    if expires_at:
        details["expires_at"] = expires_at

    log_entry = await repo.log_billing_action(
        org_id=user_id,
        user_id=admin_user_id,
        action="admin.credits_granted",
        details=details,
    )

    logger.info(
        "Admin granted {} credits to user/org {}: reason={}",
        amount, user_id, reason,
    )

    return {
        "user_id": user_id,
        "credits_granted": amount,
        "reason": reason,
        "expires_at": expires_at,
        "logged_at": log_entry.get("created_at"),
    }


async def get_billing_overview() -> dict[str, Any]:
    """
    Get billing overview statistics.

    Returns aggregate metrics: total subscriptions by status, plan distribution, etc.
    When billing is disabled, returns a minimal response.
    """
    if not is_billing_enabled():
        return {
            "billing_enabled": False,
            "total_subscriptions": 0,
            "active_subscriptions": 0,
            "canceled_subscriptions": 0,
            "past_due_subscriptions": 0,
            "plan_distribution": {},
            "mrr_estimate_usd": 0,
        }

    pool = await get_db_pool()
    is_pg = getattr(pool, "pool", None) is not None

    try:
        async with pool.acquire() as conn:
            if is_pg:
                # Status counts
                status_rows = await conn.fetch(
                    "SELECT status, COUNT(*) as cnt FROM org_subscriptions GROUP BY status"
                )
                status_counts = {r["status"]: r["cnt"] for r in status_rows}

                # Plan distribution
                plan_rows = await conn.fetch(
                    """
                    SELECT sp.name, COUNT(*) as cnt
                    FROM org_subscriptions os
                    JOIN subscription_plans sp ON os.plan_id = sp.id
                    WHERE os.status = 'active'
                    GROUP BY sp.name
                    """
                )
                plan_dist = {r["name"]: r["cnt"] for r in plan_rows}

                # MRR estimate from active paid plans
                mrr_rows = await conn.fetch(
                    """
                    SELECT COALESCE(SUM(sp.price_usd_monthly), 0) as mrr
                    FROM org_subscriptions os
                    JOIN subscription_plans sp ON os.plan_id = sp.id
                    WHERE os.status = 'active' AND sp.price_usd_monthly > 0
                    """
                )
                mrr = mrr_rows[0]["mrr"] if mrr_rows else 0
            else:
                # SQLite path
                cur = await conn.execute(
                    "SELECT status, COUNT(*) as cnt FROM org_subscriptions GROUP BY status"
                )
                rows = await cur.fetchall()
                cols = [c[0] for c in cur.description]
                status_counts = {
                    r[cols.index("status")]: r[cols.index("cnt")] for r in rows
                }

                cur = await conn.execute(
                    """
                    SELECT sp.name, COUNT(*) as cnt
                    FROM org_subscriptions os
                    JOIN subscription_plans sp ON os.plan_id = sp.id
                    WHERE os.status = 'active'
                    GROUP BY sp.name
                    """
                )
                rows = await cur.fetchall()
                cols = [c[0] for c in cur.description]
                plan_dist = {r[cols.index("name")]: r[cols.index("cnt")] for r in rows}

                cur = await conn.execute(
                    """
                    SELECT COALESCE(SUM(sp.price_usd_monthly), 0) as mrr
                    FROM org_subscriptions os
                    JOIN subscription_plans sp ON os.plan_id = sp.id
                    WHERE os.status = 'active' AND sp.price_usd_monthly > 0
                    """
                )
                row = await cur.fetchone()
                mrr = row[0] if row else 0

        total = sum(status_counts.values())
        return {
            "billing_enabled": True,
            "total_subscriptions": total,
            "active_subscriptions": status_counts.get("active", 0),
            "canceled_subscriptions": status_counts.get("canceled", 0),
            "past_due_subscriptions": status_counts.get("past_due", 0),
            "plan_distribution": plan_dist,
            "mrr_estimate_usd": mrr,
        }
    except Exception as exc:
        logger.error("admin_billing_service.get_billing_overview failed: {}", exc)
        raise


async def list_billing_events(
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """
    List recent billing audit log events.

    Returns a dict with ``items`` (list of event dicts) and ``total``.
    """
    pool = await get_db_pool()
    is_pg = getattr(pool, "pool", None) is not None

    try:
        async with pool.acquire() as conn:
            if is_pg:
                total = await conn.fetchval(
                    "SELECT COUNT(*) FROM billing_audit_log"
                )
                rows = await conn.fetch(
                    """
                    SELECT id, org_id, user_id, action, details, ip_address, created_at
                    FROM billing_audit_log
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit,
                )
                items = [dict(r) for r in rows]
            else:
                cur = await conn.execute("SELECT COUNT(*) FROM billing_audit_log")
                row = await cur.fetchone()
                total = row[0] if row else 0

                cur = await conn.execute(
                    """
                    SELECT id, org_id, user_id, action, details, ip_address, created_at
                    FROM billing_audit_log
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                rows = await cur.fetchall()
                columns = [col[0] for col in cur.description]
                items = [{columns[i]: val for i, val in enumerate(r)} for r in rows]

        return {"items": items, "total": total}
    except Exception as exc:
        logger.error("admin_billing_service.list_billing_events failed: {}", exc)
        raise
