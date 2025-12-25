from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend
from tldw_Server_API.app.core.Billing.plan_limits import get_plan_limits


def _parse_json_payload(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.debug(f"admin budgets: invalid JSON payload: {exc}")
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _build_budget_item(row: Dict[str, Any]) -> Dict[str, Any]:
    plan_name = row.get("plan_name") or "free"
    plan_display_name = row.get("plan_display_name") or plan_name.title()
    plan_limits = _parse_json_payload(row.get("plan_limits_json"))
    if not plan_limits:
        plan_limits = get_plan_limits(plan_name)

    custom_limits = _parse_json_payload(row.get("custom_limits_json"))
    budgets = {}
    if isinstance(custom_limits, dict):
        budgets = custom_limits.get("budgets") or {}
        if not isinstance(budgets, dict):
            budgets = {}

    effective_limits = dict(plan_limits)
    if isinstance(custom_limits, dict) and custom_limits:
        effective_limits.update(custom_limits)

    return {
        "org_id": int(row.get("org_id")),
        "org_name": row.get("org_name") or "",
        "org_slug": row.get("org_slug"),
        "plan_name": plan_name,
        "plan_display_name": plan_display_name,
        "budgets": budgets,
        "custom_limits": custom_limits,
        "effective_limits": effective_limits,
        "updated_at": row.get("updated_at"),
    }


def merge_budget_settings(
    existing: Dict[str, Any],
    updates: Optional[Dict[str, Any]],
    *,
    clear: bool,
) -> Dict[str, Any]:
    """Merge budget updates into existing budget settings."""
    if clear:
        return {}
    if not updates:
        return dict(existing)
    merged = dict(existing)
    for key, value in updates.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


async def _fetchval(db, query: str, params: List[Any]) -> Any:
    if hasattr(db, "fetchval"):
        return await db.fetchval(query, *params)
    cur = await db.execute(query, params)
    row = await cur.fetchone()
    return row[0] if row else None


async def _fetchrow(db, query: str, params: List[Any]) -> Optional[Dict[str, Any]]:
    if hasattr(db, "fetchrow"):
        row = await db.fetchrow(query, *params)
        return dict(row) if row and not isinstance(row, dict) else row
    cur = await db.execute(query, params)
    row = await cur.fetchone()
    if not row:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row) if not isinstance(row, dict) else row


async def _fetchrows(db, query: str, params: List[Any]) -> List[Any]:
    if hasattr(db, "fetch"):
        return await db.fetch(query, *params)
    cur = await db.execute(query, params)
    return await cur.fetchall()


async def list_org_budgets(
    db,
    *,
    org_ids: Optional[List[int]],
    page: int,
    limit: int,
) -> Tuple[List[Dict[str, Any]], int]:
    offset = (page - 1) * limit
    pg = await is_postgres_backend()
    if pg:
        try:
            from tldw_Server_API.app.core.AuthNZ.pg_migrations_extra import ensure_billing_tables_pg

            await ensure_billing_tables_pg()
        except Exception as exc:
            logger.debug(f"admin budgets: ensure billing tables skipped/failed: {exc}")
    if org_ids is not None and len(org_ids) == 0:
        return [], 0

    conditions: List[str] = []
    params: List[Any] = []
    if org_ids is not None:
        if pg:
            conditions.append(f"o.id = ANY(${len(params) + 1})")
            params.append(org_ids)
        else:
            placeholders = ",".join("?" for _ in org_ids)
            conditions.append(f"o.id IN ({placeholders})")
            params.extend(org_ids)

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""

    count_sql = f"SELECT COUNT(*) FROM organizations o{where_clause}"
    total = int(await _fetchval(db, count_sql, params) or 0)

    if pg:
        limit_placeholder = f"${len(params) + 1}"
        offset_placeholder = f"${len(params) + 2}"
    else:
        limit_placeholder = "?"
        offset_placeholder = "?"

    sql = (
        "SELECT o.id as org_id, o.name as org_name, o.slug as org_slug, "
        "os.custom_limits_json, os.updated_at, "
        "sp.name as plan_name, sp.display_name as plan_display_name, sp.limits_json as plan_limits_json "
        "FROM organizations o "
        "LEFT JOIN org_subscriptions os ON os.org_id = o.id "
        "LEFT JOIN subscription_plans sp ON os.plan_id = sp.id "
        f"{where_clause} "
        f"ORDER BY o.name ASC LIMIT {limit_placeholder} OFFSET {offset_placeholder}"
    )

    rows = await _fetchrows(db, sql, params + [limit, offset])
    items = []
    for row in rows:
        row_dict = dict(row) if not isinstance(row, dict) else row
        items.append(_build_budget_item(row_dict))
    return items, total


