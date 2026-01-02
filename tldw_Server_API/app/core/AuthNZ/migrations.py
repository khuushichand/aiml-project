# migrations.py
# Description: Database migrations for AuthNZ module tables
#
# Imports
from typing import Any, Dict, List, Optional
import sqlite3
import json
from pathlib import Path
#
# 3rd-party imports
from loguru import logger
#
# Local imports
from tldw_Server_API.app.core.DB_Management.migrations import Migration, MigrationManager

#######################################################################################################################
#
# AuthNZ Migrations
#

def migration_001_create_users_table(conn: sqlite3.Connection) -> None:
    """Create the users table for authentication"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            is_superuser INTEGER DEFAULT 0,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            email_verified INTEGER DEFAULT 0,
            storage_quota_mb INTEGER DEFAULT 5120,
            storage_used_mb INTEGER DEFAULT 0
        )
    """)

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")

    conn.commit()
    logger.info("Migration 001: Created users table")


def migration_002_create_sessions_table(conn: sqlite3.Connection) -> None:
    """Create the sessions table for session management"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            refresh_token_hash TEXT,
            encrypted_token TEXT,
            encrypted_refresh TEXT,
            expires_at TIMESTAMP NOT NULL,
            refresh_expires_at TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            device_id TEXT,
            is_active INTEGER DEFAULT 1,
            is_revoked INTEGER DEFAULT 0,
            revoked_at TIMESTAMP,
            revoked_by INTEGER,
            revoke_reason TEXT,
            access_jti TEXT,
            refresh_jti TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Create indexes
    try:
        cursor = conn.execute("PRAGMA table_info(sessions)")
        columns = {row[1] for row in cursor.fetchall()}

        def add_col(name: str, decl: str):
            if name not in columns:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {decl}")
                columns.add(name)

        # Legacy schemas may lack critical columns; add safe defaults where possible
        add_col('token_hash', "token_hash TEXT")
        add_col('refresh_token_hash', "refresh_token_hash TEXT")
        add_col('encrypted_token', "encrypted_token TEXT")
        add_col('encrypted_refresh', "encrypted_refresh TEXT")
        add_col('refresh_expires_at', "refresh_expires_at TIMESTAMP")
        add_col('access_jti', "access_jti TEXT")
        add_col('refresh_jti', "refresh_jti TEXT")
        add_col('is_active', "is_active INTEGER DEFAULT 1")
        add_col('is_revoked', "is_revoked INTEGER DEFAULT 0")
        add_col('revoked_at', "revoked_at TIMESTAMP")
        add_col('revoked_by', "revoked_by INTEGER")
        add_col('revoke_reason', "revoke_reason TEXT")
    except Exception:
        pass

    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_access_jti ON sessions(access_jti)")

    conn.commit()
    logger.info("Migration 002: Created sessions table")


def migration_003_create_api_keys_table(conn: sqlite3.Connection) -> None:
    """Create the api_keys table for API key management"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key_hash TEXT UNIQUE NOT NULL,
            key_id TEXT,
            key_prefix TEXT,
            name TEXT,
            description TEXT,
            scope TEXT DEFAULT 'read',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            last_used_at TIMESTAMP,
            last_used_ip TEXT,
            usage_count INTEGER DEFAULT 0,
            rate_limit INTEGER,
            allowed_ips TEXT,
            metadata TEXT,
            rotated_from INTEGER REFERENCES api_keys(id),
            rotated_to INTEGER REFERENCES api_keys(id),
            revoked_at TIMESTAMP,
            revoked_by INTEGER,
            revoke_reason TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Harmonize legacy schemas: add missing columns if needed
    try:
        cur = conn.execute("PRAGMA table_info(api_keys)")
        cols = {row[1] for row in cur.fetchall()}

        def add_col(name: str, decl: str):
            if name not in cols:
                conn.execute(f"ALTER TABLE api_keys ADD COLUMN {decl}")
                cols.add(name)

        add_col('key_id', "key_id TEXT")
        add_col('key_prefix', "key_prefix TEXT")
        add_col('description', "description TEXT")
        add_col('scope', "scope TEXT DEFAULT 'read'")
        add_col('status', "status TEXT DEFAULT 'active'")
        add_col('last_used_at', "last_used_at TIMESTAMP")
        add_col('last_used_ip', "last_used_ip TEXT")
        add_col('usage_count', "usage_count INTEGER DEFAULT 0")
        add_col('rate_limit', "rate_limit INTEGER")
        add_col('allowed_ips', "allowed_ips TEXT")
        add_col('metadata', "metadata TEXT")
        add_col('rotated_from', "rotated_from INTEGER REFERENCES api_keys(id)")
        add_col('rotated_to', "rotated_to INTEGER REFERENCES api_keys(id)")
        add_col('revoked_at', "revoked_at TIMESTAMP")
        add_col('revoked_by', "revoked_by INTEGER")
        add_col('revoke_reason', "revoke_reason TEXT")
    except Exception:
        pass

    # Create indexes (only if columns exist)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_key_id ON api_keys(key_id)")
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status)")
    except Exception:
        pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_expires_at ON api_keys(expires_at)")

    conn.commit()
    logger.info("Migration 003: Created api_keys table")


def migration_004_create_api_key_audit_log(conn: sqlite3.Connection) -> None:
    """Create the api_key_audit_log table for tracking API key actions"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_key_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            user_id INTEGER,
            ip_address TEXT,
            user_agent TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE
        )
    """)

    # Create index
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_key_audit_log_api_key_id ON api_key_audit_log(api_key_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_key_audit_log_created_at ON api_key_audit_log(created_at)")

    conn.commit()
    logger.info("Migration 004: Created api_key_audit_log table")


def migration_005_create_rate_limits_table(conn: sqlite3.Connection) -> None:
    """Create the rate_limits table for rate limiting"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            request_count INTEGER DEFAULT 1,
            window_start TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(identifier, endpoint, window_start)
        )
    """)

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rate_limits_identifier ON rate_limits(identifier)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rate_limits_window_start ON rate_limits(window_start)")

    conn.commit()
    logger.info("Migration 005: Created rate_limits table")


def migration_006_create_registration_codes_table(conn: sqlite3.Connection) -> None:
    """Create the registration_codes table for controlled registration"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS registration_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            max_uses INTEGER DEFAULT 1,
            uses_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            metadata TEXT,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_registration_codes_code ON registration_codes(code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_registration_codes_expires_at ON registration_codes(expires_at)")

    conn.commit()
    logger.info("Migration 006: Created registration_codes table")


def migration_007_create_audit_logs_table(conn: sqlite3.Connection) -> None:
    """Create the audit_logs table for security auditing"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            ip_address TEXT,
            user_agent TEXT,
            status TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)")

    conn.commit()
    logger.info("Migration 007: Created audit_logs table")


def migration_008_add_password_history_table(conn: sqlite3.Connection) -> None:
    """Create the password_history table to prevent password reuse"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_password_history_user_id ON password_history(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_password_history_created_at ON password_history(created_at)")

    conn.commit()
    logger.info("Migration 008: Created password_history table")


def migration_009_add_session_encryption_columns(conn: sqlite3.Connection) -> None:
    """Add encryption columns to sessions table if they don't exist"""
    # Check if columns already exist
    cursor = conn.execute("PRAGMA table_info(sessions)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'encrypted_token' not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN encrypted_token TEXT")
        logger.info("Added encrypted_token column to sessions table")

    if 'encrypted_refresh' not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN encrypted_refresh TEXT")
        logger.info("Added encrypted_refresh column to sessions table")

    conn.commit()
    logger.info("Migration 009: Added session encryption columns")


