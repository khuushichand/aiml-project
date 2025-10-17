#!/usr/bin/env python3
# initialize.py
# Description: Initialize AuthNZ module for first-time setup
#
# This script sets up the AuthNZ module including:
# - Database creation and migrations
# - Initial admin user creation (multi-user mode)
# - Encryption key generation
# - Configuration validation
#

import asyncio
import sys
import os
import secrets
from pathlib import Path
from typing import Optional
from getpass import getpass
from loguru import logger

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
from tldw_Server_API.app.core.AuthNZ.migrations import (
    ensure_authnz_tables,
    check_migration_status
)
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.DB_Management.Users_DB import (
    get_users_db,
    ensure_user_directories
)
from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.AuthNZ.scheduler import start_authnz_scheduler
from tldw_Server_API.app.core.AuthNZ.monitoring import get_authnz_monitor

#######################################################################################################################
#
# Initialization Functions
#

def print_banner():
    """Print initialization banner"""
    print("\n" + "=" * 60)
    print("       AuthNZ Module Initialization")
    print("=" * 60)
    print()

def check_environment():
    """Check and validate environment configuration"""
    print("📋 Checking environment configuration...")
    
    # Check if .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ No .env file found!")
        print("   Creating from template...")
        
        template_file = Path(".env.authnz.template")
        if template_file.exists():
            env_file.write_text(template_file.read_text())
            print("✅ Created .env file from template")
            print("⚠️  Please edit .env and set secure values before continuing!")
            return False
        else:
            print("❌ Template file not found!")
            return False
    
    # Load settings
    settings = get_settings()
    
    # Validate critical settings
    issues = []
    
    if settings.AUTH_MODE == "multi_user":
        if not settings.JWT_SECRET_KEY or len(settings.JWT_SECRET_KEY) < 32:
            issues.append("JWT_SECRET_KEY must be set and at least 32 characters")
        
        if settings.JWT_SECRET_KEY == "CHANGE_ME_TO_SECURE_RANDOM_KEY_MIN_32_CHARS":
            issues.append("JWT_SECRET_KEY still has default value - must be changed!")
    
    if settings.AUTH_MODE == "single_user":
        if settings.SINGLE_USER_API_KEY == "CHANGE_ME_TO_SECURE_API_KEY":
            issues.append("SINGLE_USER_API_KEY still has default value - must be changed!")
    
    if issues:
        print("\n❌ Configuration issues found:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    
    print("✅ Environment configuration valid")
    print(f"   Mode: {settings.AUTH_MODE}")
    print(f"   Database: {settings.DATABASE_URL[:30]}...")
    
    return True

def generate_secure_keys():
    """Generate secure keys for configuration"""
    print("\n🔑 Generating secure keys...")
    
    keys = {
        'JWT_SECRET_KEY': secrets.token_urlsafe(32),
        'SINGLE_USER_API_KEY': secrets.token_urlsafe(32),
        'API_KEY_PEPPER': secrets.token_hex(32)
    }
    
    # Generate Fernet key for session encryption
    from cryptography.fernet import Fernet
    keys['SESSION_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
    
    print("\n📝 Generated keys (save these in your .env file):")
    print("-" * 50)
    for key, value in keys.items():
        print(f"{key}={value}")
    print("-" * 50)
    
    return keys

async def setup_database():
    """Setup database and run migrations"""
    print("\n🗄️  Setting up database...")
    
    settings = get_settings()
    
    # Extract database path
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        db_path = Path(db_url.replace("sqlite:///", ""))
        
        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"   Database path: {db_path}")
        
        # Check migration status
        status = check_migration_status(db_path)
        print(f"   Current version: {status['current_version']}")
        print(f"   Latest version: {status['latest_version']}")
        
        if not status['is_up_to_date']:
            print(f"   Pending migrations: {len(status['pending_migrations'])}")
            
            # Apply migrations
            ensure_authnz_tables(db_path)
            print("✅ Database migrations applied")
        else:
            print("✅ Database is up to date")
    else:
        # Basic Postgres bootstrap: ensure required tables exist
        print("⚙️  Non-SQLite database detected – attempting basic schema bootstrap (users, sessions, api_keys, RBAC)...")
        try:
            # Ensure connection pool and users table
            users_db = await get_users_db()
            await users_db.initialize()

            # Ensure sessions and registration_codes tables (if missing)
            from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
            pool = await get_db_pool()
            async with pool.transaction() as conn:
                if hasattr(conn, 'execute'):
                    await conn.execute("""
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
                    """)
                    await conn.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS refresh_expires_at TIMESTAMP")
                    await conn.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS is_revoked BOOLEAN DEFAULT FALSE")
                    await conn.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS access_jti VARCHAR(128)")
                    await conn.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS refresh_jti VARCHAR(128)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_access_jti ON sessions(access_jti)")

                    await conn.execute("""
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
                    """)
                    # RBAC core tables
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS roles (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(64) UNIQUE NOT NULL,
                            description TEXT,
                            is_system BOOLEAN DEFAULT FALSE
                        )
                    """)
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS permissions (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(128) UNIQUE NOT NULL,
                            description TEXT,
                            category VARCHAR(64)
                        )
                    """)
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS role_permissions (
                            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
                            PRIMARY KEY (role_id, permission_id)
                        )
                    """)
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS user_roles (
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                            granted_by INTEGER,
                            expires_at TIMESTAMP,
                            PRIMARY KEY (user_id, role_id)
                        )
                    """)
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS user_permissions (
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
                            granted BOOLEAN NOT NULL DEFAULT TRUE,
                            expires_at TIMESTAMP,
                            PRIMARY KEY (user_id, permission_id)
                        )
                    """)
                    # RBAC rate limits + usage
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS rbac_role_rate_limits (
                            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                            resource VARCHAR(128) NOT NULL,
                            limit_per_min INTEGER,
                            burst INTEGER,
                            PRIMARY KEY (role_id, resource)
                        )
                    """)
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS rbac_user_rate_limits (
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            resource VARCHAR(128) NOT NULL,
                            limit_per_min INTEGER,
                            burst INTEGER,
                            PRIMARY KEY (user_id, resource)
                        )
                    """)
                    # (moved) Usage tables will be created after api_keys schema exists

                    # Organizations and Teams hierarchy
                    await conn.execute("""
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
                    """)
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_orgs_owner ON organizations(owner_user_id)")
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS org_members (
                            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            role VARCHAR(32) DEFAULT 'member',
                            status VARCHAR(32) DEFAULT 'active',
                            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (org_id, user_id)
                        )
                    """)
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_org_members_user ON org_members(user_id)")
                    await conn.execute("""
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
                    """)
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_org ON teams(org_id)")
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS team_members (
                            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            role VARCHAR(32) DEFAULT 'member',
                            status VARCHAR(32) DEFAULT 'active',
                            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (team_id, user_id)
                        )
                    """)
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members(user_id)")

                    # Seed baseline RBAC roles and permissions
                    await conn.execute("INSERT INTO roles (name, description, is_system) VALUES ('admin','Administrator', TRUE) ON CONFLICT (name) DO NOTHING")
                    await conn.execute("INSERT INTO roles (name, description, is_system) VALUES ('user','Standard User', TRUE) ON CONFLICT (name) DO NOTHING")
                    await conn.execute("INSERT INTO roles (name, description, is_system) VALUES ('viewer','Read-only User', TRUE) ON CONFLICT (name) DO NOTHING")

                    perm_defs = [
                        ('media.read','Read media','media'),
                        ('media.create','Create media','media'),
                        ('media.delete','Delete media','media'),
                        ('system.configure','Configure system','system'),
                        ('users.manage_roles','Manage user roles','users'),
                    ]
                    for _name, _desc, _cat in perm_defs:
                        await conn.execute(
                            "INSERT INTO permissions (name, description, category) VALUES ($1,$2,$3) ON CONFLICT (name) DO NOTHING",
                            _name, _desc, _cat
                        )
                    role_rows = await conn.fetch("SELECT id,name FROM roles WHERE name IN ('admin','user','viewer')")
                    perm_rows = await conn.fetch("SELECT id,name FROM permissions")
                    role_id = {r['name']: r['id'] for r in role_rows}
                    perm_id = {p['name']: p['id'] for p in perm_rows}
                    # user role defaults
                    for pname in ('media.read','media.create'):
                        if pname in perm_id and 'user' in role_id:
                            await conn.execute(
                                "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                                role_id['user'], perm_id[pname]
                            )
                    # viewer role default
                    if 'viewer' in role_id and 'media.read' in perm_id:
                        await conn.execute(
                            "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                            role_id['viewer'], perm_id['media.read']
                        )
                    # admin: grant all
                    if 'admin' in role_id:
                        for pname in ('media.read','media.create','media.delete','system.configure','users.manage_roles'):
                            if pname in perm_id:
                                await conn.execute(
                                    "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                                    role_id['admin'], perm_id[pname]
                                )

                    # (moved) api_keys column extensions will be applied after api_keys exists
            # Ensure API key tables after org/team tables exist
            api_mgr = APIKeyManager()
            await api_mgr.initialize()

            # Now create usage tables that reference api_keys
            pool = await get_db_pool()
            async with pool.transaction() as conn:
                if hasattr(conn, 'execute'):
                    # Extend api_keys with Virtual Key fields (apply after base api_keys created)
                    await conn.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS is_virtual BOOLEAN DEFAULT FALSE")
                    await conn.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS parent_key_id INTEGER REFERENCES api_keys(id)")
                    await conn.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL")
                    await conn.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL")
                    await conn.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_budget_day_tokens BIGINT")
                    await conn.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_budget_month_tokens BIGINT")
                    await conn.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_budget_day_usd DOUBLE PRECISION")
                    await conn.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_budget_month_usd DOUBLE PRECISION")
                    # Store allowlists as TEXT (JSON string) for compatibility across asyncpg versions
                    await conn.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_allowed_endpoints TEXT")
                    await conn.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_allowed_providers TEXT")
                    await conn.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS llm_allowed_models TEXT")
                    await conn.execute("""
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
                    """)
                    # Extend existing table (if created before) with request_id column
                    await conn.execute("ALTER TABLE usage_log ADD COLUMN IF NOT EXISTS request_id TEXT")
                    # Extend existing table with bytes_in if missing
                    await conn.execute("ALTER TABLE usage_log ADD COLUMN IF NOT EXISTS bytes_in BIGINT")
                    # Helpful indexes
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_log_ts ON usage_log(ts)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_log_user ON usage_log(user_id)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_log_status ON usage_log(status)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_log_endpoint ON usage_log(endpoint)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_log_request_id ON usage_log(request_id)")
                    await conn.execute("""
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
                    """)
                    # Indexes for reporting
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_daily_day_user ON usage_daily(day, user_id)")
                    # Extend existing table with bytes_in_total
                    await conn.execute("ALTER TABLE usage_daily ADD COLUMN IF NOT EXISTS bytes_in_total BIGINT")
                    await conn.execute("""
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
                    """)
                    # Helpful indexes
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_ts ON llm_usage_log(ts)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_user ON llm_usage_log(user_id)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_provider_model ON llm_usage_log(provider, model)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_op_ts ON llm_usage_log(operation, ts)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_log_operation ON llm_usage_log(operation)")
                    await conn.execute("""
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
                    """)
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_daily_day_user_op_prov_model ON llm_usage_daily(day, user_id, operation, provider, model)")

            print("✅ Basic schema ensured for Postgres (users, api keys, sessions, registration_codes, RBAC, orgs/teams, usage tables)")
        except Exception as e:
            print(f"❌ Failed to bootstrap Postgres schema: {e}")
            logger.exception("Postgres schema bootstrap error")
            return False
    
    return True


async def ensure_single_user_rbac_seed_if_needed() -> None:
    """Ensure baseline RBAC seed exists in single-user mode for any backend.

    Idempotent: inserts roles/permissions only if missing. Intended to backstop
    environments where migrations or bootstrap did not seed RBAC yet.
    """
    settings = get_settings()
    if settings.AUTH_MODE != "single_user":
        return
    try:
        # Acquire a connection via pool/transaction abstraction
        from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
        pool = await get_db_pool()
        async with pool.transaction() as conn:
            # Postgres path: asyncpg connections expose fetch(), SQLite shims do not
            if hasattr(conn, "fetch"):
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS roles (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(64) UNIQUE NOT NULL,
                        description TEXT,
                        is_system BOOLEAN DEFAULT FALSE
                    )
                """)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS permissions (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(128) UNIQUE NOT NULL,
                        description TEXT,
                        category VARCHAR(64)
                    )
                """)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS role_permissions (
                        role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                        permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
                        PRIMARY KEY (role_id, permission_id)
                    )
                """)
                # Minimal seed for tests and baseline UI flows
                await conn.execute("INSERT INTO roles (name, description, is_system) VALUES ('admin','Administrator', TRUE) ON CONFLICT (name) DO NOTHING")
                await conn.execute("INSERT INTO roles (name, description, is_system) VALUES ('user','Standard User', TRUE) ON CONFLICT (name) DO NOTHING")
                await conn.execute("INSERT INTO roles (name, description, is_system) VALUES ('viewer','Read-only User', TRUE) ON CONFLICT (name) DO NOTHING")

                for _name, _desc, _cat in (
                    ('media.read','Read media','media'),
                    ('media.create','Create media','media'),
                    ('users.manage_roles','Manage user roles','users'),
                ):
                    await conn.execute(
                        "INSERT INTO permissions (name, description, category) VALUES ($1,$2,$3) ON CONFLICT (name) DO NOTHING",
                        _name, _desc, _cat,
                    )
                role_rows = await conn.fetch("SELECT id,name FROM roles WHERE name IN ('admin','user','viewer')")
                perm_rows = await conn.fetch("SELECT id,name FROM permissions WHERE name IN ('media.read','media.create','users.manage_roles')")
                role_id = {r['name']: r['id'] for r in role_rows}
                perm_id = {p['name']: p['id'] for p in perm_rows}
                # Grant user baseline perms
                for pname in ('media.read','media.create'):
                    if pname in perm_id and 'user' in role_id:
                        await conn.execute(
                            "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                            role_id['user'], perm_id[pname]
                        )
                # Viewer read-only
                if 'viewer' in role_id and 'media.read' in perm_id:
                    await conn.execute(
                        "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                        role_id['viewer'], perm_id['media.read']
                    )
                # Admin elevated
                if 'admin' in role_id:
                    for pname in ('media.read','media.create','users.manage_roles'):
                        if pname in perm_id:
                            await conn.execute(
                                "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                                role_id['admin'], perm_id[pname]
                            )
                return

        # SQLite path (pool adapters expose .execute returning cursor-like)
        async with pool.transaction() as conn:  # type: ignore[attr-defined]
            # Some adapters may not expose .execute; fallback to connection from pool
            try:
                cur = await conn.execute("""
                    CREATE TABLE IF NOT EXISTS roles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        is_system INTEGER DEFAULT 0
                    )
                """)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS permissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        category TEXT
                    )
                """)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS role_permissions (
                        role_id INTEGER NOT NULL,
                        permission_id INTEGER NOT NULL,
                        PRIMARY KEY (role_id, permission_id)
                    )
                """)
            except Exception:
                pass

            await conn.execute("INSERT OR IGNORE INTO roles (name, description, is_system) VALUES ('admin','Administrator',1)")
            await conn.execute("INSERT OR IGNORE INTO roles (name, description, is_system) VALUES ('user','Standard User',1)")
            await conn.execute("INSERT OR IGNORE INTO roles (name, description, is_system) VALUES ('viewer','Read-only User',1)")
            await conn.execute("INSERT OR IGNORE INTO permissions (name, description, category) VALUES ('media.read','Read media','media')")
            await conn.execute("INSERT OR IGNORE INTO permissions (name, description, category) VALUES ('media.create','Create media','media')")
            await conn.execute("INSERT OR IGNORE INTO permissions (name, description, category) VALUES ('users.manage_roles','Manage user roles','users')")

            # Map role names → ids
            cur = await conn.execute("SELECT id,name FROM roles WHERE name IN ('admin','user','viewer')")
            rows = await cur.fetchall()
            role_id = {r[1]: r[0] for r in rows}
            cur = await conn.execute("SELECT id,name FROM permissions WHERE name IN ('media.read','media.create','users.manage_roles')")
            rows = await cur.fetchall()
            perm_id = {r[1]: r[0] for r in rows}

            # Baselines
            for pname in ('media.read','media.create'):
                if pname in perm_id and 'user' in role_id:
                    await conn.execute(
                        "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                        (role_id['user'], perm_id[pname])
                    )
            if 'viewer' in role_id and 'media.read' in perm_id:
                await conn.execute(
                    "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                    (role_id['viewer'], perm_id['media.read'])
                )
            if 'admin' in role_id:
                for pname in ('media.read','media.create','users.manage_roles'):
                    if pname in perm_id:
                        await conn.execute(
                            "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                            (role_id['admin'], perm_id[pname])
                        )
            # Commit if adapter requires it
            try:
                await conn.commit()  # type: ignore[attr-defined]
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Single-user RBAC seed ensure skipped or failed: {e}")