async def upsert_org_budget(
    db,
    *,
    org_id: int,
    budget_updates: Optional[Dict[str, Any]],
    clear_budgets: bool,
) -> Dict[str, Any]:
    pg = await is_postgres_backend()
    if pg:
        try:
            from tldw_Server_API.app.core.AuthNZ.pg_migrations_extra import ensure_billing_tables_pg

            await ensure_billing_tables_pg()
        except Exception as exc:
            logger.debug(f"admin budgets: ensure billing tables skipped/failed: {exc}")

    org_row = await _fetchrow(
        db,
        "SELECT id, name, slug FROM organizations WHERE id = $1",
        [org_id],
    )
    if not org_row:
        raise ValueError("org_not_found")
    org_data = dict(org_row) if not isinstance(org_row, dict) else org_row

    sub_row = await _fetchrow(
        db,
        """
        SELECT os.org_id, os.custom_limits_json, os.updated_at,
               sp.name as plan_name, sp.display_name as plan_display_name, sp.limits_json as plan_limits_json
        FROM org_subscriptions os
        JOIN subscription_plans sp ON os.plan_id = sp.id
        WHERE os.org_id = $1
        """,
        [org_id],
    )

    if not sub_row:
        plan_row = await _fetchrow(
            db,
            "SELECT id, name, display_name, limits_json FROM subscription_plans WHERE name = $1",
            ["free"],
        )
        if not plan_row:
            default_limits = get_plan_limits("free")
            if pg:
                await db.execute(
                    """
                    INSERT INTO subscription_plans
                    (name, display_name, description, price_usd_monthly, price_usd_yearly, limits_json, sort_order)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
                    ON CONFLICT (name) DO NOTHING
                    """,
                    "free",
                    "Free",
                    "Get started with basic features",
                    0,
                    0,
                    json.dumps(default_limits),
                    0,
                )
            else:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO subscription_plans
                    (name, display_name, description, price_usd_monthly, price_usd_yearly, limits_json, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "free",
                        "Free",
                        "Get started with basic features",
                        0,
                        0,
                        json.dumps(default_limits),
                        0,
                    ),
                )
            plan_row = await _fetchrow(
                db,
                "SELECT id, name, display_name, limits_json FROM subscription_plans WHERE name = $1",
                ["free"],
            )
        if not plan_row:
            raise ValueError("plan_not_found")
        plan_data = dict(plan_row) if not isinstance(plan_row, dict) else plan_row
        plan_id = int(plan_data.get("id"))
        await db.execute(
            """
            INSERT INTO org_subscriptions (org_id, plan_id, status)
            VALUES ($1, $2, 'active')
            ON CONFLICT (org_id) DO NOTHING
            """,
            org_id,
            plan_id,
        )
        sub_row = await _fetchrow(
            db,
            """
            SELECT os.org_id, os.custom_limits_json, os.updated_at,
                   sp.name as plan_name, sp.display_name as plan_display_name, sp.limits_json as plan_limits_json
            FROM org_subscriptions os
            JOIN subscription_plans sp ON os.plan_id = sp.id
            WHERE os.org_id = $1
            """,
            [org_id],
        )

    if not sub_row:
        raise ValueError("subscription_not_found")

    row_dict = dict(sub_row) if not isinstance(sub_row, dict) else sub_row
    custom_limits = _parse_json_payload(row_dict.get("custom_limits_json"))
    existing_budgets = custom_limits.get("budgets") if isinstance(custom_limits, dict) else {}
    if not isinstance(existing_budgets, dict):
        existing_budgets = {}

    merged_budgets = merge_budget_settings(existing_budgets, budget_updates, clear=clear_budgets)
    if merged_budgets:
        custom_limits["budgets"] = merged_budgets
    else:
        custom_limits.pop("budgets", None)

    if budget_updates is not None or clear_budgets:
        payload = json.dumps(custom_limits) if custom_limits else None
        now = datetime.utcnow()
        if pg:
            await db.execute(
                """
                UPDATE org_subscriptions
                SET custom_limits_json = $2::jsonb, updated_at = $3
                WHERE org_id = $1
                """,
                org_id,
                payload,
                now,
            )
        else:
            await db.execute(
                """
                UPDATE org_subscriptions
                SET custom_limits_json = ?, updated_at = ?
                WHERE org_id = ?
                """,
                (payload, now, org_id),
            )

        row_dict["custom_limits_json"] = payload
        row_dict["updated_at"] = now

    row_dict.update(
        {
            "org_id": org_data.get("id"),
            "org_name": org_data.get("name"),
            "org_slug": org_data.get("slug"),
        }
    )
    return _build_budget_item(row_dict)
