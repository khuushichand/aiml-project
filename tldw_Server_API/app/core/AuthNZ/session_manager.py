# session_manager.py
# Description: Session management with Redis caching, encryption, and automatic cleanup
#
# Imports
import json
import hmac
import hashlib
import secrets
import base64
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import asyncio
#
# 3rd-party imports
from redis import asyncio as redis_async
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from loguru import logger
from jose import jwt as jose_jwt
import time
from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter, log_histogram
#
# Local imports
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import derive_hmac_key
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool, reset_db_pool
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    SessionError,
    InvalidSessionError,
    SessionRevokedException,
    DatabaseError
)
from tldw_Server_API.app.core.AuthNZ.token_blacklist import get_token_blacklist

#######################################################################################################################
#
# Session Manager Class

class SessionManager:
    """Manages user sessions with database persistence, encryption, and optional Redis caching"""
    
    def __init__(
        self,
        db_pool: Optional[DatabasePool] = None,
        settings: Optional[Settings] = None
    ):
        """Initialize session manager"""
        self.settings = settings or get_settings()
        self.db_pool = db_pool
        self._external_db_pool = db_pool is not None
        self.redis_client: Optional[redis_async.Redis] = None
        self.scheduler = AsyncIOScheduler()
        self._initialized = False
        self.cipher_suite: Optional[Fernet] = None
        self._init_encryption()
        
    async def initialize(self):
        """Initialize session manager and start cleanup scheduler"""
        if self._initialized:
            return
        
        # Get database pool
        self.db_pool = await self._ensure_db_pool()
        
        # Initialize Redis if configured
        if self.settings.REDIS_URL:
            try:
                self.redis_client = redis_async.from_url(
                    self.settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                    max_connections=self.settings.REDIS_MAX_CONNECTIONS,
                    health_check_interval=30
                )
                
                # Test connection
                await self.redis_client.ping()
                logger.info("Redis connected for session caching")
                
            except (RedisConnectionError, RedisError) as e:
                logger.warning(f"Redis unavailable, using database only: {e}")
                self.redis_client = None
        
        # Schedule session cleanup
        if self.settings.SESSION_CLEANUP_INTERVAL_HOURS > 0:
            self.scheduler.add_job(
                self.cleanup_expired_sessions,
                trigger=IntervalTrigger(hours=self.settings.SESSION_CLEANUP_INTERVAL_HOURS),
                id='session_cleanup',
                replace_existing=True,
                max_instances=1
            )
            self.scheduler.start()
            logger.info(
                f"Session cleanup scheduled every {self.settings.SESSION_CLEANUP_INTERVAL_HOURS} hours"
            )
        
        self._initialized = True
        logger.info("SessionManager initialized with encryption enabled")

    async def _ensure_db_pool(self) -> DatabasePool:
        """Ensure we have a database pool compatible with the current event loop."""
        current_settings = get_settings()

        if not self._external_db_pool:
            global_pool = await get_db_pool()
            if self.db_pool is not global_pool:
                logger.debug("SessionManager adopting refreshed AuthNZ DatabasePool instance")
                self.db_pool = global_pool
            self.settings = current_settings
        else:
            self.settings = current_settings

        if not self.db_pool:
            self.db_pool = await get_db_pool()
            return self.db_pool

        pool_ref = getattr(self.db_pool, "pool", None)
        pool_closed = bool(pool_ref) and getattr(pool_ref, "closed", False)

        loop_changed = False
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        stored_loop = getattr(self.db_pool, "_loop", None)
        if pool_ref and stored_loop and current_loop and stored_loop is not current_loop:
            loop_changed = True

        if pool_closed or loop_changed:
            logger.debug(
                "SessionManager refreshing database pool "
                f"(pool_closed={pool_closed}, loop_changed={loop_changed})"
            )
            if not self._external_db_pool:
                await reset_db_pool()
                self.db_pool = await get_db_pool()
                return self.db_pool
            await self.db_pool.close()
            await self.db_pool.initialize()
            return self.db_pool

        if not getattr(self.db_pool, "_initialized", False):
            await self.db_pool.initialize()

        return self.db_pool
    
    def _init_encryption(self):
        """Initialize encryption for session tokens"""
        # Get or generate encryption key
        encryption_key = self._get_or_create_encryption_key()
        self.cipher_suite = Fernet(encryption_key)
        logger.debug("Session token encryption initialized")
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for session tokens"""
        # Try to get key from settings/environment
        if hasattr(self.settings, 'SESSION_ENCRYPTION_KEY') and self.settings.SESSION_ENCRYPTION_KEY:
            # Decode from base64 if provided as string
            if isinstance(self.settings.SESSION_ENCRYPTION_KEY, str):
                return base64.urlsafe_b64decode(self.settings.SESSION_ENCRYPTION_KEY)
            return self.settings.SESSION_ENCRYPTION_KEY
        
        # Derive key from dedicated credentials (pepper/JWT material) for deterministic encryption.
        candidate_secrets: List[Optional[str]] = [
            getattr(self.settings, "API_KEY_PEPPER", None),
            getattr(self.settings, "JWT_SECRET_KEY", None),
            getattr(self.settings, "JWT_PRIVATE_KEY", None),
        ]
        if getattr(self.settings, "AUTH_MODE", "single_user") == "single_user":
            # Allow the configured API key to seed deterministic encryption when no pepper/JWT secret exists.
            candidate_secrets.insert(1, getattr(self.settings, "SINGLE_USER_API_KEY", None))

        for secret in candidate_secrets:
            if secret:
                if isinstance(secret, bytes):
                    raw = secret
                else:
                    raw = str(secret).encode("utf-8")
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b"session_encryption_salt_v1",
                    iterations=100000,
                )
                key_material = kdf.derive(raw)
                return base64.urlsafe_b64encode(key_material)
        
        # No deterministic secret available – allow random key only for explicit tests.
        test_mode = os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
        pytest_active = os.getenv("PYTEST_CURRENT_TEST") is not None
        if not (test_mode or pytest_active):
            raise ValueError(
                "Session encryption key is not configured. "
                "Set SESSION_ENCRYPTION_KEY or provide API_KEY_PEPPER / JWT secrets."
            )
        logger.warning("Generating temporary session encryption key for test context.")
        return Fernet.generate_key()
    
    def hash_token(self, token: str) -> str:
        """Create HMAC-SHA256 of token for lookup/indexing (aligned with AuthNZ)."""
        key = derive_hmac_key(self.settings)
        return hmac.new(key, token.encode('utf-8'), hashlib.sha256).hexdigest()
    
    def encrypt_token(self, token: str) -> str:
        """Encrypt a token for secure storage"""
        if not self.cipher_suite:
            self._init_encryption()
        
        encrypted = self.cipher_suite.encrypt(token.encode())
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt a stored token"""
        if not self.cipher_suite:
            self._init_encryption()
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_token.encode('utf-8'))
            decrypted = self.cipher_suite.decrypt(encrypted_bytes)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decrypt token: {e}")
            raise InvalidSessionError("Failed to decrypt session token")

    @staticmethod
    def _extract_token_metadata(token: Optional[str]) -> Tuple[Optional[str], Optional[datetime]]:
        """Return (jti, expires_at) tuple without verifying signature."""
        if not token:
            return None, None
        try:
            claims = jose_jwt.get_unverified_claims(token)
            jti = claims.get("jti")
            exp = claims.get("exp")
            expires_at = None
            if isinstance(exp, (int, float)):
                expires_at = datetime.utcfromtimestamp(exp)
            return jti, expires_at
        except Exception:
            return None, None
    
    async def create_session(
        self,
        user_id: int,
        access_token: str,
        refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new session for a user
        
        Args:
            user_id: User's database ID
            access_token: JWT access token
            refresh_token: JWT refresh token
            ip_address: Client IP address
            user_agent: Client user agent string
            device_id: Optional device identifier
            
        Returns:
            Session information dictionary
        """
        start_time = time.perf_counter()
        log_counter("auth_session_create_attempt")
        if not self._initialized:
            await self.initialize()
        
        # Hash tokens for indexing/lookup
        access_hash = self.hash_token(access_token)
        refresh_hash = self.hash_token(refresh_token)
        
        # Encrypt tokens for secure storage
        encrypted_access = self.encrypt_token(access_token)
        encrypted_refresh = self.encrypt_token(refresh_token)
        expires_at = datetime.utcnow() + timedelta(
            minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        refresh_expires_at = datetime.utcnow() + timedelta(
            days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        access_jti, access_exp_override = self._extract_token_metadata(access_token)
        if access_exp_override:
            expires_at = access_exp_override
        refresh_jti, refresh_exp_override = self._extract_token_metadata(refresh_token)
        if refresh_exp_override:
            refresh_expires_at = refresh_exp_override
        
        session_id = None
        
        try:
            db_pool = await self._ensure_db_pool()
            async with db_pool.transaction() as conn:
                if hasattr(conn, 'fetchval'):
                    # PostgreSQL
                    session_id = await conn.fetchval(
                        """
                        INSERT INTO sessions (
                            user_id, token_hash, refresh_token_hash,
                            encrypted_token, encrypted_refresh,
                            expires_at, refresh_expires_at,
                            ip_address, user_agent, device_id,
                            access_jti, refresh_jti
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        RETURNING id
                        """,
                        user_id, access_hash, refresh_hash,
                        encrypted_access, encrypted_refresh,
                        expires_at, refresh_expires_at,
                        ip_address, user_agent, device_id,
                        access_jti, refresh_jti
                    )
                else:
                    # SQLite
                    cursor = await conn.execute(
                        """
                        INSERT INTO sessions (
                            user_id, token_hash, refresh_token_hash,
                            encrypted_token, encrypted_refresh,
                            expires_at, refresh_expires_at,
                            ip_address, user_agent, device_id,
                            access_jti, refresh_jti
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (user_id, access_hash, refresh_hash,
                         encrypted_access, encrypted_refresh,
                         expires_at.isoformat(),
                         refresh_expires_at.isoformat() if refresh_expires_at else None,
                         ip_address, user_agent, device_id,
                         access_jti, refresh_jti)
                    )
                    session_id = cursor.lastrowid
                    await conn.commit()
                
                # Cache in Redis if available
                if self.redis_client:
                    await self._cache_session(
                        access_hash,
                        user_id,
                        session_id,
                        expires_at,
                        user_active=True,
                        revoked=False,
                    )
                
                if self.settings.PII_REDACT_LOGS:
                    logger.info("Created session [redacted]")
                else:
                    logger.info(f"Created session {session_id} for user {user_id}")
                log_counter("auth_session_create_success")
                log_histogram("auth_session_create_duration", time.perf_counter() - start_time)
                
                return {
                    "session_id": session_id,
                    "user_id": user_id,
                    "expires_at": expires_at.isoformat(),
                    "access_token": access_token,
                    "refresh_token": refresh_token
                }
                
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            log_counter("auth_session_create_error")
            log_histogram("auth_session_create_duration", time.perf_counter() - start_time)
            raise SessionError(f"Failed to create session: {e}")
    
    async def validate_session(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a session by access token
        
        Args:
            access_token: JWT access token
            
        Returns:
            Session data if valid, None otherwise
        """
        if not self._initialized:
            await self.initialize()
        
        token_hash = self.hash_token(access_token)
        cached: Optional[Dict[str, Any]] = None
        if self.redis_client:
            cached = await self._get_cached_session(token_hash)
        
        try:
            db_pool = await self._ensure_db_pool()
            async with db_pool.acquire() as conn:
                session_data: Optional[Dict[str, Any]] = None

                # Attempt to reuse cached session_id to minimize lookups,
                # but always verify current DB state.
                if cached and cached.get("session_id") is not None:
                    session_data = await self._fetch_session_record(
                        conn,
                        session_id=int(cached["session_id"]),
                    )
                    if not session_data and cached.get("session_id") is not None:
                        # Cache is stale; purge it.
                        await self._clear_session_cache(int(cached["session_id"]))

                if not session_data:
                    session_data = await self._fetch_session_record(
                        conn,
                        token_hash=token_hash,
                    )

                if not session_data:
                    return None

                user_active = bool(session_data.get("user_active"))
                revoked_flag = bool(session_data.get("revoked_at"))
                if not user_active:
                    if self.settings.PII_REDACT_LOGS:
                        logger.warning("Session valid but user is inactive [redacted]")
                    else:
                        logger.warning(f"Session valid but user {session_data['user_id']} is inactive")
                    return None

                if revoked_flag:
                    if self.settings.PII_REDACT_LOGS:
                        logger.warning("Session revoked [redacted]")
                    else:
                        logger.warning(f"Session {session_data['id']} was revoked")
                    raise SessionRevokedException()

                await self._update_last_activity(session_data['id'], conn)

            # Outside of the DB context – refresh cache with validation status
            expires_at = session_data.get('expires_at')
            if isinstance(expires_at, str):
                expires_at_dt = datetime.fromisoformat(expires_at)
            else:
                expires_at_dt = expires_at

            if self.redis_client and expires_at_dt:
                await self._cache_session(
                    token_hash,
                    session_data['user_id'],
                    session_data['id'],
                    expires_at_dt,
                    user_active=user_active,
                    revoked=revoked_flag,
                )

            return session_data

        except SessionRevokedException:
            raise
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return None
    
    async def revoke_session(
        self,
        session_id: int,
        revoked_by: Optional[int] = None,
        reason: Optional[str] = None
    ):
        """Revoke a specific session"""
        if not self._initialized:
            await self.initialize()
        
        try:
            db_pool = await self._ensure_db_pool()
            async with db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    # PostgreSQL
                    await conn.execute(
                        """
                        UPDATE sessions
                        SET is_active = FALSE,
                            is_revoked = TRUE,
                            revoked_at = CURRENT_TIMESTAMP,
                            revoked_by = $2,
                            revoke_reason = $3
                        WHERE id = $1
                        """,
                        session_id, revoked_by, reason
                    )
                else:
                    # SQLite
                    await conn.execute(
                        """
                        UPDATE sessions
                        SET is_active = 0,
                            is_revoked = 1,
                            revoked_at = datetime('now'),
                            revoked_by = ?,
                            revoke_reason = ?
                        WHERE id = ?
                        """,
                        (revoked_by, reason, session_id)
                    )
                    await conn.commit()
                
                # Clear from cache
                if self.redis_client:
                    await self._clear_session_cache(session_id)
                
                if self.settings.PII_REDACT_LOGS:
                    logger.info("Revoked session [redacted]")
                else:
                    logger.info(f"Revoked session {session_id}")
                
        except Exception as e:
            logger.error(f"Failed to revoke session: {e}")
            raise SessionError(f"Failed to revoke session: {e}")
    
    async def revoke_all_user_sessions(
        self,
        user_id: int,
        except_session_id: Optional[int] = None
    ):
        """Revoke all sessions for a user, optionally except one"""
        if not self._initialized:
            await self.initialize()
        
        try:
            db_pool = await self._ensure_db_pool()
            async with db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    # PostgreSQL
                    if except_session_id:
                        await conn.execute(
                            """
                            UPDATE sessions
                            SET is_active = FALSE,
                                is_revoked = TRUE,
                                revoked_at = CURRENT_TIMESTAMP
                            WHERE user_id = $1 AND id != $2
                            """,
                            user_id, except_session_id
                        )
                    else:
                        await conn.execute(
                            """
                            UPDATE sessions
                            SET is_active = FALSE,
                                is_revoked = TRUE,
                                revoked_at = CURRENT_TIMESTAMP
                            WHERE user_id = $1
                            """,
                            user_id
                        )
                else:
                    # SQLite
                    if except_session_id:
                        await conn.execute(
                            """
                            UPDATE sessions
                            SET is_active = 0,
                                is_revoked = 1,
                                revoked_at = datetime('now')
                            WHERE user_id = ? AND id != ?
                            """,
                            (user_id, except_session_id)
                        )
                    else:
                        await conn.execute(
                            """
                            UPDATE sessions
                            SET is_active = 0,
                                is_revoked = 1,
                                revoked_at = datetime('now')
                            WHERE user_id = ?
                            """,
                            (user_id,)
                        )
                    await conn.commit()
                
                # Clear from cache
                if self.redis_client:
                    await self._clear_user_sessions_cache(user_id)
                
                if self.settings.PII_REDACT_LOGS:
                    logger.info("Revoked all sessions [redacted]")
                else:
                    logger.info(f"Revoked all sessions for user {user_id}")
                
        except Exception as e:
            logger.error(f"Failed to revoke user sessions: {e}")
            raise SessionError(f"Failed to revoke sessions: {e}")

        # After sessions are marked revoked, ensure associated JTIs are blacklisted
        try:
            blacklist = get_token_blacklist()
            await blacklist.revoke_all_user_tokens(user_id)
        except Exception as bl_error:
            logger.warning(f"Failed to blacklist tokens for user {user_id}: {bl_error}")
    
    async def refresh_session(
        self,
        refresh_token: str,
        new_access_token: str,
        new_refresh_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Refresh a session with new tokens"""
        if not self._initialized:
            await self.initialize()
        
        old_refresh_hash = self.hash_token(refresh_token)
        new_access_hash = self.hash_token(new_access_token)
        new_refresh_hash = self.hash_token(new_refresh_token) if new_refresh_token else None
        encrypted_access_token = self.encrypt_token(new_access_token)
        encrypted_refresh_token = self.encrypt_token(new_refresh_token) if new_refresh_token else None
        access_jti, access_exp = self._extract_token_metadata(new_access_token)
        refresh_jti, refresh_exp = self._extract_token_metadata(new_refresh_token) if new_refresh_token else (None, None)
        expires_at = access_exp or (datetime.utcnow() + timedelta(
            minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES
        ))
        refresh_expires_at = None
        if new_refresh_token:
            refresh_expires_at = refresh_exp or (
                datetime.utcnow() + timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS)
            )
        
        try:
            db_pool = await self._ensure_db_pool()
            async with db_pool.transaction() as conn:
                    # Find session by refresh token
                    if hasattr(conn, 'fetchrow'):
                        # PostgreSQL
                        session = await conn.fetchrow(
                            """
                            SELECT id, user_id FROM sessions
                            WHERE refresh_token_hash = $1
                            AND is_active = TRUE
                            """,
                            old_refresh_hash
                        )

                        if not session:
                            raise InvalidSessionError()

                        # Update session with new tokens
                        await conn.execute(
                            """
                            UPDATE sessions
                            SET token_hash = $2,
                                access_jti = COALESCE($3, access_jti),
                                expires_at = $4,
                                encrypted_token = $5,
                                refresh_token_hash = COALESCE($6, refresh_token_hash),
                                refresh_jti = COALESCE($7, refresh_jti),
                                refresh_expires_at = COALESCE($8, refresh_expires_at),
                                encrypted_refresh = COALESCE($9, encrypted_refresh),
                                last_activity = CURRENT_TIMESTAMP
                            WHERE id = $1
                            """,
                            session['id'],
                            new_access_hash,
                            access_jti,
                            expires_at,
                            encrypted_access_token,
                            new_refresh_hash,
                            refresh_jti,
                            refresh_expires_at,
                            encrypted_refresh_token,
                        )

                        session_data = dict(session)

                    else:
                        # SQLite
                        cursor = await conn.execute(
                            """
                            SELECT id, user_id FROM sessions
                            WHERE refresh_token_hash = ?
                            AND is_active = 1
                            """,
                            (old_refresh_hash,)
                        )
                        row = await cursor.fetchone()

                        if not row:
                            raise InvalidSessionError()

                        session_data = {"id": row[0], "user_id": row[1]}

                        # Update session
                        await conn.execute(
                            """
                            UPDATE sessions
                            SET token_hash = ?,
                                access_jti = COALESCE(?, access_jti),
                                expires_at = ?,
                                encrypted_token = ?,
                                refresh_token_hash = COALESCE(?, refresh_token_hash),
                                refresh_jti = COALESCE(?, refresh_jti),
                                refresh_expires_at = COALESCE(?, refresh_expires_at),
                                encrypted_refresh = COALESCE(?, encrypted_refresh),
                                last_activity = datetime('now')
                            WHERE id = ?
                            """,
                            (
                                new_access_hash,
                                access_jti,
                                expires_at.isoformat(),
                                encrypted_access_token,
                                new_refresh_hash,
                                refresh_jti,
                                refresh_expires_at.isoformat() if refresh_expires_at else None,
                                encrypted_refresh_token,
                                session_data['id'],
                            )
                        )
                        await conn.commit()

                    # Update cache
                    if self.redis_client:
                        await self._clear_session_cache(session_data['id'])
                        await self._cache_session(
                            new_access_hash,
                            session_data['user_id'],
                            session_data['id'],
                            expires_at,
                            user_active=True,
                            revoked=False,
                        )

                    if self.settings.PII_REDACT_LOGS:
                        logger.info("Refreshed session [redacted]")
                    else:
                        logger.info(f"Refreshed session {session_data['id']}")

                    return {
                        "session_id": session_data['id'],
                        "user_id": session_data['user_id'],
                        "expires_at": expires_at.isoformat()
                    }

        except InvalidSessionError:
            raise
        except Exception as e:
            logger.error(f"Failed to refresh session: {e}")
            raise SessionError(f"Failed to refresh session: {e}")
    
    async def update_session_tokens(
        self,
        session_id: int,
        access_token: str,
        refresh_token: str
    ):
        """Update session with actual tokens after creation"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Hash tokens for storage
            access_token_hash = self.hash_token(access_token)
            refresh_token_hash = self.hash_token(refresh_token)
            access_jti, access_exp = self._extract_token_metadata(access_token)
            refresh_jti, refresh_exp = self._extract_token_metadata(refresh_token)
            encrypted_access_token = self.encrypt_token(access_token)
            encrypted_refresh_token = self.encrypt_token(refresh_token)
            
            db_pool = await self._ensure_db_pool()
            if getattr(db_pool, "pool", None):
                # PostgreSQL
                await db_pool.execute(
                    """
                    UPDATE sessions
                    SET token_hash = $1,
                        refresh_token_hash = $2,
                        access_jti = COALESCE($3, access_jti),
                        refresh_jti = COALESCE($4, refresh_jti),
                        expires_at = COALESCE($5, expires_at),
                        refresh_expires_at = COALESCE($6, refresh_expires_at),
                        encrypted_token = $7,
                        encrypted_refresh = $8
                    WHERE id = $9
                    """,
                    access_token_hash,
                    refresh_token_hash,
                    access_jti,
                    refresh_jti,
                    access_exp,
                    refresh_exp,
                    encrypted_access_token,
                    encrypted_refresh_token,
                    session_id
                )
            else:
                # SQLite
                await db_pool.execute(
                    """
                    UPDATE sessions
                    SET token_hash = ?,
                        refresh_token_hash = ?,
                        access_jti = COALESCE(?, access_jti),
                        refresh_jti = COALESCE(?, refresh_jti),
                        expires_at = COALESCE(?, expires_at),
                        refresh_expires_at = COALESCE(?, refresh_expires_at),
                        encrypted_token = ?,
                        encrypted_refresh = ?
                    WHERE id = ?
                    """,
                    (
                        access_token_hash,
                        refresh_token_hash,
                        access_jti,
                        refresh_jti,
                        access_exp.isoformat() if access_exp else None,
                        refresh_exp.isoformat() if refresh_exp else None,
                        encrypted_access_token,
                        encrypted_refresh_token,
                        session_id,
                    )
                )
            
            logger.debug(f"Updated session {session_id} with token hashes")
            
        except Exception as e:
            logger.error(f"Failed to update session tokens: {e}")
            raise SessionError(f"Failed to update session tokens: {e}")
    
    async def is_token_blacklisted(self, token: str, jti: Optional[str] = None) -> bool:
        """
        Check if a token has been blacklisted/revoked
        
        Args:
            token: JWT token to check
            jti: Optional JWT ID (if already parsed by caller)
            
        Returns:
            True if token is blacklisted, False otherwise
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # Fail-closed on missing token material
            if not token:
                logger.warning("is_token_blacklisted invoked without token; treating as revoked")
                return True

            # Determine JWT ID (JTI) if not provided
            jti_value = jti
            if not jti_value:
                try:
                    from jose import jwt as _jwt  # Lazy import to avoid top-level dependency
                    claims = _jwt.get_unverified_claims(token)
                    jti_value = claims.get("jti")
                except Exception as exc:
                    logger.warning(f"Failed to extract JTI from token; treating as revoked: {exc}")
                    return True

            if not jti_value:
                logger.warning("Token missing JTI claim; treating as revoked")
                return True

            # Consult shared token blacklist (fail-closed on error)
            try:
                blacklist = get_token_blacklist()
                if await blacklist.is_blacklisted(jti_value):
                    return True
            except Exception as exc:
                logger.error(f"Token blacklist check failed; treating token as revoked: {exc}")
                return True

            # Hash the token for storage/comparison
            token_hash = self.hash_token(token)
            
            # Check Redis cache first if available
            if self.redis_client:
                try:
                    blacklisted = await self.redis_client.get(f"blacklist:{token_hash}")
                    if blacklisted:
                        return True
                except RedisError:
                    pass  # Fall back to database
            
            # Check database for revoked sessions
            db_pool = await self._ensure_db_pool()
            if getattr(db_pool, "pool", None):
                # PostgreSQL
                result = await db_pool.fetchval(
                    """
                    SELECT COUNT(*) 
                    FROM sessions 
                    WHERE token_hash = $1 AND is_revoked = true
                    """,
                    token_hash
                )
            else:
                # SQLite
                result = await db_pool.fetchval(
                    """
                    SELECT COUNT(*) 
                    FROM sessions 
                    WHERE token_hash = ? AND is_revoked = 1
                    """,
                    token_hash
                )
            
            return result > 0
            
        except Exception as e:
            logger.error(f"Error checking token blacklist; treating token as revoked: {e}")
            return True
    
    async def get_user_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all sessions for a user (alias for get_active_sessions)"""
        return await self.get_active_sessions(user_id)
    
    async def get_active_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all active sessions for a user"""
        if not self._initialized:
            await self.initialize()
        
        try:
            db_pool = await self._ensure_db_pool()
            async with db_pool.acquire() as conn:
                if hasattr(conn, 'fetch'):
                    # PostgreSQL
                    rows = await conn.fetch(
                        """
                        SELECT id, ip_address, user_agent, device_id,
                               created_at, last_activity, expires_at
                        FROM sessions
                        WHERE user_id = $1 AND is_active = TRUE
                        ORDER BY last_activity DESC
                        """,
                        user_id
                    )
                    sessions = [dict(row) for row in rows]
                else:
                    # SQLite
                    cursor = await conn.execute(
                        """
                        SELECT id, ip_address, user_agent, device_id,
                               created_at, last_activity, expires_at
                        FROM sessions
                        WHERE user_id = ? AND is_active = 1
                        ORDER BY last_activity DESC
                        """,
                        (user_id,)
                    )
                    rows = await cursor.fetchall()
                    sessions = []
                    for row in rows:
                        sessions.append({
                            "id": row[0],
                            "ip_address": row[1],
                            "user_agent": row[2],
                            "device_id": row[3],
                            "created_at": row[4],
                            "last_activity": row[5],
                            "expires_at": row[6]
                        })
            
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions from database and cache"""
        if not self._initialized:
            await self.initialize()
        
        try:
            logger.info("Starting session cleanup...")
            
            db_pool = await self._ensure_db_pool()
            async with db_pool.transaction() as conn:
                # First check if the sessions table exists
                if hasattr(conn, 'fetchval'):
                    # PostgreSQL
                    table_exists = await conn.fetchval(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'sessions'
                        )
                        """
                    )
                else:
                    # SQLite
                    cursor = await conn.execute(
                        """
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name='sessions'
                        """
                    )
                    result = await cursor.fetchone()
                    table_exists = result is not None
                
                if not table_exists:
                    logger.debug("Sessions table does not exist, skipping cleanup")
                    return
                
                # Proceed with cleanup if table exists
                if hasattr(conn, 'fetchval'):
                    # PostgreSQL
                    rows = await conn.fetch(
                        """
                        DELETE FROM sessions
                        WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '1 day'
                        OR (is_active = FALSE AND revoked_at < CURRENT_TIMESTAMP - INTERVAL '7 days')
                        RETURNING id
                        """
                    )
                    deleted = len(rows)
                else:
                    # SQLite
                    cursor = await conn.execute(
                        """
                        DELETE FROM sessions
                        WHERE datetime(expires_at) < datetime('now', '-1 day')
                        OR (is_active = 0 AND datetime(revoked_at) < datetime('now', '-7 days'))
                        """
                    )
                    deleted = cursor.rowcount
                    await conn.commit()
                
                if deleted:
                    logger.info(f"Cleaned up {deleted} expired sessions")
                
                # Clean Redis cache
                if self.redis_client:
                    await self._cleanup_redis_cache()
                    
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
    
    # Redis cache helpers
    async def _fetch_session_record(
        self,
        conn,
        *,
        token_hash: Optional[str] = None,
        session_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetch session metadata joined with user state and active/expiry filters."""
        if token_hash is None and session_id is None:
            raise ValueError("Must provide token_hash or session_id")

        if hasattr(conn, "fetchrow"):
            # PostgreSQL
            if session_id is not None:
                row = await conn.fetchrow(
                    """
                    SELECT s.id, s.user_id, s.expires_at, s.is_active,
                           s.revoked_at, u.username, u.role, u.is_active as user_active
                    FROM sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.id = $1
                    AND s.is_active = TRUE
                    AND s.expires_at > CURRENT_TIMESTAMP
                    """,
                    session_id,
                )
            else:
                row = await conn.fetchrow(
                    """
                    SELECT s.id, s.user_id, s.expires_at, s.is_active,
                           s.revoked_at, u.username, u.role, u.is_active as user_active
                    FROM sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.token_hash = $1
                    AND s.is_active = TRUE
                    AND s.expires_at > CURRENT_TIMESTAMP
                    """,
                    token_hash,
                )
            return dict(row) if row else None

        # SQLite path
        if session_id is not None:
            cursor = await conn.execute(
                """
                SELECT s.id, s.user_id, s.expires_at, s.is_active,
                       s.revoked_at, u.username, u.role, u.is_active as user_active
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.id = ?
                AND s.is_active = 1
                AND datetime(s.expires_at) > datetime('now')
                """,
                (session_id,),
            )
        else:
            cursor = await conn.execute(
                """
                SELECT s.id, s.user_id, s.expires_at, s.is_active,
                       s.revoked_at, u.username, u.role, u.is_active as user_active
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token_hash = ?
                AND s.is_active = 1
                AND datetime(s.expires_at) > datetime('now')
                """,
                (token_hash,),
            )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "expires_at": row[2],
            "is_active": row[3],
            "revoked_at": row[4],
            "username": row[5],
            "role": row[6],
            "user_active": row[7],
        }

    async def _cache_session(
        self,
        token_hash: str,
        user_id: int,
        session_id: int,
        expires_at: datetime,
        *,
        user_active: bool = True,
        revoked: bool = False,
    ):
        """Cache session metadata in Redis (validation state included)."""
        if not self.redis_client:
            return
        
        try:
            cache_data = {
                "user_id": user_id,
                "session_id": session_id,
                "expires_at": expires_at.isoformat(),
                "user_active": bool(user_active),
                "revoked": bool(revoked),
            }
            
            # Calculate TTL
            ttl = int((expires_at - datetime.utcnow()).total_seconds())
            if ttl > 0:
                # Cache session data
                await self.redis_client.setex(
                    f"session:{token_hash}",
                    ttl,
                    json.dumps(cache_data)
                )
                
                # Add to user's session set
                await self.redis_client.sadd(f"user:{user_id}:sessions", session_id)
                await self.redis_client.expire(f"user:{user_id}:sessions", ttl)
                
        except RedisError as e:
            logger.warning(f"Failed to cache session: {e}")
    
    async def _get_cached_session(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """Get session metadata from Redis cache (if still valid)."""
        if not self.redis_client:
            return None
        
        try:
            cached = await self.redis_client.get(f"session:{token_hash}")
            if cached:
                data = json.loads(cached)
                expires = datetime.fromisoformat(data['expires_at'])
                if expires > datetime.utcnow():
                    data.setdefault("user_active", True)
                    data.setdefault("revoked", False)
                    return data
                else:
                    # Expired, remove from cache
                    await self.redis_client.delete(f"session:{token_hash}")
            return None
            
        except RedisError:
            return None
    
    async def _clear_session_cache(self, session_id: int):
        """Clear specific session from cache"""
        if not self.redis_client:
            return
        
        try:
            # Find and delete session by scanning (not ideal but necessary)
            async for key in self.redis_client.scan_iter("session:*"):
                data = await self.redis_client.get(key)
                if data:
                    session_data = json.loads(data)
                    if session_data.get('session_id') == session_id:
                        await self.redis_client.delete(key)
                        break
                        
        except RedisError:
            pass
    
    async def _clear_user_sessions_cache(self, user_id: int):
        """Clear all sessions for a user from cache"""
        if not self.redis_client:
            return
        
        try:
            # Clear each session
            async for key in self.redis_client.scan_iter("session:*"):
                data = await self.redis_client.get(key)
                if data:
                    session_data = json.loads(data)
                    if session_data.get('user_id') == user_id:
                        await self.redis_client.delete(key)
            
            # Clear user's session set
            await self.redis_client.delete(f"user:{user_id}:sessions")
            
        except RedisError:
            pass
    
    async def _cleanup_redis_cache(self):
        """Clean up expired sessions from Redis"""
        if not self.redis_client:
            return
        
        try:
            count = 0
            async for key in self.redis_client.scan_iter("session:*"):
                ttl = await self.redis_client.ttl(key)
                if ttl == -1:  # No expiry set
                    await self.redis_client.delete(key)
                    count += 1
            
            if count:
                logger.info(f"Cleaned {count} sessions from Redis cache")
                
        except RedisError as e:
            logger.warning(f"Redis cache cleanup failed: {e}")
    
    async def _update_last_activity(self, session_id: int, conn):
        """Update last activity timestamp for a session"""
        try:
            if hasattr(conn, 'fetchrow'):
                # PostgreSQL
                await conn.execute(
                    "UPDATE sessions SET last_activity = CURRENT_TIMESTAMP WHERE id = $1",
                    session_id
                )
            else:
                # SQLite
                await conn.execute(
                    "UPDATE sessions SET last_activity = datetime('now') WHERE id = ?",
                    (session_id,)
                )
        except Exception:
            # Don't fail on activity update
            pass
    
    async def shutdown(self):
        """Shutdown session manager and cleanup"""
        # Guard against shutdown being called after the event loop has closed
        try:
            if self.scheduler.running:
                loop = None
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = None
                if loop is None or not loop.is_closed():
                    self.scheduler.shutdown(wait=False)
        except Exception as e:
            # In tests, teardown may run after the loop is closed; ignore scheduler shutdown errors
            logger.debug(f"SessionManager scheduler shutdown skipped: {e}")
        
        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception as e:
                logger.debug(f"Ignoring Redis client shutdown error: {e}")
            finally:
                self.redis_client = None
        
        logger.info("SessionManager shutdown complete")


#######################################################################################################################
#
# Module Functions

# Global instance
_session_manager: Optional[SessionManager] = None


async def get_session_manager() -> SessionManager:
    """Get session manager singleton instance"""
    global _session_manager
    if not _session_manager:
        _session_manager = SessionManager()
        await _session_manager.initialize()
    return _session_manager


async def reset_session_manager():
    """Reset session manager (for testing)"""
    global _session_manager
    if _session_manager:
        await _session_manager.shutdown()
    _session_manager = None


#
# End of session_manager.py
#######################################################################################################################