def migration_010_add_2fa_columns(conn: sqlite3.Connection) -> None:
    """Add two-factor authentication columns to users table"""
    # Check if columns already exist
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'totp_secret' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN totp_secret TEXT")
        logger.info("Added totp_secret column to users table")

    if 'two_factor_enabled' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN two_factor_enabled INTEGER DEFAULT 0")
        logger.info("Added two_factor_enabled column to users table")

    if 'backup_codes' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN backup_codes TEXT")
        logger.info("Added backup_codes column to users table")

    conn.commit()
    logger.info("Migration 010: Added 2FA columns to users table")


# Rollback functions (for migrations that can be rolled back)

def rollback_001_drop_users_table(conn: sqlite3.Connection) -> None:
    """Rollback: Drop the users table"""
    conn.execute("DROP TABLE IF EXISTS users")
    conn.commit()
    logger.info("Rollback 001: Dropped users table")


def rollback_002_drop_sessions_table(conn: sqlite3.Connection) -> None:
    """Rollback: Drop the sessions table"""
    conn.execute("DROP TABLE IF EXISTS sessions")
    conn.commit()
    logger.info("Rollback 002: Dropped sessions table")


def rollback_003_drop_api_keys_table(conn: sqlite3.Connection) -> None:
    """Rollback: Drop the api_keys table"""
    conn.execute("DROP TABLE IF EXISTS api_keys")
    conn.commit()
    logger.info("Rollback 003: Dropped api_keys table")


def migration_011_add_enhanced_auth_tables(conn: sqlite3.Connection) -> None:
    """Create tables for enhanced authentication features"""
    logger.info("Migration 011: START enhanced auth tables + uuid")

    # Password reset tokens table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT UNIQUE,
            expires_at TIMESTAMP NOT NULL,
            used_at TIMESTAMP,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    # Harmonize legacy column name 'token' -> ensure 'token_hash' exists
    try:
        cur = conn.execute("PRAGMA table_info(password_reset_tokens)")
        cols = {row[1] for row in cur.fetchall()}
        if 'token_hash' not in cols:
            conn.execute("ALTER TABLE password_reset_tokens ADD COLUMN token_hash TEXT UNIQUE")
    except Exception:
        pass
    # Indexes
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reset_tokens_hash ON password_reset_tokens(token_hash)")
    except Exception:
        pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reset_tokens_user ON password_reset_tokens(user_id)")

    # Failed attempts table for lockout tracking
    conn.execute("""
        CREATE TABLE IF NOT EXISTS failed_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier TEXT NOT NULL,
            attempt_type TEXT NOT NULL,
            attempt_count INTEGER DEFAULT 1,
            window_start TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(identifier, attempt_type)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_failed_attempts_identifier ON failed_attempts(identifier)")

    # Account lockouts table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS account_lockouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier TEXT UNIQUE NOT NULL,
            locked_until TIMESTAMP NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lockouts_identifier ON account_lockouts(identifier)")

    # Token blacklist table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS token_blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jti TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            token_type TEXT,
            revoked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            reason TEXT,
            revoked_by INTEGER,
            ip_address TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blacklist_jti ON token_blacklist(jti)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blacklist_expires ON token_blacklist(expires_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blacklist_user ON token_blacklist(user_id)")

    # Add columns to users if not exists
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'uuid' not in columns:
        # SQLite cannot add a UNIQUE constraint via ALTER TABLE. Add column first,
        # then create a unique index to enforce uniqueness. This keeps the
        # migration compatible with fresh DBs and legacy ones.
        conn.execute("ALTER TABLE users ADD COLUMN uuid TEXT")
        try:
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_uuid ON users(uuid)")
        except Exception:
            # If an older schema already enforced uniqueness differently, ignore
            pass
        logger.info("Added uuid column to users table with unique index")

    if 'email_verified_at' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMP")
        logger.info("Added email_verified_at column to users table")

    if 'is_verified' not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
        logger.info("Added is_verified column to users table")

    conn.commit()
    logger.info("Migration 011: Created enhanced authentication tables")


def migration_012_create_rbac_tables(conn: sqlite3.Connection) -> None:
    """Create core RBAC tables: roles, permissions, mappings, and user overrides."""
    logger.info("Migration 012: START RBAC core tables")
    # Roles
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            is_system INTEGER DEFAULT 0
        )
        """
    )

    # Permissions (use column name 'name' to match existing DB accessors)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            category TEXT
        )
        """
    )

    # Role -> Permission mapping
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            PRIMARY KEY (role_id, permission_id),
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
            FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
        )
        """
    )

    # User -> Role mapping (with optional expiration)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            granted_by INTEGER,
            expires_at TIMESTAMP,
            PRIMARY KEY (user_id, role_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
        )
        """
    )

    # User permission overrides (allow/deny via boolean 'granted')
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_permissions (
            user_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            granted INTEGER NOT NULL DEFAULT 1, -- 1 = allow, 0 = deny
            expires_at TIMESTAMP,
            PRIMARY KEY (user_id, permission_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
        )
        """
    )

    # Helpful indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_permissions_user ON user_permissions(user_id)")

    conn.commit()
    logger.info("Migration 012: Created RBAC core tables (roles, permissions, mappings, overrides)")


