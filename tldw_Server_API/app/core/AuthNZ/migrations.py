# migrations.py
# Description: Database migrations for AuthNZ module tables
#
# Imports
from typing import List
import sqlite3
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
    # Seed roles
    conn.execute(
        """
        INSERT OR IGNORE INTO roles (name, description, is_system)
        VALUES
          ('admin', 'Administrator (full access)', 1),
          ('user', 'Standard user (baseline permissions)', 1),
          ('moderator', 'Moderator (curated elevated access)', 1)
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
        ('api.rate_limit_override','Override rate limits','api')
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

    conn.commit()
    logger.info("Migration 014: Seeded default roles and permissions")


def migration_015_create_llm_usage_tables(conn: sqlite3.Connection) -> None:
    """Create llm_usage_log and llm_usage_daily tables (SQLite)."""
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
    ]


def apply_authnz_migrations(db_path: Path, target_version: int = None) -> None:
    """
    Apply AuthNZ migrations to a database

    Args:
        db_path: Path to the database file
        target_version: Target migration version (None = latest)
    """
    manager = MigrationManager(db_path)

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
        logger.info(f"Database needs migrations. Current: {status['current_version']}, Latest: {status['latest_version']}")
        apply_authnz_migrations(db_path)
    else:
        logger.debug("AuthNZ tables are up to date")


#
# End of migrations.py
#######################################################################################################################
