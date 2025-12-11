# api_key_manager.py
# Description: API key management with rotation, expiration, and revocation capabilities
#
# Imports
import secrets
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, TYPE_CHECKING
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

if TYPE_CHECKING:
    from tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo import AuthnzApiKeysRepo

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
        self._repo: Optional["AuthnzApiKeysRepo"] = None
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
        if not self.db_pool:
            raise DatabaseError(
                f"APIKeyManager database pool is not initialized {self._db_context_hint()}"
            )
        from tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo import AuthnzApiKeysRepo

        if self._repo is None or getattr(self._repo, "db_pool", None) is not self.db_pool:
            self._repo = AuthnzApiKeysRepo(self.db_pool)
        return self._repo

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
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

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
                "created_at": datetime.utcnow().isoformat(),
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
                "created_at": datetime.utcnow().isoformat(),
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
                    await repo.update_key_hash(key_info["id"], primary_hash)
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

        except Exception as e:  # noqa: BLE001 - validation failures degrade to 'no key'
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
            repo = self._get_repo()
            # Get existing key info (authorization check remains here)
            old_key = await repo.fetch_key_for_user(key_id=key_id, user_id=user_id)

            if not old_key:
                raise ValueError("API key not found or unauthorized")

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

            # Update rotation references via repository
            await repo.mark_rotated(
                old_key_id=key_id,
                new_key_id=new_key_result["id"],
                rotated_status=APIKeyStatus.ROTATED.value,
                reason="Key rotation",
                revoked_at=datetime.utcnow(),
            )

            # Log the rotation
            await self._log_action(key_id, "rotated", user_id)
            await self._log_action(new_key_result['id'], "created_from_rotation", user_id)

            logger.info(f"Rotated API key {key_id} to {new_key_result['id']}")

            return new_key_result

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
                revoked_at=datetime.utcnow(),
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
                now=datetime.utcnow(),
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
            logger.error(f"Failed to update usage: {e}")

    async def _mark_expired(self, key_id: int):
        """Mark a key as expired"""
        try:
            repo = self._get_repo()
            await repo.mark_key_expired(key_id=key_id, expired_status=APIKeyStatus.EXPIRED.value)
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
            repo = self._get_repo()
            await repo.insert_audit_log(
                key_id=key_id,
                action=action,
                user_id=user_id,
                details=details,
            )
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
