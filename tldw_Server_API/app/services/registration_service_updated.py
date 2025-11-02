# registration_service_updated.py
# Description: Updated registration service to use new UserDatabase
#
# This service handles user registration using the new UserDatabase class
# that follows the MediaDatabase pattern.
#
########################################################################################################################

import os
import shutil
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

# Local imports
from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings
from tldw_Server_API.app.core.DB_Management.UserDatabase import (
    UserDatabase,
    DuplicateUserError,
    RegistrationCodeError
)
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService, get_password_service
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    RegistrationError,
    InvalidRegistrationCodeError,
    RegistrationDisabledError,
    WeakPasswordError
)

########################################################################################################################
# Registration Service Class (Updated)
########################################################################################################################

class RegistrationService:
    """Service for user registration using new UserDatabase"""

    def __init__(
        self,
        user_db: Optional[UserDatabase] = None,
        password_service: Optional[PasswordService] = None,
        settings: Optional[Settings] = None
    ):
        """Initialize registration service"""
        self.settings = settings or get_settings()
        self.password_service = password_service or get_password_service()

        # Initialize UserDatabase if not provided
        if user_db is None:
            db_path = self.settings.DATABASE_URL.replace("sqlite:///", "")
            self.user_db = UserDatabase(db_path, client_id="registration_service")
        else:
            self.user_db = user_db

        # Thread pool for directory operations
        self.executor = ThreadPoolExecutor(max_workers=2)

        # Check if registration is enabled
        self.registration_enabled = self.settings.ENABLE_REGISTRATION
        self.require_code = self.settings.REQUIRE_REGISTRATION_CODE

        logger.info(
            f"RegistrationService initialized (enabled={self.registration_enabled}, "
            f"require_code={self.require_code})"
        )

    def _create_user_directories(self, user_id: int) -> bool:
        """
        Create user directories (runs in thread pool)

        Args:
            user_id: User's database ID

        Returns:
            True if successful, False otherwise
        """
        try:
            base_path = Path(self.settings.USER_DATA_BASE_PATH)
            user_dir = base_path / str(user_id)

            # Create main user directory
            user_dir.mkdir(parents=True, exist_ok=True)

            # Create subdirectories
            subdirs = ["media", "notes", "embeddings", "exports", "temp"]
            for subdir in subdirs:
                (user_dir / subdir).mkdir(exist_ok=True)

            # Create user-specific ChromaDB directory if configured
            if self.settings.CHROMADB_BASE_PATH:
                chroma_path = Path(self.settings.CHROMADB_BASE_PATH) / str(user_id)
                chroma_path.mkdir(parents=True, exist_ok=True)

            # Set permissions on Unix-like systems
            if os.name != 'nt':
                os.chmod(user_dir, 0o750)
                for subdir in subdirs:
                    os.chmod(user_dir / subdir, 0o750)

            logger.debug(f"Created directories for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to create directories for user {user_id}: {e}")
            return False

    def _cleanup_user_directories(self, user_id: int):
        """
        Clean up user directories (for rollback)

        Args:
            user_id: User's database ID
        """
        try:
            # Remove user data directory
            user_dir = Path(self.settings.USER_DATA_BASE_PATH) / str(user_id)
            if user_dir.exists():
                shutil.rmtree(user_dir, ignore_errors=True)

            # Remove ChromaDB directory
            if self.settings.CHROMADB_BASE_PATH:
                chroma_dir = Path(self.settings.CHROMADB_BASE_PATH) / str(user_id)
                if chroma_dir.exists():
                    shutil.rmtree(chroma_dir, ignore_errors=True)

            logger.debug(f"Cleaned up directories for user {user_id}")

        except Exception as e:
            logger.error(f"Error cleaning up directories for user {user_id}: {e}")

    async def register_user(
        self,
        username: str,
        email: str,
        password: str,
        registration_code: Optional[str] = None,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Register a new user with full transaction safety

        Args:
            username: Username (must be unique)
            email: Email address (must be unique)
            password: Plain text password
            registration_code: Optional registration code
            created_by: ID of user creating this account (for admin creation)

        Returns:
            Dictionary with user information

        Raises:
            Various registration exceptions
        """
        # Check if registration is enabled
        if not self.registration_enabled and not created_by:
            raise RegistrationDisabledError()

        # Validate password strength
        self.password_service.validate_password_strength(password, username)

        # Hash password
        password_hash = self.password_service.hash_password(password)

        user_id = None
        directories_created = False

        try:
            # Validate registration code if required
            role = self.settings.DEFAULT_USER_ROLE

            if self.require_code and registration_code and not created_by:
                code_info = self.user_db.validate_registration_code(registration_code)
                if not code_info:
                    raise InvalidRegistrationCodeError()

                # Get role from registration code
                role = code_info.get('role_name', role)
            elif self.require_code and not registration_code and not created_by:
                raise InvalidRegistrationCodeError("Registration code required")

            # Create user in database
            user_id = self.user_db.create_user(
                username=username,
                email=email,
                password_hash=password_hash,
                role=role,
                is_verified=bool(created_by)  # Auto-verify if created by admin
            )

            # Use registration code if provided
            if registration_code and not created_by:
                self.user_db.use_registration_code(
                    registration_code,
                    user_id,
                    ip_address=None,  # Could be passed from request
                    user_agent=None   # Could be passed from request
                )

            # Create user directories (async)
            loop = asyncio.get_event_loop()
            directories_created = await loop.run_in_executor(
                self.executor,
                self._create_user_directories,
                user_id
            )

            if not directories_created:
                raise RegistrationError("Failed to create user directories")

            # Get complete user info
            user_info = self.user_db.get_user(user_id=user_id)

            logger.info(f"Successfully registered user: {username} (ID: {user_id})")

            return {
                "id": user_id,
                "username": username,
                "email": email,
                "role": role,
                "is_active": True,
                "is_verified": bool(created_by),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "message": "User registered successfully"
            }

        except DuplicateUserError as e:
            logger.warning(f"Registration failed - duplicate user: {e}")
            raise
        except (InvalidRegistrationCodeError, RegistrationDisabledError, WeakPasswordError) as e:
            logger.warning(f"Registration failed: {e}")
            raise
        except Exception as e:
            # Cleanup on failure
            logger.error(f"Registration failed unexpectedly: {e}")

            if user_id:
                # Delete user from database
                try:
                    self.user_db.delete_user(user_id)
                except Exception as del_err:
                    logger.debug(f"Failed to delete partially-created user after registration failure: user_id={user_id}, error={del_err}")

                # Cleanup directories
                if directories_created:
                    self._cleanup_user_directories(user_id)

            raise RegistrationError(f"Registration failed: {e}")

    async def create_admin_registration_code(
        self,
        admin_id: int,
        expires_in_days: int = 7,
        max_uses: int = 1,
        role: str = 'user'
    ) -> str:
        """
        Create a registration code (admin function)

        Args:
            admin_id: ID of admin creating the code
            expires_in_days: Days until expiration
            max_uses: Maximum uses allowed
            role: Role to assign to users

        Returns:
            The generated registration code
        """
        code = self.user_db.create_registration_code(
            created_by=admin_id,
            expires_in_days=expires_in_days,
            max_uses=max_uses,
            role=role
        )

        logger.info(f"Admin {admin_id} created registration code: {code[:8]}...")
        return code

    async def verify_email(self, user_id: int, token: str) -> bool:
        """
        Verify user's email address

        Args:
            user_id: User ID
            token: Verification token

        Returns:
            True if verification successful
        """
        # This would check email_verification_tokens table
        # For now, just mark user as verified
        return self.user_db.update_user(user_id, is_verified=True)

    async def resend_verification_email(self, user_id: int) -> bool:
        """
        Resend verification email

        Args:
            user_id: User ID

        Returns:
            True if email sent successfully
        """
        # This would generate a new token and send email
        # For now, just log
        logger.info(f"Would send verification email to user {user_id}")
        return True

# Singleton instance
_registration_service: Optional[RegistrationService] = None

def get_registration_service() -> RegistrationService:
    """Get or create registration service singleton"""
    global _registration_service
    if not _registration_service:
        _registration_service = RegistrationService()
    return _registration_service

async def get_registration_service_dep() -> RegistrationService:
    """FastAPI dependency for registration service"""
    return get_registration_service()

#
# End of registration_service_updated.py
########################################################################################################################
