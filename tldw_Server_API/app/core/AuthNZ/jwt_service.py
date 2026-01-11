# jwt_service.py
# Description: JWT token service with persistent secret management
#
# Imports
import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from uuid import uuid4
#
# 3rd-party imports
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError, JWTClaimsError
from loguru import logger
#
# Local imports
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import (
    derive_hmac_key,
    derive_hmac_key_candidates,
)
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    InvalidTokenError,
    TokenExpiredError,
    ConfigurationError
)

#######################################################################################################################
#
# JWT Service Class

class JWTService:
    """Service for creating and verifying JWT tokens with persistent secret management"""

    # Valid token types - reject any token with an unknown type
    VALID_TOKEN_TYPES = frozenset({
        "access",
        "refresh",
        "password_reset",
        "email_verification",
        "service",
    })

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize JWT service"""
        self.settings = settings or get_settings()

        # Validate we're in multi-user mode
        if self.settings.AUTH_MODE != "multi_user":
            logger.warning("JWTService initialized in single-user mode - JWT features may not work correctly")

        # JWT configuration
        self.algorithm = self.settings.JWT_ALGORITHM
        # Note: We don't cache timedeltas to allow dynamic configuration changes during testing

        # Select signing/verification keys according to algorithm
        alg_upper = (self.algorithm or "").upper()
        if alg_upper.startswith("HS"):
            # Symmetric HMAC
            self._encode_key = self.settings.JWT_SECRET_KEY
            self._decode_key = self.settings.JWT_SECRET_KEY
            self._secondary_decode_key = self.settings.JWT_SECONDARY_SECRET
            if not self._encode_key:
                # In single-user mode, allow initialization for hashing by deriving a per-instance key
                if (self.settings.AUTH_MODE == "single_user" and getattr(self.settings, "SINGLE_USER_API_KEY", None)):
                    try:
                        # Derive a stable surrogate secret from the API key
                        derived = derive_hmac_key(self.settings)
                        # jose accepts str/bytes; use hex string for readability
                        self._encode_key = derived.hex()
                        self._decode_key = self._encode_key
                        logger.debug("JWTService: using derived single-user surrogate key for HS algorithms")
                    except Exception:
                        raise ConfigurationError("JWT_SECRET_KEY", "JWT secret key not configured for HS algorithms")
                else:
                    raise ConfigurationError("JWT_SECRET_KEY", "JWT secret key not configured for HS algorithms")
        elif alg_upper.startswith("RS") or alg_upper.startswith("ES"):
            # Asymmetric (RSA/ECDSA)
            self._encode_key = self.settings.JWT_PRIVATE_KEY
            # Allow verifying with public if provided, else private
            if self.settings.JWT_PUBLIC_KEY:
                self._decode_key = self.settings.JWT_PUBLIC_KEY
            else:
                # Warn when using private key for verification - unusual configuration
                self._decode_key = self.settings.JWT_PRIVATE_KEY
                if self._decode_key:
                    logger.warning(
                        "JWTService: No JWT_PUBLIC_KEY configured; using private key for verification. "
                        "Consider configuring JWT_PUBLIC_KEY for asymmetric algorithms."
                    )
            self._secondary_decode_key = self.settings.JWT_SECONDARY_PUBLIC_KEY
            if not self._encode_key:
                raise ConfigurationError("JWT_PRIVATE_KEY", f"Private key required for {self.algorithm}")
            if not self._decode_key:
                raise ConfigurationError("JWT_PUBLIC_KEY", f"Public key (or private) required for {self.algorithm}")
        else:
            raise ConfigurationError("JWT_ALGORITHM", f"Unsupported algorithm: {self.algorithm}")

        logger.debug(f"JWTService initialized with algorithm: {self.algorithm}")

    def create_access_token(
        self,
        user_id: int,
        username: str,
        role: str,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create an access token for a user

        Args:
            user_id: User's database ID
            username: User's username
            role: User's role
            additional_claims: Additional claims to include in token

        Returns:
            Encoded JWT access token
        """
        # Calculate expiration dynamically from settings
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        # Build token payload
        payload = {
            "sub": str(user_id),  # Subject (user ID)
            "username": username,
            "role": role,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid4()),  # JWT ID for tracking
            "type": "access"
        }
        # Optional issuer/audience
        if self.settings.JWT_ISSUER:
            payload["iss"] = self.settings.JWT_ISSUER
        if self.settings.JWT_AUDIENCE:
            payload["aud"] = self.settings.JWT_AUDIENCE

        # Add any additional claims
        if additional_claims:
            payload.update(additional_claims)

        # Encode the token
        try:
            token = jwt.encode(payload, self._encode_key, algorithm=self.algorithm)
            if self.settings.PII_REDACT_LOGS:
                logger.debug("Created access token for authenticated user (details redacted)")
            else:
                logger.debug(f"Created access token for user {username} (ID: {user_id})")
            return token

        except Exception as e:
            logger.error(f"Failed to create access token: {e}")
            raise InvalidTokenError(f"Failed to create token: {e}")

    def create_refresh_token(
        self,
        user_id: int,
        username: str,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a refresh token for a user

        Args:
            user_id: User's database ID
            username: User's username
            additional_claims: Additional claims to include in token

        Returns:
            Encoded JWT refresh token
        """
        # Calculate expiration dynamically from settings
        expire = datetime.now(timezone.utc) + timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS)

        # Build token payload (minimal claims for refresh token)
        payload = {
            "sub": str(user_id),
            "username": username,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid4()),
            "type": "refresh"
        }
        if self.settings.JWT_ISSUER:
            payload["iss"] = self.settings.JWT_ISSUER
        if self.settings.JWT_AUDIENCE:
            payload["aud"] = self.settings.JWT_AUDIENCE

        # Add any additional claims
        if additional_claims:
            payload.update(additional_claims)

        # Encode the token
        try:
            token = jwt.encode(payload, self._encode_key, algorithm=self.algorithm)
            if self.settings.PII_REDACT_LOGS:
                logger.debug("Created refresh token for authenticated user (details redacted)")
            else:
                logger.debug(f"Created refresh token for user {username} (ID: {user_id})")
            return token

        except Exception as e:
            logger.error(f"Failed to create refresh token: {e}")
            raise InvalidTokenError(f"Failed to create token: {e}")

    async def verify_token_async(self, token: str, token_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify and decode a JWT token with blacklist checking (async version)

        Args:
            token: JWT token to verify
            token_type: Expected token type ('access' or 'refresh')

        Returns:
            Decoded token payload

        Raises:
            InvalidTokenError: If token is invalid, malformed, or blacklisted
            TokenExpiredError: If token has expired
        """
        try:
            # Decode the token
            # Enforce optional issuer/audience when configured
            decode_kwargs = {
                "algorithms": [self.algorithm],
            }
            if self.settings.JWT_AUDIENCE:
                decode_kwargs["audience"] = self.settings.JWT_AUDIENCE
            if self.settings.JWT_ISSUER:
                decode_kwargs["issuer"] = self.settings.JWT_ISSUER
            try:
                payload = jwt.decode(token, self._decode_key, **decode_kwargs)
            except JWTError as primary_err:
                # Dual-key fallback during rotations
                if getattr(self, "_secondary_decode_key", None):
                    try:
                        payload = jwt.decode(token, self._secondary_decode_key, **decode_kwargs)
                        # SECURITY: Log when secondary key is used - indicates key rotation in progress
                        logger.info(
                            "JWT verified using secondary key - key rotation may be in progress. "
                            "Primary key verification failed, falling back to secondary."
                        )
                    except JWTError as secondary_err:
                        # Both keys failed - chain exceptions to preserve both error contexts
                        logger.debug(f"Token verification failed with both keys: primary={primary_err}, secondary={secondary_err}")
                        raise primary_err from secondary_err
                else:
                    raise

            # Check if token is blacklisted
            jti = payload.get("jti")
            if jti:
                from tldw_Server_API.app.core.AuthNZ.token_blacklist import is_token_blacklisted
                if await is_token_blacklisted(jti):
                    raise InvalidTokenError("Token has been revoked")

            # Validate token type against whitelist
            actual_type = payload.get("type")
            if actual_type and actual_type not in self.VALID_TOKEN_TYPES:
                logger.warning(f"Token has unknown type: {actual_type}")
                raise InvalidTokenError(f"Unknown token type: {actual_type}")

            # Verify token type if specified
            if token_type and actual_type != token_type:
                raise InvalidTokenError(f"Invalid token type. Expected {token_type}, got {actual_type}")

            if self.settings.PII_REDACT_LOGS:
                logger.debug("Token verified successfully for authenticated user (details redacted)")
            else:
                logger.debug(f"Token verified successfully for user ID: {payload.get('sub')}")
            return payload

        except ExpiredSignatureError:
            logger.debug("Token has expired")
            raise TokenExpiredError()

        except JWTClaimsError as e:
            logger.warning(f"JWT claims error: {e}")
            raise InvalidTokenError(f"Invalid token claims: {e}")

        except JWTError as e:
            logger.warning(f"JWT verification error: {e}")
            raise InvalidTokenError(f"Invalid token: {e}")

        except Exception as e:
            logger.error(f"Unexpected error verifying token: {e}")
            raise InvalidTokenError(f"Token verification failed: {e}")

    def verify_token(self, token: str, token_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify and decode a JWT token (sync, stateless; no blacklist checks).

        SECURITY WARNING: This method performs ONLY cryptographic signature
        validation and expiry checks. It does NOT check if the token has been
        revoked/blacklisted. Revoked tokens will still pass validation here.

        For security-critical paths that require blacklist enforcement, use
        `verify_token_async()` instead, which checks the token blacklist.

        Use cases for this sync method:
        - Performance-critical read operations where blacklist lag is acceptable
        - Contexts where async is not available and revocation is handled elsewhere
        - Token introspection/debugging (not for authorization decisions)

        Args:
            token: JWT token to verify
            token_type: Expected token type ('access' or 'refresh')

        Returns:
            Decoded token payload

        Raises:
            InvalidTokenError: If token is invalid or malformed
            TokenExpiredError: If token has expired
        """
        try:
            # Decode the token
            decode_kwargs = {
                "algorithms": [self.algorithm],
            }
            if self.settings.JWT_AUDIENCE:
                decode_kwargs["audience"] = self.settings.JWT_AUDIENCE
            if self.settings.JWT_ISSUER:
                decode_kwargs["issuer"] = self.settings.JWT_ISSUER
            try:
                payload = jwt.decode(token, self._decode_key, **decode_kwargs)
            except JWTError as primary_err:
                if getattr(self, "_secondary_decode_key", None):
                    try:
                        payload = jwt.decode(token, self._secondary_decode_key, **decode_kwargs)
                    except JWTError as secondary_err:
                        # Both keys failed - chain exceptions to preserve both error contexts
                        logger.debug(f"Token verification failed with both keys: primary={primary_err}, secondary={secondary_err}")
                        raise primary_err from secondary_err
                else:
                    raise

            # Validate token type against whitelist
            actual_type = payload.get("type")
            if actual_type and actual_type not in self.VALID_TOKEN_TYPES:
                logger.warning(f"Token has unknown type: {actual_type}")
                raise InvalidTokenError(f"Unknown token type: {actual_type}")

            # Verify token type if specified
            if token_type and actual_type != token_type:
                raise InvalidTokenError(f"Invalid token type. Expected {token_type}, got {actual_type}")

            # Note: blacklist enforcement is only supported in verify_token_async()

            if self.settings.PII_REDACT_LOGS:
                logger.debug("Token verified successfully for authenticated user (details redacted)")
            else:
                logger.debug(f"Token verified successfully for user ID: {payload.get('sub')}")
            return payload

        except ExpiredSignatureError:
            logger.debug("Token has expired")
            raise TokenExpiredError()

        except JWTClaimsError as e:
            logger.warning(f"JWT claims error: {e}")
            raise InvalidTokenError(f"Invalid token claims: {e}")

        except JWTError as e:
            logger.warning(f"JWT verification error: {e}")
            raise InvalidTokenError(f"Invalid token: {e}")

        except Exception as e:
            logger.error(f"Unexpected error verifying token: {e}")
            raise InvalidTokenError(f"Token verification failed: {e}")

    def decode_access_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and verify an access token

        Args:
            token: Access token to decode

        Returns:
            Decoded token payload

        Raises:
            InvalidTokenError: If token is invalid
            ExpiredTokenError: If token has expired
        """
        return self.verify_token(token, token_type="access")

    def decode_refresh_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and verify a refresh token

        Args:
            token: Refresh token to decode

        Returns:
            Decoded token payload

        Raises:
            InvalidTokenError: If token is invalid
            ExpiredTokenError: If token has expired
        """
        return self.verify_token(token, token_type="refresh")

    def verify_password_reset_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode a password reset token.

        Args:
            token: Password reset token to verify

        Returns:
            Decoded token payload containing user_id and email

        Raises:
            InvalidTokenError: If token is invalid or wrong type
            TokenExpiredError: If token has expired
        """
        return self.verify_token(token, token_type="password_reset")

    def verify_email_verification_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode an email verification token.

        Args:
            token: Email verification token to verify

        Returns:
            Decoded token payload containing user_id and email

        Raises:
            InvalidTokenError: If token is invalid or wrong type
            TokenExpiredError: If token has expired
        """
        return self.verify_token(token, token_type="email_verification")

    def verify_service_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode a service account token.

        Args:
            token: Service account token to verify

        Returns:
            Decoded token payload containing service name and permissions

        Raises:
            InvalidTokenError: If token is invalid or wrong type
            TokenExpiredError: If token has expired
        """
        return self.verify_token(token, token_type="service")

    def create_virtual_access_token(
        self,
        *,
        user_id: int,
        username: str,
        role: str,
        scope: str = "workflows",
        ttl_minutes: int = 60,
        schedule_id: Optional[str] = None,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a short-lived, scoped access token ("virtual key").

        Intended for internal automation (e.g., Workflows scheduler) and
        constrained integrations. Tokens include a required `scope` claim and
        optional `schedule_id` claim for further restriction.

        Args:
            user_id: Subject user id
            username: Display username for diagnostics
            role: User role (admin/user)
            scope: Logical scope string (e.g., 'workflows')
            ttl_minutes: Time-to-live in minutes
            schedule_id: Optional associated schedule id
            additional_claims: Extra claims to include

        Returns:
            Encoded JWT access token (scoped)
        """
        expire = datetime.now(timezone.utc) + timedelta(minutes=max(1, int(ttl_minutes)))
        payload: Dict[str, Any] = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid4()),
            "type": "access",
            "scope": str(scope or "workflows"),
        }
        if schedule_id:
            payload["schedule_id"] = str(schedule_id)
        if self.settings.JWT_ISSUER:
            payload["iss"] = self.settings.JWT_ISSUER
        if self.settings.JWT_AUDIENCE:
            payload["aud"] = self.settings.JWT_AUDIENCE
        if additional_claims:
            payload.update(additional_claims)
        try:
            token = jwt.encode(payload, self._encode_key, algorithm=self.algorithm)
            logger.debug(
                f"Created virtual access token scope={payload.get('scope')} user={username} ttl={ttl_minutes}m"
            )
            return token
        except Exception as e:
            logger.error(f"Failed to create virtual access token: {e}")
            raise InvalidTokenError(f"Failed to create token: {e}")

    def hash_token_candidates(self, token: str) -> list[str]:
        """Return ordered HMAC-SHA256 hashes derived from current and legacy secrets."""
        hashes: list[str] = []
        try:
            key_candidates = derive_hmac_key_candidates(self.settings)
        except Exception:
            key_candidates = [derive_hmac_key(self.settings)]
        for key in key_candidates:
            digest = hmac.new(key, token.encode("utf-8"), hashlib.sha256).hexdigest()
            if digest not in hashes:
                hashes.append(digest)
        return hashes

    def hash_token(self, token: str) -> str:
        """
        Create a secure hash of a token for storage using HMAC-SHA256.

        This provides better security than plain SHA256 by using a secret key,
        preventing length extension attacks and providing authentication.

        Note: We use HMAC-SHA256 instead of Argon2 because:
        - Tokens are already high-entropy (cryptographically random)
        - This hash is used for fast lookups on every request
        - Argon2 would add unnecessary latency without security benefit

        Args:
            token: Token to hash

        Returns:
            HMAC-SHA256 hash of the token
        """
        candidates = self.hash_token_candidates(token)
        if not candidates:
            raise ValueError("Unable to derive HMAC hash for token")
        return candidates[0]

    def hash_password_reset_token(self, token: str) -> str:
        """
        Create a computationally expensive hash of a password reset token.

        This uses PBKDF2-HMAC with SHA256 and a high iteration count so that
        brute-forcing reset tokens is significantly more expensive than a
        single SHA256 evaluation.

        Args:
            token: Password reset token to hash

        Returns:
            Hex-encoded PBKDF2-HMAC-SHA256 hash of the token
        """
        # Derive a stable salt from the existing HMAC key material
        base_key = derive_hmac_key(self.settings)
        salt = hmac.new(base_key, b"password-reset-token-salt", hashlib.sha256).digest()
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            token.encode("utf-8"),
            salt,
            200_000,
        )
        return dk.hex()

    def hash_password_reset_token_candidates(self, token: str) -> list[str]:
        """Return ordered PBKDF2-HMAC hashes for a password reset token."""
        hashes: list[str] = []
        try:
            key_candidates = derive_hmac_key_candidates(self.settings)
        except Exception:
            key_candidates = [derive_hmac_key(self.settings)]
        for key in key_candidates:
            salt = hmac.new(key, b"password-reset-token-salt", hashlib.sha256).digest()
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                token.encode("utf-8"),
                salt,
                200_000,
            )
            digest = dk.hex()
            if digest not in hashes:
                hashes.append(digest)
        return hashes

    def extract_jti(self, token: str) -> Optional[str]:
        """
        Extract the JTI (JWT ID) from a token without full verification

        Args:
            token: JWT token

        Returns:
            JTI if present, None otherwise
        """
        try:
            # Decode without verification to get JTI
            unverified = jwt.get_unverified_claims(token)
            return unverified.get("jti")
        except Exception:
            return None


    def create_password_reset_token(
        self,
        user_id: int,
        email: str,
        expires_in_hours: int = 1
    ) -> str:
        """
        Create a password reset token

        Args:
            user_id: User's database ID
            email: User's email
            expires_in_hours: Token validity in hours

        Returns:
            Encoded password reset token
        """
        expire = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

        payload = {
            "sub": str(user_id),
            "email": email,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid4()),
            "type": "password_reset"
        }
        if self.settings.JWT_ISSUER:
            payload["iss"] = self.settings.JWT_ISSUER
        if self.settings.JWT_AUDIENCE:
            payload["aud"] = self.settings.JWT_AUDIENCE

        try:
            token = jwt.encode(payload, self._encode_key, algorithm=self.algorithm)
            if self.settings.PII_REDACT_LOGS:
                logger.info("Created password reset token for authenticated user (details redacted)")
            else:
                logger.info(f"Created password reset token for user {user_id}")
            return token

        except Exception as e:
            logger.error(f"Failed to create password reset token: {e}")
            raise InvalidTokenError(f"Failed to create token: {e}")

    def create_email_verification_token(
        self,
        user_id: int,
        email: str,
        expires_in_hours: int = 24
    ) -> str:
        """
        Create an email verification token

        Args:
            user_id: User's database ID
            email: Email to verify
            expires_in_hours: Token validity in hours

        Returns:
            Encoded email verification token
        """
        expire = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

        payload = {
            "sub": str(user_id),
            "email": email,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid4()),
            "type": "email_verification"
        }
        if self.settings.JWT_ISSUER:
            payload["iss"] = self.settings.JWT_ISSUER
        if self.settings.JWT_AUDIENCE:
            payload["aud"] = self.settings.JWT_AUDIENCE

        try:
            token = jwt.encode(payload, self._encode_key, algorithm=self.algorithm)
            if self.settings.PII_REDACT_LOGS:
                logger.info("Created email verification token for authenticated user (details redacted)")
            else:
                logger.info(f"Created email verification token for user {user_id}")
            return token

        except Exception as e:
            logger.error(f"Failed to create email verification token: {e}")
            raise InvalidTokenError(f"Failed to create token: {e}")

    def create_service_account_token(
        self,
        service_name: str,
        permissions: list,
        expires_in_days: int = 365
    ) -> str:
        """
        Create a long-lived token for service accounts

        Args:
            service_name: Name of the service
            permissions: List of permissions granted
            expires_in_days: Token validity in days

        Returns:
            Encoded service account token
        """
        expire = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        payload = {
            "sub": f"service:{service_name}",
            "service": service_name,
            "permissions": permissions,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid4()),
            "type": "service"
        }
        if self.settings.JWT_ISSUER:
            payload["iss"] = self.settings.JWT_ISSUER
        if self.settings.JWT_AUDIENCE:
            payload["aud"] = self.settings.JWT_AUDIENCE

        try:
            token = jwt.encode(payload, self._encode_key, algorithm=self.algorithm)
            logger.info(f"Created service account token for {service_name}")
            return token

        except Exception as e:
            logger.error(f"Failed to create service account token: {e}")
            raise InvalidTokenError(f"Failed to create token: {e}")

    def refresh_access_token(self, refresh_token: str) -> tuple[str, str]:
        """
        Create a new access token from a refresh token (helper).

        Args:
            refresh_token: Valid refresh token

        Returns:
            Tuple of (new_access_token, refresh_token_out)

        Raises:
            InvalidTokenError: If refresh token is invalid
        """
        # NOTE:
        # This helper performs cryptographic validation and minting only.
        # It does NOT update session records or reliably enforce blacklist checks.
        # For production flows, prefer the /auth/refresh endpoint logic which
        # calls SessionManager.refresh_session() to persist rotation and ensure
        # revocation of previous refresh tokens.

        # Verify the refresh token (stateless by default; see note above)
        payload = self.verify_token(refresh_token, token_type="refresh")

        # Optional guard: best-effort blacklist enforcement for the presented refresh token
        # SECURITY: Always check blacklist regardless of async context
        try:
            jti = payload.get("jti")
            if jti:
                import asyncio as _asyncio
                from tldw_Server_API.app.core.AuthNZ.token_blacklist import is_token_blacklisted as _is_bl
                # Check if we're in an event loop
                try:
                    loop = _asyncio.get_running_loop()
                    in_loop = True
                except RuntimeError:
                    loop = None
                    in_loop = False

                if not in_loop:
                    # Not in event loop - run synchronously
                    if _asyncio.run(_is_bl(jti)):
                        raise InvalidTokenError("Token has been revoked")
                else:
                    # In event loop - we need to check synchronously using the blacklist cache
                    # The blacklist has an in-memory hint cache that can be checked without async
                    from tldw_Server_API.app.core.AuthNZ.token_blacklist import get_token_blacklist as _get_bl
                    bl = _get_bl()
                    # Check in-memory cache first (synchronous)
                    if hasattr(bl, '_hint_cache') and jti in getattr(bl, '_hint_cache', {}):
                        raise InvalidTokenError("Token has been revoked")
                    # Log warning that full async check cannot be performed in sync context
                    # Callers in async context should use the async-aware /auth/refresh endpoint
                    logger.warning(
                        "refresh_access_token called in sync context within event loop; "
                        "full blacklist check deferred. Prefer /auth/refresh endpoint for complete revocation enforcement."
                    )
        except InvalidTokenError:
            raise
        except Exception as _guard_e:
            logger.debug(f"Refresh helper blacklist guard skipped: {_guard_e}")

        # Extract user information
        user_id = int(payload["sub"])
        username = payload.get("username", "")

        # Fetch role from the configured user database for correctness
        role = payload.get("role", "user")
        try:
            from tldw_Server_API.app.core.AuthNZ.db_config import get_configured_user_database
            user_db = get_configured_user_database(client_id="jwt_service")
            roles = []
            try:
                roles = user_db.get_user_roles(user_id)
            except Exception:
                # Fallback to full user fetch if roles accessor differs
                user = user_db.get_user(user_id=user_id)
                roles = (user or {}).get("roles", []) if isinstance(user, dict) else []
            if roles:
                role = "admin" if "admin" in roles else roles[0]
        except Exception as e:
            logger.debug(f"JWTService: failed to fetch user role on refresh; using fallback: {e}")

        # Create new access token
        new_access_token = self.create_access_token(
            user_id=user_id,
            username=username,
            role=role
        )

        # Handle optional refresh rotation based on settings
        refresh_out = refresh_token
        try:
            if getattr(self.settings, "ROTATE_REFRESH_TOKENS", False):
                refresh_out = self.create_refresh_token(
                    user_id=user_id,
                    username=username,
                    additional_claims={k: v for k, v in (payload.items()) if k in {"session_id"}}
                )
                # Best-effort: attempt to blacklist old refresh JTI without breaking sync context
                try:
                    old_jti = payload.get("jti")
                    old_exp = payload.get("exp")
                    if old_jti and isinstance(old_exp, (int, float)):
                        from datetime import datetime as _dt, timezone as _tz
                        exp_dt = _dt.fromtimestamp(old_exp, tz=_tz.utc)
                        import asyncio as _asyncio
                        from tldw_Server_API.app.core.AuthNZ.token_blacklist import get_token_blacklist as _get_bl
                        try:
                            loop = _asyncio.get_running_loop()
                        except RuntimeError:
                            loop = None
                        if loop and loop.is_running():
                            # Schedule blacklist in the current loop to avoid blocking
                            try:
                                bl = _get_bl()
                                try:
                                    bl.hint_blacklisted(old_jti, exp_dt)
                                except Exception as _hint_e:
                                    logger.debug(f"Refresh rotation: hint cache failed: {_hint_e}")
                                loop.create_task(
                                    bl.revoke_token(
                                        jti=old_jti,
                                        expires_at=exp_dt,
                                        user_id=user_id,
                                        token_type="refresh",
                                        reason="refresh-rotated",
                                        revoked_by=None,
                                        ip_address=None,
                                    )
                                )
                            except Exception as _sched_e:
                                logger.debug(f"Refresh rotation: failed to schedule blacklist task: {_sched_e}")
                        else:
                            bl = _get_bl()
                            try:
                                bl.hint_blacklisted(old_jti, exp_dt)
                            except Exception as _hint_e:
                                logger.debug(f"Refresh rotation: hint cache failed: {_hint_e}")
                            # Run async revoke in a temporary loop
                            _asyncio.run(
                                bl.revoke_token(
                                    jti=old_jti,
                                    expires_at=exp_dt,
                                    user_id=user_id,
                                    token_type="refresh",
                                    reason="refresh-rotated",
                                    revoked_by=None,
                                    ip_address=None,
                                )
                            )
                except Exception as _e:
                    logger.debug(f"Refresh rotation: best-effort blacklist failed: {_e}")
        except Exception as _rot_err:
            logger.debug(f"Refresh rotation not applied: {_rot_err}")

        if self.settings.PII_REDACT_LOGS:
            logger.info("Refreshed access token for authenticated user (details redacted)")
        else:
            logger.info(f"Refreshed access token for user {username}")
        return new_access_token, refresh_out

    def get_token_remaining_time(self, token: str) -> Optional[int]:
        """
        Get remaining time before token expires

        Args:
            token: JWT token

        Returns:
            Remaining seconds until expiration, None if invalid
        """
        try:
            payload = self.verify_token(token)
            exp = payload.get("exp")
            if exp:
                remaining = exp - datetime.now(timezone.utc).timestamp()
                return max(0, int(remaining))
            return None

        except (InvalidTokenError, TokenExpiredError):
            return None


#######################################################################################################################
#
# Module Functions for convenience

# Global instance with thread-safe initialization
_jwt_service: Optional[JWTService] = None
_jwt_service_lock = threading.Lock()


def get_jwt_service() -> JWTService:
    """Get JWT service singleton instance (thread-safe)"""
    global _jwt_service
    # Fast path - no lock if already initialized
    if _jwt_service is not None:
        return _jwt_service

    # Slow path - acquire lock for initialization
    with _jwt_service_lock:
        # Double-check after acquiring lock
        if _jwt_service is None:
            _jwt_service = JWTService()
        return _jwt_service


def reset_jwt_service() -> None:
    """Reset the cached JWTService singleton (used in tests to pick up new settings)."""
    global _jwt_service
    with _jwt_service_lock:
        _jwt_service = None


def create_access_token(user_id: int, username: str, role: str) -> str:
    """Convenience function to create an access token"""
    return get_jwt_service().create_access_token(user_id, username, role)


def create_refresh_token(user_id: int, username: str) -> str:
    """Convenience function to create a refresh token"""
    return get_jwt_service().create_refresh_token(user_id, username)


def verify_token(token: str, token_type: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function to verify a token"""
    return get_jwt_service().verify_token(token, token_type)


def hash_token(token: str) -> str:
    """Convenience function to hash a token"""
    return get_jwt_service().hash_token(token)


def hash_token_candidates(token: str) -> list[str]:
    """Convenience function to retrieve hash candidates for a token."""
    return get_jwt_service().hash_token_candidates(token)


#
# End of jwt_service.py
#######################################################################################################################
