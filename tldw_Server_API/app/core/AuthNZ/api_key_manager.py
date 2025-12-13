# api_key_manager.py
# Description: API key management with rotation, expiration, and revocation capabilities
#
# Imports
import secrets
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from enum import Enum
#
# 3rd-party imports
from loguru import logger
#
# Local imports
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.exceptions import DatabaseError, InvalidTokenError
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import (
    derive_hmac_key,
    derive_hmac_key_candidates,
)

if TYPE_CHECKING:
    from tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo import AuthnzApiKeysRepo


def _compute_hmac_fingerprint(settings: Settings) -> str:
    """
    Compute a non-reversible fingerprint of HMAC key material for cache invalidation.

    This mirrors the precedence and candidate selection used by
    derive_hmac_key_candidates so that changes to SINGLE_USER_API_KEY,
    API_KEY_PEPPER, or JWT secrets/keys all produce a new fingerprint.
    """
    try:
        candidates = derive_hmac_key_candidates(settings)
        if not candidates:
            return ""
        # Use the current key candidate (first entry) as fingerprint material.
        # The candidate is already a 32-byte SHA256 digest; hash once more and
        # return a hex string to avoid exposing raw key bytes.
        return hashlib.sha256(candidates[0]).hexdigest()
    except Exception:
        # Preserve previous behavior: on any settings/derivation issue, return
        # an empty string rather than raising during manager initialization.
        return ""

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
        self._db_pool: Optional[DatabasePool] = None
        self._repo: Optional["AuthnzApiKeysRepo"] = None
        # Use the property setter so that any future re-binding of db_pool
        # explicitly clears the cached repository.
        self.db_pool = db_pool
        self._initialized = False
        self.settings = get_settings()
        self.key_prefix = "tldw_"  # Prefix for identifying our API keys
        self.key_length = 32  # Length of random part
        # Fingerprint the HMAC key material to detect settings changes (e.g., JWT_SECRET_KEY)
        self._hmac_key_fingerprint = _compute_hmac_fingerprint(self.settings)

    @property
    def db_pool(self) -> Optional[DatabasePool]:
        """Current database pool bound to this manager."""
        return getattr(self, "_db_pool", None)

    @db_pool.setter
    def db_pool(self, value: Optional[DatabasePool]) -> None:
        """
        Bind a database pool and reset the cached repository when it changes.

        This keeps the AuthnzApiKeysRepo lifecycle obvious when tests or
        callers swap out the underlying DatabasePool.
        """
        if getattr(self, "_db_pool", None) is not value:
            self._db_pool = value
            if hasattr(self, "_repo"):
                self._repo = None

    def _db_context_hint(self) -> str:
        """
        Return a short, non-sensitive description of the current AuthNZ DB context.

        Used only for error messages to help diagnose misconfigured tests or
        startup issues without logging full connection strings or secrets.
        """
        try:
            auth_mode = getattr(self.settings, "AUTH_MODE", None)
            db_url = getattr(self.settings, "DATABASE_URL", None)
            db_url_set = bool(db_url)
        except (AttributeError, TypeError):
            return "(AuthNZ settings unavailable)"
        return f"(AUTH_MODE={auth_mode}, DATABASE_URL_set={db_url_set})"

    def _get_repo(self) -> "AuthnzApiKeysRepo":
        """
        Lazily construct an AuthnzApiKeysRepo bound to the current db_pool.

        Import is local to avoid circular dependencies between the manager
        and the repository module.

        Raises:
            DatabaseError: If no database pool has been configured.
        """
        if self.db_pool is None:
            raise DatabaseError(
                f"APIKeyManager database pool is not initialized {self._db_context_hint()}"
            )
        from tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo import AuthnzApiKeysRepo

        if self._repo is None or getattr(self._repo, "db_pool", None) is not self.db_pool:
            self._repo = AuthnzApiKeysRepo(self.db_pool)
        return self._repo

    @staticmethod
    def _coerce_json_field(value: Any) -> Optional[Any]:
        """
        Normalize stored JSON/JSONB fields that may be parsed or serialized.

        Preserves previous behavior by raising JSON decode errors to callers.
        """
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str) and value.strip():
            return json.loads(value)
        return None

    def _parse_expires_at(self, expires_at_raw: Any) -> Optional[datetime]:
        """Parse and normalize expires_at to a timezone-aware datetime.

        Returns ``None`` when the value is missing or cannot be parsed.
        """
        if expires_at_raw is None:
            return None

        expires_at: Optional[datetime]
        if isinstance(expires_at_raw, datetime):
            expires_at = expires_at_raw
        elif isinstance(expires_at_raw, str):
            expires_at_str = expires_at_raw.strip()
            if not expires_at_str:
                return None
            expires_at_str = expires_at_str.replace("Z", "+00:00")
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
            except ValueError:
                return None
        else:
            return None

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return expires_at

    async def initialize(self):
        """Initialize database connection and ensure tables exist"""
        if self._initialized:
            return

        # Get database pool
        if self.db_pool is None:
            self.db_pool = await get_db_pool()

        # Create API keys table if it doesn't exist
        await self._create_tables()

        self._initialized = True
        logger.info("APIKeyManager initialized")

    async def _create_tables(self):
        """Create API keys and related tables if they don't exist"""
        try:
            repo = self._get_repo()
            await repo.ensure_tables()
            logger.debug("API keys tables and indexes created/verified")
        except Exception as e:
            logger.error(f"Failed to create API keys tables: {e}")
            raise DatabaseError(
                f"Failed to create API keys tables {self._db_context_hint()}: {e}"
            ) from e

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
        if expires_in_days is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        try:
            repo = self._get_repo()
            key_id = await repo.create_api_key_row(
                user_id=user_id,
                key_hash=key_hash,
                key_prefix=key_prefix,
                name=name,
                description=description,
                scope=scope,
                expires_at=expires_at,
                rate_limit=rate_limit,
                allowed_ips=allowed_ips,
                metadata=metadata,
            )

            # Log the creation (audit rows are still written here)
            await self._log_action(key_id, "created", user_id)

            if self.settings.PII_REDACT_LOGS:
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
                "created_at": datetime.now(timezone.utc).isoformat(),
                "message": "Store this key securely - it will not be shown again"
            }
        except Exception as e:
            logger.error(f"Failed to create API key: {e}")
            raise DatabaseError(
                f"Failed to create API key {self._db_context_hint()}: {e}"
            ) from e

    async def create_virtual_key(
        self,
        *,
        user_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        expires_in_days: Optional[int] = 30,
        org_id: Optional[int] = None,
        team_id: Optional[int] = None,
        allowed_endpoints: Optional[List[str]] = None,
        allowed_providers: Optional[List[str]] = None,
        allowed_models: Optional[List[str]] = None,
        budget_day_tokens: Optional[int] = None,
        budget_month_tokens: Optional[int] = None,
        budget_day_usd: Optional[float] = None,
        budget_month_usd: Optional[float] = None,
        parent_key_id: Optional[int] = None,
        # Extra generic constraints (stored in metadata)
        allowed_methods: Optional[List[str]] = None,
        allowed_paths: Optional[List[str]] = None,
        max_calls: Optional[int] = None,
        max_runs: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a Virtual API Key with LLM endpoint scope and budgets."""
        if not self._initialized:
            await self.initialize()

        full_key, key_hash = self.generate_api_key()
        key_prefix = full_key[:10] + "..."
        expires_at = None
        if expires_in_days is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        try:
            repo = self._get_repo()
            key_id = await repo.create_virtual_key_row(
                user_id=user_id,
                key_hash=key_hash,
                key_prefix=key_prefix,
                name=name,
                description=description,
                expires_at=expires_at,
                org_id=org_id,
                team_id=team_id,
                allowed_endpoints=allowed_endpoints,
                allowed_providers=allowed_providers,
                allowed_models=allowed_models,
                budget_day_tokens=budget_day_tokens,
                budget_month_tokens=budget_month_tokens,
                budget_day_usd=budget_day_usd,
                budget_month_usd=budget_month_usd,
                parent_key_id=parent_key_id,
                allowed_methods=allowed_methods,
                allowed_paths=allowed_paths,
                max_calls=max_calls,
                max_runs=max_runs,
            )

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
                "created_at": datetime.now(timezone.utc).isoformat(),
                "message": "Store this key securely - it will not be shown again"
            }

        except Exception as e:
            logger.error(f"Failed to create virtual API key: {e}")
            raise DatabaseError(
                f"Failed to create virtual API key {self._db_context_hint()}: {e}"
            ) from e

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
            repo = self._get_repo()
            result = await repo.fetch_active_by_hash_candidates(hash_candidates)
            if not result:
                return None

            key_info = dict(result)
            stored_hash = key_info.get("key_hash")
            primary_hash = hash_candidates[0]

            # Check expiration
            if key_info["expires_at"]:
                expires_at = self._parse_expires_at(key_info["expires_at"])
                if expires_at is None:
                    logger.error(
                        f"API key {key_info['id']} expires_at could not be parsed; denying access"
                    )
                    return None
                now_utc = datetime.now(timezone.utc)
                if expires_at < now_utc:
                    await self._mark_expired(key_info["id"])
                    return None

            # Check IP restrictions
            if key_info["allowed_ips"]:
                try:
                    allowed_ips_raw = self._coerce_json_field(key_info.get("allowed_ips"))
                    if allowed_ips_raw is None:
                        allowed_ips_value = key_info.get("allowed_ips")
                        if isinstance(allowed_ips_value, str) and allowed_ips_value.strip():
                            allowed_ips_raw = []
                        else:
                            raise TypeError("API key allowlist must be stored as JSON array")
                    if not isinstance(allowed_ips_raw, list):
                        raise TypeError("API key allowlist must be stored as JSON array")
                    allowed_ips = {str(ip).strip() for ip in allowed_ips_raw if str(ip).strip()}
                except (TypeError, ValueError, json.JSONDecodeError) as decode_error:
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
                    await repo.update_key_hash(key_info["id"], primary_hash)
                    key_info["key_hash"] = primary_hash
                except Exception as normalize_exc:
                    logger.warning(
                        f"Failed to normalize API key hash for key {key_info.get('id')}: {normalize_exc}"
                    )
            key_info.pop("key_hash", None)

            # Check scope
            if required_scope:
                key_scope = key_info.get("scope")
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

        except DatabaseError:
            # Surface explicit database failures so callers can respond with
            # a clear server-side error instead of silently denying access.
            raise
        except Exception as e:  # noqa: BLE001 - validation failures degrade to 'no key'
            logger.error(
                f"Failed to validate API key (ip={ip_address}, scope={required_scope}): {e}"
            )
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
            repo = self._get_repo()
            # Get existing key info (authorization check remains here)
            old_key = await repo.fetch_key_for_user(key_id=key_id, user_id=user_id)

            if not old_key:
                raise ValueError("API key not found or unauthorized")

            # Create new key with same settings
            new_key_result = await self.create_api_key(
                user_id=user_id,
                name=f"{old_key['name']} (rotated)" if old_key['name'] else "Rotated key",
                description=old_key['description'],
                scope=old_key['scope'],
                expires_in_days=expires_in_days,
                rate_limit=old_key['rate_limit'],
                allowed_ips=self._coerce_json_field(old_key.get('allowed_ips')),
                metadata=self._coerce_json_field(old_key.get('metadata'))
            )

            # Update rotation references via repository
            await repo.mark_rotated(
                old_key_id=key_id,
                new_key_id=new_key_result["id"],
                rotated_status=APIKeyStatus.ROTATED.value,
                reason="Key rotation",
                revoked_at=datetime.now(timezone.utc),
            )

            # Log the rotation
            await self._log_action(key_id, "rotated", user_id)
            await self._log_action(new_key_result['id'], "created_from_rotation", user_id)

            logger.info(f"Rotated API key {key_id} to {new_key_result['id']}")

            return new_key_result

        except (ValueError, InvalidTokenError):
            # Preserve auth/not-found semantics; callers map to appropriate 4xx.
            raise
        except Exception as e:
            logger.error(f"Failed to rotate API key: {e}")
            raise DatabaseError(
                f"Failed to rotate API key {self._db_context_hint()}: {e}"
            ) from e

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
            repo = self._get_repo()
            success = await repo.revoke_api_key_for_user(
                key_id=key_id,
                user_id=user_id,
                revoked_status=APIKeyStatus.REVOKED.value,
                active_status=APIKeyStatus.ACTIVE.value,
                reason=reason or "Manual revocation",
                revoked_at=datetime.now(timezone.utc),
            )

            if success:
                await self._log_action(key_id, "revoked", user_id, {"reason": reason})
                logger.info(f"Revoked API key {key_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to revoke API key: {e}")
            raise DatabaseError(
                f"Failed to revoke API key {self._db_context_hint()}: {e}"
            ) from e

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
            repo = self._get_repo()
            results = await repo.list_user_keys(user_id=user_id, include_revoked=include_revoked)

            keys = []
            for row in results:
                key_dict = dict(row)
                # Never return the actual hash
                key_dict.pop('key_hash', None)
                keys.append(key_dict)

            return keys

        except Exception as e:
            logger.error(f"Failed to list user keys: {e}")
            raise DatabaseError(
                f"Failed to list user keys {self._db_context_hint()}: {e}"
            ) from e

    async def cleanup_expired_keys(self):
        """Mark expired keys as expired"""
        if not self._initialized:
            await self.initialize()

        try:
            repo = self._get_repo()
            updated = await repo.expire_keys_before(
                now=datetime.now(timezone.utc),
                expired_status=APIKeyStatus.EXPIRED.value,
                active_status=APIKeyStatus.ACTIVE.value,
            )
            logger.debug(f"Cleaned up expired API keys (updated={updated})")
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
            repo = self._get_repo()
            await repo.increment_usage(key_id=key_id, ip_address=ip_address)
        except Exception as e:  # noqa: BLE001 - usage updates must not break requests
            logger.warning(f"Failed to update API key usage (key_id={key_id}): {e}")

    async def _mark_expired(self, key_id: int):
        """Mark a key as expired"""
        try:
            repo = self._get_repo()
            await repo.mark_key_expired(key_id=key_id, expired_status=APIKeyStatus.EXPIRED.value)
        except Exception as e:  # noqa: BLE001 - expiration updates must not break requests
            logger.warning(f"Failed to mark API key as expired (key_id={key_id}): {e}")

    async def _log_action(
        self,
        key_id: int,
        action: str,
        user_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log an action in the audit log"""
        try:
            repo = self._get_repo()
            await repo.insert_audit_log(
                key_id=key_id,
                action=action,
                user_id=user_id,
                details=details,
            )
        except Exception as e:  # noqa: BLE001 - audit logging should not block requests
            logger.warning(
                f"Failed to write API key audit log (key_id={key_id}, action={action}): {e}"
            )


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
        current_fp = _compute_hmac_fingerprint(current_settings)
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