def migration_013_create_rbac_limits_and_usage(conn: sqlite3.Connection) -> None:
    """Create optional RBAC rate limit and usage tables (SQLite)."""
    logger.info("Migration 013: START RBAC limits + usage tables")
    # Role-level rate limits
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rbac_role_rate_limits (
            role_id INTEGER NOT NULL,
            resource TEXT NOT NULL,
            limit_per_min INTEGER,
            burst INTEGER,
            PRIMARY KEY (role_id, resource),
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
        )
        """
    )

    # User-level rate limits (override role defaults)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rbac_user_rate_limits (
            user_id INTEGER NOT NULL,
            resource TEXT NOT NULL,
            limit_per_min INTEGER,
            burst INTEGER,
            PRIMARY KEY (user_id, resource),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )

    # Lightweight per-request usage (for API analytics)
    # In pytest/TEST_MODE, relax foreign keys to simplify isolated table tests.
    try:
        import os as _os
        _relax_fk = (
            _os.getenv("DISABLE_USAGE_FOREIGN_KEYS", "").lower() in {"1", "true", "yes", "on"}
            or _os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
            or _os.getenv("PYTEST_CURRENT_TEST") is not None
        )
    except Exception:
        _relax_fk = False

    if _relax_fk:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                key_id INTEGER,
                endpoint TEXT,
                status INTEGER,
                latency_ms INTEGER,
                bytes INTEGER,
                bytes_in INTEGER,
                meta TEXT
            )
            """
        )
    else:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                key_id INTEGER,
                endpoint TEXT,
                status INTEGER,
                latency_ms INTEGER,
                bytes INTEGER,
                bytes_in INTEGER,
                meta TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (key_id) REFERENCES api_keys(id) ON DELETE SET NULL
            )
            """
        )

    # Daily aggregate for reporting
    if _relax_fk:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_daily (
                user_id INTEGER NOT NULL,
                day DATE NOT NULL,
                requests INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                bytes_total INTEGER DEFAULT 0,
                latency_avg_ms REAL,
                PRIMARY KEY (user_id, day)
            )
            """
        )
    else:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_daily (
                user_id INTEGER NOT NULL,
                day DATE NOT NULL,
                requests INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                bytes_total INTEGER DEFAULT 0,
                latency_avg_ms REAL,
                PRIMARY KEY (user_id, day),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

    conn.commit()
    logger.info("Migration 013: Created RBAC rate limit and usage tables")


def migration_014_seed_roles_permissions(conn: sqlite3.Connection) -> None:
    """Seed default roles and a baseline permission catalog."""
    logger.info("Migration 014: START seed default roles + permissions")
    # Seed roles
    conn.execute(
        """
        INSERT OR IGNORE INTO roles (name, description, is_system)
        VALUES
          ('admin', 'Administrator (full access)', 1),
          ('user', 'Standard user (baseline permissions)', 1),
          ('moderator', 'Moderator (curated elevated access)', 1),
          ('reviewer', 'Claims reviewer', 1)
        """
    )

    # Seed permissions (align with AuthNZ/permissions.py constants; use name column)
    perms = [
        # media
        ('media.create','Create media','media'),
        ('media.read','Read media','media'),
        ('media.update','Update media','media'),
        ('media.delete','Delete media','media'),
        ('media.transcribe','Transcribe audio/video','media'),
        ('media.export','Export media','media'),
        # users
        ('users.create','Create users','users'),
        ('users.read','Read users','users'),
        ('users.update','Update users','users'),
        ('users.delete','Delete users','users'),
        ('users.manage_roles','Manage user roles','users'),
        ('users.invite','Invite users','users'),
        # system
        ('system.configure','Configure system','system'),
        ('system.backup','Backup system','system'),
        ('system.export','Export system data','system'),
        ('system.logs','View system logs','system'),
        ('system.maintenance','Maintenance operations','system'),
        # api
        ('api.generate_keys','Generate API keys','api'),
        ('api.manage_webhooks','Manage webhooks','api'),
        ('api.rate_limit_override','Override rate limits','api'),
        # claims
        ('claims.review','Review claims','claims'),
        ('claims.admin','Administer claims','claims')
    ]
    for name, description, category in perms:
        conn.execute(
            "INSERT OR IGNORE INTO permissions (name, description, category) VALUES (?, ?, ?)",
            (name, description, category),
        )

    # Helper: get id by name
    def _id(table: str, key: str) -> int:
        cur = conn.execute(f"SELECT id FROM {table} WHERE name = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    admin_id = _id('roles', 'admin')
    user_id = _id('roles', 'user')
    mod_id = _id('roles', 'moderator')
    reviewer_id = _id('roles', 'reviewer')

    # Grant all permissions to admin
    cur = conn.execute("SELECT id FROM permissions")
    for (perm_id,) in cur.fetchall():
        if admin_id is not None:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (admin_id, perm_id),
            )

    # Baseline user permissions
    baseline = [
        'media.create','media.read','media.update','media.transcribe',
        'users.read'
    ]
    for code in baseline:
        pid = _id('permissions', code)
        if pid is not None and user_id is not None:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (user_id, pid),
            )

    # Moderator: baseline + delete and some users.manage_roles
    mod_extra = ['media.delete', 'users.manage_roles']
    for code in set(baseline + mod_extra):
        pid = _id('permissions', code)
        if pid is not None and mod_id is not None:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (mod_id, pid),
            )

    # Reviewer: read media + claims.review
    reviewer_perms = ['media.read', 'claims.review']
    for code in reviewer_perms:
        pid = _id('permissions', code)
        if pid is not None and reviewer_id is not None:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (reviewer_id, pid),
            )

    conn.commit()
    logger.info("Migration 014: Seeded default roles and permissions")


def migration_015_create_llm_usage_tables(conn: sqlite3.Connection) -> None:
    """Create llm_usage_log and llm_usage_daily tables (SQLite)."""
    logger.info("Migration 015: START LLM usage tables")
    # Per-request LLM usage log
    try:
        import os as _os
        _relax_fk = (
            _os.getenv("DISABLE_USAGE_FOREIGN_KEYS", "").lower() in {"1", "true", "yes", "on"}
            or _os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
            or _os.getenv("PYTEST_CURRENT_TEST") is not None
        )
    except Exception:
        _relax_fk = False

    if _relax_fk:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                key_id INTEGER,
                endpoint TEXT,
                operation TEXT,
                provider TEXT,
                model TEXT,
                status INTEGER,
                latency_ms INTEGER,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                prompt_cost_usd REAL,
                completion_cost_usd REAL,
                total_cost_usd REAL,
                currency TEXT DEFAULT 'USD',
                estimated INTEGER DEFAULT 0,
                request_id TEXT
            )
            """
        )
    else:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                key_id INTEGER,
                endpoint TEXT,
                operation TEXT,
                provider TEXT,
                model TEXT,
                status INTEGER,
                latency_ms INTEGER,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                prompt_cost_usd REAL,
                completion_cost_usd REAL,
                total_cost_usd REAL,
                currency TEXT DEFAULT 'USD',
                estimated INTEGER DEFAULT 0,
                request_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (key_id) REFERENCES api_keys(id) ON DELETE SET NULL
            )
            """
        )

    # Helpful indexes for common queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_ts ON llm_usage_log(ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_user ON llm_usage_log(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_provider_model ON llm_usage_log(provider, model)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_op_ts ON llm_usage_log(operation, ts)")

    # Daily aggregate table
    if _relax_fk:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_usage_daily (
                day DATE NOT NULL,
                user_id INTEGER NOT NULL,
                operation TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                requests INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                total_cost_usd REAL DEFAULT 0.0,
                latency_avg_ms REAL,
                PRIMARY KEY (day, user_id, operation, provider, model)
            )
            """
        )
    else:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_usage_daily (
                day DATE NOT NULL,
                user_id INTEGER NOT NULL,
                operation TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                requests INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                total_cost_usd REAL DEFAULT 0.0,
                latency_avg_ms REAL,
                PRIMARY KEY (day, user_id, operation, provider, model),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

    conn.commit()
    logger.info("Migration 015: Created LLM usage tables (llm_usage_log, llm_usage_daily)")


def migration_016_create_orgs_teams(conn: sqlite3.Connection) -> None:
    """Create Organizations/Teams hierarchy tables (SQLite)."""
    logger.info("Migration 016: START organizations/teams tables")
    # organizations
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE,
            name TEXT UNIQUE NOT NULL,
            slug TEXT UNIQUE,
            owner_user_id INTEGER,
            is_active INTEGER DEFAULT 1,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orgs_owner ON organizations(owner_user_id)")

    # org_members
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS org_members (
            org_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'member',
            status TEXT DEFAULT 'active',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, user_id),
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_org_members_user ON org_members(user_id)")

    # teams
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            slug TEXT,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (org_id, name),
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_org ON teams(org_id)")

    # team_members
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS team_members (
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'member',
            status TEXT DEFAULT 'active',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (team_id, user_id),
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members(user_id)")

    conn.commit()
    logger.info("Migration 016: Created organizations, org_members, teams, team_members")


def migration_017_extend_api_keys_virtual(conn: sqlite3.Connection) -> None:
    """Extend api_keys table with Virtual Key fields (SQLite)."""
    # Helper to check column existence
    cur = conn.execute("PRAGMA table_info(api_keys)")
    cols = {row[1] for row in cur.fetchall()}

    def add_col(name: str, decl: str) -> None:
        if name not in cols:
            conn.execute(f"ALTER TABLE api_keys ADD COLUMN {decl}")

    add_col('is_virtual', "is_virtual INTEGER DEFAULT 0")
    add_col('parent_key_id', "parent_key_id INTEGER REFERENCES api_keys(id)")
    add_col('org_id', "org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL")
    add_col('team_id', "team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL")
    add_col('llm_budget_day_tokens', "llm_budget_day_tokens INTEGER")
    add_col('llm_budget_month_tokens', "llm_budget_month_tokens INTEGER")
    add_col('llm_budget_day_usd', "llm_budget_day_usd REAL")
    add_col('llm_budget_month_usd', "llm_budget_month_usd REAL")
    add_col('llm_allowed_endpoints', "llm_allowed_endpoints TEXT")
    add_col('llm_allowed_providers', "llm_allowed_providers TEXT")
    add_col('llm_allowed_models', "llm_allowed_models TEXT")

    # Helpful indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_virtual ON api_keys(is_virtual)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_org ON api_keys(org_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_team ON api_keys(team_id)")

    conn.commit()
    logger.info("Migration 017: Extended api_keys with virtual key fields")


def migration_018_add_usage_indexes(conn: sqlite3.Connection) -> None:
    """Add helpful indexes for usage tables (SQLite)."""
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_log_ts ON usage_log(ts)")
    except Exception:
        pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_log_user ON usage_log(user_id)")
    except Exception:
        pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_log_status ON usage_log(status)")
    except Exception:
        pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_daily_day_user ON usage_daily(day, user_id)")
    except Exception:
        pass
    conn.commit()
    logger.info("Migration 018: Added indexes for usage_log and usage_daily")


def migration_019_usage_log_add_request_id(conn: sqlite3.Connection) -> None:
    """Add request_id column to usage_log and index it (SQLite)."""
    try:
        conn.execute("ALTER TABLE usage_log ADD COLUMN request_id TEXT")
    except Exception:
        # Column may already exist
        pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_log_request_id ON usage_log(request_id)")
    except Exception:
        pass
    conn.commit()
    logger.info("Migration 019: Added request_id column to usage_log")


def migration_020_usage_log_add_bytes_in(conn: sqlite3.Connection) -> None:
    """Add bytes_in column to usage_log (SQLite)."""
    try:
        conn.execute("ALTER TABLE usage_log ADD COLUMN bytes_in INTEGER")
    except Exception:
        # Column may already exist
        pass
    conn.commit()
    logger.info("Migration 020: Added bytes_in column to usage_log")


def migration_021_usage_daily_add_bytes_in_total(conn: sqlite3.Connection) -> None:
    """Add bytes_in_total column to usage_daily (SQLite)."""
    try:
        conn.execute("ALTER TABLE usage_daily ADD COLUMN bytes_in_total INTEGER DEFAULT 0")
    except Exception:
        # Column may already exist
        pass
    conn.commit()
    logger.info("Migration 021: Added bytes_in_total column to usage_daily")


def migration_022_create_tool_catalogs(conn: sqlite3.Connection) -> None:
    """Create tables for MCP tool catalogs (SQLite)."""
    # tool_catalogs: scoped by (org_id, team_id) with name unique per scope
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tool_catalogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            org_id INTEGER,
            team_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, org_id, team_id),
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE SET NULL,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_catalogs_org_team ON tool_catalogs(org_id, team_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_catalogs_name ON tool_catalogs(name)")

    # tool_catalog_entries
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tool_catalog_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            catalog_id INTEGER NOT NULL,
            tool_name TEXT NOT NULL,
            module_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(catalog_id, tool_name),
            FOREIGN KEY (catalog_id) REFERENCES tool_catalogs(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_catalog_entries_catalog ON tool_catalog_entries(catalog_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_catalog_entries_tool ON tool_catalog_entries(tool_name)")
    conn.commit()
    logger.info("Migration 022: Created tool_catalogs and tool_catalog_entries tables")


def migration_023_create_virtual_key_counters(conn: sqlite3.Connection) -> None:
    """Create counters tables for virtual keys (SQLite)."""
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vk_jwt_counters (
                jti TEXT NOT NULL,
                counter_type TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (jti, counter_type)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vk_api_key_counters (
                api_key_id INTEGER NOT NULL,
                counter_type TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (api_key_id, counter_type)
            )
            """
        )
        # Helpful indexes for reporting/cleanup (best-effort)
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vk_jwt_counters_type ON vk_jwt_counters(counter_type)")
        except Exception:
            pass
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vk_api_key_counters_type ON vk_api_key_counters(counter_type)")
        except Exception:
            pass
        conn.commit()
        logger.info("Migration 023: Created virtual key counters tables")
    except Exception as e:
        logger.warning(f"Migration 023 skipped/failed: {e}")


