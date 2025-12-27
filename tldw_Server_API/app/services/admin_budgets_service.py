from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import is_postgres_backend
from tldw_Server_API.app.core.Billing.plan_limits import get_plan_limits


_BUDGET_KEYS = {
    "budget_day_usd",
    "budget_month_usd",
    "budget_day_tokens",
    "budget_month_tokens",
}


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


def _normalize_threshold_list(values: Any) -> List[int]:
    if not isinstance(values, list):
        raise ValueError("Alert thresholds must be a list")
    if not values:
        raise ValueError("Alert thresholds must not be empty")
    cleaned: List[int] = []
    for val in values:
        try:
            num = int(val)
        except (TypeError, ValueError) as exc:
            raise ValueError("Alert thresholds must be integers") from exc
        if num < 1 or num > 100:
            raise ValueError("Alert thresholds must be between 1 and 100")
        cleaned.append(num)
    return sorted(set(cleaned))


def _coerce_alert_thresholds(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, list):
        return {"global": value}
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        if "global" in value:
            out["global"] = value.get("global")
        if "per_metric" in value:
            out["per_metric"] = value.get("per_metric")
        return out or None
    return None


def _coerce_enforcement_mode(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, str):
        return {"global": value}
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        if "global" in value:
            out["global"] = value.get("global")
        if "per_metric" in value:
            out["per_metric"] = value.get("per_metric")
        return out or None
    return None


def _normalize_alert_thresholds_update(value: Any) -> Optional[Dict[str, Any]]:
    payload = _coerce_alert_thresholds(value)
    if payload is None:
        return None
    out: Dict[str, Any] = {}
    if "global" in payload:
        global_value = payload.get("global")
        if global_value is None:
            out["global"] = None
        else:
            out["global"] = _normalize_threshold_list(global_value)
    if "per_metric" in payload:
        per_metric = payload.get("per_metric")
        if per_metric is None:
            out["per_metric"] = None
        elif not isinstance(per_metric, dict):
            raise ValueError("Per-metric thresholds must be a mapping")
        else:
            cleaned: Dict[str, Any] = {}
            for key, values in per_metric.items():
                if key not in _BUDGET_KEYS:
                    raise ValueError("Unknown per-metric budget key")
                if values is None:
                    cleaned[key] = None
                else:
                    cleaned[key] = _normalize_threshold_list(values)
            out["per_metric"] = cleaned
    return out or None


def _normalize_enforcement_mode_update(value: Any) -> Optional[Dict[str, Any]]:
    payload = _coerce_enforcement_mode(value)
    if payload is None:
        return None
    out: Dict[str, Any] = {}
    if "global" in payload:
        global_value = payload.get("global")
        if global_value is None:
            out["global"] = None
        elif global_value in {"none", "soft", "hard"}:
            out["global"] = global_value
        else:
            raise ValueError("Enforcement mode must be none, soft, or hard")
    if "per_metric" in payload:
        per_metric = payload.get("per_metric")
        if per_metric is None:
            out["per_metric"] = None
        elif not isinstance(per_metric, dict):
            raise ValueError("Per-metric enforcement must be a mapping")
        else:
            cleaned: Dict[str, Any] = {}
            for key, value in per_metric.items():
                if key not in _BUDGET_KEYS:
                    raise ValueError("Unknown per-metric budget key")
                if value is None:
                    cleaned[key] = None
                elif value in {"none", "soft", "hard"}:
                    cleaned[key] = value
                else:
                    raise ValueError("Enforcement mode must be none, soft, or hard")
            out["per_metric"] = cleaned
    return out or None


