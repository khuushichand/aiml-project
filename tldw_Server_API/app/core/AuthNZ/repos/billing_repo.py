"""
billing_repo.py

Repository for billing-related database operations.
Handles subscription plans, org subscriptions, payment history, and billing audit logs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool


@dataclass
class AuthnzBillingRepo:
    """Repository for billing operations."""

    db_pool: DatabasePool

    def _is_postgres(self, conn: Optional[Any] = None) -> bool:
        """Detect whether the current backend is PostgreSQL."""
        if conn is not None:
            return hasattr(conn, "fetchrow")
        return getattr(self.db_pool, "pool", None) is not None

    # =========================================================================
    # Subscription Plans
    # =========================================================================

    async def list_plans(
        self,
        *,
        active_only: bool = True,
        public_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        List subscription plans.

        Args:
            active_only: Only return active plans
            public_only: Only return publicly visible plans

        Returns:
            List of plan dicts with parsed limits_json
        """
        conditions = []
        if active_only:
            conditions.append("is_active = 1" if not self._is_postgres() else "is_active = TRUE")
        if public_only:
            conditions.append("is_public = 1" if not self._is_postgres() else "is_public = TRUE")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        try:
            async with self.db_pool.acquire() as conn:
                if self._is_postgres(conn):
                    rows = await conn.fetch(
                        f"""
                        SELECT id, name, display_name, description, stripe_product_id, stripe_price_id,
                               price_usd_monthly, price_usd_yearly, limits_json, is_active, is_public,
                               sort_order, created_at
                        FROM subscription_plans
                        {where_clause}
                        ORDER BY sort_order ASC, created_at ASC
                        """
                    )
                    return [self._plan_row_to_dict(dict(r)) for r in rows]
                else:
                    cur = await conn.execute(
                        f"""
                        SELECT id, name, display_name, description, stripe_product_id, stripe_price_id,
                               price_usd_monthly, price_usd_yearly, limits_json, is_active, is_public,
                               sort_order, created_at
                        FROM subscription_plans
                        {where_clause}
                        ORDER BY sort_order ASC, created_at ASC
                        """
                    )
                    rows = await cur.fetchall()
                    return [
                        self._plan_row_to_dict({
                            "id": r[0], "name": r[1], "display_name": r[2], "description": r[3],
                            "stripe_product_id": r[4], "stripe_price_id": r[5],
                            "price_usd_monthly": r[6], "price_usd_yearly": r[7],
                            "limits_json": r[8], "is_active": bool(r[9]), "is_public": bool(r[10]),
                            "sort_order": r[11], "created_at": r[12],
                        })
                        for r in rows
                    ]
        except Exception as exc:
            logger.error(f"AuthnzBillingRepo.list_plans failed: {exc}")
            raise

    async def get_plan_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a subscription plan by name."""
        try:
            async with self.db_pool.acquire() as conn:
                if self._is_postgres(conn):
                    row = await conn.fetchrow(
                        """
                        SELECT id, name, display_name, description, stripe_product_id, stripe_price_id,
                               price_usd_monthly, price_usd_yearly, limits_json, is_active, is_public,
                               sort_order, created_at
                        FROM subscription_plans
                        WHERE name = $1
                        """,
                        name,
                    )
                    return self._plan_row_to_dict(dict(row)) if row else None
                else:
                    cur = await conn.execute(
                        """
                        SELECT id, name, display_name, description, stripe_product_id, stripe_price_id,
                               price_usd_monthly, price_usd_yearly, limits_json, is_active, is_public,
                               sort_order, created_at
                        FROM subscription_plans
                        WHERE name = ?
                        """,
                        (name,),
                    )
                    row = await cur.fetchone()
                    if not row:
                        return None
                    return self._plan_row_to_dict({
                        "id": row[0], "name": row[1], "display_name": row[2], "description": row[3],
                        "stripe_product_id": row[4], "stripe_price_id": row[5],
                        "price_usd_monthly": row[6], "price_usd_yearly": row[7],
                        "limits_json": row[8], "is_active": bool(row[9]), "is_public": bool(row[10]),
                        "sort_order": row[11], "created_at": row[12],
                    })
        except Exception as exc:
            logger.error(f"AuthnzBillingRepo.get_plan_by_name failed: {exc}")
            raise

    async def get_plan_by_id(self, plan_id: int) -> Optional[Dict[str, Any]]:
        """Get a subscription plan by ID."""
        try:
            async with self.db_pool.acquire() as conn:
                if self._is_postgres(conn):
                    row = await conn.fetchrow(
                        """
                        SELECT id, name, display_name, description, stripe_product_id, stripe_price_id,
                               price_usd_monthly, price_usd_yearly, limits_json, is_active, is_public,
                               sort_order, created_at
                        FROM subscription_plans WHERE id = $1
                        """,
                        plan_id,
                    )
                    return self._plan_row_to_dict(dict(row)) if row else None
                else:
                    cur = await conn.execute(
                        """
                        SELECT id, name, display_name, description, stripe_product_id, stripe_price_id,
                               price_usd_monthly, price_usd_yearly, limits_json, is_active, is_public,
                               sort_order, created_at
                        FROM subscription_plans WHERE id = ?
                        """,
                        (plan_id,),
                    )
                    row = await cur.fetchone()
                    if not row:
                        return None
                    return self._plan_row_to_dict({
                        "id": row[0], "name": row[1], "display_name": row[2], "description": row[3],
                        "stripe_product_id": row[4], "stripe_price_id": row[5],
                        "price_usd_monthly": row[6], "price_usd_yearly": row[7],
                        "limits_json": row[8], "is_active": bool(row[9]), "is_public": bool(row[10]),
                        "sort_order": row[11], "created_at": row[12],
                    })
        except Exception as exc:
            logger.error(f"AuthnzBillingRepo.get_plan_by_id failed: {exc}")
            raise

    def _plan_row_to_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert plan row to dict with parsed limits."""
        result = dict(row)
        if result.get("limits_json"):
            try:
                if isinstance(result["limits_json"], str):
                    result["limits"] = json.loads(result["limits_json"])
                else:
                    result["limits"] = result["limits_json"]
            except (json.JSONDecodeError, TypeError):
                result["limits"] = {}
        else:
            result["limits"] = {}
        return result

    # =========================================================================
    # Organization Subscriptions
    # =========================================================================

    async def get_org_subscription(self, org_id: int) -> Optional[Dict[str, Any]]:
        """Get the subscription for an organization."""
        try:
            async with self.db_pool.acquire() as conn:
                if self._is_postgres(conn):
                    row = await conn.fetchrow(
                        """
                        SELECT os.id, os.org_id, os.plan_id, os.stripe_customer_id, os.stripe_subscription_id,
                               os.stripe_subscription_status, os.billing_cycle, os.current_period_start,
                               os.current_period_end, os.status, os.trial_end, os.custom_limits_json,
                               os.created_at, sp.name as plan_name, sp.display_name as plan_display_name,
                               sp.limits_json as plan_limits_json
                        FROM org_subscriptions os
                        JOIN subscription_plans sp ON os.plan_id = sp.id
                        WHERE os.org_id = $1
                        """,
                        org_id,
                    )
                    return self._subscription_row_to_dict(dict(row)) if row else None
                else:
                    cur = await conn.execute(
                        """
                        SELECT os.id, os.org_id, os.plan_id, os.stripe_customer_id, os.stripe_subscription_id,
                               os.stripe_subscription_status, os.billing_cycle, os.current_period_start,
                               os.current_period_end, os.status, os.trial_end, os.custom_limits_json,
                               os.created_at, sp.name as plan_name, sp.display_name as plan_display_name,
                               sp.limits_json as plan_limits_json
                        FROM org_subscriptions os
                        JOIN subscription_plans sp ON os.plan_id = sp.id
                        WHERE os.org_id = ?
                        """,
                        (org_id,),
                    )
                    row = await cur.fetchone()
                    if not row:
                        return None
                    return self._subscription_row_to_dict({
                        "id": row[0], "org_id": row[1], "plan_id": row[2],
                        "stripe_customer_id": row[3], "stripe_subscription_id": row[4],
                        "stripe_subscription_status": row[5], "billing_cycle": row[6],
                        "current_period_start": row[7], "current_period_end": row[8],
                        "status": row[9], "trial_end": row[10], "custom_limits_json": row[11],
                        "created_at": row[12], "plan_name": row[13], "plan_display_name": row[14],
                        "plan_limits_json": row[15],
                    })
        except Exception as exc:
            logger.error(f"AuthnzBillingRepo.get_org_subscription failed: {exc}")
            raise

    async def create_org_subscription(
        self,
        *,
        org_id: int,
        plan_id: int,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        billing_cycle: str = "monthly",
        status: str = "active",
        trial_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a subscription for an organization."""
        trial_end = None
        if trial_days:
            trial_end = datetime.utcnow() + timedelta(days=trial_days)

        try:
            async with self.db_pool.transaction() as conn:
                if self._is_postgres(conn):
                    row = await conn.fetchrow(
                        """
                        INSERT INTO org_subscriptions (org_id, plan_id, stripe_customer_id, stripe_subscription_id,
                                                       billing_cycle, status, trial_end)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (org_id) DO UPDATE SET
                            plan_id = EXCLUDED.plan_id,
                            stripe_customer_id = EXCLUDED.stripe_customer_id,
                            stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                            billing_cycle = EXCLUDED.billing_cycle,
                            status = EXCLUDED.status,
                            trial_end = EXCLUDED.trial_end
                        RETURNING id, org_id, plan_id, stripe_customer_id, stripe_subscription_id,
                                  stripe_subscription_status, billing_cycle, current_period_start,
                                  current_period_end, status, trial_end, custom_limits_json, created_at
                        """,
                        org_id, plan_id, stripe_customer_id, stripe_subscription_id,
                        billing_cycle, status, trial_end,
                    )
                    return dict(row)
                else:
                    await conn.execute(
                        """
                        INSERT INTO org_subscriptions (org_id, plan_id, stripe_customer_id, stripe_subscription_id,
                                                       billing_cycle, status, trial_end)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (org_id) DO UPDATE SET
                            plan_id = excluded.plan_id,
                            stripe_customer_id = excluded.stripe_customer_id,
                            stripe_subscription_id = excluded.stripe_subscription_id,
                            billing_cycle = excluded.billing_cycle,
                            status = excluded.status,
                            trial_end = excluded.trial_end
                        """,
                        (org_id, plan_id, stripe_customer_id, stripe_subscription_id,
                         billing_cycle, status, trial_end.isoformat() if trial_end else None),
                    )
                    cur = await conn.execute(
                        "SELECT id, org_id, plan_id, stripe_customer_id, stripe_subscription_id, "
                        "stripe_subscription_status, billing_cycle, current_period_start, "
                        "current_period_end, status, trial_end, custom_limits_json, created_at "
                        "FROM org_subscriptions WHERE org_id = ?",
                        (org_id,),
                    )
                    row = await cur.fetchone()
                    return {
                        "id": row[0], "org_id": row[1], "plan_id": row[2],
                        "stripe_customer_id": row[3], "stripe_subscription_id": row[4],
                        "stripe_subscription_status": row[5], "billing_cycle": row[6],
                        "current_period_start": row[7], "current_period_end": row[8],
                        "status": row[9], "trial_end": row[10], "custom_limits_json": row[11],
                        "created_at": row[12],
                    }
        except Exception as exc:
            logger.error(f"AuthnzBillingRepo.create_org_subscription failed: {exc}")
            raise

    async def update_org_subscription(
        self,
        org_id: int,
        **updates: Any,
    ) -> Optional[Dict[str, Any]]:
        """Update an organization's subscription."""
        if not updates:
            return await self.get_org_subscription(org_id)

        # Handle special cases
        if "custom_limits" in updates:
            updates["custom_limits_json"] = json.dumps(updates.pop("custom_limits"))

        allowed_fields = {
            "plan_id", "stripe_customer_id", "stripe_subscription_id",
            "stripe_subscription_status", "billing_cycle", "current_period_start",
            "current_period_end", "status", "trial_end", "custom_limits_json",
        }
        updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not updates:
            return await self.get_org_subscription(org_id)

        try:
            async with self.db_pool.transaction() as conn:
                if self._is_postgres(conn):
                    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
                    params = [org_id] + list(updates.values())
                    await conn.execute(
                        f"UPDATE org_subscriptions SET {set_clause} WHERE org_id = $1",
                        *params,
                    )
                else:
                    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
                    params = list(updates.values()) + [org_id]
                    await conn.execute(
                        f"UPDATE org_subscriptions SET {set_clause} WHERE org_id = ?",
                        tuple(params),
                    )

            return await self.get_org_subscription(org_id)
        except Exception as exc:
            logger.error(f"AuthnzBillingRepo.update_org_subscription failed: {exc}")
            raise

    async def get_subscription_by_stripe_customer(self, stripe_customer_id: str) -> Optional[Dict[str, Any]]:
        """Get subscription by Stripe customer ID."""
        try:
            async with self.db_pool.acquire() as conn:
                if self._is_postgres(conn):
                    row = await conn.fetchrow(
                        "SELECT org_id FROM org_subscriptions WHERE stripe_customer_id = $1",
                        stripe_customer_id,
                    )
                    if row:
                        return await self.get_org_subscription(row["org_id"])
                    return None
                else:
                    cur = await conn.execute(
                        "SELECT org_id FROM org_subscriptions WHERE stripe_customer_id = ?",
                        (stripe_customer_id,),
                    )
                    row = await cur.fetchone()
                    if row:
                        return await self.get_org_subscription(row[0])
                    return None
        except Exception as exc:
            logger.error(f"AuthnzBillingRepo.get_subscription_by_stripe_customer failed: {exc}")
            raise

    def _subscription_row_to_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert subscription row to dict with parsed limits."""
        result = dict(row)
        # Parse custom limits
        if result.get("custom_limits_json"):
            try:
                if isinstance(result["custom_limits_json"], str):
                    result["custom_limits"] = json.loads(result["custom_limits_json"])
                else:
                    result["custom_limits"] = result["custom_limits_json"]
            except (json.JSONDecodeError, TypeError):
                result["custom_limits"] = {}
        else:
            result["custom_limits"] = {}

        # Parse plan limits
        if result.get("plan_limits_json"):
            try:
                if isinstance(result["plan_limits_json"], str):
                    result["plan_limits"] = json.loads(result["plan_limits_json"])
                else:
                    result["plan_limits"] = result["plan_limits_json"]
            except (json.JSONDecodeError, TypeError):
                result["plan_limits"] = {}
        else:
            result["plan_limits"] = {}

        # Merge limits: custom overrides plan
        result["effective_limits"] = {**result["plan_limits"], **result["custom_limits"]}
        return result

    # =========================================================================
    # Payment History
    # =========================================================================

    async def add_payment(
        self,
        *,
        org_id: int,
        stripe_invoice_id: Optional[str] = None,
        amount_cents: int,
        currency: str = "usd",
        status: str = "succeeded",
        description: Optional[str] = None,
        invoice_pdf_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a payment in history."""
        try:
            async with self.db_pool.transaction() as conn:
                if self._is_postgres(conn):
                    row = await conn.fetchrow(
                        """
                        INSERT INTO payment_history (org_id, stripe_invoice_id, amount_cents, currency,
                                                     status, description, invoice_pdf_url)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        RETURNING id, org_id, stripe_invoice_id, amount_cents, currency, status,
                                  description, invoice_pdf_url, created_at
                        """,
                        org_id, stripe_invoice_id, amount_cents, currency, status,
                        description, invoice_pdf_url,
                    )
                    return dict(row)
                else:
                    cur = await conn.execute(
                        """
                        INSERT INTO payment_history (org_id, stripe_invoice_id, amount_cents, currency,
                                                     status, description, invoice_pdf_url)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (org_id, stripe_invoice_id, amount_cents, currency, status,
                         description, invoice_pdf_url),
                    )
                    payment_id = cur.lastrowid
                    cur2 = await conn.execute(
                        "SELECT id, org_id, stripe_invoice_id, amount_cents, currency, status, "
                        "description, invoice_pdf_url, created_at FROM payment_history WHERE id = ?",
                        (payment_id,),
                    )
                    row = await cur2.fetchone()
                    return {
                        "id": row[0], "org_id": row[1], "stripe_invoice_id": row[2],
                        "amount_cents": row[3], "currency": row[4], "status": row[5],
                        "description": row[6], "invoice_pdf_url": row[7], "created_at": row[8],
                    }
        except Exception as exc:
            logger.error(f"AuthnzBillingRepo.add_payment failed: {exc}")
            raise

    async def list_payments(
        self,
        org_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List payment history for an organization."""
        try:
            async with self.db_pool.acquire() as conn:
                if self._is_postgres(conn):
                    rows = await conn.fetch(
                        """
                        SELECT id, org_id, stripe_invoice_id, amount_cents, currency, status,
                               description, invoice_pdf_url, created_at
                        FROM payment_history
                        WHERE org_id = $1
                        ORDER BY created_at DESC
                        LIMIT $2 OFFSET $3
                        """,
                        org_id, limit, offset,
                    )
                    total = await conn.fetchval(
                        "SELECT COUNT(*) FROM payment_history WHERE org_id = $1",
                        org_id,
                    )
                    return [dict(r) for r in rows], int(total or 0)
                else:
                    cur = await conn.execute(
                        """
                        SELECT id, org_id, stripe_invoice_id, amount_cents, currency, status,
                               description, invoice_pdf_url, created_at
                        FROM payment_history
                        WHERE org_id = ?
                        ORDER BY created_at DESC
                        LIMIT ? OFFSET ?
                        """,
                        (org_id, limit, offset),
                    )
                    rows = await cur.fetchall()
                    cur2 = await conn.execute(
                        "SELECT COUNT(*) FROM payment_history WHERE org_id = ?",
                        (org_id,),
                    )
                    total_row = await cur2.fetchone()
                    payments = [
                        {
                            "id": r[0], "org_id": r[1], "stripe_invoice_id": r[2],
                            "amount_cents": r[3], "currency": r[4], "status": r[5],
                            "description": r[6], "invoice_pdf_url": r[7], "created_at": r[8],
                        }
                        for r in rows
                    ]
                    return payments, int(total_row[0]) if total_row else 0
        except Exception as exc:
            logger.error(f"AuthnzBillingRepo.list_payments failed: {exc}")
            raise

    # =========================================================================
    # Billing Audit Log
    # =========================================================================

    async def log_billing_action(
        self,
        *,
        org_id: int,
        action: str,
        user_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Log a billing-related action for audit purposes."""
        details_json = json.dumps(details) if details else None

        try:
            async with self.db_pool.transaction() as conn:
                if self._is_postgres(conn):
                    row = await conn.fetchrow(
                        """
                        INSERT INTO billing_audit_log (org_id, user_id, action, details, ip_address)
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING id, org_id, user_id, action, details, ip_address, created_at
                        """,
                        org_id, user_id, action, details_json, ip_address,
                    )
                    return dict(row)
                else:
                    cur = await conn.execute(
                        """
                        INSERT INTO billing_audit_log (org_id, user_id, action, details, ip_address)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (org_id, user_id, action, details_json, ip_address),
                    )
                    log_id = cur.lastrowid
                    cur2 = await conn.execute(
                        "SELECT id, org_id, user_id, action, details, ip_address, created_at "
                        "FROM billing_audit_log WHERE id = ?",
                        (log_id,),
                    )
                    row = await cur2.fetchone()
                    return {
                        "id": row[0], "org_id": row[1], "user_id": row[2],
                        "action": row[3], "details": row[4], "ip_address": row[5],
                        "created_at": row[6],
                    }
        except Exception as exc:
            logger.error(f"AuthnzBillingRepo.log_billing_action failed: {exc}")
            raise

    # =========================================================================
    # Stripe Webhook Events
    # =========================================================================

    async def record_webhook_event(
        self,
        stripe_event_id: str,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> bool:
        """
        Record a Stripe webhook event for idempotency.

        Returns True if this is a new event, False if already processed.
        """
        try:
            async with self.db_pool.transaction() as conn:
                if self._is_postgres(conn):
                    # Try to insert, ignore conflict (idempotency)
                    row = await conn.fetchrow(
                        """
                        INSERT INTO stripe_webhook_events (stripe_event_id, event_type, event_data)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (stripe_event_id) DO NOTHING
                        RETURNING id
                        """,
                        stripe_event_id, event_type, json.dumps(event_data),
                    )
                    return row is not None
                else:
                    try:
                        await conn.execute(
                            """
                            INSERT INTO stripe_webhook_events (stripe_event_id, event_type, event_data)
                            VALUES (?, ?, ?)
                            """,
                            (stripe_event_id, event_type, json.dumps(event_data)),
                        )
                        return True
                    except Exception:
                        # Likely unique constraint violation
                        return False
        except Exception as exc:
            logger.error(f"AuthnzBillingRepo.record_webhook_event failed: {exc}")
            raise

    async def mark_webhook_processed(
        self,
        stripe_event_id: str,
        *,
        error_message: Optional[str] = None,
    ) -> None:
        """Mark a webhook event as processed."""
        status = "failed" if error_message else "processed"
        try:
            async with self.db_pool.transaction() as conn:
                if self._is_postgres(conn):
                    await conn.execute(
                        """
                        UPDATE stripe_webhook_events
                        SET status = $2, processed_at = CURRENT_TIMESTAMP, error_message = $3
                        WHERE stripe_event_id = $1
                        """,
                        stripe_event_id, status, error_message,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE stripe_webhook_events
                        SET status = ?, processed_at = CURRENT_TIMESTAMP, error_message = ?
                        WHERE stripe_event_id = ?
                        """,
                        (status, error_message, stripe_event_id),
                    )
        except Exception as exc:
            logger.error(f"AuthnzBillingRepo.mark_webhook_processed failed: {exc}")
            raise

    # =========================================================================
    # Effective Limits Helper
    # =========================================================================

    async def get_org_limits(self, org_id: int) -> Dict[str, Any]:
        """
        Get the effective limits for an organization.

        Returns merged limits from plan + custom overrides.
        Falls back to free tier if no subscription exists.
        """
        subscription = await self.get_org_subscription(org_id)

        if not subscription:
            # Fall back to free plan
            free_plan = await self.get_plan_by_name("free")
            if free_plan:
                return free_plan.get("limits", {})
            # Ultimate fallback
            return {
                "storage_gb": 1,
                "api_calls_day": 100,
                "llm_tokens_month": 300000,
                "team_members": 1,
            }

        return subscription.get("effective_limits", {})
