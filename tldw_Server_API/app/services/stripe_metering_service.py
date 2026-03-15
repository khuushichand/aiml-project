"""
Stripe Usage Metering Reconciliation Service.

Syncs aggregated usage from usage_daily table to Stripe's metering API.
Runs as a periodic background task to keep billing in sync.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

# Stripe import is optional - mirrors stripe_client.py pattern
try:
    import stripe
    import stripe.error

    STRIPE_AVAILABLE = True
except ImportError:
    stripe = None  # type: ignore[assignment]
    STRIPE_AVAILABLE = False


class StripeMeteringService:
    """Reconciles local usage tracking with Stripe metering."""

    def __init__(self) -> None:
        self._enabled = os.getenv("BILLING_ENABLED", "false").lower() in ("1", "true")
        self._stripe_key = os.getenv("STRIPE_API_KEY", "")
        self._meter_event_name = os.getenv("STRIPE_METER_EVENT_NAME", "api_requests")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_db_pool(self) -> Any:
        """Lazily acquire the AuthNZ database pool."""
        from tldw_Server_API.app.core.AuthNZ.database import get_db_pool

        return await get_db_pool()

    @staticmethod
    def _is_postgres(conn: Any) -> bool:
        """Detect whether *conn* is a PostgreSQL connection (asyncpg)."""
        return hasattr(conn, "fetchrow")

    async def _query_usage_for_date(self, pool: Any, target_date: str) -> list[dict[str, Any]]:
        """Fetch usage_daily rows for *target_date*.

        Returns a list of dicts with keys: user_id, requests, errors,
        bytes_total, bytes_in_total, latency_avg_ms.
        """
        async with pool.acquire() as conn:
            if self._is_postgres(conn):
                rows = await conn.fetch(
                    "SELECT user_id, requests, errors, bytes_total, "
                    "COALESCE(bytes_in_total, 0) AS bytes_in_total, latency_avg_ms "
                    "FROM usage_daily WHERE day = $1",
                    target_date,
                )
                return [dict(r) for r in rows]
            else:
                cur = await conn.execute(
                    "SELECT user_id, requests, errors, bytes_total, "
                    "COALESCE(bytes_in_total, 0) AS bytes_in_total, latency_avg_ms "
                    "FROM usage_daily WHERE day = ?",
                    (target_date,),
                )
                raw_rows = await cur.fetchall()
                if not raw_rows:
                    return []
                columns = [col[0] for col in cur.description]
                return [dict(zip(columns, row)) for row in raw_rows]

    async def _query_user_subscription(
        self, pool: Any, user_id: int
    ) -> dict[str, Any] | None:
        """Look up the active Stripe subscription for a user.

        Joins through org_members -> org_subscriptions to find the user's
        organisation subscription that has a Stripe subscription ID.
        Falls back to checking the ``organizations.owner_user_id`` path.
        """
        async with pool.acquire() as conn:
            if self._is_postgres(conn):
                row = await conn.fetchrow(
                    """
                    SELECT os.stripe_customer_id,
                           os.stripe_subscription_id,
                           os.org_id
                    FROM org_subscriptions os
                    JOIN org_members om ON om.org_id = os.org_id
                    WHERE om.user_id = $1
                      AND om.status = 'active'
                      AND os.status = 'active'
                      AND os.stripe_subscription_id IS NOT NULL
                    LIMIT 1
                    """,
                    user_id,
                )
                return dict(row) if row else None
            else:
                cur = await conn.execute(
                    """
                    SELECT os.stripe_customer_id,
                           os.stripe_subscription_id,
                           os.org_id
                    FROM org_subscriptions os
                    JOIN org_members om ON om.org_id = os.org_id
                    WHERE om.user_id = ?
                      AND om.status = 'active'
                      AND os.status = 'active'
                      AND os.stripe_subscription_id IS NOT NULL
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = await cur.fetchone()
                if not row:
                    return None
                columns = [col[0] for col in cur.description]
                return dict(zip(columns, row))

    async def _get_subscription_metered_item(
        self, subscription_id: str
    ) -> str | None:
        """Return the first metered subscription-item ID on *subscription_id*.

        Stripe usage records are attached to a *subscription item*, not the
        subscription itself.  This helper retrieves the subscription and picks
        the first item whose price has ``usage_type == 'metered'``.
        """
        if not STRIPE_AVAILABLE:
            return None
        try:
            sub = await asyncio.to_thread(
                stripe.Subscription.retrieve,
                subscription_id,
                expand=["items.data.price"],
            )
            for item in sub.get("items", {}).get("data", []):
                price = item.get("price", {})
                if price.get("recurring", {}).get("usage_type") == "metered":
                    return item["id"]
            # No metered item found — return None so caller can skip
            return None
        except Exception as exc:
            logger.warning(
                "Failed to retrieve subscription items for {}: {}",
                subscription_id,
                exc,
            )
            return None

    async def _ensure_metering_sync_table(self, pool: Any) -> None:
        """Create the ``metering_sync_log`` tracking table if it does not exist."""
        async with pool.acquire() as conn:
            if self._is_postgres(conn):
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metering_sync_log (
                        user_id INTEGER NOT NULL,
                        day DATE NOT NULL,
                        stripe_subscription_id TEXT NOT NULL,
                        requests_synced INTEGER DEFAULT 0,
                        bytes_synced BIGINT DEFAULT 0,
                        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, day, stripe_subscription_id)
                    )
                    """
                )
            else:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metering_sync_log (
                        user_id INTEGER NOT NULL,
                        day DATE NOT NULL,
                        stripe_subscription_id TEXT NOT NULL,
                        requests_synced INTEGER DEFAULT 0,
                        bytes_synced INTEGER DEFAULT 0,
                        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, day, stripe_subscription_id)
                    )
                    """
                )
                await conn.commit()

    async def _already_synced(
        self, pool: Any, user_id: int, day: str, subscription_id: str
    ) -> bool:
        """Return True if usage for this user/day/subscription was already synced."""
        async with pool.acquire() as conn:
            if self._is_postgres(conn):
                row = await conn.fetchval(
                    "SELECT 1 FROM metering_sync_log "
                    "WHERE user_id = $1 AND day = $2 AND stripe_subscription_id = $3",
                    user_id,
                    day,
                    subscription_id,
                )
                return row is not None
            else:
                cur = await conn.execute(
                    "SELECT 1 FROM metering_sync_log "
                    "WHERE user_id = ? AND day = ? AND stripe_subscription_id = ?",
                    (user_id, day, subscription_id),
                )
                return (await cur.fetchone()) is not None

    async def _record_sync(
        self,
        pool: Any,
        user_id: int,
        day: str,
        subscription_id: str,
        requests: int,
        bytes_total: int,
    ) -> None:
        """Record a successful sync in metering_sync_log."""
        async with pool.acquire() as conn:
            if self._is_postgres(conn):
                await conn.execute(
                    "INSERT INTO metering_sync_log "
                    "(user_id, day, stripe_subscription_id, requests_synced, bytes_synced) "
                    "VALUES ($1, $2, $3, $4, $5) "
                    "ON CONFLICT (user_id, day, stripe_subscription_id) DO UPDATE "
                    "SET requests_synced = EXCLUDED.requests_synced, "
                    "    bytes_synced = EXCLUDED.bytes_synced, "
                    "    synced_at = CURRENT_TIMESTAMP",
                    user_id,
                    day,
                    subscription_id,
                    requests,
                    bytes_total,
                )
            else:
                await conn.execute(
                    "INSERT OR REPLACE INTO metering_sync_log "
                    "(user_id, day, stripe_subscription_id, requests_synced, bytes_synced) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_id, day, subscription_id, requests, bytes_total),
                )
                await conn.commit()

    async def _report_usage_to_stripe(
        self, subscription_item_id: str, quantity: int, timestamp: int
    ) -> None:
        """Create a Stripe usage record on the given subscription item.

        Uses the legacy ``SubscriptionItem.create_usage_record`` API which is
        widely supported across stripe-python versions.
        """
        if not STRIPE_AVAILABLE:
            raise RuntimeError("stripe package is not installed")

        await asyncio.to_thread(
            stripe.SubscriptionItem.create_usage_record,
            subscription_item_id,
            quantity=quantity,
            timestamp=timestamp,
            action="set",
        )

    async def _query_sync_totals(self, pool: Any, target_date: str) -> list[dict[str, Any]]:
        """Fetch synced totals from metering_sync_log for *target_date*."""
        async with pool.acquire() as conn:
            if self._is_postgres(conn):
                rows = await conn.fetch(
                    "SELECT user_id, stripe_subscription_id, requests_synced, bytes_synced "
                    "FROM metering_sync_log WHERE day = $1",
                    target_date,
                )
                return [dict(r) for r in rows]
            else:
                cur = await conn.execute(
                    "SELECT user_id, stripe_subscription_id, requests_synced, bytes_synced "
                    "FROM metering_sync_log WHERE day = ?",
                    (target_date,),
                )
                raw = await cur.fetchall()
                if not raw:
                    return []
                cols = [c[0] for c in cur.description]
                return [dict(zip(cols, r)) for r in raw]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_daily_usage(self, date: str | None = None) -> dict[str, Any]:
        """Sync a day's usage to Stripe metering.

        Args:
            date: ISO date string (YYYY-MM-DD). Defaults to yesterday.

        Returns:
            Summary of synced records.
        """
        if not self._enabled or not self._stripe_key:
            return {"status": "skipped", "reason": "billing_not_enabled"}

        if not STRIPE_AVAILABLE:
            return {"status": "skipped", "reason": "stripe_package_not_installed"}

        target_date = date or (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).strftime("%Y-%m-%d")

        logger.info("Stripe metering sync for {}: started", target_date)

        # Configure stripe key (stripe is guaranteed non-None since STRIPE_AVAILABLE is True)
        stripe.api_key = self._stripe_key  # type: ignore[union-attr]

        # Acquire DB pool
        try:
            pool = await self._get_db_pool()
        except Exception as exc:
            logger.error("Stripe metering sync: failed to get DB pool: {}", exc)
            return {
                "status": "error",
                "date": target_date,
                "error": f"db_pool_unavailable: {exc}",
            }

        # Ensure tracking table exists
        try:
            await self._ensure_metering_sync_table(pool)
        except Exception as exc:
            logger.warning(
                "Stripe metering sync: could not ensure sync table: {}", exc
            )
            # Non-fatal — table may already exist, or usage_daily may not exist either

        # Query usage for the target date
        try:
            usage_rows = await self._query_usage_for_date(pool, target_date)
        except Exception as exc:
            logger.error(
                "Stripe metering sync for {}: failed to query usage: {}",
                target_date,
                exc,
            )
            return {
                "status": "error",
                "date": target_date,
                "error": f"usage_query_failed: {exc}",
            }

        if not usage_rows:
            logger.info("Stripe metering sync for {}: no usage data", target_date)
            return {
                "status": "completed",
                "date": target_date,
                "synced_users": 0,
                "skipped_users": 0,
                "errors": 0,
                "message": "no_usage_data",
            }

        # Compute the epoch timestamp for end-of-day (23:59:59 UTC)
        try:
            dt = datetime.strptime(target_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            usage_timestamp = int(dt.timestamp())
        except ValueError:
            usage_timestamp = int(datetime.now(timezone.utc).timestamp())

        synced = 0
        skipped = 0
        errors = 0

        for row in usage_rows:
            user_id = row["user_id"]
            requests = row.get("requests", 0) or 0
            bytes_total = row.get("bytes_total", 0) or 0

            if requests == 0:
                skipped += 1
                continue

            try:
                # Look up user's Stripe subscription
                sub_info = await self._query_user_subscription(pool, user_id)
                if not sub_info:
                    skipped += 1
                    continue

                subscription_id = sub_info["stripe_subscription_id"]

                # Check for duplicate sync
                try:
                    if await self._already_synced(
                        pool, user_id, target_date, subscription_id
                    ):
                        logger.debug(
                            "Skipping already-synced user {} for {}",
                            user_id,
                            target_date,
                        )
                        skipped += 1
                        continue
                except Exception:
                    # Table might not exist; proceed with sync
                    pass

                # Find the metered subscription item
                item_id = await self._get_subscription_metered_item(subscription_id)
                if not item_id:
                    logger.debug(
                        "No metered item on subscription {} for user {}",
                        subscription_id,
                        user_id,
                    )
                    skipped += 1
                    continue

                # Report usage to Stripe
                await self._report_usage_to_stripe(
                    item_id, requests, usage_timestamp
                )

                logger.debug(
                    "Synced usage for user {}: requests={}, bytes={}",
                    user_id,
                    requests,
                    bytes_total,
                )

                # Record the sync to prevent double-counting
                try:
                    await self._record_sync(
                        pool,
                        user_id,
                        target_date,
                        subscription_id,
                        requests,
                        bytes_total,
                    )
                except Exception as rec_exc:
                    logger.warning(
                        "Failed to record sync for user {}: {}",
                        user_id,
                        rec_exc,
                    )

                synced += 1

            except Exception as exc:
                logger.error(
                    "Failed to sync usage for user {}: {}", user_id, exc
                )
                errors += 1

        logger.info(
            "Stripe metering sync for {}: completed (synced={}, skipped={}, errors={})",
            target_date,
            synced,
            skipped,
            errors,
        )

        return {
            "status": "completed",
            "date": target_date,
            "synced_users": synced,
            "skipped_users": skipped,
            "errors": errors,
        }

    async def check_reconciliation(
        self, date: str | None = None
    ) -> dict[str, Any]:
        """Compare local usage totals with synced records for drift detection.

        Args:
            date: ISO date string (YYYY-MM-DD). Defaults to yesterday.

        Returns:
            Reconciliation report with any discrepancies found.
        """
        if not self._enabled:
            return {"status": "skipped", "reason": "billing_not_enabled"}

        target_date = date or (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).strftime("%Y-%m-%d")

        # Acquire DB pool
        try:
            pool = await self._get_db_pool()
        except Exception as exc:
            logger.error("Reconciliation check: failed to get DB pool: {}", exc)
            return {
                "status": "error",
                "date": target_date,
                "error": f"db_pool_unavailable: {exc}",
                "discrepancies": [],
            }

        # Fetch local usage totals
        try:
            usage_rows = await self._query_usage_for_date(pool, target_date)
        except Exception as exc:
            logger.error(
                "Reconciliation for {}: failed to query usage: {}",
                target_date,
                exc,
            )
            return {
                "status": "error",
                "date": target_date,
                "error": f"usage_query_failed: {exc}",
                "discrepancies": [],
            }

        # Fetch synced totals
        try:
            sync_rows = await self._query_sync_totals(pool, target_date)
        except Exception as exc:
            logger.warning(
                "Reconciliation for {}: sync log query failed (table may not exist): {}",
                target_date,
                exc,
            )
            sync_rows = []

        # Build lookup: user_id -> synced requests
        synced_by_user: dict[int, int] = {}
        for sr in sync_rows:
            uid = sr["user_id"]
            synced_by_user[uid] = synced_by_user.get(uid, 0) + sr.get(
                "requests_synced", 0
            )

        # Compare
        discrepancies: list[dict[str, Any]] = []
        total_local_requests = 0
        total_synced_requests = 0

        for row in usage_rows:
            uid = row["user_id"]
            local_requests = row.get("requests", 0) or 0
            synced_requests = synced_by_user.pop(uid, 0)

            total_local_requests += local_requests
            total_synced_requests += synced_requests

            if local_requests != synced_requests:
                discrepancies.append(
                    {
                        "user_id": uid,
                        "local_requests": local_requests,
                        "synced_requests": synced_requests,
                        "drift": local_requests - synced_requests,
                    }
                )

        # Any users in sync log but not in usage_daily (shouldn't happen normally)
        for uid, extra_synced in synced_by_user.items():
            total_synced_requests += extra_synced
            discrepancies.append(
                {
                    "user_id": uid,
                    "local_requests": 0,
                    "synced_requests": extra_synced,
                    "drift": -extra_synced,
                }
            )

        return {
            "status": "completed",
            "date": target_date,
            "total_local_requests": total_local_requests,
            "total_synced_requests": total_synced_requests,
            "discrepancies": discrepancies,
        }

    @property
    def is_enabled(self) -> bool:
        """Whether Stripe metering is enabled."""
        return self._enabled and bool(self._stripe_key)
