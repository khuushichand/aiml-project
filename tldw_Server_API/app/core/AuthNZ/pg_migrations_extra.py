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


_CREATE_AUTHNZ_CORE_TABLES = [
    # audit_logs
    (
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            action VARCHAR(255) NOT NULL,
            resource_type VARCHAR(128),
            resource_id INTEGER,
            ip_address VARCHAR(45),
            user_agent TEXT,
            status VARCHAR(32),
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)", ()),
    # sessions (core columns + additive columns/indexes)
    (
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token_hash VARCHAR(64) NOT NULL,
            refresh_token_hash VARCHAR(64),
            encrypted_token TEXT,
            encrypted_refresh TEXT,
            expires_at TIMESTAMP NOT NULL,
            refresh_expires_at TIMESTAMP,
            ip_address VARCHAR(45),
            user_agent TEXT,
            device_id TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            is_revoked BOOLEAN DEFAULT FALSE,
            revoked_at TIMESTAMP,
            revoked_by INTEGER,
            revoke_reason TEXT,
            access_jti VARCHAR(128),
            refresh_jti VARCHAR(128),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,
        (),
    ),
    ("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS refresh_expires_at TIMESTAMP", ()),
    ("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS is_revoked BOOLEAN DEFAULT FALSE", ()),
    ("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS access_jti VARCHAR(128)", ()),
    ("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS refresh_jti VARCHAR(128)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_sessions_access_jti ON sessions(access_jti)", ()),
    # registration_codes
    (
        """
        CREATE TABLE IF NOT EXISTS registration_codes (
            id SERIAL PRIMARY KEY,
            code VARCHAR(128) UNIQUE NOT NULL,
            role_to_grant VARCHAR(50) DEFAULT 'user',
            max_uses INTEGER DEFAULT 1,
            uses INTEGER DEFAULT 0,
            expires_at TIMESTAMP,
            created_by INTEGER,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        (),
    ),
    # RBAC core tables
    (
        """
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name VARCHAR(64) UNIQUE NOT NULL,
            description TEXT,
            is_system BOOLEAN DEFAULT FALSE
        )
        """,
        (),
    ),
    (
        """
        CREATE TABLE IF NOT EXISTS permissions (
            id SERIAL PRIMARY KEY,
            name VARCHAR(128) UNIQUE NOT NULL,
            description TEXT,
            category VARCHAR(64)
        )
        """,
        (),
    ),
    (
        """
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
            PRIMARY KEY (role_id, permission_id)
        )
        """,
        (),
    ),
    (
        """
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            granted_by INTEGER,
            expires_at TIMESTAMP,
            PRIMARY KEY (user_id, role_id)
        )
        """,
        (),
    ),
    (
        """
        CREATE TABLE IF NOT EXISTS user_permissions (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
            granted BOOLEAN NOT NULL DEFAULT TRUE,
            expires_at TIMESTAMP,
            PRIMARY KEY (user_id, permission_id)
        )
        """,
        (),
    ),
    # RBAC rate limits
    (
        """
        CREATE TABLE IF NOT EXISTS rbac_role_rate_limits (
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            resource VARCHAR(128) NOT NULL,
            limit_per_min INTEGER,
            burst INTEGER,
            PRIMARY KEY (role_id, resource)
        )
        """,
        (),
    ),
    (
        """
        CREATE TABLE IF NOT EXISTS rbac_user_rate_limits (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            resource VARCHAR(128) NOT NULL,
            limit_per_min INTEGER,
            burst INTEGER,
            PRIMARY KEY (user_id, resource)
        )
        """,
        (),
    ),
    # Organizations and teams hierarchy
    (
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY,
            uuid VARCHAR(64) UNIQUE,
            name VARCHAR(255) UNIQUE NOT NULL,
            slug VARCHAR(255) UNIQUE,
            owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            is_active BOOLEAN DEFAULT TRUE,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_orgs_owner ON organizations(owner_user_id)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS org_members (
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role VARCHAR(32) DEFAULT 'member',
            status VARCHAR(32) DEFAULT 'active',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, user_id)
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_org_members_user ON org_members(user_id)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS teams (
            id SERIAL PRIMARY KEY,
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(255),
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (org_id, name)
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_teams_org ON teams(org_id)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS team_members (
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role VARCHAR(32) DEFAULT 'member',
            status VARCHAR(32) DEFAULT 'active',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (team_id, user_id)
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members(user_id)", ()),
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


async def ensure_authnz_core_tables_pg(pool: Optional[DatabasePool] = None) -> bool:
    """Ensure core AuthNZ tables exist for PostgreSQL backends.

    This covers audit_logs, sessions, registration_codes, RBAC tables,
    role/user rate-limits, and the organizations/teams hierarchy. It is
    intended as a bootstrap guardrail for Postgres deployments that have
    not yet run dedicated migrations for these tables.
    """
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False
        for sql, params in _CREATE_AUTHNZ_CORE_TABLES:
            try:
                await db_pool.execute(sql, *params)
            except Exception as exc:
                logger.debug(f"PG ensure authnz core tables DDL failed: {exc}")
        logger.info(
            "Ensured PostgreSQL AuthNZ core tables "
            "(audit_logs, sessions, registration_codes, RBAC, orgs/teams)"
        )
        return True
    except Exception as exc:
        logger.warning(f"Failed to ensure PostgreSQL AuthNZ core tables: {exc}")
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