def migration_024_ensure_api_keys_status_column(conn: sqlite3.Connection) -> None:
    """Ensure the api_keys table exposes a status column prior to creating status-based indexes."""
    try:
        teams_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='teams'"
        ).fetchone()
        orgs_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='organizations'"
        ).fetchone()
        if not teams_exists or not orgs_exists:
            migration_016_create_orgs_teams(conn)
    except Exception as error:
        logger.warning(f"Migration 024: unable to verify organization/team tables ({error})")

    try:
        cursor = conn.execute("PRAGMA table_info(api_keys)")
        columns = {row[1] for row in cursor.fetchall()}
        if "status" not in columns:
            conn.execute("ALTER TABLE api_keys ADD COLUMN status TEXT DEFAULT 'active'")
            conn.execute("UPDATE api_keys SET status = 'active' WHERE status IS NULL")
    except sqlite3.OperationalError as error:
        logger.warning(f"Migration 024 skipped: api_keys table unavailable ({error})")
        conn.commit()
        return
    except Exception as error:
        logger.warning(f"Migration 024 encountered an unexpected error inspecting api_keys: {error}")
        conn.commit()
        return

    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status)")
    except sqlite3.OperationalError as error:
        logger.warning(f"Migration 024: idx_api_keys_status creation skipped ({error})")
    conn.commit()
    logger.info("Migration 024: Ensured api_keys.status column and index")


