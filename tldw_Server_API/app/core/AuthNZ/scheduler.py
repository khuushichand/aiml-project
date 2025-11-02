# scheduler.py
# Description: Scheduled jobs for AuthNZ maintenance tasks
#
# Imports
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
#
# 3rd-party imports
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
#
# Local imports
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.AuthNZ.rate_limiter import get_rate_limiter
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.alerting import get_security_alert_dispatcher
from tldw_Server_API.app.core.Metrics import set_gauge

#######################################################################################################################
#
# Scheduled Jobs
#

class AuthNZScheduler:
    """Manages scheduled maintenance tasks for the AuthNZ module"""

    def __init__(self):
        """Initialize the scheduler"""
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.settings = get_settings()
        self._started = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self):
        """Start the scheduler and register all jobs"""
        loop = asyncio.get_running_loop()

        if self._started and self._loop is loop and self.scheduler and self.scheduler.running:
            logger.warning("AuthNZ scheduler already started on current event loop")
            return

        # If we were previously started on a different loop or have a stale scheduler, tear it down
        if self.scheduler and self._loop is not loop:
            logger.info("Restarting AuthNZ scheduler on new event loop")
            try:
                self.scheduler.shutdown(wait=True)
            except Exception as e:
                logger.debug(f"Ignoring scheduler shutdown error during restart: {e}")
            finally:
                self.scheduler = None
                self._started = False
                self._loop = None

        # Always create a fresh scheduler when starting to avoid stale loop bindings
        if not self.scheduler:
            self.scheduler = AsyncIOScheduler(event_loop=loop)
            self._loop = loop

        # Register cleanup jobs
        self._register_session_cleanup()
        self._register_api_key_cleanup()
        self._register_rate_limit_cleanup()
        self._register_audit_log_cleanup()
        self._register_expired_registration_cleanup()

        # Register monitoring jobs
        self._register_auth_failure_monitor()
        self._register_api_usage_monitor()
        self._register_rate_limit_monitor()
        # Evaluations: idempotency keys cleanup
        self._register_evaluations_idempotency_cleanup()

        # Usage log pruning jobs
        self._register_usage_log_cleanup()
        self._register_llm_usage_log_cleanup()
        # Daily aggregates pruning jobs
        self._register_usage_daily_cleanup()
        self._register_llm_usage_daily_cleanup()
        # Privilege snapshot retention housekeeping
        self._register_privilege_snapshot_retention()

        # Start the scheduler
        self.scheduler.start()
        self._started = True
        self._loop = loop
        logger.info("AuthNZ scheduler started with all jobs registered")

    async def stop(self):
        """Stop the scheduler"""
        if not self.scheduler:
            self._started = False
            self._loop = None
            return

        if self.scheduler.running:
            try:
                self.scheduler.shutdown(wait=True)
            except Exception as e:
                logger.debug(f"Ignoring scheduler shutdown error: {e}")

        self._started = False
        self._loop = None
        self.scheduler = None
        logger.info("AuthNZ scheduler stopped")

    def _register_session_cleanup(self):
        """Register job to clean up expired sessions"""
        self.scheduler.add_job(
            self._cleanup_expired_sessions,
            trigger=IntervalTrigger(
                hours=self.settings.SESSION_CLEANUP_INTERVAL_HOURS
            ),
            id='session_cleanup',
            name='Clean up expired sessions',
            replace_existing=True,
            max_instances=1
        )
        logger.debug(f"Registered session cleanup job (every {self.settings.SESSION_CLEANUP_INTERVAL_HOURS} hours)")

    def _register_api_key_cleanup(self):
        """Register job to clean up expired API keys"""
        self.scheduler.add_job(
            self._cleanup_expired_api_keys,
            trigger=CronTrigger(
                hour=2,  # Run at 2 AM daily
                minute=0
            ),
            id='api_key_cleanup',
            name='Clean up expired API keys',
            replace_existing=True,
            max_instances=1
        )
        logger.debug("Registered API key cleanup job (daily at 2 AM)")

    def _register_rate_limit_cleanup(self):
        """Register job to clean up old rate limit entries"""
        self.scheduler.add_job(
            self._cleanup_old_rate_limits,
            trigger=IntervalTrigger(hours=6),  # Every 6 hours
            id='rate_limit_cleanup',
            name='Clean up old rate limit entries',
            replace_existing=True,
            max_instances=1
        )
        logger.debug("Registered rate limit cleanup job (every 6 hours)")

    def _register_audit_log_cleanup(self):
        """Register job to prune old audit logs"""
        self.scheduler.add_job(
            self._prune_audit_logs,
            trigger=CronTrigger(
                day=1,  # First day of month
                hour=3,
                minute=0
            ),
            id='audit_log_cleanup',
            name='Prune old audit logs',
            replace_existing=True,
            max_instances=1
        )
        logger.debug("Registered audit log cleanup job (monthly)")

    def _register_usage_log_cleanup(self):
        """Register job to prune old usage_log rows"""
        self.scheduler.add_job(
            self._prune_usage_logs,
            trigger=CronTrigger(hour=3, minute=15),  # Daily at 03:15
            id='usage_log_cleanup',
            name='Prune old usage logs',
            replace_existing=True,
            max_instances=1
        )
        logger.debug("Registered usage log cleanup job (daily at 03:15)")

    def _register_llm_usage_log_cleanup(self):
        """Register job to prune old llm_usage_log rows"""
        self.scheduler.add_job(
            self._prune_llm_usage_logs,
            trigger=CronTrigger(hour=3, minute=30),  # Daily at 03:30
            id='llm_usage_log_cleanup',
            name='Prune old LLM usage logs',
            replace_existing=True,
            max_instances=1
        )
        logger.debug("Registered LLM usage log cleanup job (daily at 03:30)")

    def _register_usage_daily_cleanup(self):
        """Register job to prune old usage_daily rows"""
        self.scheduler.add_job(
            self._prune_usage_daily,
            trigger=CronTrigger(hour=3, minute=40),  # Daily at 03:40
            id='usage_daily_cleanup',
            name='Prune old usage_daily rows',
            replace_existing=True,
            max_instances=1
        )
        logger.debug("Registered usage_daily cleanup job (daily at 03:40)")

    def _register_llm_usage_daily_cleanup(self):
        """Register job to prune old llm_usage_daily rows"""
        self.scheduler.add_job(
            self._prune_llm_usage_daily,
            trigger=CronTrigger(hour=3, minute=45),  # Daily at 03:45
            id='llm_usage_daily_cleanup',
            name='Prune old llm_usage_daily rows',
            replace_existing=True,
            max_instances=1
        )
        logger.debug("Registered llm_usage_daily cleanup job (daily at 03:45)")

    def _register_privilege_snapshot_retention(self):
        """Register job to enforce privilege snapshot retention policy."""
        self.scheduler.add_job(
            self._prune_privilege_snapshots,
            trigger=CronTrigger(hour=2, minute=20),  # Daily at 02:20
            id='privilege_snapshot_retention',
            name='Prune privilege snapshots per retention policy',
            replace_existing=True,
            max_instances=1,
        )
        logger.debug("Registered privilege snapshot retention job (daily at 02:20)")

    def _register_expired_registration_cleanup(self):
        """Register job to clean up expired registration codes"""
        self.scheduler.add_job(
            self._cleanup_expired_registration_codes,
            trigger=CronTrigger(
                hour=1,  # Run at 1 AM daily
                minute=30
            ),
            id='registration_cleanup',
            name='Clean up expired registration codes',
            replace_existing=True,
            max_instances=1
        )
        logger.debug("Registered registration code cleanup job (daily at 1:30 AM)")

    def _register_auth_failure_monitor(self):
        """Register job to monitor authentication failures"""
        self.scheduler.add_job(
            self._monitor_auth_failures,
            trigger=IntervalTrigger(minutes=5),  # Every 5 minutes
            id='auth_failure_monitor',
            name='Monitor authentication failures',
            replace_existing=True,
            max_instances=1
        )
        logger.debug("Registered auth failure monitor (every 5 minutes)")

    def _register_api_usage_monitor(self):
        """Register job to monitor API key usage patterns"""
        self.scheduler.add_job(
            self._monitor_api_usage,
            trigger=IntervalTrigger(hours=1),  # Every hour
            id='api_usage_monitor',
            name='Monitor API key usage',
            replace_existing=True,
            max_instances=1
        )
        logger.debug("Registered API usage monitor (hourly)")

    def _register_rate_limit_monitor(self):
        """Register job to monitor rate limit violations"""
        self.scheduler.add_job(
            self._monitor_rate_limits,
            trigger=IntervalTrigger(minutes=15),  # Every 15 minutes
            id='rate_limit_monitor',
            name='Monitor rate limit violations',
            replace_existing=True,
            max_instances=1
        )
        logger.debug("Registered rate limit monitor (every 15 minutes)")

    def _register_evaluations_idempotency_cleanup(self):
        """Register job to cleanup stale idempotency keys in Evaluations DBs."""
        # Daily at 4:00 AM
        self.scheduler.add_job(
            self._cleanup_evaluations_idempotency,
            trigger=CronTrigger(hour=4, minute=0),
            id='evaluations_idempotency_cleanup',
            name='Cleanup Evaluations idempotency keys',
            replace_existing=True,
            max_instances=1,
        )
        logger.debug("Registered evaluations idempotency cleanup (daily at 04:00)")

    async def _cleanup_evaluations_idempotency(self):
        """Iterate user evaluation DBs and purge old idempotency keys."""
        try:
            from pathlib import Path
            from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths as _DP
            from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase as _EDB
            # Discover user database base dir (reuse DatabasePaths fallback by building a known path)
            base = Path(_DP.get_user_base_directory(_DP.get_single_user_id())).parent
            deleted_total = 0
            # Include single-user fixed id explicitly
            candidate_ids = set()
            try:
                candidate_ids.add(int(_DP.get_single_user_id()))
            except Exception:
                pass
            try:
                if base.exists():
                    for entry in base.iterdir():
                        if entry.is_dir():
                            try:
                                candidate_ids.add(int(entry.name))
                            except Exception:
                                continue
            except Exception:
                pass
            for uid in sorted(candidate_ids):
                try:
                    db_path = _DP.get_evaluations_db_path(uid)
                    if not db_path.exists():
                        continue
                    db = _EDB(str(db_path))
                    deleted = db.cleanup_idempotency_keys(ttl_hours=72)
                    deleted_total += int(deleted)
                except Exception:
                    continue
            if deleted_total:
                logger.info(f"Evaluations idempotency cleanup removed {deleted_total} rows across user DBs")
        except Exception as e:
            logger.error(f"Failed evaluations idempotency cleanup: {e}")

    # Cleanup Jobs

    async def _cleanup_expired_sessions(self):
        """Clean up expired sessions from the database"""
        try:
            session_manager = await get_session_manager()
            count = await session_manager.cleanup_expired_sessions()
            if count > 0:
                logger.info(f"Cleaned up {count} expired sessions")
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")

    async def _cleanup_expired_api_keys(self):
        """Mark expired API keys as expired"""
        try:
            api_key_manager = await get_api_key_manager()
            await api_key_manager.cleanup_expired_keys()
            logger.info("Completed API key expiration check")
        except Exception as e:
            logger.error(f"Failed to cleanup expired API keys: {e}")

    async def _cleanup_old_rate_limits(self):
        """Remove old rate limit entries"""
        try:
            rate_limiter = await get_rate_limiter()
            await rate_limiter.cleanup_old_entries(hours=24)  # Remove entries older than 24 hours
            logger.info("Cleaned up old rate limit entries")
        except Exception as e:
            logger.error(f"Failed to cleanup rate limits: {e}")

    async def _prune_audit_logs(self):
        """Prune audit logs older than retention period"""
        try:
            db_pool = await get_db_pool()
            retention_days = self.settings.AUDIT_LOG_RETENTION_DAYS
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            async with db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    # PostgreSQL
                    result = await conn.execute(
                        "DELETE FROM audit_logs WHERE created_at < $1",
                        cutoff_date
                    )
                    # Extract count from result
                    count = int(result.split()[-1]) if isinstance(result, str) else 0
                else:
                    # SQLite
                    cursor = await conn.execute(
                        "DELETE FROM audit_logs WHERE created_at < ?",
                        (cutoff_date.isoformat(),)
                    )
                    count = cursor.rowcount
                    await conn.commit()

            if count > 0:
                logger.info(f"Pruned {count} audit log entries older than {retention_days} days")
        except Exception as e:
            logger.error(f"Failed to prune audit logs: {e}")

    async def _prune_usage_logs(self):
        """Prune usage_log rows older than retention period."""
        try:
            db_pool = await get_db_pool()
            cutoff = datetime.utcnow() - timedelta(days=self.settings.USAGE_LOG_RETENTION_DAYS)
            async with db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    result = await conn.execute(
                        "DELETE FROM usage_log WHERE ts < $1",
                        cutoff
                    )
                    count = int(result.split()[-1]) if isinstance(result, str) else 0
                else:
                    cursor = await conn.execute(
                        "DELETE FROM usage_log WHERE ts < ?",
                        (cutoff.isoformat(),)
                    )
                    count = cursor.rowcount
                    await conn.commit()
            if count:
                logger.info(f"Pruned {count} usage_log rows older than {self.settings.USAGE_LOG_RETENTION_DAYS} days")
        except Exception as e:
            logger.error(f"Failed to prune usage_log: {e}")

    async def _prune_llm_usage_logs(self):
        """Prune llm_usage_log rows older than retention period."""
        try:
            db_pool = await get_db_pool()
            cutoff = datetime.utcnow() - timedelta(days=self.settings.LLM_USAGE_LOG_RETENTION_DAYS)
            async with db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    result = await conn.execute(
                        "DELETE FROM llm_usage_log WHERE ts < $1",
                        cutoff
                    )
                    count = int(result.split()[-1]) if isinstance(result, str) else 0
                else:
                    cursor = await conn.execute(
                        "DELETE FROM llm_usage_log WHERE ts < ?",
                        (cutoff.isoformat(),)
                    )
                    count = cursor.rowcount
                    await conn.commit()
            if count:
                logger.info(f"Pruned {count} llm_usage_log rows older than {self.settings.LLM_USAGE_LOG_RETENTION_DAYS} days")
        except Exception as e:
            logger.error(f"Failed to prune llm_usage_log: {e}")

    async def _prune_usage_daily(self):
        """Prune usage_daily rows older than retention period"""
        try:
            db_pool = await get_db_pool()
            from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _gs
            retention_days = _gs().USAGE_DAILY_RETENTION_DAYS
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            async with db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    result = await conn.execute("DELETE FROM usage_daily WHERE day < $1::date", cutoff_date.date())
                    count = int(result.split()[-1]) if isinstance(result, str) else 0
                else:
                    cursor = await conn.execute("DELETE FROM usage_daily WHERE day < ?", (cutoff_date.date().isoformat(),))
                    count = cursor.rowcount
                    await conn.commit()
            if count:
                logger.info(f"Pruned {count} usage_daily rows older than {retention_days} days")
        except Exception as e:
            logger.error(f"Failed to prune usage_daily: {e}")

    async def _prune_llm_usage_daily(self):
        """Prune llm_usage_daily rows older than retention period"""
        try:
            db_pool = await get_db_pool()
            from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _gs
            retention_days = _gs().LLM_USAGE_DAILY_RETENTION_DAYS
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            async with db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    result = await conn.execute("DELETE FROM llm_usage_daily WHERE day < $1::date", cutoff_date.date())
                    count = int(result.split()[-1]) if isinstance(result, str) else 0
                else:
                    cursor = await conn.execute("DELETE FROM llm_usage_daily WHERE day < ?", (cutoff_date.date().isoformat(),))
                    count = cursor.rowcount
                    await conn.commit()
            if count:
                logger.info(f"Pruned {count} llm_usage_daily rows older than {retention_days} days")
        except Exception as e:
            logger.error(f"Failed to prune llm_usage_daily: {e}")

    async def _prune_privilege_snapshots(self):
        """Enforce privilege snapshot retention (daily + weekly) and emit metrics."""
        try:
            db_pool = await get_db_pool()
            retention_days = max(int(getattr(self.settings, "PRIVILEGE_SNAPSHOT_RETENTION_DAYS", 90)), 0)
            weekly_retention_days = max(
                int(getattr(self.settings, "PRIVILEGE_SNAPSHOT_WEEKLY_RETENTION_DAYS", 365)),
                retention_days,
            )
            now = datetime.now(timezone.utc)
            weekly_cutoff = now - timedelta(days=weekly_retention_days) if weekly_retention_days > 0 else None
            primary_cutoff = now - timedelta(days=retention_days) if retention_days > 0 else None

            def _normalize_rowcount(value: Optional[int]) -> int:
                if value is None:
                    return 0
                try:
                    count = int(value)
                except (TypeError, ValueError):
                    return 0
                return count if count > 0 else 0

            purged_legacy = 0
            purged_duplicates = 0

            async with db_pool.transaction() as conn:
                is_postgres = hasattr(conn, "fetch")

                # Purge anything older than the weekly retention window
                if weekly_cutoff is not None:
                    if is_postgres:
                        result = await conn.execute(
                            "DELETE FROM privilege_snapshots WHERE generated_at::timestamptz < $1",
                            weekly_cutoff,
                        )
                        if isinstance(result, str):
                            try:
                                purged_legacy = int(result.split()[-1])
                            except (ValueError, IndexError):
                                purged_legacy = 0
                    else:
                        # SQLite's datetime() doesn't reliably parse ISO8601 with timezone offsets.
                        # Compare ISO strings directly (stored as ISO8601) for robust behavior.
                        cursor = await conn.execute(
                            "DELETE FROM privilege_snapshots WHERE generated_at < ?",
                            (weekly_cutoff.isoformat(),),
                        )
                        purged_legacy = _normalize_rowcount(getattr(cursor, "rowcount", None))

                # Downsample older snapshots (retain first per ISO week per org/team)
                if (
                    primary_cutoff is not None
                    and weekly_cutoff is not None
                    and weekly_retention_days > retention_days
                ):
                    if is_postgres:
                        dedupe_sql = """
                        WITH ranked AS (
                            SELECT
                                snapshot_id,
                                COALESCE(org_id, '__global__') AS org_bucket,
                                COALESCE(team_id, '__none__') AS team_bucket,
                                to_char(generated_at::timestamptz, 'IYYY-IW') AS iso_week,
                                ROW_NUMBER() OVER (
                                    PARTITION BY
                                        COALESCE(org_id, '__global__'),
                                        COALESCE(team_id, '__none__'),
                                        to_char(generated_at::timestamptz, 'IYYY-IW')
                                    ORDER BY generated_at::timestamptz ASC
                                ) AS rn
                            FROM privilege_snapshots
                            WHERE generated_at::timestamptz < $1
                              AND generated_at::timestamptz >= $2
                        )
                        DELETE FROM privilege_snapshots
                        WHERE snapshot_id IN (
                            SELECT snapshot_id FROM ranked WHERE rn > 1
                        )
                        """
                        result = await conn.execute(dedupe_sql, primary_cutoff, weekly_cutoff)
                        if isinstance(result, str):
                            try:
                                purged_duplicates = int(result.split()[-1])
                            except (ValueError, IndexError):
                                purged_duplicates = 0
                    else:
                        # Use string-based comparisons and week bucketing compatible with ISO8601 strings.
                        dedupe_sql = """
                        WITH ranked AS (
                            SELECT
                                snapshot_id,
                                COALESCE(org_id, '__global__') AS org_bucket,
                                COALESCE(team_id, '__none__') AS team_bucket,
                                substr(generated_at, 1, 4) || '-' || printf('%02d', cast((strftime('%j', replace(replace(generated_at, 'Z',''), '+00:00','')) - 1) / 7 + 1 as integer)) AS iso_week,
                                ROW_NUMBER() OVER (
                                    PARTITION BY
                                        COALESCE(org_id, '__global__'),
                                        COALESCE(team_id, '__none__'),
                                        substr(generated_at, 1, 4) || '-' || printf('%02d', cast((strftime('%j', replace(replace(generated_at, 'Z',''), '+00:00','')) - 1) / 7 + 1 as integer))
                                    ORDER BY generated_at ASC
                                ) AS rn
                            FROM privilege_snapshots
                            WHERE generated_at < ?
                              AND generated_at >= ?
                        )
                        DELETE FROM privilege_snapshots
                        WHERE snapshot_id IN (
                            SELECT snapshot_id FROM ranked WHERE rn > 1
                        )
                        """
                        cursor = await conn.execute(
                            dedupe_sql,
                            (primary_cutoff.isoformat(), weekly_cutoff.isoformat()),
                        )
                        purged_duplicates = _normalize_rowcount(getattr(cursor, "rowcount", None))

            row_count = await db_pool.fetchval("SELECT COUNT(*) FROM privilege_snapshots") or 0
            size_bytes = None
            try:
                size_bytes = await db_pool.fetchval(
                    "SELECT pg_total_relation_size('privilege_snapshots')"
                )
            except Exception:
                size_bytes = None

            if size_bytes is not None:
                set_gauge("privilege_snapshots_table_bytes", float(size_bytes))
            set_gauge("privilege_snapshots_table_rows", float(row_count))

            logger.info(
                "Privilege snapshot retention pruned %s legacy rows (> %s days) and %s weekly duplicates (> %s days); remaining=%s rows",
                purged_legacy,
                weekly_retention_days,
                purged_duplicates,
                retention_days,
                row_count,
            )
        except Exception as e:
            logger.error(f"Failed to prune privilege snapshots: {e}")

    async def _cleanup_expired_registration_codes(self):
        """Clean up expired registration codes"""
        try:
            db_pool = await get_db_pool()

            async with db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    # PostgreSQL
                    result = await conn.execute(
                        """
                        UPDATE registration_codes
                        SET is_active = FALSE
                        WHERE is_active = TRUE
                        AND expires_at < $1
                        """,
                        datetime.utcnow()
                    )
                    count = int(result.split()[-1]) if isinstance(result, str) else 0
                else:
                    # SQLite
                    cursor = await conn.execute(
                        """
                        UPDATE registration_codes
                        SET is_active = 0
                        WHERE is_active = 1
                        AND expires_at < ?
                        """,
                        (datetime.utcnow().isoformat(),)
                    )
                    count = cursor.rowcount
                    await conn.commit()

            if count > 0:
                logger.info(f"Deactivated {count} expired registration codes")
        except Exception as e:
            logger.error(f"Failed to cleanup registration codes: {e}")

    # Monitoring Jobs

    async def _monitor_auth_failures(self):
        """Monitor and alert on authentication failures"""
        try:
            db_pool = await get_db_pool()
            threshold = 10  # Alert if more than 10 failures in 5 minutes
            time_window = datetime.utcnow() - timedelta(minutes=5)
            is_postgres = getattr(db_pool, "pool", None) is not None
            cutoff = time_window if is_postgres else time_window.isoformat()

            if is_postgres:
                result = await db_pool.fetchone(
                    """
                    SELECT COUNT(*) as failure_count,
                           COUNT(DISTINCT ip_address) as unique_ips
                    FROM audit_logs
                    WHERE action = ANY($1)
                    AND created_at > $2
                    """,
                    ['login_failed', 'invalid_api_key', 'invalid_token'],
                    cutoff,
                )
            else:
                result = await db_pool.fetchone(
                    """
                    SELECT COUNT(*) as failure_count,
                           COUNT(DISTINCT ip_address) as unique_ips
                    FROM audit_logs
                    WHERE action IN (?, ?, ?)
                    AND created_at > ?
                    """,
                    ('login_failed', 'invalid_api_key', 'invalid_token', cutoff),
                )

            if result:
                failure_count = result['failure_count'] or 0
                unique_ips = result['unique_ips'] or 0

                if failure_count > threshold:
                    logger.warning(
                        f"⚠️ High authentication failure rate detected: "
                        f"{failure_count} failures from {unique_ips} unique IPs in last 5 minutes"
                    )

                    # Here you would trigger actual alerts (email, Slack, etc.)
                    await self._send_security_alert(
                        "High Authentication Failure Rate",
                        f"{failure_count} failures from {unique_ips} IPs",
                        severity="high",
                        metadata={
                            "failure_count": failure_count,
                            "unique_ips": unique_ips,
                            "window_minutes": 5,
                        },
                    )
        except Exception as e:
            logger.error(f"Failed to monitor auth failures: {e}")

    async def _monitor_api_usage(self):
        """Monitor API key usage patterns"""
        try:
            db_pool = await get_db_pool()

            # Get API usage statistics for the last hour
            time_window = datetime.utcnow() - timedelta(hours=1)
            is_postgres = getattr(db_pool, "pool", None) is not None
            cutoff = time_window if is_postgres else time_window.isoformat()

            results = await db_pool.fetchall(
                """
                SELECT
                    k.id,
                    k.name,
                    k.user_id,
                    COUNT(l.id) as usage_count,
                    k.rate_limit
                FROM api_keys k
                LEFT JOIN api_key_audit_log l ON k.id = l.api_key_id
                WHERE k.status = ?
                AND l.created_at > ?
                GROUP BY k.id, k.name, k.user_id, k.rate_limit
                HAVING COUNT(l.id) > 0
                ORDER BY usage_count DESC
                LIMIT 10
                """,
                ('active', cutoff),
            )

            for row in results:
                usage = row['usage_count']
                rate_limit = row['rate_limit'] or 60  # Default rate limit

                # Alert if usage is approaching rate limit
                if usage > rate_limit * 0.8:  # 80% of rate limit
                    logger.warning(
                        f"API key '{row['name']}' (ID: {row['id']}) "
                        f"approaching rate limit: {usage}/{rate_limit} requests/hour"
                    )

            # Log summary
            if results:
                total_usage = sum(r['usage_count'] for r in results)
                logger.info(f"API usage monitoring: {total_usage} total requests in last hour")

        except Exception as e:
            logger.error(f"Failed to monitor API usage: {e}")

    async def _monitor_rate_limits(self):
        """Monitor rate limit violations"""
        try:
            db_pool = await get_db_pool()
            time_window = datetime.utcnow() - timedelta(minutes=15)
            is_postgres = getattr(db_pool, "pool", None) is not None
            cutoff = time_window if is_postgres else time_window.isoformat()

            # Find IPs/users hitting rate limits
            rate_threshold = self.settings.RATE_LIMIT_PER_MINUTE * 15  # 15 minute threshold

            results = await db_pool.fetchall(
                """
                SELECT
                    identifier,
                    endpoint,
                    SUM(request_count) as total_requests,
                    COUNT(*) as window_count
                FROM rate_limits
                WHERE window_start > ?
                GROUP BY identifier, endpoint
                HAVING SUM(request_count) > ?
                ORDER BY total_requests DESC
                LIMIT 20
                """,
                (cutoff, rate_threshold),
            )

            if results:
                logger.warning(f"Rate limit violations detected for {len(results)} identifiers")

                for row in results:
                    logger.warning(
                        f"Rate limit violation: {row['identifier']} on {row['endpoint']} "
                        f"({row['total_requests']} requests in 15 minutes)"
                    )

                # Send alert if there are many violations
                if len(results) > 10:
                    await self._send_security_alert(
                        "Multiple Rate Limit Violations",
                        f"{len(results)} identifiers exceeding rate limits",
                        severity="high",
                        metadata={
                            "identifier_count": len(results),
                            "threshold": rate_threshold,
                            "window_minutes": 15,
                        },
                    )

        except Exception as e:
            logger.error(f"Failed to monitor rate limits: {e}")

    async def _send_security_alert(
        self,
        subject: str,
        message: str,
        *,
        severity: str = "high",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Dispatch a security alert using the configured dispatcher.

        Returns:
            True if the dispatcher attempted to send the alert, False otherwise.
        """
        dispatcher = get_security_alert_dispatcher()
        payload_metadata: Dict[str, Any] = {"source": "authnz_scheduler"}
        if metadata:
            payload_metadata.update(metadata)

        try:
            return await dispatcher.dispatch(
                subject=subject,
                message=message,
                severity=severity,
                metadata=payload_metadata,
            )
        except Exception as exc:
            logger.error(f"Security alert dispatch failed: {exc}")
            logger.critical(f"🚨 SECURITY ALERT [{severity.upper()}]: {subject} - {message}")
            return False


#######################################################################################################################
#
# Module Functions
#

# Global scheduler instance
_scheduler: Optional[AuthNZScheduler] = None

async def get_authnz_scheduler() -> AuthNZScheduler:
    """Get the AuthNZ scheduler singleton"""
    global _scheduler
    if not _scheduler:
        _scheduler = AuthNZScheduler()
    return _scheduler

async def start_authnz_scheduler():
    """Start the AuthNZ scheduler"""
    scheduler = await get_authnz_scheduler()
    await scheduler.start()
    logger.info("AuthNZ scheduled jobs started")

async def stop_authnz_scheduler():
    """Stop the AuthNZ scheduler"""
    global _scheduler
    if not _scheduler:
        return
    await _scheduler.stop()
    logger.info("AuthNZ scheduled jobs stopped")

async def reset_authnz_scheduler():
    """Reset scheduler singleton (primarily for tests)."""
    global _scheduler
    if _scheduler:
        try:
            await _scheduler.stop()
        except Exception as e:
            logger.debug(f"Ignoring scheduler stop error during reset: {e}")
        finally:
            _scheduler = None

#
# End of scheduler.py
#######################################################################################################################