def _normalize_alert_thresholds_payload(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    out: Dict[str, Any] = {}
    if "global" in value and value.get("global") is not None:
        out["global"] = _normalize_threshold_list(value.get("global"))
    if "per_metric" in value and isinstance(value.get("per_metric"), dict):
        cleaned: Dict[str, Any] = {}
        for key, values in value.get("per_metric", {}).items():
            if key not in _BUDGET_KEYS:
                raise ValueError("Unknown per-metric budget key")
            if values is None:
                continue
            cleaned[key] = _normalize_threshold_list(values)
        if cleaned:
            out["per_metric"] = cleaned
    return out or None


def _normalize_enforcement_mode_payload(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    out: Dict[str, Any] = {}
    global_value = value.get("global")
    if global_value is not None:
        if global_value not in {"none", "soft", "hard"}:
            raise ValueError("Enforcement mode must be none, soft, or hard")
        out["global"] = global_value
    per_metric = value.get("per_metric")
    if isinstance(per_metric, dict):
        cleaned: Dict[str, Any] = {}
        for key, per_value in per_metric.items():
            if key not in _BUDGET_KEYS:
                raise ValueError("Unknown per-metric budget key")
            if per_value is None:
                continue
            if per_value not in {"none", "soft", "hard"}:
                raise ValueError("Enforcement mode must be none, soft, or hard")
            cleaned[key] = per_value
        if cleaned:
            out["per_metric"] = cleaned
    return out or None


def _normalize_budget_payload(raw: Any) -> Dict[str, Any]:
    data = _parse_json_payload(raw)
    if not data:
        return {}

    budgets: Dict[str, Any] = {}
    if isinstance(data.get("budgets"), dict):
        budgets.update(data.get("budgets") or {})
    for key in _BUDGET_KEYS:
        if key in data and key not in budgets:
            budgets[key] = data[key]
    payload = {"budgets": budgets} if budgets else {}
    thresholds = _coerce_alert_thresholds(data.get("alert_thresholds"))
    if thresholds is not None:
        payload["alert_thresholds"] = thresholds
    enforcement = _coerce_enforcement_mode(data.get("enforcement_mode"))
    if enforcement is not None:
        payload["enforcement_mode"] = enforcement
    return payload


def _flatten_budget_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict) or not payload:
        return {}
    flat: Dict[str, Any] = {}
    if isinstance(payload.get("budgets"), dict):
        flat.update(payload.get("budgets") or {})
    else:
        for key in _BUDGET_KEYS:
            if key in payload:
                flat[key] = payload[key]
    if "alert_thresholds" in payload:
        flat["alert_thresholds"] = payload.get("alert_thresholds")
    if "enforcement_mode" in payload:
        flat["enforcement_mode"] = payload.get("enforcement_mode")
    return flat


def _inflate_budget_payload(flat: Dict[str, Any]) -> Dict[str, Any]:
    if not flat:
        return {}
    payload: Dict[str, Any] = {}
    for key in _BUDGET_KEYS:
        if key in flat:
            payload[key] = flat[key]
    if "alert_thresholds" in flat:
        payload["alert_thresholds"] = flat.get("alert_thresholds")
    if "enforcement_mode" in flat:
        payload["enforcement_mode"] = flat.get("enforcement_mode")
    return payload


def _build_budget_item(row: Dict[str, Any]) -> Dict[str, Any]:
    plan_name = row.get("plan_name") or "free"
    plan_display_name = row.get("plan_display_name") or plan_name.title()
    plan_limits = _parse_json_payload(row.get("plan_limits_json"))
    if not plan_limits:
        plan_limits = get_plan_limits(plan_name)

    custom_limits = _parse_json_payload(row.get("custom_limits_json"))
    budgets_payload = _normalize_budget_payload(row.get("budgets_json"))
    if not budgets_payload and isinstance(custom_limits, dict) and "budgets" in custom_limits:
        budgets_payload = _normalize_budget_payload(custom_limits.get("budgets"))
    budgets = _flatten_budget_payload(budgets_payload)
    if isinstance(custom_limits, dict) and "budgets" in custom_limits:
        custom_limits = dict(custom_limits)
        custom_limits.pop("budgets", None)

    effective_limits = dict(plan_limits)
    if isinstance(custom_limits, dict) and custom_limits:
        effective_limits.update(custom_limits)
    if budgets:
        effective_limits["budgets"] = _inflate_budget_payload(budgets)

    return {
        "org_id": int(row.get("org_id")),
        "org_name": row.get("org_name") or "",
        "org_slug": row.get("org_slug"),
        "plan_name": plan_name,
        "plan_display_name": plan_display_name,
        "budgets": budgets,
        "custom_limits": custom_limits,
        "effective_limits": effective_limits,
        "updated_at": row.get("budgets_updated_at") or row.get("updated_at"),
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
        if key in _BUDGET_KEYS:
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
            continue
        if key == "alert_thresholds":
            merged_thresholds = _merge_alert_thresholds(merged.get(key), value)
            if merged_thresholds is None:
                merged.pop(key, None)
            else:
                merged[key] = merged_thresholds
            continue
        if key == "enforcement_mode":
            merged_enforcement = _merge_enforcement_mode(merged.get(key), value)
            if merged_enforcement is None:
                merged.pop(key, None)
            else:
                merged[key] = merged_enforcement
            continue
        raise ValueError("invalid_budget_update")
    return merged


def _merge_alert_thresholds(existing: Any, updates: Any) -> Optional[Dict[str, Any]]:
    if updates is None:
        return None
    existing_payload = existing if isinstance(existing, dict) else {}
    merged: Dict[str, Any] = {}
    if "global" in existing_payload:
        merged["global"] = existing_payload.get("global")
    if isinstance(existing_payload.get("per_metric"), dict):
        merged["per_metric"] = dict(existing_payload.get("per_metric") or {})

    normalized_updates = _normalize_alert_thresholds_update(updates)
    if not normalized_updates:
        return _normalize_alert_thresholds_payload(merged)

    if "global" in normalized_updates:
        if normalized_updates["global"] is None:
            merged.pop("global", None)
        else:
            merged["global"] = normalized_updates["global"]
    if "per_metric" in normalized_updates:
        if normalized_updates["per_metric"] is None:
            merged.pop("per_metric", None)
        else:
            per_metric = merged.get("per_metric")
            if not isinstance(per_metric, dict):
                per_metric = {}
            for key, values in normalized_updates["per_metric"].items():
                if values is None:
                    per_metric.pop(key, None)
                else:
                    per_metric[key] = values
            if per_metric:
                merged["per_metric"] = per_metric
            else:
                merged.pop("per_metric", None)
    return _normalize_alert_thresholds_payload(merged)


def _merge_enforcement_mode(existing: Any, updates: Any) -> Optional[Dict[str, Any]]:
    if updates is None:
        return None
    existing_payload = existing if isinstance(existing, dict) else {}
    merged: Dict[str, Any] = {}
    if "global" in existing_payload:
        merged["global"] = existing_payload.get("global")
    if isinstance(existing_payload.get("per_metric"), dict):
        merged["per_metric"] = dict(existing_payload.get("per_metric") or {})

    normalized_updates = _normalize_enforcement_mode_update(updates)
    if not normalized_updates:
        return _normalize_enforcement_mode_payload(merged)

    if "global" in normalized_updates:
        if normalized_updates["global"] is None:
            merged.pop("global", None)
        else:
            merged["global"] = normalized_updates["global"]
    if "per_metric" in normalized_updates:
        if normalized_updates["per_metric"] is None:
            merged.pop("per_metric", None)
        else:
            per_metric = merged.get("per_metric")
            if not isinstance(per_metric, dict):
                per_metric = {}
            for key, value in normalized_updates["per_metric"].items():
                if value is None:
                    per_metric.pop(key, None)
                else:
                    per_metric[key] = value
            if per_metric:
                merged["per_metric"] = per_metric
            else:
                merged.pop("per_metric", None)
    return _normalize_enforcement_mode_payload(merged)


def _infer_change_data_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def build_budget_change_log(
    existing_budgets: Dict[str, Any],
    merged_budgets: Dict[str, Any],
    budget_updates: Optional[Dict[str, Any]],
    *,
    clear_budgets: bool,
) -> List[Dict[str, Any]]:
    """Create audit-friendly change entries for budget updates."""
    if clear_budgets:
        return [
            {
                "field_name": "budgets",
                "old_value": existing_budgets or {},
                "new_value": None,
                "data_type": "object",
                "notes": "clear_budgets=true",
            }
        ]

    if not budget_updates:
        return []

    changes: List[Dict[str, Any]] = []
    for key, _ in budget_updates.items():
        if key in _BUDGET_KEYS:
            old_value = existing_budgets.get(key)
            new_value = merged_budgets.get(key)
            if old_value == new_value:
                continue
            data_type = _infer_change_data_type(new_value if new_value is not None else old_value)
            changes.append(
                {
                    "field_name": f"budgets.{key}",
                    "old_value": old_value,
                    "new_value": new_value,
                    "data_type": data_type,
                }
            )
            continue
        if key == "alert_thresholds":
            changes.extend(
                _build_nested_changes(
                    "alert_thresholds",
                    existing_budgets.get("alert_thresholds"),
                    merged_budgets.get("alert_thresholds"),
                    budget_updates.get("alert_thresholds"),
                )
            )
            continue
        if key == "enforcement_mode":
            changes.extend(
                _build_nested_changes(
                    "enforcement_mode",
                    existing_budgets.get("enforcement_mode"),
                    merged_budgets.get("enforcement_mode"),
                    budget_updates.get("enforcement_mode"),
                )
            )
            continue
    return changes


def _build_nested_changes(
    field_name: str,
    existing_value: Any,
    merged_value: Any,
    update_value: Any,
) -> List[Dict[str, Any]]:
    if update_value is None:
        if existing_value is None:
            return []
        return [
            {
                "field_name": f"budgets.{field_name}",
                "old_value": existing_value,
                "new_value": None,
                "data_type": _infer_change_data_type(existing_value),
            }
        ]

    if field_name == "alert_thresholds":
        update_payload = _coerce_alert_thresholds(update_value) or {}
    elif field_name == "enforcement_mode":
        update_payload = _coerce_enforcement_mode(update_value) or {}
    else:
        update_payload = {}

    if not update_payload:
        return []

    existing_payload = existing_value if isinstance(existing_value, dict) else {}
    merged_payload = merged_value if isinstance(merged_value, dict) else {}
    changes: List[Dict[str, Any]] = []

    if "global" in update_payload:
        old_value = existing_payload.get("global")
        new_value = merged_payload.get("global")
        if old_value != new_value:
            changes.append(
                {
                    "field_name": f"budgets.{field_name}.global",
                    "old_value": old_value,
                    "new_value": new_value,
                    "data_type": _infer_change_data_type(new_value if new_value is not None else old_value),
                }
            )

    if "per_metric" in update_payload:
        per_metric_update = update_payload.get("per_metric")
        if per_metric_update is None:
            old_value = existing_payload.get("per_metric")
            new_value = merged_payload.get("per_metric")
            if old_value != new_value:
                changes.append(
                    {
                        "field_name": f"budgets.{field_name}.per_metric",
                        "old_value": old_value,
                        "new_value": new_value,
                        "data_type": _infer_change_data_type(new_value if new_value is not None else old_value),
                    }
                )
        elif isinstance(per_metric_update, dict):
            old_map = existing_payload.get("per_metric") if isinstance(existing_payload.get("per_metric"), dict) else {}
            new_map = merged_payload.get("per_metric") if isinstance(merged_payload.get("per_metric"), dict) else {}
            for metric_key in per_metric_update.keys():
                old_value = old_map.get(metric_key)
                new_value = new_map.get(metric_key)
                if old_value == new_value:
                    continue
                changes.append(
                    {
                        "field_name": f"budgets.{field_name}.per_metric.{metric_key}",
                        "old_value": old_value,
                        "new_value": new_value,
                        "data_type": _infer_change_data_type(new_value if new_value is not None else old_value),
                    }
                )

    return changes


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
        "ob.budgets_json, ob.updated_at as budgets_updated_at, "
        "sp.name as plan_name, sp.display_name as plan_display_name, sp.limits_json as plan_limits_json "
        "FROM organizations o "
        "LEFT JOIN org_subscriptions os ON os.org_id = o.id "
        "LEFT JOIN subscription_plans sp ON os.plan_id = sp.id "
        "LEFT JOIN org_budgets ob ON ob.org_id = o.id "
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
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
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
    cleaned_custom_limits = custom_limits
    removed_custom_budget = False
    if isinstance(custom_limits, dict) and "budgets" in custom_limits:
        cleaned_custom_limits = dict(custom_limits)
        cleaned_custom_limits.pop("budgets", None)
        removed_custom_budget = True

    budget_row = await _fetchrow(
        db,
        "SELECT org_id, budgets_json, updated_at FROM org_budgets WHERE org_id = $1",
        [org_id],
    )
    budgets_payload = _normalize_budget_payload(
        budget_row.get("budgets_json") if budget_row else None
    )
    legacy_budgets = False
    if not budgets_payload and isinstance(custom_limits, dict) and "budgets" in custom_limits:
        budgets_payload = _normalize_budget_payload(custom_limits.get("budgets"))
        legacy_budgets = True

    existing_budgets = _flatten_budget_payload(budgets_payload)
    merged_budgets = merge_budget_settings(existing_budgets, budget_updates, clear=clear_budgets)
    audit_changes = build_budget_change_log(
        existing_budgets,
        merged_budgets,
        budget_updates,
        clear_budgets=clear_budgets,
    )
    updated_payload = _inflate_budget_payload(merged_budgets)

    now = datetime.utcnow()
    should_upsert_budget = budget_updates is not None or clear_budgets or legacy_budgets
    if should_upsert_budget:
        payload = json.dumps(updated_payload) if updated_payload else None
        if pg:
            await db.execute(
                """
                INSERT INTO org_budgets (org_id, budgets_json, updated_at)
                VALUES ($1, $2::jsonb, $3)
                ON CONFLICT (org_id)
                DO UPDATE SET budgets_json = EXCLUDED.budgets_json, updated_at = EXCLUDED.updated_at
                """,
                org_id,
                payload,
                now,
            )
        else:
            await db.execute(
                """
                INSERT INTO org_budgets (org_id, budgets_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(org_id)
                DO UPDATE SET budgets_json = excluded.budgets_json, updated_at = excluded.updated_at
                """,
                (org_id, payload, now),
            )
        row_dict["budgets_json"] = payload
        row_dict["budgets_updated_at"] = now
    else:
        row_dict["budgets_json"] = budgets_payload
        row_dict["budgets_updated_at"] = budget_row.get("updated_at") if budget_row else None

    if removed_custom_budget:
        payload = json.dumps(cleaned_custom_limits) if cleaned_custom_limits else None
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
    return _build_budget_item(row_dict), audit_changes