def migration_025_team_members_added_at(conn: sqlite3.Connection) -> None:
    """Ensure team_members table exposes added_at column and backfill legacy data."""
    try:
        cursor = conn.execute("PRAGMA table_info(team_members)")
        columns = {row[1] for row in cursor.fetchall()}
    except sqlite3.OperationalError as error:
        logger.warning(f"Migration 025 skipped: team_members table unavailable ({error})")
        conn.commit()
        return

    if "added_at" not in columns:
        conn.execute(
            "ALTER TABLE team_members ADD COLUMN added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )

    if "joined_at" in columns:
        conn.execute(
            """
            UPDATE team_members
            SET added_at = COALESCE(added_at, joined_at, CURRENT_TIMESTAMP)
            """
        )

    conn.commit()
    logger.info("Migration 025: Ensured team_members.added_at column with backfill")


def migration_026_create_privilege_snapshots_table(conn: sqlite3.Connection) -> None:
    """Create privilege_snapshots table for snapshot storage."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS privilege_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            generated_at TEXT NOT NULL,
            generated_by TEXT NOT NULL,
            org_id TEXT,
            team_id TEXT,
            catalog_version TEXT NOT NULL,
            summary_json TEXT,
            scope_index TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_priv_snapshots_generated_at ON privilege_snapshots(generated_at)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_priv_snapshots_org ON privilege_snapshots(org_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_priv_snapshots_team ON privilege_snapshots(team_id)")
    conn.commit()
    logger.info("Migration 026: Created privilege_snapshots table")


def rollback_026_drop_privilege_snapshots_table(conn: sqlite3.Connection) -> None:
    """Drop privilege_snapshots table during rollback/testing."""
    conn.execute("DROP TABLE IF EXISTS privilege_snapshots")
    conn.commit()
    logger.info("Rollback 026: Dropped privilege_snapshots table")
#######################################################################################################################
#
# Additional maintenance migrations
#


def migration_027_add_session_revocation_columns(conn: sqlite3.Connection) -> None:
    """Ensure sessions table has revocation bookkeeping columns for legacy upgrades."""
    try:
        cursor = conn.execute("PRAGMA table_info(sessions)")
        rows = cursor.fetchall()
        columns = {row[1] for row in rows}

        def add_col(name: str, decl: str):
            if name not in columns:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {decl}")
                columns.add(name)

        add_col("is_active", "is_active INTEGER DEFAULT 1")
        add_col("is_revoked", "is_revoked INTEGER DEFAULT 0")
        add_col("revoked_at", "revoked_at TIMESTAMP")
        add_col("revoked_by", "revoked_by INTEGER")
        add_col("revoke_reason", "revoke_reason TEXT")
        conn.commit()
        logger.info("Migration 027: Harmonized session revocation columns")
    except Exception as exc:
        logger.warning(f"Migration 027: Unable to harmonize session columns: {exc}")


def migration_028_create_org_invites(conn: sqlite3.Connection) -> None:
    """Create org_invites table for shareable invite codes."""
    logger.info("Migration 028: START org_invites table")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS org_invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            org_id INTEGER NOT NULL,
            team_id INTEGER,
            role_to_grant TEXT DEFAULT 'member',
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            max_uses INTEGER DEFAULT 1,
            uses_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            description TEXT,
            metadata TEXT,
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_org_invites_code ON org_invites(code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_org_invites_org_active ON org_invites(org_id, is_active)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_org_invites_expires ON org_invites(expires_at)")
    conn.commit()
    logger.info("Migration 028: Created org_invites table")


def rollback_028_drop_org_invites_table(conn: sqlite3.Connection) -> None:
    """Drop org_invites table during rollback/testing."""
    conn.execute("DROP TABLE IF EXISTS org_invites")
    conn.commit()
    logger.info("Rollback 028: Dropped org_invites table")


def migration_029_create_org_invite_redemptions(conn: sqlite3.Connection) -> None:
    """Create org_invite_redemptions table to track who redeemed invites."""
    logger.info("Migration 029: START org_invite_redemptions table")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS org_invite_redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invite_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (invite_id) REFERENCES org_invites(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(invite_id, user_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_invite_redemptions_invite ON org_invite_redemptions(invite_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_invite_redemptions_user ON org_invite_redemptions(user_id)")
    conn.commit()
    logger.info("Migration 029: Created org_invite_redemptions table")


def rollback_029_drop_org_invite_redemptions_table(conn: sqlite3.Connection) -> None:
    """Drop org_invite_redemptions table during rollback/testing."""
    conn.execute("DROP TABLE IF EXISTS org_invite_redemptions")
    conn.commit()
    logger.info("Rollback 029: Dropped org_invite_redemptions table")


def migration_030_create_subscription_plans(conn: sqlite3.Connection) -> None:
    """Create subscription_plans table for plan tier definitions."""
    logger.info("Migration 030: START subscription_plans table")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS subscription_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            stripe_product_id TEXT,
            stripe_price_id TEXT,
            stripe_price_id_yearly TEXT,
            price_usd_monthly REAL DEFAULT 0,
            price_usd_yearly REAL DEFAULT 0,
            limits_json TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            is_public INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subscription_plans_name ON subscription_plans(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subscription_plans_active ON subscription_plans(is_active)")

    # Seed default plans
    default_plans = [
        {
            "name": "free",
            "display_name": "Free",
            "description": "Get started with basic features",
            "price_usd_monthly": 0,
            "price_usd_yearly": 0,
            "sort_order": 0,
            "limits_json": json.dumps({
                "storage_mb": 1024,
                "api_calls_day": 100,
                "api_calls_month": 3000,
                "llm_tokens_day": 10000,
                "llm_tokens_month": 300000,
                "llm_cost_month_usd": 0,
                "transcription_minutes_month": 10,
                "rag_queries_day": 50,
                "concurrent_jobs": 1,
                "team_members": 1,
                "rate_limit_rpm": 10,
                "features": ["basic_search", "fts5_search", "basic_chat"]
            })
        },
        {
            "name": "pro",
            "display_name": "Pro",
            "description": "For power users and small teams",
            "price_usd_monthly": 29,
            "price_usd_yearly": 290,
            "sort_order": 1,
            "limits_json": json.dumps({
                "storage_mb": 10240,
                "api_calls_day": 5000,
                "api_calls_month": 150000,
                "llm_tokens_day": 500000,
                "llm_tokens_month": 15000000,
                "llm_cost_month_usd": 50,
                "transcription_minutes_month": 300,
                "rag_queries_day": 500,
                "concurrent_jobs": 5,
                "team_members": 5,
                "rate_limit_rpm": 120,
                "features": ["*", "rag_advanced", "vector_search", "priority_support"]
            })
        },
        {
            "name": "enterprise",
            "display_name": "Enterprise",
            "description": "For organizations with advanced needs",
            "price_usd_monthly": 199,
            "price_usd_yearly": 1990,
            "sort_order": 2,
            "limits_json": json.dumps({
                "storage_mb": 102400,
                "api_calls_day": 50000,
                "api_calls_month": 1500000,
                "llm_tokens_day": 5000000,
                "llm_tokens_month": 150000000,
                "llm_cost_month_usd": 500,
                "transcription_minutes_month": 3000,
                "rag_queries_day": 5000,
                "concurrent_jobs": 20,
                "team_members": -1,
                "rate_limit_rpm": 600,
                "features": ["*", "sso", "audit_logs", "dedicated_support", "custom_models"]
            })
        }
    ]

    for plan in default_plans:
        conn.execute(
            """
            INSERT OR IGNORE INTO subscription_plans
            (name, display_name, description, price_usd_monthly, price_usd_yearly, limits_json, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (plan["name"], plan["display_name"], plan["description"],
             plan["price_usd_monthly"], plan["price_usd_yearly"], plan["limits_json"], plan["sort_order"])
        )

    conn.commit()
    logger.info("Migration 030: Created subscription_plans table with default plans")


def rollback_030_drop_subscription_plans_table(conn: sqlite3.Connection) -> None:
    """Drop subscription_plans table during rollback/testing."""
    conn.execute("DROP TABLE IF EXISTS subscription_plans")
    conn.commit()
    logger.info("Rollback 030: Dropped subscription_plans table")


def migration_031_create_org_subscriptions(conn: sqlite3.Connection) -> None:
    """Create org_subscriptions table for organization subscription state."""
    logger.info("Migration 031: START org_subscriptions table")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS org_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL UNIQUE,
            plan_id INTEGER NOT NULL,
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
            cancel_at_period_end INTEGER DEFAULT 0,
            custom_limits_json TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (plan_id) REFERENCES subscription_plans(id) ON DELETE RESTRICT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_org_subs_org ON org_subscriptions(org_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_org_subs_stripe_customer ON org_subscriptions(stripe_customer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_org_subs_stripe_sub ON org_subscriptions(stripe_subscription_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_org_subs_status ON org_subscriptions(status)")
    conn.commit()
    logger.info("Migration 031: Created org_subscriptions table")


def rollback_031_drop_org_subscriptions_table(conn: sqlite3.Connection) -> None:
    """Drop org_subscriptions table during rollback/testing."""
    conn.execute("DROP TABLE IF EXISTS org_subscriptions")
    conn.commit()
    logger.info("Rollback 031: Dropped org_subscriptions table")


def migration_032_create_stripe_webhook_events(conn: sqlite3.Connection) -> None:
    """Create stripe_webhook_events table for idempotency and audit."""
    logger.info("Migration 032: START stripe_webhook_events table")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS stripe_webhook_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stripe_event_id TEXT UNIQUE NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            processed_at TIMESTAMP,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stripe_events_event_id ON stripe_webhook_events(stripe_event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stripe_events_type ON stripe_webhook_events(event_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stripe_events_status ON stripe_webhook_events(status)")
    conn.commit()
    logger.info("Migration 032: Created stripe_webhook_events table")


def rollback_032_drop_stripe_webhook_events_table(conn: sqlite3.Connection) -> None:
    """Drop stripe_webhook_events table during rollback/testing."""
    conn.execute("DROP TABLE IF EXISTS stripe_webhook_events")
    conn.commit()
    logger.info("Rollback 032: Dropped stripe_webhook_events table")


def migration_033_create_payment_history(conn: sqlite3.Connection) -> None:
    """Create payment_history table for invoice display."""
    logger.info("Migration 033: START payment_history table")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            stripe_invoice_id TEXT,
            stripe_payment_intent_id TEXT,
            amount_cents INTEGER NOT NULL,
            currency TEXT DEFAULT 'usd',
            status TEXT NOT NULL,
            description TEXT,
            invoice_pdf_url TEXT,
            receipt_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_payment_history_org ON payment_history(org_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_payment_history_org_date ON payment_history(org_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_payment_history_stripe_invoice ON payment_history(stripe_invoice_id)")
    conn.commit()
    logger.info("Migration 033: Created payment_history table")


def rollback_033_drop_payment_history_table(conn: sqlite3.Connection) -> None:
    """Drop payment_history table during rollback/testing."""
    conn.execute("DROP TABLE IF EXISTS payment_history")
    conn.commit()
    logger.info("Rollback 033: Dropped payment_history table")


def migration_034_create_billing_audit_log(conn: sqlite3.Connection) -> None:
    """Create billing_audit_log table for billing operation audit trail."""
    logger.info("Migration 034: START billing_audit_log table")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS billing_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_billing_audit_org ON billing_audit_log(org_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_billing_audit_action ON billing_audit_log(action)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_billing_audit_created ON billing_audit_log(created_at)")
    conn.commit()
    logger.info("Migration 034: Created billing_audit_log table")


def rollback_034_drop_billing_audit_log_table(conn: sqlite3.Connection) -> None:
    """Drop billing_audit_log table during rollback/testing."""
    conn.execute("DROP TABLE IF EXISTS billing_audit_log")
    conn.commit()
    logger.info("Rollback 034: Dropped billing_audit_log table")


def migration_035_backfill_storage_mb_limits(conn: sqlite3.Connection) -> None:
    """Normalize storage limits to storage_mb in plan and custom limit JSON."""
    logger.info("Migration 035: START storage_mb limit backfill")

    def _normalize_limits_json(raw_json: str) -> Optional[str]:
        if not raw_json:
            return None
        try:
            data = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(data, dict):
            return None

        changed = False
        if "storage_gb" in data:
            storage_mb = None
            try:
                storage_mb = int(float(data["storage_gb"]) * 1024)
            except (TypeError, ValueError):
                storage_mb = None
            if storage_mb is not None and "storage_mb" not in data:
                data["storage_mb"] = storage_mb
            data.pop("storage_gb", None)
            changed = True
        return json.dumps(data) if changed else None

    # Update subscription plans.
    cur = conn.execute("SELECT id, limits_json FROM subscription_plans")
    rows = cur.fetchall()
    for plan_id, limits_json in rows:
        updated = _normalize_limits_json(limits_json)
        if updated is not None:
            conn.execute(
                "UPDATE subscription_plans SET limits_json = ? WHERE id = ?",
                (updated, plan_id),
            )

    # Update org custom limits.
    cur = conn.execute(
        "SELECT id, custom_limits_json FROM org_subscriptions WHERE custom_limits_json IS NOT NULL"
    )
    rows = cur.fetchall()
    for sub_id, limits_json in rows:
        updated = _normalize_limits_json(limits_json)
        if updated is not None:
            conn.execute(
                "UPDATE org_subscriptions SET custom_limits_json = ? WHERE id = ?",
                (updated, sub_id),
            )

    conn.commit()
    logger.info("Migration 035: Completed storage_mb limit backfill")


def migration_036_create_user_provider_secrets(conn: sqlite3.Connection) -> None:
    """Create the user_provider_secrets table for per-user BYOK credentials."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_provider_secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            encrypted_blob TEXT NOT NULL,
            key_hint TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (user_id, provider)
        )
        """
    )

    # Harmonize legacy schemas: add missing columns if needed
    try:
        cur = conn.execute("PRAGMA table_info(user_provider_secrets)")
        cols = {row[1] for row in cur.fetchall()}

        def add_col(name: str, decl: str):
            if name not in cols:
                conn.execute(f"ALTER TABLE user_provider_secrets ADD COLUMN {decl}")
                cols.add(name)

        add_col("encrypted_blob", "encrypted_blob TEXT")
        add_col("key_hint", "key_hint TEXT")
        add_col("metadata", "metadata TEXT")
        add_col("created_at", "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        add_col("updated_at", "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        add_col("last_used_at", "last_used_at TIMESTAMP")
    except Exception:
        pass

    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_provider_secrets_user_id ON user_provider_secrets(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_provider_secrets_provider ON user_provider_secrets(provider)")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_provider_secrets_user_provider "
        "ON user_provider_secrets(user_id, provider)"
    )

    conn.commit()
    logger.info("Migration 036: Created user_provider_secrets table")


def rollback_036_drop_user_provider_secrets_table(conn: sqlite3.Connection) -> None:
    """Rollback migration 036 by dropping the user_provider_secrets table."""
    conn.execute("DROP TABLE IF EXISTS user_provider_secrets")
    conn.commit()
    logger.info("Rollback 036: Dropped user_provider_secrets table")


def migration_037_create_org_provider_secrets(conn: sqlite3.Connection) -> None:
    """Create the org_provider_secrets table for org/team shared BYOK credentials."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS org_provider_secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_type TEXT NOT NULL,
            scope_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            encrypted_blob TEXT NOT NULL,
            key_hint TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP,
            UNIQUE (scope_type, scope_id, provider)
        )
        """
    )

    # Harmonize legacy schemas: add missing columns if needed
    try:
        cur = conn.execute("PRAGMA table_info(org_provider_secrets)")
        cols = {row[1] for row in cur.fetchall()}

        def add_col(name: str, decl: str):
            if name not in cols:
                conn.execute(f"ALTER TABLE org_provider_secrets ADD COLUMN {decl}")
                cols.add(name)

        add_col("encrypted_blob", "encrypted_blob TEXT")
        add_col("key_hint", "key_hint TEXT")
        add_col("metadata", "metadata TEXT")
        add_col("created_at", "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        add_col("updated_at", "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        add_col("last_used_at", "last_used_at TIMESTAMP")
    except Exception:
        pass

    conn.execute("CREATE INDEX IF NOT EXISTS idx_org_provider_secrets_scope ON org_provider_secrets(scope_type, scope_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_org_provider_secrets_provider ON org_provider_secrets(provider)")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_org_provider_secrets_scope_provider "
        "ON org_provider_secrets(scope_type, scope_id, provider)"
    )

    conn.commit()
    logger.info("Migration 037: Created org_provider_secrets table")


def rollback_037_drop_org_provider_secrets_table(conn: sqlite3.Connection) -> None:
    """Rollback migration 037 by dropping the org_provider_secrets table."""
    conn.execute("DROP TABLE IF EXISTS org_provider_secrets")
    conn.commit()
    logger.info("Rollback 037: Dropped org_provider_secrets table")


def migration_038_add_org_provider_secrets_cleanup_triggers(conn: sqlite3.Connection) -> None:
    """Add cleanup triggers for org_provider_secrets when orgs/teams are deleted."""
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS delete_org_provider_secrets_on_org_delete
            AFTER DELETE ON organizations
            FOR EACH ROW
        BEGIN
            DELETE FROM org_provider_secrets WHERE scope_type = 'org' AND scope_id = OLD.id;
        END;
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS delete_org_provider_secrets_on_team_delete
            AFTER DELETE ON teams
            FOR EACH ROW
        BEGIN
            DELETE FROM org_provider_secrets WHERE scope_type = 'team' AND scope_id = OLD.id;
        END;
        """
    )
    conn.commit()
    logger.info("Migration 038: Added org_provider_secrets cleanup triggers")


def rollback_038_drop_org_provider_secrets_cleanup_triggers(conn: sqlite3.Connection) -> None:
    """Rollback migration 038 by dropping org_provider_secrets cleanup triggers."""
    conn.execute("DROP TRIGGER IF EXISTS delete_org_provider_secrets_on_org_delete")
    conn.execute("DROP TRIGGER IF EXISTS delete_org_provider_secrets_on_team_delete")
    conn.commit()
    logger.info("Rollback 038: Dropped org_provider_secrets cleanup triggers")


def migration_039_ensure_user_storage_columns(conn: sqlite3.Connection) -> None:
    """Ensure legacy users tables include storage quota/usage columns."""
    logger.info("Migration 039: START ensure storage columns on users table")
    try:
        cur = conn.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cur.fetchall()}

        if "storage_quota_mb" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN storage_quota_mb INTEGER DEFAULT 5120")
            columns.add("storage_quota_mb")

        if "storage_used_mb" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN storage_used_mb INTEGER DEFAULT 0")
            columns.add("storage_used_mb")

        conn.commit()
        logger.info("Migration 039: storage columns ensured on users table")
    except Exception as exc:
        logger.error("Migration 039: failed to ensure storage columns: %s", exc)
        raise


def migration_040_extend_registration_codes_for_org_invites(conn: sqlite3.Connection) -> None:
    """Add org-scoped invite columns and missing registration code fields."""
    logger.info("Migration 040: START registration_codes org invite fields")
    cur = conn.execute("PRAGMA table_info(registration_codes)")
    columns = {row[1] for row in cur.fetchall()}

    def add_col(name: str, decl: str) -> None:
        if name not in columns:
            conn.execute(f"ALTER TABLE registration_codes ADD COLUMN {decl}")
            columns.add(name)

    # Core fields expected by registration/admin flows
    add_col("role_to_grant", "role_to_grant TEXT DEFAULT 'user'")
    add_col("description", "description TEXT")
    add_col("allowed_email_domain", "allowed_email_domain TEXT")
    add_col("times_used", "times_used INTEGER DEFAULT 0")
    add_col("is_active", "is_active INTEGER DEFAULT 1")
    add_col("metadata", "metadata TEXT")

    # Org-scoped invite extension
    add_col("org_id", "org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL")
    add_col("org_role", "org_role TEXT")
    add_col("team_id", "team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL")

    # Backfill times_used from legacy uses_count if present
    if "uses_count" in columns and "times_used" in columns:
        conn.execute(
            """
            UPDATE registration_codes
            SET times_used = uses_count
            WHERE (times_used IS NULL OR times_used = 0)
              AND uses_count > 0
            """
        )

    conn.commit()
    logger.info("Migration 040: Updated registration_codes for org invites")


def migration_041_add_llm_provider_overrides(conn: sqlite3.Connection) -> None:
    """Add llm_provider_overrides table for runtime provider overrides."""
    logger.info("Migration 041: START llm_provider_overrides table")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_provider_overrides (
            provider TEXT PRIMARY KEY,
            is_enabled INTEGER,
            allowed_models TEXT,
            config_json TEXT,
            secret_blob TEXT,
            api_key_hint TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_llm_provider_overrides_enabled ON llm_provider_overrides(is_enabled)"
    )
    conn.commit()
    logger.info("Migration 041: Created llm_provider_overrides table")


def rollback_041_drop_llm_provider_overrides(conn: sqlite3.Connection) -> None:
    """Rollback migration 041 by dropping llm_provider_overrides table."""
    conn.execute("DROP TABLE IF EXISTS llm_provider_overrides")
    conn.commit()
    logger.info("Rollback 041: Dropped llm_provider_overrides table")


def migration_042_create_org_budgets(conn: sqlite3.Connection) -> None:
    """Create org_budgets table and migrate legacy budget data."""
    logger.info("Migration 042: START org_budgets table")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS org_budgets (
            org_id INTEGER PRIMARY KEY,
            budgets_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_org_budgets_org ON org_budgets(org_id)")

    def _normalize_alert_thresholds(value: Any) -> Optional[Dict[str, Any]]:
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

    def _normalize_enforcement_mode(value: Any) -> Optional[Dict[str, Any]]:
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

    def _inflate_legacy_budgets(legacy: Dict[str, Any]) -> Dict[str, Any]:
        budgets = {key: legacy[key] for key in ("budget_day_usd", "budget_month_usd", "budget_day_tokens", "budget_month_tokens") if key in legacy}
        payload: Dict[str, Any] = {}
        if budgets:
            payload["budgets"] = budgets
        thresholds = _normalize_alert_thresholds(legacy.get("alert_thresholds"))
        if thresholds is not None:
            payload["alert_thresholds"] = thresholds
        enforcement = _normalize_enforcement_mode(legacy.get("enforcement_mode"))
        if enforcement is not None:
            payload["enforcement_mode"] = enforcement
        return payload

    cur = conn.execute(
        "SELECT org_id, custom_limits_json FROM org_subscriptions WHERE custom_limits_json IS NOT NULL"
    )
    rows = cur.fetchall()
    for org_id, custom_limits_json in rows:
        if not custom_limits_json:
            continue
        try:
            data = json.loads(custom_limits_json)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        legacy_budgets = data.get("budgets")
        if not isinstance(legacy_budgets, dict):
            continue
        payload = _inflate_legacy_budgets(legacy_budgets)
        if payload:
            conn.execute(
                """
                INSERT OR REPLACE INTO org_budgets (org_id, budgets_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (org_id, json.dumps(payload)),
            )
        data.pop("budgets", None)
        conn.execute(
            "UPDATE org_subscriptions SET custom_limits_json = ? WHERE org_id = ?",
            (json.dumps(data) if data else None, org_id),
        )

    conn.commit()
    logger.info("Migration 042: Created org_budgets table and migrated legacy budgets")


def rollback_042_drop_org_budgets(conn: sqlite3.Connection) -> None:
    """Rollback migration 042 by dropping org_budgets table."""
    conn.execute("DROP TABLE IF EXISTS org_budgets")
    conn.commit()
    logger.info("Rollback 042: Dropped org_budgets table")


def migration_043_create_retention_policy_overrides(conn: sqlite3.Connection) -> None:
    """Create retention_policy_overrides table for persisted retention settings."""
    logger.info("Migration 043: START retention_policy_overrides table")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS retention_policy_overrides (
            policy_key TEXT PRIMARY KEY,
            days INTEGER NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    logger.info("Migration 043: Created retention_policy_overrides table")


def rollback_043_drop_retention_policy_overrides(conn: sqlite3.Connection) -> None:
    """Rollback migration 043 by dropping retention_policy_overrides table."""
    conn.execute("DROP TABLE IF EXISTS retention_policy_overrides")
    conn.commit()
    logger.info("Rollback 043: Dropped retention_policy_overrides table")


def migration_044_add_api_keys_key_id(conn: sqlite3.Connection) -> None:
    """Add key_id column + index for api_keys (SQLite)."""
    try:
        cur = conn.execute("PRAGMA table_info(api_keys)")
        cols = {row[1] for row in cur.fetchall()}
        if "key_id" not in cols:
            conn.execute("ALTER TABLE api_keys ADD COLUMN key_id TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_key_id ON api_keys(key_id)")
        conn.commit()
        logger.info("Migration 044: Added api_keys.key_id + index")
    except Exception as error:
        logger.warning(f"Migration 044 skipped or failed: {error}")


#######################################################################################################################
#
# Migration Registry
#

def get_authnz_migrations() -> List[Migration]:
    """Get all AuthNZ migrations in order"""
    return [
        Migration(1, "Create users table", migration_001_create_users_table, rollback_001_drop_users_table),
        Migration(2, "Create sessions table", migration_002_create_sessions_table, rollback_002_drop_sessions_table),
        Migration(3, "Create api_keys table", migration_003_create_api_keys_table, rollback_003_drop_api_keys_table),
        Migration(4, "Create api_key_audit_log table", migration_004_create_api_key_audit_log),
        Migration(5, "Create rate_limits table", migration_005_create_rate_limits_table),
        Migration(6, "Create registration_codes table", migration_006_create_registration_codes_table),
        Migration(7, "Create audit_logs table", migration_007_create_audit_logs_table),
        Migration(8, "Add password_history table", migration_008_add_password_history_table),
        Migration(9, "Add session encryption columns", migration_009_add_session_encryption_columns),
        Migration(10, "Add 2FA columns to users", migration_010_add_2fa_columns),
        Migration(11, "Enhanced auth tables + uuid", migration_011_add_enhanced_auth_tables),
        Migration(12, "Create RBAC core tables", migration_012_create_rbac_tables),
        Migration(13, "Create RBAC limits and usage tables", migration_013_create_rbac_limits_and_usage),
        Migration(14, "Seed default roles and permissions", migration_014_seed_roles_permissions),
        Migration(15, "Create LLM usage tables", migration_015_create_llm_usage_tables),
        Migration(16, "Create organizations and teams tables", migration_016_create_orgs_teams),
        Migration(17, "Extend api_keys with virtual key fields", migration_017_extend_api_keys_virtual),
        Migration(18, "Add indexes for usage tables", migration_018_add_usage_indexes),
        Migration(19, "Add request_id to usage_log", migration_019_usage_log_add_request_id),
        Migration(20, "Add bytes_in to usage_log", migration_020_usage_log_add_bytes_in),
        Migration(21, "Add bytes_in_total to usage_daily", migration_021_usage_daily_add_bytes_in_total),
        Migration(22, "Create tool catalogs tables", migration_022_create_tool_catalogs),
        Migration(23, "Create virtual key counters tables", migration_023_create_virtual_key_counters),
        Migration(24, "Ensure api_keys status column before index", migration_024_ensure_api_keys_status_column),
        Migration(25, "Backfill team_members added_at column", migration_025_team_members_added_at),
        Migration(
            26,
            "Create privilege_snapshots table",
            migration_026_create_privilege_snapshots_table,
            rollback_026_drop_privilege_snapshots_table,
        ),
        Migration(
            27,
            "Ensure session revocation columns",
            migration_027_add_session_revocation_columns,
        ),
        Migration(28, "Create org_invites table", migration_028_create_org_invites, rollback_028_drop_org_invites_table),
        Migration(
            29,
            "Create org_invite_redemptions table",
            migration_029_create_org_invite_redemptions,
            rollback_029_drop_org_invite_redemptions_table,
        ),
        Migration(
            30,
            "Create subscription_plans table",
            migration_030_create_subscription_plans,
            rollback_030_drop_subscription_plans_table,
        ),
        Migration(
            31,
            "Create org_subscriptions table",
            migration_031_create_org_subscriptions,
            rollback_031_drop_org_subscriptions_table,
        ),
        Migration(
            32,
            "Create stripe_webhook_events table",
            migration_032_create_stripe_webhook_events,
            rollback_032_drop_stripe_webhook_events_table,
        ),
        Migration(
            33,
            "Create payment_history table",
            migration_033_create_payment_history,
            rollback_033_drop_payment_history_table,
        ),
        Migration(
            34,
            "Create billing_audit_log table",
            migration_034_create_billing_audit_log,
            rollback_034_drop_billing_audit_log_table,
        ),
        Migration(
            35,
            "Backfill storage_mb limits",
            migration_035_backfill_storage_mb_limits,
        ),
        Migration(
            36,
            "Create user_provider_secrets table",
            migration_036_create_user_provider_secrets,
            rollback_036_drop_user_provider_secrets_table,
        ),
        Migration(
            37,
            "Create org_provider_secrets table",
            migration_037_create_org_provider_secrets,
            rollback_037_drop_org_provider_secrets_table,
        ),
        Migration(
            38,
            "Add org_provider_secrets cleanup triggers",
            migration_038_add_org_provider_secrets_cleanup_triggers,
            rollback_038_drop_org_provider_secrets_cleanup_triggers,
        ),
        Migration(
            39,
            "Ensure users storage columns",
            migration_039_ensure_user_storage_columns,
        ),
        Migration(
            40,
            "Extend registration_codes for org invites",
            migration_040_extend_registration_codes_for_org_invites,
        ),
        Migration(
            41,
            "Add llm_provider_overrides table",
            migration_041_add_llm_provider_overrides,
            rollback_041_drop_llm_provider_overrides,
        ),
        Migration(
            42,
            "Create org_budgets table",
            migration_042_create_org_budgets,
            rollback_042_drop_org_budgets,
        ),
        Migration(
            43,
            "Create retention_policy_overrides table",
            migration_043_create_retention_policy_overrides,
            rollback_043_drop_retention_policy_overrides,
        ),
        Migration(
            44,
            "Add api_keys.key_id column",
            migration_044_add_api_keys_key_id,
        ),
    ]


def apply_authnz_migrations(db_path: Path, target_version: int = None) -> None:
    """
    Apply AuthNZ migrations to a database

    Args:
        db_path: Path to the database file
        target_version: Target migration version (None = latest)
    """
    manager = MigrationManager(db_path)
    try:
        from loguru import logger as _logger
        _latest = len(get_authnz_migrations())
        _logger.info(
            f"AuthNZ.apply_migrations: db={db_path} target={'latest' if target_version is None else target_version} latest={_latest}"
        )
    except Exception:
        pass

    # Add all migrations to the manager
    for migration in get_authnz_migrations():
        manager.add_migration(migration)

    # Apply migrations
    manager.migrate(target_version)

    logger.info(f"Applied AuthNZ migrations to {db_path}")


def rollback_authnz_migrations(db_path: Path, target_version: int = 0) -> None:
    """
    Rollback AuthNZ migrations

    Args:
        db_path: Path to the database file
        target_version: Target migration version to rollback to
    """
    manager = MigrationManager(db_path)

    # Add all migrations to the manager
    for migration in get_authnz_migrations():
        manager.add_migration(migration)

    # Rollback migrations
    manager.rollback(target_version)

    logger.info(f"Rolled back AuthNZ migrations to version {target_version}")


#######################################################################################################################
#
# Utility Functions
#

def check_migration_status(db_path: Path) -> dict:
    """
    Check the migration status of a database

    Args:
        db_path: Path to the database file

    Returns:
        Dictionary with migration status information
    """
    manager = MigrationManager(db_path)

    # Add all migrations
    for migration in get_authnz_migrations():
        manager.add_migration(migration)

    current_version = manager.get_current_version()
    pending = manager.get_pending_migrations()

    return {
        "current_version": current_version,
        "latest_version": len(get_authnz_migrations()),
        "pending_migrations": [{"version": m.version, "name": m.name} for m in pending],
        "is_up_to_date": len(pending) == 0
    }


def ensure_authnz_tables(db_path: Path) -> None:
    """
    Ensure all AuthNZ tables exist in the database

    Args:
        db_path: Path to the database file
    """
    # Check current status
    status = check_migration_status(db_path)

    if not status["is_up_to_date"]:
        logger.info(
            f"Database needs migrations for {db_path}. Current: {status['current_version']}, Latest: {status['latest_version']}"
        )
        apply_authnz_migrations(db_path)
    else:
        logger.debug("AuthNZ tables are up to date")


#
# End of migrations.py
#######################################################################################################################
