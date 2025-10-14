#!/usr/bin/env python3
"""
Smoke test for AuthNZ with SQLite using in-process TestClient.

Steps:
- Set environment for multi_user with SQLite
- Ensure SQLite AuthNZ schema is migrated (adds missing cols like uuid)
- Import FastAPI app and hit /api/v1/auth/register and /api/v1/auth/login
"""

import os
import json
import secrets
from pathlib import Path


def main():
    # Configure environment for multi_user + SQLite (dev-safe)
    os.environ.setdefault("AUTH_MODE", "multi_user")
    os.environ.setdefault("DATABASE_URL", "sqlite:///./Databases/users.db")
    os.environ.setdefault("ENABLE_REGISTRATION", "true")
    os.environ.setdefault("REQUIRE_REGISTRATION_CODE", "false")
    os.environ.setdefault("JWT_SECRET_KEY", secrets.token_urlsafe(32))
    os.environ.setdefault("TEST_MODE", "1")
    os.environ.setdefault("tldw_production", "false")

    # Bootstrap minimal AuthNZ schema for SQLite using internal helpers (avoid full migrations in smoke)
    db_url = os.environ["DATABASE_URL"]
    assert db_url.startswith("sqlite:///"), "Smoke test expects SQLite database URL"
    db_path = Path(db_url.replace("sqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import asyncio
    from tldw_Server_API.app.core.DB_Management.Users_DB import UsersDB
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool

    async def _bootstrap():
        # Ensure users and api_keys tables exist via module initializers
        udb = UsersDB()
        await udb.initialize()
        akm = APIKeyManager()
        await akm.initialize()

        # Ensure sessions table exists (SQLite schema)
        pool = await get_db_pool()
        async with pool.transaction() as conn:
            if hasattr(conn, 'execute'):  # sqlite path
                await conn.execute(
                    """
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
                        access_jti TEXT,
                        refresh_jti TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)")
        return True

    asyncio.run(_bootstrap())

    # Import app and create TestClient
    from fastapi.testclient import TestClient
    # Use the full app to retain logger configuration and startup behavior
    try:
        from tldw_Server_API.app.main import app
    except Exception as e:
        print("FAILED TO IMPORT APP.MAIN: ", repr(e))
        raise
    try:
        client = TestClient(app)
    except Exception as e:
        print("FAILED TO START APP (TestClient init): ", repr(e))
        raise

    # Register user
    username = "smoke_user"
    email = "smoke_user@example.com"
    password = "VeryStrongPass123!"
    reg_payload = {"username": username, "email": email, "password": password}

    reg_resp = client.post("/api/v1/auth/register", json=reg_payload)
    print("REGISTER STATUS:", reg_resp.status_code)
    try:
        print("REGISTER BODY:", json.dumps(reg_resp.json(), indent=2))
    except Exception:
        print("REGISTER BODY (raw):", reg_resp.text)

    if reg_resp.status_code not in (200, 201):
        raise SystemExit(1)

    # Login (OAuth2 form-encoded)
    form = {"username": username, "password": password}
    login_resp = client.post("/api/v1/auth/login", data=form, headers={"Content-Type": "application/x-www-form-urlencoded"})
    print("LOGIN STATUS:", login_resp.status_code)
    try:
        print("LOGIN BODY:", json.dumps(login_resp.json(), indent=2))
    except Exception:
        print("LOGIN BODY (raw):", login_resp.text)

    if login_resp.status_code != 200 or "access_token" not in login_resp.json():
        raise SystemExit(1)

    print("\n✅ Smoke test passed: register + login on SQLite")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback, sys
        traceback.print_exc()
        sys.exit(2)
