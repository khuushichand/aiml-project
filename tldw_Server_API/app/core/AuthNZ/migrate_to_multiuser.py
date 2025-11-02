#!/usr/bin/env python3
# migrate_to_multiuser.py
# Description: Migration script to transition from single-user to multi-user mode
#
# This script helps migrate an existing single-user tldw_server installation
# to multi-user mode with proper RBAC setup.
#
########################################################################################################################

import os
import sys
import json
import secrets
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import getpass
import argparse

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from tldw_Server_API.app.core.DB_Management.UserDatabase import UserDatabase
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.AuthNZ.settings import get_settings

########################################################################################################################
# Migration Functions
########################################################################################################################

def create_admin_user(user_db: UserDatabase, password_service: PasswordService) -> Dict[str, Any]:
    """
    Create the initial admin user for multi-user mode.

    Args:
        user_db: UserDatabase instance
        password_service: PasswordService instance

    Returns:
        Dict containing admin user info
    """
    print("\n" + "="*60)
    print("ADMIN USER CREATION")
    print("="*60)

    # Get admin username
    while True:
        username = input("\nEnter admin username (default: admin): ").strip() or "admin"
        if len(username) >= 3:
            break
        print("❌ Username must be at least 3 characters long")

    # Get admin email
    while True:
        email = input("Enter admin email: ").strip()
        if "@" in email and "." in email.split("@")[1]:
            break
        print("❌ Please enter a valid email address")

    # Get admin password
    while True:
        password = getpass.getpass("Enter admin password (min 10 chars): ")
        if len(password) >= 10:
            confirm = getpass.getpass("Confirm password: ")
            if password == confirm:
                break
            else:
                print("❌ Passwords do not match")
        else:
            print("❌ Password must be at least 10 characters long")

    # Hash password
    password_hash = password_service.hash_password(password)

    # Create admin user
    try:
        user_id = user_db.create_user(
            username=username,
            email=email,
            password_hash=password_hash,
            role='admin',
            is_verified=True,
            created_by_migration=True
        )

        print(f"\n✅ Admin user '{username}' created successfully (ID: {user_id})")

        return {
            'id': user_id,
            'username': username,
            'email': email,
            'role': 'admin'
        }

    except Exception as e:
        print(f"\n❌ Failed to create admin user: {e}")
        sys.exit(1)

def generate_registration_codes(user_db: UserDatabase, admin_id: int, count: int = 5) -> list:
    """
    Generate initial registration codes.

    Args:
        user_db: UserDatabase instance
        admin_id: Admin user ID who creates the codes
        count: Number of codes to generate

    Returns:
        List of registration codes
    """
    print("\n" + "="*60)
    print("REGISTRATION CODE GENERATION")
    print("="*60)

    codes = []

    # Ask if user wants to generate codes
    response = input(f"\nGenerate {count} registration codes? (y/n): ").strip().lower()

    if response == 'y':
        for i in range(count):
            code = user_db.create_registration_code(
                created_by=admin_id,
                expires_in_days=30,
                max_uses=1,
                role='user'
            )
            codes.append(code)
            print(f"  Code {i+1}: {code}")

        print(f"\n✅ Generated {count} registration codes (valid for 30 days)")

        # Save codes to file
        codes_file = Path("registration_codes.txt")
        with open(codes_file, "w") as f:
            f.write("Registration Codes (Generated on {})\n".format(datetime.now().isoformat()))
            f.write("="*60 + "\n\n")
            for i, code in enumerate(codes, 1):
                f.write(f"Code {i}: {code}\n")
            f.write("\n" + "="*60 + "\n")
            f.write("Each code is valid for 30 days and can be used once.\n")
            f.write("Share these codes with users who need to register.\n")

        print(f"📄 Codes saved to: {codes_file.absolute()}")

    return codes

def migrate_existing_data(user_db: UserDatabase) -> None:
    """
    Migrate existing single-user data to multi-user structure.

    Args:
        user_db: UserDatabase instance
    """
    print("\n" + "="*60)
    print("DATA MIGRATION")
    print("="*60)

    # Check for existing Media database (per-user default)
    try:
        from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
        media_db_path = Path(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id()))
    except Exception:
        # Anchor fallback to project root to avoid writing outside repo
        try:
            from tldw_Server_API.app.core.Utils.Utils import get_project_root
            media_db_path = Path(get_project_root()) / "Databases" / "Media_DB_v2.db"
        except Exception:
            media_db_path = Path(__file__).resolve().parents[5] / "Databases" / "Media_DB_v2.db"

    if media_db_path.exists():
        print(f"\n📁 Found existing Media database at: {media_db_path}")

        # In single-user mode, all content belongs to admin
        # No actual migration needed, but we could add user_id columns in future
        print("✅ Existing media content will be accessible to all authorized users")
    else:
        print("ℹ️  No existing Media database found")

    # Check for existing configuration
    config_path = Path("tldw_Server_API/Config_Files/config.txt")

    if config_path.exists():
        print(f"\n📋 Found existing configuration at: {config_path}")
        print("⚠️  Remember to update AUTH_MODE to 'multi_user' in config")

