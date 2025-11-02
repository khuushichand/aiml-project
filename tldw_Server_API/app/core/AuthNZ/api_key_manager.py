# api_key_manager.py
# Description: API key management with rotation, expiration, and revocation capabilities
#
# Imports
import secrets
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
#
# 3rd-party imports
from loguru import logger
#
# Local imports
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.exceptions import DatabaseError, InvalidTokenError
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import (
    derive_hmac_key,
    derive_hmac_key_candidates,
)

#######################################################################################################################
#
# Enums and Constants
#

class APIKeyStatus(Enum):
    """API key status states"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ROTATED = "rotated"

class APIKeyScope(Enum):
    """API key permission scopes"""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    SERVICE = "service"

#######################################################################################################################
#
# API Key Manager Class
#

class APIKeyManager:
    """Manages API keys with rotation, expiration, and revocation capabilities"""

    def __init__(self, db_pool: Optional[DatabasePool] = None):
        """Initialize API key manager"""
        self.db_pool = db_pool
        self._initialized = False
        self.settings = get_settings()
        self.key_prefix = "tldw_"  # Prefix for identifying our API keys
        self.key_length = 32  # Length of random part
        # Fingerprint the HMAC key material to detect settings changes (e.g., JWT_SECRET_KEY)
        try:
            key_material = (
                (self.settings.JWT_SECRET_KEY or "")
                or (self.settings.API_KEY_PEPPER or "")
            ) or "tldw_default_api_key_hmac"
            self._hmac_key_fingerprint = (key_material[:32])
        except Exception:
            self._hmac_key_fingerprint = ""

    async def initialize(self):
        """Initialize database connection and ensure tables exist"""
        if self._initialized:
            return

        # Get database pool
        if not self.db_pool:
            self.db_pool = await get_db_pool()

        # Create API keys table if it doesn't exist
        await self._create_tables()

        self._initialized = True
        logger.info("APIKeyManager initialized")

    async def _create_tables(self):
        """Create API keys and related tables if they don't exist"""
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, 'fetchval'):
                    # PostgreSQL
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS api_keys (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL,
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
                            revoke_reason TEXT,
                            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                        )
                    """)

                    # Create indexes
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_expires_at ON api_keys(expires_at)")

                    # Create API key audit log table
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS api_key_audit_log (
                            id SERIAL PRIMARY KEY,
                            api_key_id INTEGER NOT NULL,
                            action VARCHAR(50) NOT NULL,
                            user_id INTEGER,
                            ip_address VARCHAR(45),
                            user_agent TEXT,
                            details JSONB,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE
                        )
                    """)
                    # Ensure Virtual Key columns (Postgres)
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

                else:
                    # SQLite
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS api_keys (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            key_hash TEXT UNIQUE NOT NULL,
                            key_prefix TEXT NOT NULL,
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
                    # Ensure Virtual Key columns (SQLite)
                    cur = await conn.execute("PRAGMA table_info(api_keys)")
                    rows = await cur.fetchall()
                    cols = {r[1] for r in rows}
                    async def _add_col(name: str, decl: str):
                        if name not in cols:
                            await conn.execute(f"ALTER TABLE api_keys ADD COLUMN {decl}")
                    await _add_col('is_virtual', "is_virtual INTEGER DEFAULT 0")
                    await _add_col('parent_key_id', "parent_key_id INTEGER REFERENCES api_keys(id)")
                    await _add_col('org_id', "org_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL")
                    await _add_col('team_id', "team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL")
                    await _add_col('llm_budget_day_tokens', "llm_budget_day_tokens INTEGER")
                    await _add_col('llm_budget_month_tokens', "llm_budget_month_tokens INTEGER")
                    await _add_col('llm_budget_day_usd', "llm_budget_day_usd REAL")
                    await _add_col('llm_budget_month_usd', "llm_budget_month_usd REAL")
                    await _add_col('llm_allowed_endpoints', "llm_allowed_endpoints TEXT")
                    await _add_col('llm_allowed_providers', "llm_allowed_providers TEXT")
                    await _add_col('llm_allowed_models', "llm_allowed_models TEXT")

                    # Create indexes
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_expires_at ON api_keys(expires_at)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_virtual ON api_keys(is_virtual)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_org ON api_keys(org_id)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_team ON api_keys(team_id)")

                    # Create API key audit log table
                    await conn.execute("""
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

                    await conn.commit()

                logger.debug("API keys tables and indexes created/verified")

        except Exception as e:
            logger.error(f"Failed to create API keys tables: {e}")
            raise DatabaseError(f"Failed to create API keys tables: {e}")

    def generate_api_key(self) -> tuple[str, str]:
        """
        Generate a new API key

        Returns:
            Tuple of (full_key, key_hash)
            - full_key: The complete API key to give to the user
            - key_hash: The hash to store in the database
        """
        # Generate random key
        random_part = secrets.token_urlsafe(self.key_length)
        full_key = f"{self.key_prefix}{random_part}"

        # Create HMAC hash for storage using centralized derivation
        hmac_key = derive_hmac_key(self.settings)
        key_hash = hmac.new(hmac_key, full_key.encode("utf-8"), hashlib.sha256).hexdigest()

        return full_key, key_hash

    def hash_api_key(self, api_key: str) -> str:
        """
        Hash an API key for comparison using HMAC-SHA256.

        This provides better security than plain SHA256 by using a secret key,
        preventing length extension attacks.

        Note: We use HMAC-SHA256 instead of Argon2 because:
        - API keys are already high-entropy (cryptographically random)
        - This hash is used for fast lookups on every API request
        - Argon2 would add unnecessary latency (100-1000x slower)

        Args:
            api_key: The API key to hash

        Returns:
            HMAC-SHA256 hash of the API key
        """
        candidates = self.hash_candidates(api_key)
        if not candidates:
            raise ValueError("Unable to derive API key hash candidates")
        return candidates[0]

    def hash_candidates(self, api_key: str) -> List[str]:
        """Return ordered HMAC hashes for API keys across active/legacy secrets."""
        hashes: List[str] = []
        try:
            key_candidates = derive_hmac_key_candidates(self.settings)
        except Exception:
            key_candidates = [derive_hmac_key(self.settings)]
        for key in key_candidates:
            digest = hmac.new(key, api_key.encode("utf-8"), hashlib.sha256).hexdigest()
            if digest not in hashes:
                hashes.append(digest)
        return hashes

    async def create_api_key(
        self,
        user_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        scope: str = "read",
        expires_in_days: Optional[int] = 90,
        rate_limit: Optional[int] = None,
        allowed_ips: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new API key for a user

        Args:
            user_id: User ID who owns the key
            name: Optional name for the key
            description: Optional description
            scope: Permission scope (read, write, admin, service)
            expires_in_days: Days until expiration (None = no expiration)
            rate_limit: Custom rate limit for this key
            allowed_ips: List of allowed IP addresses
            metadata: Additional metadata

        Returns:
            Dictionary with key information including the actual key (only shown once)
        """
        if not self._initialized:
            await self.initialize()

        # Generate the key
        full_key, key_hash = self.generate_api_key()
        key_prefix = full_key[:10] + "..."  # Store prefix for identification

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, 'fetchval'):
                    # PostgreSQL
                    import json
                    key_id = await conn.fetchval(
                        """
                        INSERT INTO api_keys (
                            user_id, key_hash, key_prefix, name, description,
                            scope, expires_at, rate_limit, allowed_ips, metadata
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        RETURNING id
                        """,
                        user_id, key_hash, key_prefix, name, description,
                        scope, expires_at, rate_limit,
                        json.dumps(allowed_ips) if allowed_ips else None,
                        json.dumps(metadata) if metadata else None
                    )
                else:
                    # SQLite
                    import json
                    cursor = await conn.execute(
                        """
                        INSERT INTO api_keys (
                            user_id, key_hash, key_prefix, name, description,
                            scope, expires_at, rate_limit, allowed_ips, metadata
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (user_id, key_hash, key_prefix, name, description,
                         scope, expires_at.isoformat() if expires_at else None,
                         rate_limit,
                         json.dumps(allowed_ips) if allowed_ips else None,
                         json.dumps(metadata) if metadata else None)
                    )
                    key_id = cursor.lastrowid
                    await conn.commit()

                # Log the creation
                await self._log_action(key_id, "created", user_id)

                if get_settings().PII_REDACT_LOGS:
                    logger.info("Created API key for authenticated user (details redacted)")
                else:
                    logger.info(f"Created API key {key_id} for user {user_id}")

                return {
                    "id": key_id,
                    "key": full_key,  # Only returned on creation!
                    "key_prefix": key_prefix,
                    "name": name,
                    "scope": scope,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                    "created_at": datetime.utcnow().isoformat(),
                    "message": "Store this key securely - it will not be shown again"
                }

        except Exception as e:
            logger.error(f"Failed to create API key: {e}")
            raise DatabaseError(f"Failed to create API key: {e}")

    async def create_virtual_key(
        self,
        *,
        user_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        expires_in_days: Optional[int] = 30,
        org_id: Optional[int] = None,
        team_id: Optional[int] = None,
        allowed_endpoints: Optional[list[str]] = None,
        allowed_providers: Optional[list[str]] = None,
        allowed_models: Optional[list[str]] = None,
        budget_day_tokens: Optional[int] = None,
        budget_month_tokens: Optional[int] = None,
        budget_day_usd: Optional[float] = None,
        budget_month_usd: Optional[float] = None,
        parent_key_id: Optional[int] = None,
        # Extra generic constraints (stored in metadata)
        allowed_methods: Optional[list[str]] = None,
        allowed_paths: Optional[list[str]] = None,
        max_calls: Optional[int] = None,
        max_runs: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a Virtual API Key with LLM endpoint scope and budgets."""
        if not self._initialized:
            await self.initialize()

        full_key, key_hash = self.generate_api_key()
        key_prefix = full_key[:10] + "..."
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        try:
            async with self.db_pool.transaction() as conn:
                import json
                if hasattr(conn, 'fetchval'):
                    # In asyncpg 0.30, Json wrapper is removed; pass JSON strings and cast to jsonb
                    import json as _json
                    _endpoints = _json.dumps(allowed_endpoints) if allowed_endpoints is not None else None
                    _providers = _json.dumps(allowed_providers) if allowed_providers is not None else None
                    _models    = _json.dumps(allowed_models)    if allowed_models    is not None else None
                    _meta_dict = {}
                    if allowed_methods:
                        _meta_dict['allowed_methods'] = [str(x).upper() for x in allowed_methods]
                    if allowed_paths:
                        _meta_dict['allowed_paths'] = [str(x) for x in allowed_paths]
                    if max_calls is not None:
                        _meta_dict['max_calls'] = int(max_calls)
                    if max_runs is not None:
                        _meta_dict['max_runs'] = int(max_runs)
                    _metadata = _json.dumps(_meta_dict) if _meta_dict else None

                    # Detect column types to choose JSONB cast or plain text insert (compat across migrations)
                    try:
                        col_type = await conn.fetchval(
                            """
                            SELECT data_type FROM information_schema.columns
                            WHERE table_name = 'api_keys' AND column_name = 'llm_allowed_endpoints'
                            """
                        )
                    except Exception:
                        col_type = None
                    is_jsonb = isinstance(col_type, str) and ('json' in col_type.lower())

                    if is_jsonb:
                        key_id = await conn.fetchval(
                            """
                            INSERT INTO api_keys (
                                user_id, key_hash, key_prefix, name, description, scope, status, expires_at,
                                is_virtual, parent_key_id, org_id, team_id,
                                llm_budget_day_tokens, llm_budget_month_tokens,
                                llm_budget_day_usd, llm_budget_month_usd,
                                llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models,
                                metadata
                            ) VALUES (
                                $1,$2,$3,$4,$5,$6,'active',$7,
                                TRUE,$8,$9,$10,
                                $11,$12,$13,$14,$15::jsonb,$16::jsonb,$17::jsonb,
                                ($18)::jsonb
                            ) RETURNING id
                            """,
                            user_id, key_hash, key_prefix, name, description, 'read', expires_at,
                            parent_key_id, org_id, team_id,
                            budget_day_tokens, budget_month_tokens,
                            budget_day_usd, budget_month_usd,
                            _endpoints, _providers, _models,
                            _metadata,
                        )
                    else:
                        key_id = await conn.fetchval(
                            """
                            INSERT INTO api_keys (
                                user_id, key_hash, key_prefix, name, description, scope, status, expires_at,
                                is_virtual, parent_key_id, org_id, team_id,
                                llm_budget_day_tokens, llm_budget_month_tokens,
                                llm_budget_day_usd, llm_budget_month_usd,
                                llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models,
                                metadata
                            ) VALUES (
                                $1,$2,$3,$4,$5,$6,'active',$7,
                                TRUE,$8,$9,$10,
                                $11,$12,$13,$14,$15,$16,$17,
                                $18
                            ) RETURNING id
                            """,
                            user_id, key_hash, key_prefix, name, description, 'read', expires_at,
                            parent_key_id, org_id, team_id,
                            budget_day_tokens, budget_month_tokens,
                            budget_day_usd, budget_month_usd,
                            _endpoints, _providers, _models,
                            _metadata,
                        )
                else:
                    import json
                    _meta_dict = {}
                    if allowed_methods:
                        _meta_dict['allowed_methods'] = [str(x).upper() for x in allowed_methods]
                    if allowed_paths:
                        _meta_dict['allowed_paths'] = [str(x) for x in allowed_paths]
                    if max_calls is not None:
                        _meta_dict['max_calls'] = int(max_calls)
                    if max_runs is not None:
                        _meta_dict['max_runs'] = int(max_runs)
                    _metadata = json.dumps(_meta_dict) if _meta_dict else None
                    cursor = await conn.execute(
                        """
                        INSERT INTO api_keys (
                            user_id, key_hash, key_prefix, name, description, scope, status, expires_at,
                            is_virtual, parent_key_id, org_id, team_id,
                            llm_budget_day_tokens, llm_budget_month_tokens,
                            llm_budget_day_usd, llm_budget_month_usd,
                            llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models,
                            metadata
                        ) VALUES (?,?,?,?,?,?,'active',?,
                            1,?,?,?,?,?,?,?,?,?,?,?
                        )
                        """,
                        (
                            user_id, key_hash, key_prefix, name, description, 'read',
                            expires_at.isoformat() if expires_at else None,
                            parent_key_id, org_id, team_id,
                            budget_day_tokens, budget_month_tokens,
                            budget_day_usd, budget_month_usd,
                            (json.dumps(allowed_endpoints) if allowed_endpoints else None),
                            (json.dumps(allowed_providers) if allowed_providers else None),
                            (json.dumps(allowed_models) if allowed_models else None),
                            _metadata,
                        )
                    )
                    key_id = cursor.lastrowid
                    await conn.commit()

            await self._log_action(key_id, "created_virtual", user_id, {
                "org_id": org_id, "team_id": team_id, "budgets": {
                    "day_tokens": budget_day_tokens,
                    "month_tokens": budget_month_tokens,
                    "day_usd": budget_day_usd,
                    "month_usd": budget_month_usd,
                },
                "allowed_endpoints": allowed_endpoints or []
            })

            return {
                "id": key_id,
                "key": full_key,
                "key_prefix": key_prefix,
                "name": name,
                "scope": 'read',
                "expires_at": expires_at.isoformat() if expires_at else None,
                "created_at": datetime.utcnow().isoformat(),
                "message": "Store this key securely - it will not be shown again"
            }

        except Exception as e:
            logger.error(f"Failed to create virtual API key: {e}")
            raise DatabaseError(f"Failed to create virtual API key: {e}")

    async def validate_api_key(
        self,
        api_key: str,
        required_scope: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Validate an API key and return its information

        Args:
            api_key: The API key to validate
            required_scope: Required permission scope
            ip_address: Client IP address for validation and logging

        Returns:
            Key information if valid, None if invalid
        """
        if not self._initialized:
            await self.initialize()

        hash_candidates = self.hash_candidates(api_key)
        if not hash_candidates:
            return None

        try:
            # Get key information (dialect-aware placeholders)
            if getattr(self.db_pool, 'pool', None) is not None:
                result = await self.db_pool.fetchone(
                    """
                    SELECT id, user_id, name, scope, status, expires_at,
                           rate_limit, allowed_ips, usage_count, key_hash,
                           COALESCE(is_virtual, FALSE) AS is_virtual,
                           parent_key_id, org_id, team_id,
                           llm_budget_day_tokens, llm_budget_month_tokens,
                           llm_budget_day_usd, llm_budget_month_usd,
                           llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models,
                           metadata
                    FROM api_keys
                    WHERE key_hash = ANY($1::text[]) AND status = $2
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    hash_candidates, APIKeyStatus.ACTIVE.value
                )
            else:
                placeholders = ",".join("?" for _ in hash_candidates)
                query = f"""
                    SELECT id, user_id, name, scope, status, expires_at,
                           rate_limit, allowed_ips, usage_count, key_hash,
                           COALESCE(is_virtual, 0) AS is_virtual,
                           parent_key_id, org_id, team_id,
                           llm_budget_day_tokens, llm_budget_month_tokens,
                           llm_budget_day_usd, llm_budget_month_usd,
                           llm_allowed_endpoints, llm_allowed_providers, llm_allowed_models,
                           metadata
                    FROM api_keys
                    WHERE key_hash IN ({placeholders}) AND status = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                params = (*hash_candidates, APIKeyStatus.ACTIVE.value)
                result = await self.db_pool.fetchone(query, params)

            if not result:
                return None

            key_info = dict(result)
            stored_hash = key_info.get("key_hash")
            primary_hash = hash_candidates[0]

            # Check expiration
            if key_info['expires_at']:
                expires_at = datetime.fromisoformat(key_info['expires_at']) if isinstance(key_info['expires_at'], str) else key_info['expires_at']
                if expires_at < datetime.utcnow():
                    await self._mark_expired(key_info['id'])
                    return None

            # Check IP restrictions
            if key_info['allowed_ips']:
                try:
                    raw = key_info['allowed_ips']
                    if isinstance(raw, str):
                        allowed_ips = json.loads(raw)
                    else:
                        allowed_ips = raw
                    allowed_ips = {str(ip).strip() for ip in (allowed_ips or []) if str(ip).strip()}
                except Exception as decode_error:
                    logger.error(
                        f"API key {key_info['id']} allowlist could not be decoded; denying access: {decode_error}"
                    )
                    return None
                if allowed_ips:
                    normalized_ip = (ip_address or "").strip()
                    if not normalized_ip:
                        logger.warning(
                            f"API key {key_info['id']} requires client IP but none was supplied; denying access"
                        )
                        return None
                    if normalized_ip not in allowed_ips:
                        logger.warning(
                            f"API key {key_info['id']} used from unauthorized IP: {normalized_ip}"
                        )
                        return None

            if stored_hash and stored_hash != primary_hash:
                try:
                    await self.db_pool.execute(
                        "UPDATE api_keys SET key_hash = ? WHERE id = ?",
                        primary_hash,
                        key_info["id"],
                    )
                    key_info["key_hash"] = primary_hash
                except Exception as normalize_exc:
                    logger.warning(
                        f"Failed to normalize API key hash for key {key_info.get('id')}: {normalize_exc}"
                    )
            key_info.pop("key_hash", None)

            # Check scope
            if required_scope:
                key_scope = key_info['scope']
                if not self._has_scope(key_scope, required_scope):
                    return None

            # Update usage statistics
            await self._update_usage(key_info['id'], ip_address)

            # Optional lightweight audit of usage
            try:
                if self.settings.API_KEY_AUDIT_LOG_USAGE:
                    await self._log_action(key_info['id'], "used", key_info.get('user_id'))
            except Exception as _e:
                # Do not fail request on audit write
                logger.debug(f"API key usage audit skipped/failed: {_e}")

            return key_info

        except Exception as e:
            logger.error(f"Failed to validate API key: {e}")
            return None

    async def rotate_api_key(
        self,
        key_id: int,
        user_id: int,
        expires_in_days: Optional[int] = 90
    ) -> Dict[str, Any]:
        """
        Rotate an API key - create new one and revoke old one

        Args:
            key_id: ID of the key to rotate
            user_id: User requesting rotation (for authorization)
            expires_in_days: Expiration for new key

        Returns:
            New key information
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Get existing key info
            old_key = await self.db_pool.fetchone(
                "SELECT * FROM api_keys WHERE id = ? AND user_id = ?",
                key_id, user_id
            )

            if not old_key:
                raise ValueError("API key not found or unauthorized")

            old_key = dict(old_key)

            # Normalize stored JSON/JSONB fields that may already be parsed by the driver
            def _coerce_json_field(value):
                if value is None:
                    return None
                if isinstance(value, (dict, list)):
                    return value
                if isinstance(value, str) and value.strip():
                    return json.loads(value)
                return None

            # Create new key with same settings
            new_key_result = await self.create_api_key(
                user_id=user_id,
                name=f"{old_key['name']} (rotated)" if old_key['name'] else "Rotated key",
                description=old_key['description'],
                scope=old_key['scope'],
                expires_in_days=expires_in_days,
                rate_limit=old_key['rate_limit'],
                allowed_ips=_coerce_json_field(old_key.get('allowed_ips')),
                metadata=_coerce_json_field(old_key.get('metadata'))
            )

            # Update rotation references
            async with self.db_pool.transaction() as conn:
                # Mark old key as rotated
                if hasattr(conn, 'fetchrow'):
                    await conn.execute(
                        """
                        UPDATE api_keys
                        SET status = $1, rotated_to = $2, revoked_at = $3,
                            revoke_reason = $4
                        WHERE id = $5
                        """,
                        APIKeyStatus.ROTATED.value, new_key_result['id'],
                        datetime.utcnow(), "Key rotation", key_id
                    )

                    # Update new key with rotation reference
                    await conn.execute(
                        "UPDATE api_keys SET rotated_from = $1 WHERE id = $2",
                        key_id, new_key_result['id']
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE api_keys
                        SET status = ?, rotated_to = ?, revoked_at = ?,
                            revoke_reason = ?
                        WHERE id = ?
                        """,
                        (APIKeyStatus.ROTATED.value, new_key_result['id'],
                         datetime.utcnow().isoformat(), "Key rotation", key_id)
                    )

                    await conn.execute(
                        "UPDATE api_keys SET rotated_from = ? WHERE id = ?",
                        (key_id, new_key_result['id'])
                    )

                    await conn.commit()

            # Log the rotation
            await self._log_action(key_id, "rotated", user_id)
            await self._log_action(new_key_result['id'], "created_from_rotation", user_id)

            logger.info(f"Rotated API key {key_id} to {new_key_result['id']}")

            return new_key_result

        except Exception as e:
            logger.error(f"Failed to rotate API key: {e}")
            raise DatabaseError(f"Failed to rotate API key: {e}")

    async def revoke_api_key(
        self,
        key_id: int,
        user_id: int,
        reason: Optional[str] = None
    ) -> bool:
        """
        Revoke an API key

        Args:
            key_id: ID of the key to revoke
            user_id: User requesting revocation
            reason: Reason for revocation

        Returns:
            True if successful
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    result = await conn.execute(
                        """
                        UPDATE api_keys
                        SET status = $1, revoked_at = $2, revoked_by = $3,
                            revoke_reason = $4
                        WHERE id = $5 AND user_id = $6 AND status = $7
                        """,
                        APIKeyStatus.REVOKED.value, datetime.utcnow(), user_id,
                        reason or "Manual revocation", key_id, user_id,
                        APIKeyStatus.ACTIVE.value
                    )
                    success = result != "UPDATE 0"
                else:
                    cursor = await conn.execute(
                        """
                        UPDATE api_keys
                        SET status = ?, revoked_at = ?, revoked_by = ?,
                            revoke_reason = ?
                        WHERE id = ? AND user_id = ? AND status = ?
                        """,
                        (APIKeyStatus.REVOKED.value, datetime.utcnow().isoformat(),
                         user_id, reason or "Manual revocation", key_id, user_id,
                         APIKeyStatus.ACTIVE.value)
                    )
                    success = cursor.rowcount > 0
                    await conn.commit()

            if success:
                await self._log_action(key_id, "revoked", user_id, {"reason": reason})
                logger.info(f"Revoked API key {key_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to revoke API key: {e}")
            raise DatabaseError(f"Failed to revoke API key: {e}")

    async def list_user_keys(
        self,
        user_id: int,
        include_revoked: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List all API keys for a user

        Args:
            user_id: User ID
            include_revoked: Include revoked/expired keys

        Returns:
            List of key information (without actual keys)
        """
        if not self._initialized:
            await self.initialize()

        try:
            if include_revoked:
                query = "SELECT * FROM api_keys WHERE user_id = ? ORDER BY created_at DESC"
            else:
                query = """
                    SELECT * FROM api_keys
                    WHERE user_id = ? AND status = ?
                    ORDER BY created_at DESC
                """

            if include_revoked:
                results = await self.db_pool.fetchall(query, user_id)
            else:
                results = await self.db_pool.fetchall(query, user_id, APIKeyStatus.ACTIVE.value)

            keys = []
            for row in results:
                key_dict = dict(row)
                # Never return the actual hash
                key_dict.pop('key_hash', None)
                keys.append(key_dict)

            return keys

        except Exception as e:
            logger.error(f"Failed to list user keys: {e}")
            raise DatabaseError(f"Failed to list user keys: {e}")

    async def cleanup_expired_keys(self):
        """Mark expired keys as expired"""
        if not self._initialized:
            await self.initialize()

        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    result = await conn.execute(
                        """
                        UPDATE api_keys
                        SET status = $1
                        WHERE status = $2 AND expires_at < $3
                        """,
                        APIKeyStatus.EXPIRED.value,
                        APIKeyStatus.ACTIVE.value,
                        datetime.utcnow()
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE api_keys
                        SET status = ?
                        WHERE status = ? AND expires_at < ?
                        """,
                        (APIKeyStatus.EXPIRED.value,
                         APIKeyStatus.ACTIVE.value,
                         datetime.utcnow().isoformat())
                    )
                    await conn.commit()

            logger.debug("Cleaned up expired API keys")

        except Exception as e:
            logger.error(f"Failed to cleanup expired keys: {e}")

    def _has_scope(self, key_scope: str, required_scope: str) -> bool:
        """Check if key scope satisfies required scope"""
        scope_hierarchy = {
            "read": 0,
            "write": 1,
            "admin": 2,
            "service": 3
        }

        key_level = scope_hierarchy.get(key_scope, 0)
        required_level = scope_hierarchy.get(required_scope, 0)

        return key_level >= required_level

    async def _update_usage(self, key_id: int, ip_address: Optional[str] = None):
        """Update usage statistics for a key"""
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    await conn.execute(
                        """
                        UPDATE api_keys
                        SET usage_count = COALESCE(usage_count, 0) + 1,
                            last_used_at = $1,
                            last_used_ip = $2
                        WHERE id = $3
                        """,
                        datetime.utcnow(), ip_address, key_id
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE api_keys
                        SET usage_count = COALESCE(usage_count, 0) + 1,
                            last_used_at = ?,
                            last_used_ip = ?
                        WHERE id = ?
                        """,
                        (datetime.utcnow().isoformat(), ip_address, key_id)
                    )
                    await conn.commit()
        except Exception as e:
            logger.error(f"Failed to update usage: {e}")

    async def _mark_expired(self, key_id: int):
        """Mark a key as expired"""
        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    await conn.execute(
                        "UPDATE api_keys SET status = $1 WHERE id = $2",
                        APIKeyStatus.EXPIRED.value, key_id
                    )
                else:
                    await conn.execute(
                        "UPDATE api_keys SET status = ? WHERE id = ?",
                        (APIKeyStatus.EXPIRED.value, key_id)
                    )
                    await conn.commit()
        except Exception as e:
            logger.error(f"Failed to mark key as expired: {e}")

    async def _log_action(
        self,
        key_id: int,
        action: str,
        user_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log an action in the audit log"""
        try:
            import json
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    import json as _json
                    _details = _json.dumps(details) if details is not None else None
                    await conn.execute(
                        """
                        INSERT INTO api_key_audit_log (api_key_id, action, user_id, details)
                        VALUES ($1, $2, $3, $4::jsonb)
                        """,
                        key_id, action, user_id, _details
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO api_key_audit_log (api_key_id, action, user_id, details)
                        VALUES (?, ?, ?, ?)
                        """,
                        (key_id, action, user_id,
                         json.dumps(details) if details else None)
                    )
                    await conn.commit()
        except Exception as e:
            logger.error(f"Failed to log action: {e}")


#######################################################################################################################
#
# Module Functions
#

# Global instance
_api_key_manager: Optional[APIKeyManager] = None

async def get_api_key_manager() -> APIKeyManager:
    """Get APIKeyManager singleton instance"""
    global _api_key_manager
    # If an instance exists but the HMAC key material has changed (env/settings), recreate it
    try:
        current_settings = get_settings()
        current_material = (
            (current_settings.JWT_SECRET_KEY or "")
            or (current_settings.API_KEY_PEPPER or "")
        ) or "tldw_default_api_key_hmac"
        current_fp = (current_material[:32])
    except Exception:
        current_fp = ""

    if _api_key_manager is not None:
        try:
            if getattr(_api_key_manager, "_hmac_key_fingerprint", None) != current_fp:
                _api_key_manager = None
        except Exception:
            _api_key_manager = None

    if not _api_key_manager:
        _api_key_manager = APIKeyManager()
        await _api_key_manager.initialize()
    return _api_key_manager


async def reset_api_key_manager():
    """Reset the APIKeyManager singleton (mainly for testing)."""
    global _api_key_manager
    _api_key_manager = None

#
# End of api_key_manager.py
#######################################################################################################################