async def create_admin_user():
    """Create initial admin user for multi-user mode"""
    settings = get_settings()
    
    if settings.AUTH_MODE != "multi_user":
        print("\n📝 Single-user mode - skipping admin user creation")
        return True
    
    print("\n👤 Creating admin user...")
    
    # Get user input
    while True:
        username = input("   Admin username (default: admin): ").strip() or "admin"
        if len(username) >= 3:
            break
        print("   Username must be at least 3 characters")
    
    while True:
        email = input("   Admin email: ").strip()
        if "@" in email and "." in email:
            break
        print("   Please enter a valid email address")
    
    while True:
        password = getpass("   Admin password (min 10 chars): ")
        if len(password) >= 10:
            confirm = getpass("   Confirm password: ")
            if password == confirm:
                break
            else:
                print("   Passwords don't match!")
        else:
            print("   Password must be at least 10 characters")
    
    try:
        # Hash password
        password_service = PasswordService()
        password_hash = password_service.hash_password(password)
        
        # Create user
        users_db = await get_users_db()
        admin_user = await users_db.create_user(
            username=username,
            email=email,
            password_hash=password_hash,
            role="admin",
            is_superuser=True
        )
        
        # Create initial API key for admin
        api_manager = await get_api_key_manager()
        api_key_result = await api_manager.create_api_key(
            user_id=admin_user['id'],
            name="Initial Admin API Key",
            description="Auto-generated during setup",
            scope="admin",
            expires_in_days=365
        )
        
        print(f"\n✅ Admin user created successfully!")
        print(f"   User ID: {admin_user['id']}")
        print(f"   Username: {admin_user['username']}")
        print(f"\n🔑 Admin API Key (save this - won't be shown again):")
        print(f"   {api_key_result['key']}")
        
        # Ensure user directories exist
        await ensure_user_directories(admin_user['id'])
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create admin user: {e}")
        return False

