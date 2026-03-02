"""
PostgreSQL additive migrations (runtime ensure) for AuthNZ-related extras.

This module centralizes small, idempotent DDL helpers that are safe to call
at startup on Postgres backends. They complement the SQLite migrations in
``migrations.py`` and help keep inline runtime SQL out of business logic.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from .database import DatabasePool, get_db_pool

_PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS = (
    OSError,
    ValueError,
    TypeError,
    KeyError,
    RuntimeError,
    AttributeError,
    ConnectionError,
    TimeoutError,
    json.JSONDecodeError,
)

_BUDGET_FIELD_KEYS = {
    "budget_day_usd",
    "budget_month_usd",
    "budget_day_tokens",
    "budget_month_tokens",
}


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
    # retention policy overrides
    (
        """
        CREATE TABLE IF NOT EXISTS retention_policy_overrides (
            policy_key TEXT PRIMARY KEY,
            days INTEGER NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
        """,
        (),
    ),
    # user profile config overrides
    (
        """
        CREATE TABLE IF NOT EXISTS user_config_overrides (
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value_json TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            updated_by INTEGER,
            PRIMARY KEY (user_id, key),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_user_config_overrides_user_id ON user_config_overrides(user_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_user_config_overrides_key ON user_config_overrides(key)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS org_config_overrides (
            org_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value_json TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            updated_by INTEGER,
            PRIMARY KEY (org_id, key),
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_org_config_overrides_org_id ON org_config_overrides(org_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_org_config_overrides_key ON org_config_overrides(key)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS team_config_overrides (
            team_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value_json TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            updated_by INTEGER,
            PRIMARY KEY (team_id, key),
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_team_config_overrides_team_id ON team_config_overrides(team_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_team_config_overrides_key ON team_config_overrides(key)", ()),
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
    ("ALTER TABLE IF EXISTS org_invites ADD COLUMN IF NOT EXISTS allowed_email_domain TEXT", ()),
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
    (
        """
        CREATE TABLE IF NOT EXISTS org_invites (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            team_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,
            role_to_grant TEXT DEFAULT 'member',
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            max_uses INTEGER DEFAULT 1,
            uses_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            allowed_email_domain TEXT,
            description TEXT,
            metadata JSONB
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_org_invites_code ON org_invites(code)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_org_invites_org_active ON org_invites(org_id, is_active)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_org_invites_expires ON org_invites(expires_at)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS org_invite_redemptions (
            id SERIAL PRIMARY KEY,
            invite_id INTEGER NOT NULL REFERENCES org_invites(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            UNIQUE(invite_id, user_id)
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_invite_redemptions_invite ON org_invite_redemptions(invite_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_invite_redemptions_user ON org_invite_redemptions(user_id)", ()),
    ("ALTER TABLE registration_codes ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL", ()),
    ("ALTER TABLE registration_codes ADD COLUMN IF NOT EXISTS org_role VARCHAR(50)", ()),
    ("ALTER TABLE registration_codes ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL", ()),
]


_CREATE_BILLING_TABLES = [
    (
        """
        CREATE TABLE IF NOT EXISTS subscription_plans (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            stripe_product_id TEXT,
            stripe_price_id TEXT,
            stripe_price_id_yearly TEXT,
            price_usd_monthly DOUBLE PRECISION DEFAULT 0,
            price_usd_yearly DOUBLE PRECISION DEFAULT 0,
            limits_json JSONB NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            is_public BOOLEAN DEFAULT TRUE,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_subscription_plans_name ON subscription_plans(name)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_subscription_plans_active ON subscription_plans(is_active)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS org_subscriptions (
            id SERIAL PRIMARY KEY,
            org_id INTEGER NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
            plan_id INTEGER NOT NULL REFERENCES subscription_plans(id) ON DELETE RESTRICT,
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            stripe_subscription_status TEXT,
            billing_cycle TEXT DEFAULT 'monthly',
            current_period_start TIMESTAMP,
            current_period_end TIMESTAMP,
            status TEXT DEFAULT 'active',
            trial_start TIMESTAMP,
            trial_end TIMESTAMP,
            canceled_at TIMESTAMP,
            cancel_at_period_end BOOLEAN DEFAULT FALSE,
            custom_limits_json JSONB,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_org_subs_org ON org_subscriptions(org_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_org_subs_stripe_customer ON org_subscriptions(stripe_customer_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_org_subs_stripe_sub ON org_subscriptions(stripe_subscription_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_org_subs_status ON org_subscriptions(status)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS org_budgets (
            org_id INTEGER PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
            budgets_json JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_org_budgets_org ON org_budgets(org_id)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS stripe_webhook_events (
            id SERIAL PRIMARY KEY,
            stripe_event_id TEXT UNIQUE NOT NULL,
            event_type TEXT NOT NULL,
            event_data JSONB NOT NULL,
            status TEXT DEFAULT 'pending',
            processed_at TIMESTAMPTZ,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_stripe_events_event_id ON stripe_webhook_events(stripe_event_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_stripe_events_type ON stripe_webhook_events(event_type)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_stripe_events_status ON stripe_webhook_events(status)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS payment_history (
            id SERIAL PRIMARY KEY,
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            stripe_invoice_id TEXT,
            stripe_payment_intent_id TEXT,
            amount_cents INTEGER NOT NULL,
            currency TEXT DEFAULT 'usd',
            status TEXT NOT NULL,
            description TEXT,
            invoice_pdf_url TEXT,
            receipt_url TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_payment_history_org ON payment_history(org_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_payment_history_org_date ON payment_history(org_id, created_at)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_payment_history_stripe_invoice ON payment_history(stripe_invoice_id)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS billing_audit_log (
            id SERIAL PRIMARY KEY,
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_billing_audit_org ON billing_audit_log(org_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_billing_audit_action ON billing_audit_log(action)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_billing_audit_created ON billing_audit_log(created_at)", ()),
]


_CREATE_API_KEYS_TABLES = [
    (
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            key_hash TEXT UNIQUE NOT NULL,
            key_id VARCHAR(32),
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
    ("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS key_id VARCHAR(32)", ()),
    ("ALTER TABLE api_keys ALTER COLUMN key_hash TYPE TEXT", ()),
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
    ("CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_key_id ON api_keys(key_id)", ()),
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
            created_by INTEGER,
            updated_by INTEGER,
            revoked_by INTEGER,
            revoked_at TIMESTAMP WITH TIME ZONE,
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
    ("ALTER TABLE user_provider_secrets ADD COLUMN IF NOT EXISTS created_by INTEGER", ()),
    ("ALTER TABLE user_provider_secrets ADD COLUMN IF NOT EXISTS updated_by INTEGER", ()),
    ("ALTER TABLE user_provider_secrets ADD COLUMN IF NOT EXISTS revoked_by INTEGER", ()),
    ("ALTER TABLE user_provider_secrets ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMP WITH TIME ZONE", ()),
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
            created_by INTEGER,
            updated_by INTEGER,
            revoked_by INTEGER,
            revoked_at TIMESTAMP WITH TIME ZONE,
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
    ("ALTER TABLE org_provider_secrets ADD COLUMN IF NOT EXISTS created_by INTEGER", ()),
    ("ALTER TABLE org_provider_secrets ADD COLUMN IF NOT EXISTS updated_by INTEGER", ()),
    ("ALTER TABLE org_provider_secrets ADD COLUMN IF NOT EXISTS revoked_by INTEGER", ()),
    ("ALTER TABLE org_provider_secrets ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMP WITH TIME ZONE", ()),
    ("ALTER TABLE org_provider_secrets ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", ()),
    ("ALTER TABLE org_provider_secrets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", ()),
    ("ALTER TABLE org_provider_secrets ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMP WITH TIME ZONE", ()),
    ("CREATE INDEX IF NOT EXISTS idx_org_provider_secrets_scope ON org_provider_secrets(scope_type, scope_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_org_provider_secrets_provider ON org_provider_secrets(provider)", ()),
]

_CREATE_BYOK_OAUTH_STATE = [
    (
        """
        CREATE TABLE IF NOT EXISTS byok_oauth_state (
            state TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            auth_session_id TEXT NOT NULL,
            redirect_uri TEXT NOT NULL,
            pkce_verifier_encrypted TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            consumed_at TIMESTAMP WITH TIME ZONE,
            return_path TEXT,
            PRIMARY KEY (state, user_id)
        )
        """,
        (),
    ),
    ("ALTER TABLE byok_oauth_state ADD COLUMN IF NOT EXISTS provider TEXT", ()),
    ("ALTER TABLE byok_oauth_state ADD COLUMN IF NOT EXISTS auth_session_id TEXT", ()),
    ("ALTER TABLE byok_oauth_state ADD COLUMN IF NOT EXISTS redirect_uri TEXT", ()),
    ("ALTER TABLE byok_oauth_state ADD COLUMN IF NOT EXISTS pkce_verifier_encrypted TEXT", ()),
    (
        "ALTER TABLE byok_oauth_state ADD COLUMN IF NOT EXISTS created_at "
        "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
        (),
    ),
    ("ALTER TABLE byok_oauth_state ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE", ()),
    ("ALTER TABLE byok_oauth_state ADD COLUMN IF NOT EXISTS consumed_at TIMESTAMP WITH TIME ZONE", ()),
    ("ALTER TABLE byok_oauth_state ADD COLUMN IF NOT EXISTS return_path TEXT", ()),
    (
        "CREATE INDEX IF NOT EXISTS idx_byok_oauth_state_provider_expires "
        "ON byok_oauth_state(provider, expires_at)",
        (),
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_byok_oauth_state_user_provider_consumed "
        "ON byok_oauth_state(user_id, provider, consumed_at)",
        (),
    ),
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
            request_id TEXT,
            remote_ip TEXT,
            user_agent TEXT,
            token_name TEXT,
            conversation_id TEXT
        )
        """,
        (),
    ),
    ("ALTER TABLE llm_usage_log ADD COLUMN IF NOT EXISTS remote_ip TEXT", ()),
    ("ALTER TABLE llm_usage_log ADD COLUMN IF NOT EXISTS user_agent TEXT", ()),
    ("ALTER TABLE llm_usage_log ADD COLUMN IF NOT EXISTS token_name TEXT", ()),
    ("ALTER TABLE llm_usage_log ADD COLUMN IF NOT EXISTS conversation_id TEXT", ()),
    ("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_ts ON llm_usage_log(ts)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_user ON llm_usage_log(user_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_provider_model ON llm_usage_log(provider, model)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_op_ts ON llm_usage_log(operation, ts)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_key_ts ON llm_usage_log(key_id, ts)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_operation ON llm_usage_log(operation)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_remote_ip_ts ON llm_usage_log(remote_ip, ts)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_token_name_ts ON llm_usage_log(token_name, ts)", ()),
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
    # org/team role permissions (scoped RBAC)
    (
        """
        CREATE TABLE IF NOT EXISTS org_role_permissions (
            org_role TEXT NOT NULL,
            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
            PRIMARY KEY (org_role, permission_id),
            CHECK (org_role IN ('owner', 'admin', 'lead', 'member'))
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_org_role_permissions_permission_id ON org_role_permissions(permission_id)", ()),
    (
        """
        CREATE TABLE IF NOT EXISTS team_role_permissions (
            team_role TEXT NOT NULL,
            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
            PRIMARY KEY (team_role, permission_id),
            CHECK (team_role IN ('owner', 'admin', 'lead', 'member'))
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_team_role_permissions_permission_id ON team_role_permissions(permission_id)", ()),
    (
        """
        INSERT INTO org_role_permissions (org_role, permission_id)
        SELECT 'owner', rp.permission_id
        FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id
        WHERE r.name = 'admin'
        ON CONFLICT (org_role, permission_id) DO NOTHING
        """,
        (),
    ),
    (
        """
        INSERT INTO org_role_permissions (org_role, permission_id)
        SELECT 'admin', rp.permission_id
        FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id
        WHERE r.name = 'admin'
        ON CONFLICT (org_role, permission_id) DO NOTHING
        """,
        (),
    ),
    (
        """
        INSERT INTO org_role_permissions (org_role, permission_id)
        SELECT 'lead', rp.permission_id
        FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id
        WHERE r.name = 'reviewer'
        ON CONFLICT (org_role, permission_id) DO NOTHING
        """,
        (),
    ),
    (
        """
        INSERT INTO org_role_permissions (org_role, permission_id)
        SELECT 'member', rp.permission_id
        FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id
        WHERE r.name = 'user'
        ON CONFLICT (org_role, permission_id) DO NOTHING
        """,
        (),
    ),
    (
        """
        INSERT INTO team_role_permissions (team_role, permission_id)
        SELECT 'owner', rp.permission_id
        FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id
        WHERE r.name = 'admin'
        ON CONFLICT (team_role, permission_id) DO NOTHING
        """,
        (),
    ),
    (
        """
        INSERT INTO team_role_permissions (team_role, permission_id)
        SELECT 'admin', rp.permission_id
        FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id
        WHERE r.name = 'admin'
        ON CONFLICT (team_role, permission_id) DO NOTHING
        """,
        (),
    ),
    (
        """
        INSERT INTO team_role_permissions (team_role, permission_id)
        SELECT 'lead', rp.permission_id
        FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id
        WHERE r.name = 'reviewer'
        ON CONFLICT (team_role, permission_id) DO NOTHING
        """,
        (),
    ),
    (
        """
        INSERT INTO team_role_permissions (team_role, permission_id)
        SELECT 'member', rp.permission_id
        FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id
        WHERE r.name = 'user'
        ON CONFLICT (team_role, permission_id) DO NOTHING
        """,
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


_CREATE_GENERATED_FILES_TABLES = [
    (
        """
        CREATE TABLE IF NOT EXISTS generated_files (
            id SERIAL PRIMARY KEY,
            uuid TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL,
            team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL,
            filename TEXT NOT NULL,
            original_filename TEXT,
            storage_path TEXT NOT NULL,
            mime_type TEXT,
            file_size_bytes BIGINT NOT NULL DEFAULT 0,
            checksum TEXT,
            file_category TEXT NOT NULL,
            source_feature TEXT NOT NULL,
            source_ref TEXT,
            folder_tag TEXT,
            tags JSONB,
            is_transient BOOLEAN DEFAULT FALSE,
            expires_at TIMESTAMP,
            retention_policy TEXT DEFAULT 'user_default',
            is_deleted BOOLEAN DEFAULT FALSE,
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            accessed_at TIMESTAMP
        )
        """,
        (),
    ),
    ("CREATE INDEX IF NOT EXISTS idx_generated_files_user_id ON generated_files(user_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_generated_files_org_id ON generated_files(org_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_generated_files_team_id ON generated_files(team_id)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_generated_files_uuid ON generated_files(uuid)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_generated_files_category ON generated_files(file_category)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_generated_files_source_feature ON generated_files(source_feature)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_generated_files_folder_tag ON generated_files(folder_tag)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_generated_files_is_deleted ON generated_files(is_deleted)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_generated_files_expires_at ON generated_files(expires_at)", ()),
    ("CREATE INDEX IF NOT EXISTS idx_generated_files_created_at ON generated_files(created_at)", ()),
    (
        "CREATE INDEX IF NOT EXISTS idx_generated_files_user_category "
        "ON generated_files(user_id, file_category, is_deleted)",
        (),
    ),
]


async def ensure_tool_catalogs_tables_pg(pool: DatabasePool | None = None) -> bool:
    """Ensure tool catalogs tables exist on PostgreSQL backends.

    Returns True if ensured (or not needed), False if skipped due to non-PG backend.
    """
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False  # not postgres
        try:
            await ensure_authnz_core_tables_pg(db_pool)
        except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"PG ensure authnz core tables before tool catalogs failed: {exc}")
        for sql, params in _CREATE_TOOL_CATALOGS:
            try:
                await db_pool.execute(sql, *params)
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                # Continue attempting subsequent statements; log and surface at the end
                logger.debug(f"PG ensure tool catalogs DDL failed: {exc}")
        logger.info("Ensured PostgreSQL tool catalogs tables (idempotent)")
        return True
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Failed to ensure PostgreSQL tool catalogs tables: {exc}")
        return False


async def ensure_privilege_snapshots_table_pg(pool: DatabasePool | None = None) -> bool:
    """Ensure privilege_snapshots table exists for PostgreSQL backends."""
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False
        for sql, params in _CREATE_PRIVILEGE_SNAPSHOTS:
            try:
                await db_pool.execute(sql, *params)
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG ensure privilege_snapshots DDL failed: {exc}")
        logger.info("Ensured PostgreSQL privilege_snapshots table (idempotent)")
        return True
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Failed to ensure PostgreSQL privilege_snapshots table: {exc}")
        return False


async def ensure_authnz_core_tables_pg(pool: DatabasePool | None = None) -> bool:
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
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG ensure authnz core tables DDL failed: {exc}")
        logger.info(
            "Ensured PostgreSQL AuthNZ core tables "
            "(audit_logs, sessions, registration_codes, RBAC, orgs/teams)"
        )
        return True
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Failed to ensure PostgreSQL AuthNZ core tables: {exc}")
        return False


def _parse_json_payload_pg(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.debug(f"PG budgets: invalid JSON payload: {exc}")
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _normalize_threshold_list_pg(values: Any) -> list[int] | None:
    if not isinstance(values, list):
        return None
    if not values:
        return None
    cleaned: list[int] = []
    for val in values:
        try:
            num = int(val)
        except (TypeError, ValueError):
            continue
        if num < 1 or num > 100:
            continue
        cleaned.append(num)
    if not cleaned:
        return None
    return sorted(set(cleaned))


def _coerce_alert_thresholds_pg(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return {"global": value}
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        if "global" in value:
            out["global"] = value.get("global")
        if "per_metric" in value:
            out["per_metric"] = value.get("per_metric")
        return out or None
    return None


def _coerce_enforcement_mode_pg(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return {"global": value}
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        if "global" in value:
            out["global"] = value.get("global")
        if "per_metric" in value:
            out["per_metric"] = value.get("per_metric")
        return out or None
    return None


def _normalize_alert_thresholds_pg(value: Any) -> dict[str, Any] | None:
    payload = _coerce_alert_thresholds_pg(value)
    if payload is None:
        return None
    out: dict[str, Any] = {}
    global_values = payload.get("global")
    if global_values is not None:
        normalized = _normalize_threshold_list_pg(global_values)
        if normalized:
            out["global"] = normalized
    per_metric = payload.get("per_metric")
    if isinstance(per_metric, dict):
        cleaned: dict[str, Any] = {}
        for key, values in per_metric.items():
            if key not in _BUDGET_FIELD_KEYS:
                continue
            normalized = _normalize_threshold_list_pg(values)
            if normalized:
                cleaned[key] = normalized
        if cleaned:
            out["per_metric"] = cleaned
    return out or None


def _normalize_enforcement_mode_pg(value: Any) -> dict[str, Any] | None:
    payload = _coerce_enforcement_mode_pg(value)
    if payload is None:
        return None
    out: dict[str, Any] = {}
    global_value = payload.get("global")
    if isinstance(global_value, str) and global_value in {"none", "soft", "hard"}:
        out["global"] = global_value
    per_metric = payload.get("per_metric")
    if isinstance(per_metric, dict):
        cleaned: dict[str, Any] = {}
        for key, val in per_metric.items():
            if key not in _BUDGET_FIELD_KEYS:
                continue
            if isinstance(val, str) and val in {"none", "soft", "hard"}:
                cleaned[key] = val
        if cleaned:
            out["per_metric"] = cleaned
    return out or None


def _normalize_budget_payload_pg(raw: Any) -> dict[str, Any]:
    data = _parse_json_payload_pg(raw)
    if not data:
        return {}
    budgets: dict[str, Any] = {}
    if isinstance(data.get("budgets"), dict):
        budgets.update(data.get("budgets") or {})
    for key in _BUDGET_FIELD_KEYS:
        if key in data and key not in budgets:
            budgets[key] = data[key]
    payload: dict[str, Any] = {}
    for key in _BUDGET_FIELD_KEYS:
        if key in budgets:
            payload[key] = budgets[key]
    thresholds = _normalize_alert_thresholds_pg(data.get("alert_thresholds"))
    if thresholds:
        payload["alert_thresholds"] = thresholds
    enforcement = _normalize_enforcement_mode_pg(data.get("enforcement_mode"))
    if enforcement:
        payload["enforcement_mode"] = enforcement
    return payload


async def _backfill_org_budgets_pg(db_pool: DatabasePool) -> None:
    try:
        rows = await db_pool.fetch(
            """
            SELECT os.org_id, os.custom_limits_json, ob.budgets_json
            FROM org_subscriptions os
            LEFT JOIN org_budgets ob ON ob.org_id = os.org_id
            WHERE os.custom_limits_json IS NOT NULL
            """
        )
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(f"PG budgets backfill fetch failed: {exc}")
        return

    for row in rows:
        org_id = row.get("org_id") if isinstance(row, dict) else None
        if org_id is None:
            continue
        custom_limits = _parse_json_payload_pg(row.get("custom_limits_json"))
        if not isinstance(custom_limits, dict) or "budgets" not in custom_limits:
            continue
        legacy_budgets = custom_limits.get("budgets")
        normalized_payload = _normalize_budget_payload_pg(legacy_budgets)
        existing_payload = _normalize_budget_payload_pg(row.get("budgets_json"))

        if normalized_payload and not existing_payload:
            try:
                await db_pool.execute(
                    """
                    INSERT INTO org_budgets (org_id, budgets_json, updated_at)
                    VALUES ($1, $2::jsonb, CURRENT_TIMESTAMP)
                    ON CONFLICT (org_id)
                    DO UPDATE SET budgets_json = EXCLUDED.budgets_json, updated_at = EXCLUDED.updated_at
                    """,
                    org_id,
                    json.dumps(normalized_payload),
                )
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG budgets backfill insert failed for org_id={org_id}: {exc}")
                continue

        should_strip = bool(normalized_payload or existing_payload)
        if should_strip:
            cleaned_limits = dict(custom_limits)
            cleaned_limits.pop("budgets", None)
            payload = json.dumps(cleaned_limits) if cleaned_limits else None
            try:
                await db_pool.execute(
                    """
                    UPDATE org_subscriptions
                    SET custom_limits_json = $2::jsonb
                    WHERE org_id = $1
                    """,
                    org_id,
                    payload,
                )
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG budgets backfill cleanup failed for org_id={org_id}: {exc}")


async def _normalize_org_budgets_pg(db_pool: DatabasePool) -> None:
    try:
        rows = await db_pool.fetch(
            "SELECT org_id, budgets_json FROM org_budgets WHERE budgets_json IS NOT NULL"
        )
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(f"PG budgets normalize fetch failed: {exc}")
        return

    for row in rows:
        org_id = row.get("org_id") if isinstance(row, dict) else None
        if org_id is None:
            continue
        raw_payload = row.get("budgets_json")
        normalized = _normalize_budget_payload_pg(raw_payload)
        if not normalized:
            continue
        try:
            current = _parse_json_payload_pg(raw_payload)
        except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS:
            current = {}
        if json.dumps(current, sort_keys=True) == json.dumps(normalized, sort_keys=True):
            continue
        try:
            await db_pool.execute(
                """
                UPDATE org_budgets
                SET budgets_json = $2::jsonb, updated_at = CURRENT_TIMESTAMP
                WHERE org_id = $1
                """,
                org_id,
                json.dumps(normalized),
            )
        except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"PG budgets normalize update failed for org_id={org_id}: {exc}")


async def ensure_billing_tables_pg(
    pool: DatabasePool | None = None,
    *,
    run_backfill: bool = True,
) -> bool:
    """Ensure billing-related tables exist for PostgreSQL backends."""
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False
        try:
            await ensure_authnz_core_tables_pg(db_pool)
        except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"ensure_billing_tables_pg: core table ensure skipped/failed: {exc}")

        for sql, params in _CREATE_BILLING_TABLES:
            try:
                await db_pool.execute(sql, *params)
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG ensure billing DDL failed: {exc}")

        default_plans = [
            {
                "name": "free",
                "display_name": "Free",
                "description": "Internal/default plan (not publicly listed)",
                "price_usd_monthly": 0,
                "price_usd_yearly": 0,
                "sort_order": 0,
                "is_public": False,
                "limits_json": json.dumps({
                    "storage_mb": 1024,
                    "api_calls_day": 100,
                    "api_calls_month": 3000,
                    "llm_tokens_day": 10000,
                    "llm_tokens_month": 300000,
                    "transcription_minutes_month": 10,
                    "rag_queries_day": 50,
                    "concurrent_jobs": 1,
                    "team_members": 1,
                    "rate_limit_rpm": 10,
                    "features": ["basic_search", "basic_chat"],
                }),
            },
            {
                "name": "starter",
                "display_name": "Starter",
                "description": "For individuals getting started",
                "price_usd_monthly": 10,
                "price_usd_yearly": 100,
                "sort_order": 1,
                "is_public": True,
                "limits_json": json.dumps({
                    "storage_mb": 2048,
                    "api_calls_day": 1000,
                    "api_calls_month": 30000,
                    "llm_tokens_month": 4000000,
                    "llm_tokens_premium_month": 80000,
                    "max_context_tokens": 64000,
                    "byok_enabled": True,
                    "byok_keys_saved": 1,
                    "notebooks": 100,
                    "sources_per_notebook": 50,
                    "ingestion_pages_month": 2000,
                    "ingestion_pages_day": 150,
                    "scheduled_refresh": "manual",
                    "max_upload_mb": 50,
                    "transcription_minutes_month": 120,
                    "tts_minutes_month": 30,
                    "rag_queries_day": 1000,
                    "concurrent_jobs": 2,
                    "team_members": 1,
                    "rate_limit_rpm": 20,
                    "features": ["basic_search", "basic_chat", "byok"],
                }),
            },
            {
                "name": "plus",
                "display_name": "Plus",
                "description": "For power users who need more capacity",
                "price_usd_monthly": 20,
                "price_usd_yearly": 200,
                "sort_order": 2,
                "is_public": True,
                "limits_json": json.dumps({
                    "storage_mb": 10240,
                    "api_calls_day": 5000,
                    "api_calls_month": 150000,
                    "llm_tokens_month": 12000000,
                    "llm_tokens_premium_month": 200000,
                    "max_context_tokens": 128000,
                    "byok_enabled": True,
                    "byok_keys_saved": 3,
                    "notebooks": 300,
                    "sources_per_notebook": 100,
                    "ingestion_pages_month": 10000,
                    "ingestion_pages_day": 750,
                    "scheduled_refresh": "weekly",
                    "max_upload_mb": 200,
                    "transcription_minutes_month": 300,
                    "tts_minutes_month": 90,
                    "rag_queries_day": 5000,
                    "concurrent_jobs": 5,
                    "team_members": 1,
                    "rate_limit_rpm": 60,
                    "features": ["*", "byok", "rag_advanced", "vector_search"],
                }),
            },
            {
                "name": "pro",
                "display_name": "Pro",
                "description": "For teams and professional usage",
                "price_usd_monthly": 30,
                "price_usd_yearly": 300,
                "sort_order": 3,
                "is_public": True,
                "limits_json": json.dumps({
                    "storage_mb": 30720,
                    "api_calls_day": 15000,
                    "api_calls_month": 450000,
                    "llm_tokens_month": 18000000,
                    "llm_tokens_premium_month": 300000,
                    "max_context_tokens": 200000,
                    "byok_enabled": True,
                    "byok_keys_saved": 10,
                    "notebooks": 1000,
                    "sources_per_notebook": 300,
                    "ingestion_pages_month": 30000,
                    "ingestion_pages_day": 2000,
                    "scheduled_refresh": "daily",
                    "max_upload_mb": 500,
                    "transcription_minutes_month": 500,
                    "tts_minutes_month": 150,
                    "rag_queries_day": 15000,
                    "concurrent_jobs": 10,
                    "team_members": 5,
                    "rate_limit_rpm": 120,
                    "features": ["*", "byok", "rag_advanced", "vector_search", "priority_support", "audit_logs"],
                }),
            },
        ]

        for plan in default_plans:
            try:
                await db_pool.execute(
                    """
                    INSERT INTO subscription_plans
                    (name, display_name, description, price_usd_monthly, price_usd_yearly, limits_json, sort_order, is_public)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
                    ON CONFLICT (name) DO NOTHING
                    """,
                    plan["name"],
                    plan["display_name"],
                    plan["description"],
                    plan["price_usd_monthly"],
                    plan["price_usd_yearly"],
                    plan["limits_json"],
                    plan["sort_order"],
                    plan.get("is_public", True),
                )
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG ensure billing seed failed: {exc}")

        if run_backfill:
            try:
                await _backfill_org_budgets_pg(db_pool)
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG budgets backfill skipped/failed: {exc}")

            try:
                await _normalize_org_budgets_pg(db_pool)
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG budgets normalize skipped/failed: {exc}")

        logger.info(
            "Ensured PostgreSQL billing tables "
            "(subscription_plans, org_subscriptions, org_budgets, "
            "stripe_webhook_events, payment_history, billing_audit_log)"
        )
        return True
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Failed to ensure PostgreSQL billing tables: {exc}")
        return False


async def ensure_api_keys_tables_pg(pool: DatabasePool | None = None) -> bool:
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
        except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"ensure_api_keys_tables_pg: core table ensure skipped/failed: {exc}")

        errors: list[Exception] = []
        for sql, params in _CREATE_API_KEYS_TABLES:
            try:
                await db_pool.execute(sql, *params)
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
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
        except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
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
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Failed to ensure PostgreSQL api_keys tables: {exc}")
        return False


async def ensure_user_provider_secrets_pg(pool: DatabasePool | None = None) -> bool:
    """Ensure user_provider_secrets table exists for PostgreSQL backends."""
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False

        # Ensure users table exists before adding the FK-backed BYOK table.
        try:
            await ensure_authnz_core_tables_pg(db_pool)
        except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"ensure_user_provider_secrets_pg: core table ensure skipped/failed: {exc}")

        for sql, params in _CREATE_USER_PROVIDER_SECRETS:
            try:
                await db_pool.execute(sql, *params)
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG ensure user_provider_secrets DDL failed: {exc}")

        logger.info("Ensured PostgreSQL user_provider_secrets table (idempotent)")
        return True
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Failed to ensure PostgreSQL user_provider_secrets table: {exc}")
        return False


async def ensure_org_provider_secrets_pg(pool: DatabasePool | None = None) -> bool:
    """Ensure org_provider_secrets table exists for PostgreSQL backends."""
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False

        # Ensure core tables exist first (org/team scaffolding)
        try:
            await ensure_authnz_core_tables_pg(db_pool)
        except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"ensure_org_provider_secrets_pg: core table ensure skipped/failed: {exc}")

        for sql, params in _CREATE_ORG_PROVIDER_SECRETS:
            try:
                await db_pool.execute(sql, *params)
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG ensure org_provider_secrets DDL failed: {exc}")

        logger.info("Ensured PostgreSQL org_provider_secrets table (idempotent)")
        return True
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Failed to ensure PostgreSQL org_provider_secrets table: {exc}")
        return False


async def ensure_byok_oauth_state_pg(pool: DatabasePool | None = None) -> bool:
    """Ensure byok_oauth_state table exists for PostgreSQL backends."""
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False

        # Ensure users table exists before FK-backed BYOK OAuth state table.
        try:
            await ensure_authnz_core_tables_pg(db_pool)
        except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"ensure_byok_oauth_state_pg: core table ensure skipped/failed: {exc}")

        for sql, params in _CREATE_BYOK_OAUTH_STATE:
            try:
                await db_pool.execute(sql, *params)
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG ensure byok_oauth_state DDL failed: {exc}")

        logger.info("Ensured PostgreSQL byok_oauth_state table (idempotent)")
        return True
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Failed to ensure PostgreSQL byok_oauth_state table: {exc}")
        return False


async def ensure_llm_provider_overrides_pg(pool: DatabasePool | None = None) -> bool:
    """Ensure llm_provider_overrides table exists for PostgreSQL backends."""
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False

        for sql, params in _CREATE_LLM_PROVIDER_OVERRIDES:
            try:
                await db_pool.execute(sql, *params)
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG ensure llm_provider_overrides DDL failed: {exc}")

        logger.info("Ensured PostgreSQL llm_provider_overrides table (idempotent)")
        return True
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Failed to ensure PostgreSQL llm_provider_overrides table: {exc}")
        return False

async def ensure_usage_tables_pg(pool: DatabasePool | None = None) -> bool:
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
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG ensure usage tables DDL failed: {exc}")
        logger.info("Ensured PostgreSQL usage tables (usage_log, usage_daily, llm_usage_log, llm_usage_daily)")
        return True
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Failed to ensure PostgreSQL usage tables: {exc}")
        return False


async def ensure_generated_files_table_pg(pool: DatabasePool | None = None) -> bool:
    """Ensure generated_files table exists for PostgreSQL backends."""
    try:
        db_pool = pool or await get_db_pool()
        if getattr(db_pool, "pool", None) is None:
            return False
        try:
            await ensure_authnz_core_tables_pg(db_pool)
        except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"PG ensure authnz core tables before generated_files failed: {exc}")
        for sql, params in _CREATE_GENERATED_FILES_TABLES:
            try:
                await db_pool.execute(sql, *params)
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG ensure generated_files DDL failed: {exc}")
        logger.info("Ensured PostgreSQL generated_files table (idempotent)")
        return True
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Failed to ensure PostgreSQL generated_files table: {exc}")
        return False


async def ensure_virtual_key_counters_pg(pool: DatabasePool | None = None) -> bool:
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
            except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"PG ensure virtual-key counters DDL failed: {exc}")
        logger.info("Ensured PostgreSQL virtual-key counters tables (vk_jwt_counters, vk_api_key_counters)")
        return True
    except _PG_MIGRATIONS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Failed to ensure PostgreSQL virtual-key counters tables: {exc}")
        return False