def update_configuration() -> None:
    """
    Guide user through updating configuration for multi-user mode.
    """
    print("\n" + "="*60)
    print("CONFIGURATION UPDATE")
    print("="*60)

    print("\nTo complete the migration, update your configuration:")
    print("\n1. Edit 'tldw_Server_API/Config_Files/config.txt'")
    print("2. Set or verify these settings:")
    print("   - AUTH_MODE = multi_user")
    print("   - ENABLE_REGISTRATION = true  (if you want open registration)")
    print("   - REQUIRE_REGISTRATION_CODE = true  (recommended)")
    print("   - JWT_SECRET_KEY = <generate a secure random key>")
    print("\n3. Restart the server after configuration changes")

    # Offer to generate JWT secret
    response = input("\nGenerate a JWT secret key? (y/n): ").strip().lower()

    if response == 'y':
        jwt_secret = secrets.token_urlsafe(32)
        print(f"\n🔑 JWT Secret Key (add to config or environment):")
        print(f"   JWT_SECRET_KEY={jwt_secret}")
        print("\n⚠️  Keep this secret secure and never commit it to version control!")

def verify_migration(user_db: UserDatabase) -> None:
    """
    Verify the migration was successful.

    Args:
        user_db: UserDatabase instance
    """
    print("\n" + "="*60)
    print("MIGRATION VERIFICATION")
    print("="*60)

    conn = user_db.get_connection()

    # Check users
    cursor = conn.execute("SELECT COUNT(*) as count FROM users")
    user_count = cursor.fetchone()['count']
    print(f"\n✅ Users in database: {user_count}")

    # Check roles
    cursor = conn.execute("SELECT COUNT(*) as count FROM roles")
    role_count = cursor.fetchone()['count']
    print(f"✅ Roles configured: {role_count}")

    # Check permissions
    cursor = conn.execute("SELECT COUNT(*) as count FROM permissions")
    perm_count = cursor.fetchone()['count']
    print(f"✅ Permissions defined: {perm_count}")

    # Check admin user
    cursor = conn.execute("""
        SELECT u.username
        FROM users u
        JOIN user_roles ur ON u.id = ur.user_id
        JOIN roles r ON ur.role_id = r.id
        WHERE r.name = 'admin'
    """)
    admins = cursor.fetchall()

    if admins:
        print(f"✅ Admin users: {', '.join([a['username'] for a in admins])}")
    else:
        print("⚠️  No admin users found!")

########################################################################################################################
# Main Migration Process
########################################################################################################################

def main():
    """
    Main migration process.
    """
    parser = argparse.ArgumentParser(
        description="Migrate tldw_server from single-user to multi-user mode"
    )
    parser.add_argument(
        "--skip-admin",
        action="store_true",
        help="Skip admin user creation (if already exists)"
    )
    parser.add_argument(
        "--no-codes",
        action="store_true",
        help="Don't generate registration codes"
    )
    parser.add_argument(
        "--db-path",
        default="../Databases/Users.db",
        help="Path to users database (default: ../Databases/Users.db)"
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print("TLDW_SERVER MULTI-USER MIGRATION")
    print("="*60)
    print("\nThis script will help you migrate from single-user to multi-user mode.")
    print("It will:")
    print("  1. Create the user database with RBAC tables")
    print("  2. Create an admin user")
    print("  3. Generate registration codes (optional)")
    print("  4. Provide configuration guidance")

    response = input("\nContinue with migration? (y/n): ").strip().lower()

    if response != 'y':
        print("\n❌ Migration cancelled")
        sys.exit(0)

    # Initialize database
    print(f"\n📂 Initializing user database at: {args.db_path}")

    try:
        user_db = UserDatabase(args.db_path, client_id="migration_script")
        password_service = PasswordService()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        sys.exit(1)

    # Create admin user
    admin_info = None
    if not args.skip_admin:
        admin_info = create_admin_user(user_db, password_service)
    else:
        # Get existing admin
        conn = user_db.get_connection()
        cursor = conn.execute("""
            SELECT u.id, u.username
            FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            JOIN roles r ON ur.role_id = r.id
            WHERE r.name = 'admin'
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            admin_info = {'id': row['id'], 'username': row['username']}
            print(f"\n✅ Using existing admin: {admin_info['username']}")
        else:
            print("\n⚠️  No admin user found, creating one...")
            admin_info = create_admin_user(user_db, password_service)

    # Generate registration codes
    if not args.no_codes and admin_info:
        generate_registration_codes(user_db, admin_info['id'])

    # Migrate existing data
    migrate_existing_data(user_db)

    # Update configuration
    update_configuration()

    # Verify migration
    verify_migration(user_db)

    # Final summary
    print("\n" + "="*60)
    print("MIGRATION COMPLETE!")
    print("="*60)
    print("\n✅ Successfully migrated to multi-user mode")
    print("\nNext steps:")
    print("  1. Update your configuration file")
    print("  2. Set the JWT_SECRET_KEY environment variable")
    print("  3. Restart the tldw_server")
    print("  4. Login with your admin credentials")
    print("  5. Share registration codes with users (if generated)")
    print("\n🎉 Your tldw_server is now ready for multiple users!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

#
# End of migrate_to_multiuser.py
########################################################################################################################