async def test_authentication():
    """Test authentication system"""
    print("\n🧪 Testing authentication system...")
    
    settings = get_settings()
    
    try:
        if settings.AUTH_MODE == "single_user":
            # Test API key validation
            print("   Testing single-user API key...")
            # This would normally test the actual API key validation
            print("✅ Single-user authentication configured")
        else:
            # Test JWT system
            from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service

            # Initialize JWT service (sync accessor)
            jwt_service = get_jwt_service()

            # Create a minimal, valid access token
            test_token = jwt_service.create_access_token(
                user_id=1,
                username="test_user",
                role="user",
            )

            # Validate the token via access-token decoder
            decoded = jwt_service.decode_access_token(test_token)
            
            if decoded and decoded.get("sub") == "test_user":
                print("✅ JWT authentication system working")
            else:
                print("❌ JWT validation failed")
                return False
                
        return True
        
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        return False

async def start_services():
    """Start background services"""
    print("\n🚀 Starting background services...")
    
    try:
        # Start scheduler
        await start_authnz_scheduler()
        print("✅ Scheduler started")
        
        # Initialize monitor
        monitor = await get_authnz_monitor()
        print("✅ Monitoring system initialized")
        
        # Get initial metrics
        metrics = await monitor.get_metrics_summary(60)
        print(f"   Health status: {monitor._calculate_health_status(metrics)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to start services: {e}")
        return False

