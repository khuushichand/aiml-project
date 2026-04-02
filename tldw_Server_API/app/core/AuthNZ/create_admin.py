#!/usr/bin/env python3
# create_admin.py
# Description: Non-interactive CLI to create an initial admin user for multi-user mode.
#
# Designed to be called from Docker entrypoints or CI pipelines where interactive
# input is not available. Idempotent: if an admin with the given username already
# exists, the script exits successfully without making changes.
#
# Usage:
#   python -m tldw_Server_API.app.core.AuthNZ.create_admin \
#       --username myadmin --password 'S3cureP@ss!' [--email admin@example.com]
#

import argparse
import asyncio
import sys
from pathlib import Path

from loguru import logger

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.username_utils import normalize_admin_username
from tldw_Server_API.app.core.DB_Management.Users_DB import ensure_user_directories, get_users_db


async def create_admin_user_non_interactive(
    username: str,
    password: str,
    email: str | None = None,
) -> bool:
    """Create an admin user non-interactively.

    Returns True on success or if the user already exists (idempotent).
    Returns False on failure.
    """
    settings = get_settings()

    if settings.AUTH_MODE != "multi_user":
        print("[create-admin] Not in multi_user mode; skipping admin creation.")
        return True

    # Validate username
    try:
        username = normalize_admin_username(username)
    except ValueError as exc:
        print(f"[create-admin] Invalid username: {exc}")
        return False

    # Validate password length (matches PasswordService.min_length default of 10)
    if len(password) < 10:
        print("[create-admin] Password must be at least 10 characters.")
        return False

    # Default email if not provided
    if not email:
        email = f"{username}@admin.local"

    try:
        users_db = await get_users_db()

        # Idempotency: check if user already exists
        try:
            existing = await users_db.get_user_by_username(username)
            if existing:
                print(f"[create-admin] Admin user '{username}' already exists (id={existing.get('id', '?')}). Skipping.")
                return True
        except Exception:
            # get_user_by_username may raise if schema is fresh; treat as "no user"
            pass

        # Hash password
        password_service = PasswordService()
        password_hash = password_service.hash_password(password)

        # Create user
        admin_user = await users_db.create_user(
            username=username,
            email=email,
            password_hash=password_hash,
            role="admin",
            is_superuser=True,
        )

        user_id = admin_user["id"]
        print(f"[create-admin] Admin user created: username={username}, id={user_id}")

        # Ensure user directories exist
        await ensure_user_directories(user_id)

        # Create initial API key for admin
        try:
            from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager

            api_manager = await get_api_key_manager()
            api_key_result = await api_manager.create_api_key(
                user_id=user_id,
                name="Initial Admin API Key",
                description="Auto-generated during Docker bootstrap",
                scope="admin",
                expires_in_days=365,
            )
            print(f"[create-admin] Admin API key created (expires in 365 days).")
            # Intentionally do NOT print the key to logs in Docker context for security
        except Exception as api_err:
            # Non-fatal: user can generate API keys later via the UI/API
            logger.debug(f"[create-admin] API key creation skipped: {api_err}")
            print("[create-admin] Warning: could not auto-generate API key (user can create one later).")

        return True

    except Exception as e:
        print(f"[create-admin] Failed to create admin user: {e}")
        logger.opt(exception=True).error("create_admin_user_non_interactive failed")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an initial admin user for multi-user mode (non-interactive).",
    )
    parser.add_argument(
        "--username",
        required=True,
        help="Admin username (3-50 chars, alphanumeric/underscore/hyphen).",
    )
    parser.add_argument(
        "--password",
        required=True,
        help="Admin password (min 10 characters).",
    )
    parser.add_argument(
        "--email",
        default=None,
        help="Admin email address (defaults to <username>@admin.local).",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Accepted for compatibility with entrypoint scripts (always non-interactive).",
    )

    args = parser.parse_args()

    success = asyncio.run(
        create_admin_user_non_interactive(
            username=args.username,
            password=args.password,
            email=args.email,
        )
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
