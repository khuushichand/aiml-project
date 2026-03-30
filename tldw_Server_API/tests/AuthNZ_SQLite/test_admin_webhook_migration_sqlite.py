from __future__ import annotations

import base64
import sqlite3

import pytest

from tldw_Server_API.app.core.AuthNZ.admin_webhook_secrets import (
    decrypt_admin_webhook_secret,
    encrypt_admin_webhook_secret,
)
from tldw_Server_API.app.core.AuthNZ.migrations import (
    migration_082_harden_admin_webhooks_and_create_admin_settings,
)


pytestmark = pytest.mark.unit


def _b64_key(seed: bytes) -> str:
    return base64.b64encode((seed * 32)[:32]).decode("ascii")


def _create_legacy_admin_webhooks_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE admin_webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            secret TEXT NOT NULL,
            event_types TEXT NOT NULL DEFAULT '[]',
            description TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            retry_count INTEGER NOT NULL DEFAULT 3,
            timeout_seconds INTEGER NOT NULL DEFAULT 10,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE admin_webhooks_delivery_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            webhook_id INTEGER NOT NULL REFERENCES admin_webhooks(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            signature TEXT NOT NULL,
            status_code INTEGER,
            response_body TEXT,
            latency_ms INTEGER,
            retry_attempt INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            delivered_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def test_migration_082_encrypts_admin_webhook_secrets_and_creates_admin_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"m"))
    conn = sqlite3.connect(":memory:")
    _create_legacy_admin_webhooks_schema(conn)
    conn.execute(
        """
        INSERT INTO admin_webhooks (
            id, url, secret, event_types, description, active,
            retry_count, timeout_seconds, created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            "https://example.com/hook",
            "plain-secret",
            '["*"]',
            "Legacy hook",
            1,
            3,
            10,
            7,
            "2026-03-28T00:00:00Z",
            "2026-03-28T00:00:00Z",
        ),
    )
    conn.commit()

    migration_082_harden_admin_webhooks_and_create_admin_settings(conn)

    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(admin_webhooks)").fetchall()
    }
    assert "secret" not in columns
    assert "secret_encrypted" in columns
    assert "secret_key_id" in columns

    migrated_row = conn.execute(
        "SELECT secret_encrypted, secret_key_id FROM admin_webhooks WHERE id = 1"
    ).fetchone()
    assert migrated_row is not None
    assert migrated_row[0] != "plain-secret"
    assert migrated_row[1] == "byok_primary"
    assert decrypt_admin_webhook_secret(migrated_row[0]) == "plain-secret"

    admin_settings_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'admin_settings'"
    ).fetchone()
    assert admin_settings_exists is not None

    encrypted = encrypt_admin_webhook_secret("another-secret")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO admin_webhooks (
                url, secret_encrypted, secret_key_id, event_types, description,
                active, retry_count, timeout_seconds, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://example.com/invalid",
                encrypted.encrypted_blob,
                encrypted.key_id,
                '["*"]',
                "",
                1,
                -1,
                10,
                None,
                "2026-03-28T00:00:00Z",
                "2026-03-28T00:00:00Z",
            ),
        )
