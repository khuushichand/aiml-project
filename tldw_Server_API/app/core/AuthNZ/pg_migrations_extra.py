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
    ("ALTER TABLE registration_codes ADD COLUMN IF NOT EXISTS times_used INTEGER DEFAULT 0", ()),
    ("ALTER TABLE registration_codes ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE", ()),
    ("ALTER TABLE registration_codes ADD COLUMN IF NOT EXISTS description TEXT", ()),
    ("ALTER TABLE registration_codes ADD COLUMN IF NOT EXISTS allowed_email_domain TEXT", ()),
    (
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'registration_codes' AND column_name = 'uses'
            ) THEN
                UPDATE registration_codes
                SET times_used = uses
                WHERE times_used IS NULL OR times_used = 0;
            END IF;
        END $$;
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
    # Backstop for older/minimal schemas (tests) that created user_roles without these columns.
    ("ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS granted_by INTEGER", ()),
    ("ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP", ()),
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
    ("ALTER TABLE registration_codes ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL", ()),
    ("ALTER TABLE registration_codes ADD COLUMN IF NOT EXISTS org_role VARCHAR(50)", ()),
    ("ALTER TABLE registration_codes ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL", ()),
]


_CREATE_API_KEYS_TABLES = [
    (
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            key_hash VARCHAR(64) UNIQUE NOT NULL,
            key_prefix VARCHAR(16) NOT NULL,
            name VARCHAR(255),
            description TEXT,
            scope VARCHAR(50) DEFAULT 'read',
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            last_used_at TIMESTAMP,
            last_used_ip VARCHAR(45),
            usage_count INTEGER DEFAULT 0,
            rate_limit INTEGER,
            allowed_ips TEXT,
            metadata JSONB,
            rotated_from INTEGER REFERENCES api_keys(id),
            rotated_to INTEGER REFERENCES api_keys(id),
            revoked_at TIMESTAMP,
            revoked_by INTEGER,
            revoke_reason TEXT
        )
        """,
        (),
    ),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS scope VARCHAR(50) DEFAULT 'read'", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active'", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS metadata JSONB", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS rotated_from INTEGER REFERENCES api_keys(id)", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS rotated_to INTEGER REFERENCES api_keys(id)", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMP", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS revoked_by INTEGER", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS revoke_reason TEXT", ()),
    # Virtual key fields
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS is_virtual BOOLEAN DEFAULT FALSE", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS parent_key_id INTEGER REFERENCES api_keys(id)", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_budget_day_tokens BIGINT", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_budget_month_tokens BIGINT", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_budget_day_usd DOUBLE PRECISION", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_budget_month_usd DOUBLE PRECISION", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_allowed_endpoints TEXT", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_allowed_providers TEXT", ()),
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_allowed_models TEXT", ()),
    # Helpful indexes
    ("CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_api_keys_expires_at ON api_keys(expires_at)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_api_keys_virtual ON api_keys(is_virtual)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_api_keys_org ON api_keys(org_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_api_keys_team ON api_keys(team_id)", ()),
    # Audit log
    (
        """
        CREATE TABLE IF NOT EXISTS api_key_audit_log (
            id SERIAL PRIMARY KEY,
            api_key_id INTEGER NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
            action VARCHAR(50) NOT NULL,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,
            details JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_api_key_audit_log_api_key_id ON api_key_audit_log(api_key_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_api_key_audit_log_created_at ON api_key_audit_log(created_at)", ()),
]

_CREATE_USER_PROVIDER_SECRETS = [
    (
        """
        CREATE TABLE IF NOT EXISTS user_provider_secrets (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            encrypted_blob TEXT NOT NULL,
            key_hint TEXT,
            metadata TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT uq_user_provider_secrets UNIQUE (user_id, provider)
        )
        """,
        (),
    ),
    ("ALTER TABLE user_provider_secrets ADD COLUMN IF NOT EXISTS encrypted_blob TEXT", ()),
    ("ALTER TABLE user_provider_secrets ADD COLUMN IF NOT EXISTS key_hint TEXT", ()),
    ("ALTER TABLE user_provider_secrets ADD COLUMN IF NOT EXISTS metadata TEXT", ()),
    ("ALTER TABLE user_provider_secrets ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", ()),
    ("ALTER TABLE user_provider_secrets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", ()),
    ("ALTER TABLE user_provider_secrets ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMP WITH TIME ZONE", ()),
    ("CREATE INDEX IF NOT EXISTS idx_user_provider_secrets_user_id ON user_provider_secrets(user_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_user_provider_secrets_provider ON user_provider_secrets(provider)", ()),
]

_CREATE_ORG_PROVIDER_SECRETS = [
    (
        """
        CREATE TABLE IF NOT EXISTS org_provider_secrets (
            id SERIAL PRIMARY KEY,
            scope_type TEXT NOT NULL,
            scope_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            encrypted_blob TEXT NOT NULL,
            key_hint TEXT,
            metadata TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT uq_org_provider_secrets UNIQUE (scope_type, scope_id, provider)
        )
        """,
        (),
    ),
    ("ALTER TABLE org_provider_secrets ADD COLUMN IF NOT EXISTS encrypted_blob TEXT", ()),
    ("ALTER TABLE org_provider_secrets ADD COLUMN IF NOT EXISTS key_hint TEXT", ()),
    ("ALTER TABLE org_provider_secrets ADD COLUMN IF NOT EXISTS metadata TEXT", ()),
    ("ALTER TABLE org_provider_secrets ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", ()),
    ("ALTER TABLE org_provider_secrets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", ()),
    ("ALTER TABLE org_provider_secrets ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMP WITH TIME ZONE", ()),
    ("CREATE INDEX IF NOT EXISTS idx_org_provider_secrets_scope ON org_provider_secrets(scope_type, scope_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_org_provider_secrets_provider ON org_provider_secrets(provider)", ()),
]

_CREATE_LLM_PROVIDER_OVERRIDES = [
    (
        """
        CREATE TABLE IF NOT EXISTS llm_provider_overrides (
            provider TEXT PRIMARY KEY,
            is_enabled BOOLEAN,
            allowed_models TEXT,
            config_json TEXT,
            secret_blob TEXT,
            api_key_hint TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """,
        (),
    ),
    ("ALTER TABLE llm_provider_overrides ADD COLUMN IF NOT EXISTS is_enabled BOOLEAN", ()),
    ("ALTER TABLE llm_provider_overrides ADD COLUMN IF NOT EXISTS allowed_models TEXT", ()),
    ("ALTER TABLE llm_provider_overrides ADD COLUMN IF NOT EXISTS config_json TEXT", ()),
    ("ALTER TABLE llm_provider_overrides ADD COLUMN IF NOT EXISTS secret_blob TEXT", ()),
    ("ALTER TABLE llm_provider_overrides ADD COLUMN IF NOT EXISTS api_key_hint TEXT", ()),
    ("ALTER TABLE llm_provider_overrides ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", ()),
    ("ALTER TABLE llm_provider_overrides ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", ()),
    ("CREATE INDEX IF NOT EXISTS idx_llm_provider_overrides_enabled ON llm_provider_overrides(is_enabled)", ()),
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
        try:
            await ensure_authnz_core_tables_pg(db_pool)
        except Exception as exc:
            logger.debug(f"PG ensure authnz core tables before tool catalogs failed: {exc}")
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


async def ensure_api_keys_tables_pg(pool: Optional[DatabasePool] = None) -> bool:
    """Ensure api_keys + api_key_audit_log tables exist for PostgreSQL backends.

    Returns True when ensured (or already present), False when skipped due to a non-PG backend.
    """
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False

        # api_keys includes optional org/team-scoped columns with FK references.
        # Ensure the core AuthNZ tables (including organizations/teams) exist first
        # so additive `ALTER TABLE ... REFERENCES organizations/teams` statements
        # succeed in minimal test schemas.
        try:
            await ensure_authnz_core_tables_pg(db_pool)
        except Exception as exc:
            logger.debug(f"ensure_api_keys_tables_pg: core table ensure skipped/failed: {exc}")

        errors: list[Exception] = []
        for sql, params in _CREATE_API_KEYS_TABLES:
            try:
                await db_pool.execute(sql, *params)
            except Exception as exc:
                errors.append(exc)
                logger.debug(f"PG ensure api keys DDL failed: {exc}")

        try:
            api_keys_ok = await db_pool.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'api_keys'
                )
                """
            )
            audit_ok = await db_pool.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'api_key_audit_log'
                )
                """
            )
            if not api_keys_ok or not audit_ok:
                logger.warning(
                    "PostgreSQL api_keys schema ensure did not complete "
                    f"(api_keys={bool(api_keys_ok)}, api_key_audit_log={bool(audit_ok)})"
                )
                return False
        except Exception as exc:
            # Treat verification failure as non-fatal; callers can detect missing tables later.
            logger.debug(f"PG ensure api_keys table verification failed: {exc}")

        if errors:
            logger.info(
                "Ensured PostgreSQL api_keys tables (idempotent) with "
                f"{len(errors)} non-fatal DDL errors"
            )
        else:
            logger.info("Ensured PostgreSQL api_keys tables (idempotent)")
        return True
    except Exception as exc:
        logger.warning(f"Failed to ensure PostgreSQL api_keys tables: {exc}")
        return False


async def ensure_user_provider_secrets_pg(pool: Optional[DatabasePool] = None) -> bool:
    """Ensure user_provider_secrets table exists for PostgreSQL backends."""
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False

        # Ensure users table exists before adding the FK-backed BYOK table.
        try:
            await ensure_authnz_core_tables_pg(db_pool)
        except Exception as exc:
            logger.debug(f"ensure_user_provider_secrets_pg: core table ensure skipped/failed: {exc}")

        for sql, params in _CREATE_USER_PROVIDER_SECRETS:
            try:
                await db_pool.execute(sql, *params)
            except Exception as exc:
                logger.debug(f"PG ensure user_provider_secrets DDL failed: {exc}")

        logger.info("Ensured PostgreSQL user_provider_secrets table (idempotent)")
        return True
    except Exception as exc:
        logger.warning(f"Failed to ensure PostgreSQL user_provider_secrets table: {exc}")
        return False


async def ensure_org_provider_secrets_pg(pool: Optional[DatabasePool] = None) -> bool:
    """Ensure org_provider_secrets table exists for PostgreSQL backends."""
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False

        # Ensure core tables exist first (org/team scaffolding)
        try:
            await ensure_authnz_core_tables_pg(db_pool)
        except Exception as exc:
            logger.debug(f"ensure_org_provider_secrets_pg: core table ensure skipped/failed: {exc}")

        for sql, params in _CREATE_ORG_PROVIDER_SECRETS:
            try:
                await db_pool.execute(sql, *params)
            except Exception as exc:
                logger.debug(f"PG ensure org_provider_secrets DDL failed: {exc}")

        logger.info("Ensured PostgreSQL org_provider_secrets table (idempotent)")
        return True
    except Exception as exc:
        logger.warning(f"Failed to ensure PostgreSQL org_provider_secrets table: {exc}")
        return False


async def ensure_llm_provider_overrides_pg(pool: Optional[DatabasePool] = None) -> bool:
    """Ensure llm_provider_overrides table exists for PostgreSQL backends."""
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False

        for sql, params in _CREATE_LLM_PROVIDER_OVERRIDES:
            try:
                await db_pool.execute(sql, *params)
            except Exception as exc:
                logger.debug(f"PG ensure llm_provider_overrides DDL failed: {exc}")

        logger.info("Ensured PostgreSQL llm_provider_overrides table (idempotent)")
        return True
    except Exception as exc:
        logger.warning(f"Failed to ensure PostgreSQL llm_provider_overrides table: {exc}")
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
