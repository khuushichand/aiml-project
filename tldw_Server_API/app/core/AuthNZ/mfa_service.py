# mfa_service.py
# Description: Multi-Factor Authentication service with TOTP support
#
# Imports
import base64
import secrets
import json
import hashlib
import hmac
import string
from io import BytesIO
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any
#
# 3rd-party imports
import pyotp
from loguru import logger
from cryptography.fernet import Fernet

try:
    import qrcode
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    qrcode = None  # type: ignore[assignment]
    _FALLBACK_QR_PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    )
else:
    _FALLBACK_QR_PNG = None
#
# Local imports
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings
from tldw_Server_API.app.core.AuthNZ.crypto_utils import (
    derive_hmac_key,
    derive_hmac_key_candidates,
)
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    DatabaseError
)

#######################################################################################################################
#
# MFA Service Class
#

class MFAService:
    """
    Multi-Factor Authentication service supporting TOTP (Time-based One-Time Passwords)

    Features:
    - TOTP generation and validation
    - QR code generation for authenticator apps
    - Backup codes generation and validation
    - Recovery options
    """

    def __init__(
        self,
        db_pool: Optional[DatabasePool] = None,
        settings: Optional[Settings] = None
    ):
        """Initialize MFA service"""
        self.settings = settings or get_settings()
        self.db_pool = db_pool
        self._initialized = False
        self._cipher: Optional[Fernet] = None
        self._cipher_candidates: List[Fernet] = []
        self._cipher_key_material: Tuple[bytes, ...] = tuple()

        # TOTP configuration
        self.issuer_name = self.settings.APP_NAME if hasattr(self.settings, 'APP_NAME') else "TLDW Server"
        self.totp_digits = 6
        self.totp_interval = 30  # seconds
        self.backup_codes_count = 8

        # Window for TOTP validation (allows for time drift)
        self.validation_window = 1  # Allow 1 interval before/after

    async def initialize(self):
        """Initialize MFA service"""
        if self._initialized:
            return

        # Get database pool
        if not self.db_pool:
            self.db_pool = await get_db_pool()

        self._initialized = True
        logger.info("MFAService initialized")

    def _ensure_cipher_candidates(self) -> List[Fernet]:
        """Return Fernet instances for all active/legacy key materials."""
        key_candidates = tuple(derive_hmac_key_candidates(self.settings))
        if not key_candidates:
            raise ValueError("No HMAC key material available for MFA encryption")
        if self._cipher_key_material != key_candidates:
            cipher_list: List[Fernet] = []
            for material in key_candidates:
                cipher_list.append(Fernet(base64.urlsafe_b64encode(material)))
            self._cipher_candidates = cipher_list
            self._cipher_key_material = key_candidates
            self._cipher = cipher_list[0]
        return self._cipher_candidates

    def _get_cipher(self) -> Fernet:
        """Return the primary Fernet cipher (current key material)."""
        self._ensure_cipher_candidates()
        if self._cipher is None:
            raise ValueError("Primary cipher failed to initialize")
        return self._cipher

    def _encrypt_secret(self, secret: str) -> str:
        """Encrypt a TOTP secret for storage."""
        cipher = self._get_cipher()
        return cipher.encrypt(secret.encode("utf-8")).decode("utf-8")

    def _decrypt_secret(self, encrypted_secret: Optional[str]) -> Optional[str]:
        """Decrypt a stored TOTP secret."""
        if not encrypted_secret:
            return None
        last_exc: Optional[Exception] = None
        for idx, cipher in enumerate(self._ensure_cipher_candidates()):
            try:
                decrypted = cipher.decrypt(encrypted_secret.encode("utf-8"))
                return decrypted.decode("utf-8")
            except Exception as exc:
                last_exc = exc
                logger.debug(f"Failed to decrypt MFA secret with cipher index {idx}: {exc}")
        logger.error("Failed to decrypt MFA secret with available key material")
        raise DatabaseError("Failed to decrypt MFA secret") from last_exc

    def _normalize_backup_code(self, code: str) -> str:
        """Normalize backup codes for hashing/comparison."""
        return code.replace("-", "").replace(" ", "").strip().upper()

    def _hash_backup_code(self, user_id: int, code: str) -> str:
        """Hash backup codes using per-installation secret material."""
        candidates = self._hash_backup_code_candidates(user_id, code)
        if not candidates:
            raise ValueError("No HMAC key material available for backup codes")
        return candidates[0]

    def _hash_backup_code_candidates(self, user_id: int, code: str) -> List[str]:
        """Return hash candidates for a backup code across current/legacy keys."""
        digests: List[str] = []
        normalized = self._normalize_backup_code(code)
        message = f"{user_id}:{normalized}".encode("utf-8")
        for key in derive_hmac_key_candidates(self.settings):
            digest = hmac.new(key, message, hashlib.sha256).hexdigest()
            if digest not in digests:
                digests.append(digest)
        return digests

    def generate_secret(self) -> str:
        """
        Generate a new TOTP secret

        Returns:
            Base32-encoded secret key
        """
        # Generate 20 bytes (160 bits) of random data
        random_bytes = secrets.token_bytes(20)
        # Encode as base32 for TOTP compatibility
        secret = base64.b32encode(random_bytes).decode('utf-8')
        return secret

    def generate_totp_uri(
        self,
        secret: str,
        username: str,
        issuer: Optional[str] = None
    ) -> str:
        """
        Generate TOTP URI for QR code

        Args:
            secret: Base32-encoded secret
            username: User's username/email
            issuer: Application name

        Returns:
            TOTP URI string
        """
        issuer = issuer or self.issuer_name
        totp = pyotp.TOTP(secret, issuer=issuer)
        return totp.provisioning_uri(
            name=username,
            issuer_name=issuer
        )

    def generate_qr_code(self, totp_uri: str) -> bytes:
        """
        Generate QR code image for TOTP URI

        Args:
            totp_uri: TOTP URI string

        Returns:
            PNG image bytes
        """
        if qrcode is None:  # pragma: no cover - optional dependency path
            logger.warning(
                "qrcode library unavailable; returning fallback placeholder QR image. "
                "Install the 'qrcode' extra for generated QR codes."
            )
            return _FALLBACK_QR_PNG or b""

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(totp_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    def generate_backup_codes(self, count: Optional[int] = None) -> List[str]:
        """
        Generate backup codes for account recovery

        Args:
            count: Number of codes to generate

        Returns:
            List of backup codes
        """
        count = count or self.backup_codes_count
        codes = []

        for _ in range(count):
            # Generate 8-character alphanumeric codes
            code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(8))
            # Format as XXXX-XXXX for readability
            formatted_code = f"{code[:4]}-{code[4:]}"
            codes.append(formatted_code)

        return codes

    def verify_totp(
        self,
        secret: str,
        token: str,
        window: Optional[int] = None
    ) -> bool:
        """
        Verify a TOTP token

        Args:
            secret: User's TOTP secret
            token: 6-digit token to verify
            window: Validation window (intervals before/after)

        Returns:
            True if token is valid
        """
        if not secret or not token:
            return False

        # Remove any spaces or hyphens from token
        token = token.replace(' ', '').replace('-', '')

        # Validate token format
        if not token.isdigit() or len(token) != self.totp_digits:
            return False

        try:
            totp = pyotp.TOTP(secret)
            # Use custom window or default
            validation_window = window if window is not None else self.validation_window

            # Verify with time window to account for clock drift
            return totp.verify(token, valid_window=validation_window)

        except Exception as e:
            logger.error(f"TOTP verification error: {e}")
            return False

    async def enable_mfa(
        self,
        user_id: int,
        secret: str,
        backup_codes: List[str]
    ) -> bool:
        """
        Enable MFA for a user

        Args:
            user_id: User's ID
            secret: TOTP secret
            backup_codes: List of backup codes

        Returns:
            True if successfully enabled
        """
        if not self._initialized:
            await self.initialize()

        try:
            encrypted_secret = self._encrypt_secret(secret)
            hashed_codes = [self._hash_backup_code(user_id, code) for code in backup_codes]
            backup_codes_json = json.dumps(hashed_codes)

            async with self.db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    # PostgreSQL
                    await conn.execute("""
                        UPDATE users
                        SET totp_secret = $1,
                            two_factor_enabled = true,
                            backup_codes = $2,
                            updated_at = $3
                        WHERE id = $4
                    """, encrypted_secret, backup_codes_json, datetime.utcnow(), user_id)
                else:
                    # SQLite
                    await conn.execute("""
                        UPDATE users
                        SET totp_secret = ?,
                            two_factor_enabled = 1,
                            backup_codes = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (encrypted_secret, backup_codes_json, datetime.utcnow().isoformat(), user_id))
                    await conn.commit()

            logger.info(f"MFA enabled for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to enable MFA: {e}")
            return False

    async def disable_mfa(self, user_id: int) -> bool:
        """
        Disable MFA for a user

        Args:
            user_id: User's ID

        Returns:
            True if successfully disabled
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self.db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    # PostgreSQL
                    await conn.execute("""
                        UPDATE users
                        SET totp_secret = NULL,
                            two_factor_enabled = false,
                            backup_codes = NULL,
                            updated_at = $1
                        WHERE id = $2
                    """, datetime.utcnow(), user_id)
                else:
                    # SQLite
                    await conn.execute("""
                        UPDATE users
                        SET totp_secret = NULL,
                            two_factor_enabled = 0,
                            backup_codes = NULL,
                            updated_at = ?
                        WHERE id = ?
                    """, (datetime.utcnow().isoformat(), user_id))
                    await conn.commit()

            logger.info(f"MFA disabled for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to disable MFA: {e}")
            return False

    async def get_user_totp_secret(self, user_id: int) -> Optional[str]:
        """Return decrypted TOTP secret for a user if configured."""
        if not self._initialized:
            await self.initialize()

        try:
            async with self.db_pool.acquire() as conn:
                if hasattr(conn, "fetchval"):
                    encrypted = await conn.fetchval(
                        "SELECT totp_secret FROM users WHERE id = $1",
                        user_id,
                    )
                else:
                    cursor = await conn.execute(
                        "SELECT totp_secret FROM users WHERE id = ?",
                        (user_id,),
                    )
                    result = await cursor.fetchone()
                    encrypted = result[0] if result else None
            return self._decrypt_secret(encrypted)
        except DatabaseError:
            raise
        except Exception as exc:
            logger.error(f"Failed to load MFA secret for user {user_id}: {exc}")
            raise DatabaseError("Failed to load MFA secret") from exc

    async def get_user_mfa_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get MFA status for a user

        Args:
            user_id: User's ID

        Returns:
            Dictionary with MFA status information
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self.db_pool.acquire() as conn:
                if hasattr(conn, 'fetchrow'):
                    # PostgreSQL
                    result = await conn.fetchrow("""
                        SELECT two_factor_enabled, totp_secret IS NOT NULL as has_secret,
                               backup_codes IS NOT NULL as has_backup_codes
                        FROM users WHERE id = $1
                    """, user_id)
                else:
                    # SQLite
                    cursor = await conn.execute("""
                        SELECT two_factor_enabled,
                               totp_secret IS NOT NULL as has_secret,
                               backup_codes IS NOT NULL as has_backup_codes
                        FROM users WHERE id = ?
                    """, (user_id,))
                    result = await cursor.fetchone()

                if result:
                    return {
                        "enabled": bool(result[0] if isinstance(result, tuple) else result['two_factor_enabled']),
                        "has_secret": bool(result[1] if isinstance(result, tuple) else result['has_secret']),
                        "has_backup_codes": bool(result[2] if isinstance(result, tuple) else result['has_backup_codes']),
                        "method": "totp" if result[0] else None
                    }

        except Exception as e:
            logger.error(f"Failed to get MFA status: {e}")

        return {
            "enabled": False,
            "has_secret": False,
            "has_backup_codes": False,
            "method": None
        }

    async def verify_backup_code(
        self,
        user_id: int,
        code: str
    ) -> bool:
        """
        Verify and consume a backup code

        Args:
            user_id: User's ID
            code: Backup code to verify

        Returns:
            True if code is valid and was consumed
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self.db_pool.transaction() as conn:
                # Get backup codes
                if hasattr(conn, 'fetchval'):
                    # PostgreSQL
                    backup_codes_json = await conn.fetchval(
                        "SELECT backup_codes FROM users WHERE id = $1",
                        user_id
                    )
                else:
                    # SQLite
                    cursor = await conn.execute(
                        "SELECT backup_codes FROM users WHERE id = ?",
                        (user_id,)
                    )
                    result = await cursor.fetchone()
                    backup_codes_json = result[0] if result else None

                if not backup_codes_json:
                    return False

                backup_codes = json.loads(backup_codes_json)
                hash_candidates = self._hash_backup_code_candidates(user_id, code)
                normalized_input = self._normalize_backup_code(code)

                matched = False
                for digest in hash_candidates:
                    if digest in backup_codes:
                        backup_codes.remove(digest)
                        matched = True
                        break
                if not matched:
                    for candidate in list(backup_codes):
                        if not isinstance(candidate, str):
                            continue
                        if self._normalize_backup_code(candidate) == normalized_input:
                            backup_codes.remove(candidate)
                            matched = True
                            break
                if not matched:
                    return False

                # Ensure remaining codes are stored as hashed values
                normalized_codes: List[str] = []
                for candidate in backup_codes:
                    if not isinstance(candidate, str):
                        continue
                    if len(candidate) == 64 and all(ch in string.hexdigits for ch in candidate):
                        normalized_codes.append(candidate.lower())
                    else:
                        normalized_codes.append(self._hash_backup_code(user_id, candidate))

                updated_codes_json = json.dumps(normalized_codes)

                # Update database
                if hasattr(conn, 'fetchrow'):
                    # PostgreSQL
                    await conn.execute(
                        "UPDATE users SET backup_codes = $1 WHERE id = $2",
                        updated_codes_json, user_id
                    )
                else:
                    # SQLite
                    await conn.execute(
                        "UPDATE users SET backup_codes = ? WHERE id = ?",
                        (updated_codes_json, user_id)
                    )
                    await conn.commit()

                logger.info(f"Backup code used for user {user_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to verify backup code: {e}")
            return False

    async def regenerate_backup_codes(
        self,
        user_id: int
    ) -> Optional[List[str]]:
        """
        Generate new backup codes for a user

        Args:
            user_id: User's ID

        Returns:
            List of new backup codes or None on failure
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Generate new codes
            new_codes = self.generate_backup_codes()
            hashed_codes = [self._hash_backup_code(user_id, code) for code in new_codes]
            backup_codes_json = json.dumps(hashed_codes)

            async with self.db_pool.transaction() as conn:
                if hasattr(conn, 'fetchrow'):
                    # PostgreSQL
                    await conn.execute(
                        "UPDATE users SET backup_codes = $1, updated_at = $2 WHERE id = $3",
                        backup_codes_json, datetime.utcnow(), user_id
                    )
                else:
                    # SQLite
                    await conn.execute(
                        "UPDATE users SET backup_codes = ?, updated_at = ? WHERE id = ?",
                        (backup_codes_json, datetime.utcnow().isoformat(), user_id)
                    )
                    await conn.commit()

            logger.info(f"Regenerated backup codes for user {user_id}")
            return new_codes

        except Exception as e:
            logger.error(f"Failed to regenerate backup codes: {e}")
            return None


#######################################################################################################################
#
# Module Functions for convenience
#

# Global instance
_mfa_service: Optional[MFAService] = None


def get_mfa_service() -> MFAService:
    """Get MFA service singleton instance"""
    global _mfa_service
    if not _mfa_service:
        _mfa_service = MFAService()
    return _mfa_service


def generate_totp_secret() -> str:
    """Generate a new TOTP secret"""
    return get_mfa_service().generate_secret()


def verify_totp_token(secret: str, token: str) -> bool:
    """Verify a TOTP token"""
    return get_mfa_service().verify_totp(secret, token)


#
# End of mfa_service.py
#######################################################################################################################
