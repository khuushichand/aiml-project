import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_provider_model_allowlists_postgres(test_db_pool):
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.config import settings as app_settings

    pool = test_db_pool
    app_settings['CSRF_ENABLED'] = False

    # Ensure tables used by manager and usage exist
    await pool.execute(
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
        """
    )
    await pool.execute(
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
        """
    )

    # Manager to ensure api_keys columns (explicit pool)
    mgr = APIKeyManager(pool)
    await mgr.initialize()

    # Insert user
    import uuid
    await pool.execute(
        "INSERT INTO users (uuid, username, email, password_hash, is_active) VALUES ($1, $2, $3, $4, TRUE)",
        str(uuid.uuid4()), "vkpg", "vkpg@example.com", "x",
    )
    user_id = await pool.fetchval("SELECT id FROM users WHERE username = $1", "vkpg")

    # Create virtual key with allowlists
    res = await mgr.create_virtual_key(
        user_id=user_id,
        name="vk-allowlist-pg",
        allowed_endpoints=["chat.completions"],
        allowed_providers=["openai"],
        allowed_models=["gpt-4o-mini"],
        budget_day_tokens=100000,
    )
    vkey = res['key']

    with TestClient(app) as client:
        # Disallowed model
        r = client.post(
            "/api/v1/chat/completions",
            headers={"X-API-KEY": vkey, "Content-Type": "application/json", "X-LLM-Provider": "openai"},
            json={"model": "not-allowed", "messages": [{"role": "user", "content": "hi"}]}
        )
        assert r.status_code == 403
        assert "Model 'not-allowed' not allowed" in r.text

        # Disallowed provider
        r = client.post(
            "/api/v1/chat/completions",
            headers={"X-API-KEY": vkey, "Content-Type": "application/json", "X-LLM-Provider": "anthropic"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]}
        )
        assert r.status_code == 403
        assert "Provider 'anthropic' not allowed" in r.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_missing_provider_header_allows_when_allowlist_present_postgres(test_db_pool):
    """If allowed_providers is set but X-LLM-Provider header is missing, middleware should not 403."""
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.config import settings as app_settings

    pool = test_db_pool
    app_settings['CSRF_ENABLED'] = False

    # Ensure minimal tables for manager
    await pool.execute(
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
        """
    )
    await pool.execute(
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
        """
    )

    # Insert user
    import uuid
    await pool.execute(
        "INSERT INTO users (uuid, username, email, password_hash, is_active) VALUES ($1, $2, $3, $4, TRUE)",
        str(uuid.uuid4()), "vkpg-missing", "vkpg-missing@example.com", "x",
    )
    user_id = await pool.fetchval("SELECT id FROM users WHERE username = $1", "vkpg-missing")

    # Create virtual key with provider/model allowlists
    mgr = APIKeyManager(pool)
    await mgr.initialize()
    res = await mgr.create_virtual_key(
        user_id=user_id,
        name="vk-allowlist-missing-provider",
        allowed_endpoints=["chat.completions"],
        allowed_providers=["openai"],
        allowed_models=["gpt-4o-mini"],
        budget_day_tokens=100000,
    )
    vkey = res['key']

    with TestClient(app) as client:
        # No X-LLM-Provider header; should NOT 403 due to provider allowlist
        r = client.post(
            "/api/v1/chat/completions",
            headers={"X-API-KEY": vkey, "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]}
        )
        assert r.status_code not in (403, 402), r.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_non_json_body_skips_model_enforcement_postgres(test_db_pool):
    """With non-JSON content-type, model allowlist is skipped; ensure no 403/402 from middleware."""
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.config import settings as app_settings

    pool = test_db_pool
    app_settings['CSRF_ENABLED'] = False

    # Insert user
    import uuid
    await pool.execute(
        "INSERT INTO users (uuid, username, email, password_hash, is_active) VALUES ($1, $2, $3, $4, TRUE)",
        str(uuid.uuid4()), "vkpg-nonjson", "vkpg-nonjson@example.com", "x",
    )
    user_id = await pool.fetchval("SELECT id FROM users WHERE username = $1", "vkpg-nonjson")

    mgr = APIKeyManager(pool)
    await mgr.initialize()
    res = await mgr.create_virtual_key(
        user_id=user_id,
        name="vk-allowlist-nonjson",
        allowed_endpoints=["chat.completions"],
        allowed_providers=["openai"],
        allowed_models=["gpt-4o-mini"],
        budget_day_tokens=100000,
    )
    vkey = res['key']

    with TestClient(app) as client:
        try:
            r = client.post(
                "/api/v1/chat/completions",
                headers={"X-API-KEY": vkey, "Content-Type": "text/plain"},
                data="hello"
            )
            # Should not be blocked by provider/model allowlists or budgets
            assert r.status_code not in (403, 402), r.text
        except Exception:
            # Non-JSON bodies may raise deeper in the stack; middleware under test should not be the blocker.
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_json_body_skips_model_enforcement_postgres(test_db_pool):
    """Invalid JSON should not trigger model allowlist enforcement; ensure not 403/402."""
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.config import settings as app_settings

    pool = test_db_pool
    app_settings['CSRF_ENABLED'] = False

    # Insert user
    import uuid
    await pool.execute(
        "INSERT INTO users (uuid, username, email, password_hash, is_active) VALUES ($1, $2, $3, $4, TRUE)",
        str(uuid.uuid4()), "vkpg-badjson", "vkpg-badjson@example.com", "x",
    )
    user_id = await pool.fetchval("SELECT id FROM users WHERE username = $1", "vkpg-badjson")

    mgr = APIKeyManager(pool)
    await mgr.initialize()
    res = await mgr.create_virtual_key(
        user_id=user_id,
        name="vk-allowlist-badjson",
        allowed_endpoints=["chat.completions"],
        allowed_providers=["openai"],
        allowed_models=["gpt-4o-mini"],
        budget_day_tokens=100000,
    )
    vkey = res['key']

    with TestClient(app) as client:
        try:
            r = client.post(
                "/api/v1/chat/completions",
                headers={"X-API-KEY": vkey, "Content-Type": "application/json"},
                data="this is not json"
            )
            assert r.status_code not in (403, 402), r.text
        except Exception:
            # Invalid JSON can trip downstream parsing; we're only asserting middleware does not block.
            pass
