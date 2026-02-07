"""
Integration tests for /api/v1/auth/verify-email semantics.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.tests.helpers.pg_env import get_pg_env

pytestmark = pytest.mark.integration

_PG = get_pg_env()
TEST_DB_HOST = _PG.host
TEST_DB_PORT = _PG.port
TEST_DB_USER = _PG.user
TEST_DB_PASSWORD = _PG.password


async def _insert_unverified_user(db_name: str, *, username: str, email: str) -> int:
    conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database=db_name,
    )
    try:
        user_id = await conn.fetchval(
            """
            INSERT INTO users (
                uuid,
                username,
                email,
                password_hash,
                role,
                is_active,
                is_verified,
                storage_quota_mb,
                storage_used_mb
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
            """,
            str(uuid.uuid4()),
            username,
            email,
            "HASHED_PASSWORD_FOR_TESTS",
            "user",
            True,
            False,
            5120,
            0.0,
        )
        return int(user_id)
    finally:
        await conn.close()


async def _fetch_is_verified(db_name: str, user_id: int) -> bool:
    conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database=db_name,
    )
    try:
        value = await conn.fetchval("SELECT is_verified FROM users WHERE id = $1", user_id)
        return bool(value)
    finally:
        await conn.close()


class TestVerifyEmailFlowIntegration:
    @pytest.mark.asyncio
    async def test_verify_email_success_marks_user_verified(self, isolated_test_environment):
        client, db_name = isolated_test_environment

        user_id = await _insert_unverified_user(
            db_name,
            username="verify_success_user",
            email="verify.success@example.com",
        )
        token = JWTService().create_email_verification_token(
            user_id=user_id,
            email="verify.success@example.com",
            expires_in_hours=1,
        )

        response = client.get("/api/v1/auth/verify-email", params={"token": token})
        assert response.status_code == 200
        assert response.json().get("message") == "Email verified successfully"

        assert await _fetch_is_verified(db_name, user_id) is True

    @pytest.mark.asyncio
    async def test_verify_email_mismatched_token_payload_returns_generic_400(
        self,
        isolated_test_environment,
    ):
        client, db_name = isolated_test_environment

        user_id = await _insert_unverified_user(
            db_name,
            username="verify_mismatch_user",
            email="verify.mismatch@example.com",
        )
        token = JWTService().create_email_verification_token(
            user_id=user_id,
            email="different.email@example.com",
            expires_in_hours=1,
        )

        response = client.get("/api/v1/auth/verify-email", params={"token": token})
        assert response.status_code == 400
        assert response.json().get("detail") == "Invalid or expired verification token"
        assert await _fetch_is_verified(db_name, user_id) is False

    @pytest.mark.asyncio
    async def test_verify_email_replay_returns_generic_400(self, isolated_test_environment):
        client, db_name = isolated_test_environment

        user_id = await _insert_unverified_user(
            db_name,
            username="verify_replay_user",
            email="verify.replay@example.com",
        )
        token = JWTService().create_email_verification_token(
            user_id=user_id,
            email="verify.replay@example.com",
            expires_in_hours=1,
        )

        first = client.get("/api/v1/auth/verify-email", params={"token": token})
        assert first.status_code == 200

        second = client.get("/api/v1/auth/verify-email", params={"token": token})
        assert second.status_code == 400
        assert second.json().get("detail") == "Invalid or expired verification token"
