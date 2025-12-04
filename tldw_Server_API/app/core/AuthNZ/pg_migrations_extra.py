"""
PostgreSQL additive migrations (runtime ensure) for AuthNZ-related extras.

This module centralizes small, idempotent DDL helpers that are safe to call
at startup on Postgres backends. They complement the SQLite migrations in
``migrations.py`` and help keep inline runtime SQL out of business logic.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from .database import get_db_pool, DatabasePool


_CREATE_TOOL_CATALOGS = [
    # tool_catalogs
    (
        """
        CREATE TABLE IF NOT EXISTS tool_catalogs (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NULL,
            org_id INTEGER NULL REFERENCES organizations(id) ON DELETE SET NULL,
            team_id INTEGER NULL REFERENCES teams(id) ON DELETE SET NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_tool_catalogs_scope UNIQUE (name, org_id, team_id)
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_tool_catalogs_org_team ON tool_catalogs(org_id, team_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_tool_catalogs_name ON tool_catalogs(name)", ()),
    # tool_catalog_entries
    (
        """
        CREATE TABLE IF NOT EXISTS tool_catalog_entries (
            id SERIAL PRIMARY KEY,
            catalog_id INTEGER NOT NULL REFERENCES tool_catalogs(id) ON DELETE CASCADE,
            tool_name TEXT NOT NULL,
            module_id TEXT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_tool_catalog_entries UNIQUE (catalog_id, tool_name)
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_tool_catalog_entries_catalog ON tool_catalog_entries(catalog_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_tool_catalog_entries_tool ON tool_catalog_entries(tool_name)", ()),
]


_CREATE_PRIVILEGE_SNAPSHOTS = [
    (
        """
        CREATE TABLE IF NOT EXISTS privilege_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            generated_at TIMESTAMPTZ NOT NULL,
            generated_by TEXT NOT NULL,
            org_id TEXT NULL,
            team_id TEXT NULL,
            catalog_version TEXT NOT NULL,
            summary_json TEXT NULL,
            scope_index TEXT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
        """,
        (),
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_priv_snapshots_generated_at ON privilege_snapshots(generated_at)",
        (),
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_priv_snapshots_org ON privilege_snapshots(org_id)",
        (),
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_priv_snapshots_team ON privilege_snapshots(team_id)",
        (),
    ),
]


_CREATE_USAGE_TABLES = [
    # usage_log + usage_daily
    (
        """
        CREATE TABLE IF NOT EXISTS usage_log (
            id SERIAL PRIMARY KEY,
            ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            key_id INTEGER REFERENCES api_keys(id) ON DELETE SET NULL,
            endpoint TEXT,
            status INTEGER,
            latency_ms INTEGER,
            bytes BIGINT,
            bytes_in BIGINT,
            meta JSONB,
            request_id TEXT
        )
        """,
        (),
    ),
    ("ALTER TABLE usage_log ADD COLUMN IF NOT EXISTS request_id TEXT", ()),
    ("ALTER TABLE usage_log ADD COLUMN IF NOT EXISTS bytes_in BIGINT", ()),
    ("CREATE INDEX IF NOT EXISTS idx_usage_log_ts ON usage_log(ts)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_usage_log_user ON usage_log(user_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_usage_log_status ON usage_log(status)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_usage_log_endpoint ON usage_log(endpoint)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_usage_log_request_id ON usage_log(request_id)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS usage_daily (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            day DATE NOT NULL,
            requests INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            bytes_total BIGINT DEFAULT 0,
            bytes_in_total BIGINT DEFAULT 0,
            latency_avg_ms DOUBLE PRECISION,
            PRIMARY KEY (user_id, day)
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_usage_daily_day_user ON usage_daily(day, user_id)", ()),
    ("ALTER TABLE usage_daily ADD COLUMN IF NOT EXISTS bytes_in_total BIGINT", ()),
    # llm_usage_log + llm_usage_daily
    (
        """
        CREATE TABLE IF NOT EXISTS llm_usage_log (
            id SERIAL PRIMARY KEY,
            ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            key_id INTEGER REFERENCES api_keys(id) ON DELETE SET NULL,
            endpoint TEXT,
            operation TEXT,
            provider TEXT,
            model TEXT,
            status INTEGER,
            latency_ms INTEGER,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            prompt_cost_usd DOUBLE PRECISION,
            completion_cost_usd DOUBLE PRECISION,
            total_cost_usd DOUBLE PRECISION,
            currency TEXT DEFAULT 'USD',
            estimated BOOLEAN DEFAULT FALSE,
            request_id TEXT
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_ts ON llm_usage_log(ts)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_user ON llm_usage_log(user_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_provider_model ON llm_usage_log(provider, model)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_op_ts ON llm_usage_log(operation, ts)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_operation ON llm_usage_log(operation)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS llm_usage_daily (
            day DATE NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            operation TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            requests INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            input_tokens BIGINT DEFAULT 0,
            output_tokens BIGINT DEFAULT 0,
            total_tokens BIGINT DEFAULT 0,
            total_cost_usd DOUBLE PRECISION DEFAULT 0.0,
            latency_avg_ms DOUBLE PRECISION,
            PRIMARY KEY (day, user_id, operation, provider, model)
        )
        """,
        (),
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_llm_usage_daily_day_user_op_prov_model ON llm_usage_daily(day, user_id, operation, provider, model)",
        (),
    ),
]


_CREATE_VK_COUNTERS = [
    (
        """
        CREATE TABLE IF NOT EXISTS vk_jwt_counters (
            jti TEXT NOT NULL,
            counter_type TEXT NOT NULL,
            count BIGINT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (jti, counter_type)
        )
        """,
        (),
    ),
    (
        """
        CREATE TABLE IF NOT EXISTS vk_api_key_counters (
            api_key_id INTEGER NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
            counter_type TEXT NOT NULL,
            count BIGINT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (api_key_id, counter_type)
        )
        """,
        (),
    ),
]


async def ensure_tool_catalogs_tables_pg(pool: Optional[DatabasePool] = None) -> bool:
    """Ensure tool catalogs tables exist on PostgreSQL backends.

    Returns True if ensured (or not needed), False if skipped due to non-PG backend.
    """
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False  # not postgres
        for sql, params in _CREATE_TOOL_CATALOGS:
            try:
                await db_pool.execute(sql, *params)
            except Exception as exc:
                # Continue attempting subsequent statements; log and surface at the end
                logger.debug(f"PG ensure tool catalogs DDL failed: {exc}")
        logger.info("Ensured PostgreSQL tool catalogs tables (idempotent)")
        return True
    except Exception as exc:
        logger.warning(f"Failed to ensure PostgreSQL tool catalogs tables: {exc}")
        return False


async def ensure_privilege_snapshots_table_pg(pool: Optional[DatabasePool] = None) -> bool:
    """Ensure privilege_snapshots table exists for PostgreSQL backends."""
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False
        for sql, params in _CREATE_PRIVILEGE_SNAPSHOTS:
            try:
                await db_pool.execute(sql, *params)
            except Exception as exc:
                logger.debug(f"PG ensure privilege_snapshots DDL failed: {exc}")
        logger.info("Ensured PostgreSQL privilege_snapshots table (idempotent)")
        return True
    except Exception as exc:
        logger.warning(f"Failed to ensure PostgreSQL privilege_snapshots table: {exc}")
        return False


async def ensure_usage_tables_pg(pool: Optional[DatabasePool] = None) -> bool:
    """Ensure usage and LLM usage tables exist for PostgreSQL backends.

    Mirrors the SQLite migrations (usage_log/usage_daily, llm_usage_log/llm_usage_daily)
    but uses Postgres types and indexes. Intended as bootstrap guardrails when running
    against Postgres without having executed dedicated migrations.
    """
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False
        for sql, params in _CREATE_USAGE_TABLES:
            try:
                await db_pool.execute(sql, *params)
            except Exception as exc:
                logger.debug(f"PG ensure usage tables DDL failed: {exc}")
        logger.info("Ensured PostgreSQL usage tables (usage_log, usage_daily, llm_usage_log, llm_usage_daily)")
        return True
    except Exception as exc:
        logger.warning(f"Failed to ensure PostgreSQL usage tables: {exc}")
        return False


async def ensure_virtual_key_counters_pg(pool: Optional[DatabasePool] = None) -> bool:
    """Ensure virtual-key counter tables exist for PostgreSQL backends.

    These tables back cross-instance quota counters for JWTs and API keys.
    Runtime guardrails also defensively create them, but this helper centralizes
    the Postgres DDL for bootstrap flows.
    """
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False
        for sql, params in _CREATE_VK_COUNTERS:
            try:
                await db_pool.execute(sql, *params)
            except Exception as exc:
                logger.debug(f"PG ensure virtual-key counters DDL failed: {exc}")
        logger.info("Ensured PostgreSQL virtual-key counters tables (vk_jwt_counters, vk_api_key_counters)")
        return True
    except Exception as exc:
        logger.warning(f"Failed to ensure PostgreSQL virtual-key counters tables: {exc}")
        return False