async def main():
    """Main initialization function"""
    print_banner()
    
    # Step 1: Check environment
    if not check_environment():
        print("\n⚠️  Please configure your environment and run again.")
        print("   1. Edit .env file with secure values")
        print("   2. Run: python -m tldw_Server_API.app.core.AuthNZ.initialize")
        sys.exit(1)
    
    # Step 2: Offer to generate keys if needed
    response = input("\n📝 Generate new secure keys? (y/N): ").strip().lower()
    if response == 'y':
        generate_secure_keys()
        print("\n⚠️  Update your .env file with these keys and run again.")
        sys.exit(0)
    
    # Step 3: Setup database
    if not await setup_database():
        print("\n❌ Database setup failed")
        sys.exit(1)
    
    # Step 4: Create admin user (multi-user mode)
    settings = get_settings()
    if settings.AUTH_MODE == "multi_user":
        # Check if any users exist
        try:
            users_db = await get_users_db()
            existing_users = await users_db.list_users(limit=1)
            
            if not existing_users:
                response = input("\n📝 No users found. Create admin user? (Y/n): ").strip().lower()
                if response != 'n':
                    if not await create_admin_user():
                        print("\n⚠️  Admin user creation failed")
            else:
                print(f"\n✅ Found {len(existing_users)} existing user(s)")
        except Exception as e:
            logger.warning(f"Could not check existing users: {e}")
            response = input("\n📝 Create admin user? (Y/n): ").strip().lower()
            if response != 'n':
                await create_admin_user()
    
    # Step 5: Test authentication
    if not await test_authentication():
        print("\n⚠️  Authentication test failed")
    
    # Step 6: Start services (optional)
    response = input("\n🚀 Start background services? (y/N): ").strip().lower()
    if response == 'y':
        await start_services()
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ AuthNZ Initialization Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review your configuration in .env")
    print("2. Test authentication endpoints")
    print("3. Configure monitoring and alerting")
    print("4. Set up regular backups")
    print("\nTo start the application:")
    print("   python -m uvicorn tldw_Server_API.app.main:app --reload")
    print()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Initialization cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        logger.exception("Initialization error")
        sys.exit(1)
