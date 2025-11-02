#!/usr/bin/env python3
# test_authnz_backends.py
# Description: Test script to validate both SQLite and PostgreSQL backends for AuthNZ system
#
# This script tests the AuthNZ system with both database backends to ensure
# compatibility and proper functionality.
#
########################################################################################################################

import os
import sys
import tempfile
import secrets
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import json
from urllib.parse import urlparse, parse_qs

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tldw_Server_API.app.core.DB_Management.UserDatabase_v2 import (
    UserDatabase,
    DuplicateUserError,
    UserNotFoundError
)
from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig, BackendType
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.AuthNZ.db_config import AuthDatabaseConfig

########################################################################################################################
# Test Configuration
########################################################################################################################

class TestConfig:
    """Test configuration for different backends"""

    @staticmethod
    def get_sqlite_config(temp_dir: str) -> DatabaseConfig:
        """Get SQLite test configuration"""
        db_path = os.path.join(temp_dir, "test_users.db")
        return DatabaseConfig(
            backend_type=BackendType.SQLITE,
            sqlite_path=db_path,
            sqlite_wal_mode=True,
            sqlite_foreign_keys=True
        )

    @staticmethod
    def get_postgresql_config() -> DatabaseConfig:
        """Get PostgreSQL test configuration"""
        # Use environment variables or defaults
        dsn = (os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
        if not dsn:
            dsn = "postgresql://tldw_user:TestPassword123!@localhost:5432/tldw_test"

        parsed = urlparse(dsn)
        config = DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            connection_string=dsn,
            pool_size=5,
            echo=os.getenv("TLDW_DB_ECHO", "false").lower() == "true"
        )

        if parsed.scheme.startswith("postgres"):
            config.pg_host = parsed.hostname or "localhost"
            try:
                config.pg_port = int(parsed.port or 5432)
            except Exception:
                config.pg_port = 5432
            config.pg_database = (parsed.path or "/").lstrip("/") or None
            config.pg_user = parsed.username or None
            config.pg_password = parsed.password or None
            query_params = parse_qs(parsed.query or "")
            if "sslmode" in query_params and query_params["sslmode"]:
                config.pg_sslmode = query_params["sslmode"][0]

        return config

########################################################################################################################
# Test Suite
########################################################################################################################

class AuthNZBackendTests:
    """Test suite for AuthNZ database backends"""

    def __init__(self, backend_type: str, verbose: bool = False):
        """
        Initialize test suite

        Args:
            backend_type: "sqlite" or "postgresql"
            verbose: Enable verbose output
        """
        self.backend_type = backend_type
        self.verbose = verbose
        self.password_service = PasswordService()
        self.temp_dir = None
        self.user_db = None
        self.test_results = []

    def setup(self):
        """Set up test database"""
        print(f"\n{'='*60}")
        print(f"Setting up {self.backend_type.upper()} backend tests")
        print(f"{'='*60}")

        if self.backend_type == "sqlite":
            self.temp_dir = tempfile.mkdtemp()
            config = TestConfig.get_sqlite_config(self.temp_dir)
            print(f"✓ Created temp directory: {self.temp_dir}")
        else:
            config = TestConfig.get_postgresql_config()
            print(f"✓ Using PostgreSQL: {config.connection_string.split('@')[-1]}")

        self.user_db = UserDatabase(config=config, client_id="test_suite")
        print(f"✓ Initialized UserDatabase")

    def teardown(self):
        """Clean up test database"""
        if self.backend_type == "postgresql":
            # Clean up test data
            try:
                # Drop all test users
                with self.user_db.backend.transaction() as conn:
                    self.user_db.backend.execute("DELETE FROM users WHERE username LIKE 'test_%'")
                print("✓ Cleaned up PostgreSQL test data")
            except:
                pass

        if self.temp_dir:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            print(f"✓ Removed temp directory")

    def run_test(self, test_name: str, test_func):
        """Run a single test"""
        try:
            test_func()
            self.test_results.append((test_name, "PASS", None))
            if self.verbose:
                print(f"  ✓ {test_name}")
        except Exception as e:
            self.test_results.append((test_name, "FAIL", str(e)))
            print(f"  ✗ {test_name}: {e}")

    def test_user_crud(self):
        """Test user CRUD operations"""
        print("\n🧪 Testing User CRUD Operations...")

        # Create user
        def test_create():
            username = f"test_user_{secrets.token_hex(4)}"
            email = f"{username}@example.com"
            password_hash = self.password_service.hash_password("P@ssw0rd#2024$Secure")

            user_id = self.user_db.create_user(
                username=username,
                email=email,
                password_hash=password_hash,
                role="user"
            )

            assert user_id is not None
            self.test_user_id = user_id
            self.test_username = username
            self.test_email = email

        self.run_test("Create user", test_create)

        # Read user
        def test_read():
            user = self.user_db.get_user(user_id=self.test_user_id)
            assert user is not None
            assert user['username'] == self.test_username
            assert user['email'] == self.test_email
            assert 'user' in user['roles']

        self.run_test("Read user", test_read)

        # Update user
        def test_update():
            success = self.user_db.update_user(
                self.test_user_id,
                is_verified=True,
                metadata={"test": "data"}
            )
            assert success is True

            user = self.user_db.get_user(user_id=self.test_user_id)
            assert user['is_verified'] is True

        self.run_test("Update user", test_update)

        # Delete user (soft delete)
        def test_delete():
            success = self.user_db.delete_user(self.test_user_id)
            assert success is True

            user = self.user_db.get_user(user_id=self.test_user_id)
            assert user['is_active'] is False

        self.run_test("Delete user", test_delete)

        # Test duplicate prevention
        def test_duplicate():
            username = f"test_dup_{secrets.token_hex(4)}"
            email = f"{username}@example.com"
            password_hash = self.password_service.hash_password("P@ssw0rd#2024$Secure")

            # Create first user
            self.user_db.create_user(username, email, password_hash)

            # Try to create duplicate
            try:
                self.user_db.create_user(username, email, password_hash)
                assert False, "Should have raised DuplicateUserError"
            except DuplicateUserError:
                pass  # Expected

        self.run_test("Prevent duplicates", test_duplicate)

    def test_roles_permissions(self):
        """Test RBAC functionality"""
        print("\n🧪 Testing Roles & Permissions...")

        # Create test user
        username = f"test_rbac_{secrets.token_hex(4)}"
        email = f"{username}@example.com"
        password_hash = self.password_service.hash_password("P@ssw0rd#2024$Secure")
        user_id = self.user_db.create_user(username, email, password_hash, role="user")

        # Test role assignment
        def test_assign_role():
            success = self.user_db.assign_role(user_id, "admin")
            assert success is True

            roles = self.user_db.get_user_roles(user_id)
            assert "admin" in roles
            assert "user" in roles

        self.run_test("Assign role", test_assign_role)

        # Test permission checking
        def test_permissions():
            permissions = self.user_db.get_user_permissions(user_id)

            # Admin should have all permissions
            assert "media.create" in permissions
            assert "media.delete" in permissions
            assert "system.configure" in permissions
            assert "users.manage_roles" in permissions

        self.run_test("Check permissions", test_permissions)

        # Test role revocation
        def test_revoke_role():
            success = self.user_db.revoke_role(user_id, "admin")
            assert success is True

            roles = self.user_db.get_user_roles(user_id)
            assert "admin" not in roles
            assert "user" in roles

            # Permissions should be reduced
            permissions = self.user_db.get_user_permissions(user_id)
            assert "system.configure" not in permissions
            assert "media.read" in permissions  # User still has this

        self.run_test("Revoke role", test_revoke_role)

        # Test permission helpers
        def test_permission_helpers():
            assert self.user_db.has_role(user_id, "user") is True
            assert self.user_db.has_role(user_id, "admin") is False
            assert self.user_db.has_permission(user_id, "media.read") is True
            assert self.user_db.has_permission(user_id, "system.configure") is False

        self.run_test("Permission helpers", test_permission_helpers)

    def test_registration_codes(self):
        """Test registration code functionality"""
        print("\n🧪 Testing Registration Codes...")

        # Create registration code
        def test_create_code():
            code = self.user_db.create_registration_code(
                created_by=None,
                expires_in_days=7,
                max_uses=3,
                role="viewer"
            )

            assert code is not None
            assert len(code) > 20
            self.test_code = code

        self.run_test("Create registration code", test_create_code)

        # Validate code
        def test_validate_code():
            code_info = self.user_db.validate_registration_code(self.test_code)
            assert code_info is not None
            assert code_info['max_uses'] == 3
            assert code_info['times_used'] == 0
            assert code_info['role_name'] == 'viewer'

        self.run_test("Validate registration code", test_validate_code)

        # Use registration code
        def test_use_code():
            # Create a user who uses the code
            username = f"test_reg_{secrets.token_hex(4)}"
            email = f"{username}@example.com"
            password_hash = self.password_service.hash_password("P@ssw0rd#2024$Secure")
            user_id = self.user_db.create_user(username, email, password_hash, role="viewer")

            # Use the code
            success = self.user_db.use_registration_code(
                self.test_code,
                user_id,
                ip_address="127.0.0.1",
                user_agent="Test Suite"
            )
            assert success is True

            # Check code was used
            code_info = self.user_db.validate_registration_code(self.test_code)
            assert code_info is not None
            assert code_info['times_used'] == 1

        self.run_test("Use registration code", test_use_code)

    def test_authentication(self):
        """Test authentication tracking"""
        print("\n🧪 Testing Authentication Features...")

        # Create test user
        username = f"test_auth_{secrets.token_hex(4)}"
        email = f"{username}@example.com"
        password_hash = self.password_service.hash_password("P@ssw0rd#2024$Secure")
        user_id = self.user_db.create_user(username, email, password_hash)

        # Test login recording
        def test_record_login():
            success = self.user_db.record_login(
                user_id,
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0"
            )
            assert success is True

            user = self.user_db.get_user(user_id=user_id)
            assert user['last_login'] is not None
            assert user['failed_login_attempts'] == 0

        self.run_test("Record login", test_record_login)

        # Test failed login tracking
        def test_failed_login():
            attempts = self.user_db.record_failed_login(username, ip_address="192.168.1.1")
            assert attempts == 1

            # Try multiple times
            for i in range(4):
                attempts = self.user_db.record_failed_login(username)

            assert attempts == 5

            # Should be locked after 5 attempts
            is_locked = self.user_db.is_account_locked(user_id)
            assert is_locked is True

        self.run_test("Track failed logins", test_failed_login)

    def run_all_tests(self):
        """Run all tests"""
        self.setup()

        try:
            self.test_user_crud()
            self.test_roles_permissions()
            self.test_registration_codes()
            self.test_authentication()
        finally:
            self.teardown()

        # Print summary
        print(f"\n{'='*60}")
        print(f"Test Results for {self.backend_type.upper()}")
        print(f"{'='*60}")

        passed = sum(1 for _, status, _ in self.test_results if status == "PASS")
        failed = sum(1 for _, status, _ in self.test_results if status == "FAIL")

        print(f"✓ Passed: {passed}")
        print(f"✗ Failed: {failed}")
        print(f"Total: {len(self.test_results)}")

        if failed > 0:
            print(f"\nFailed Tests:")
            for name, status, error in self.test_results:
                if status == "FAIL":
                    print(f"  - {name}: {error}")

        return failed == 0

########################################################################################################################
# Main Function
########################################################################################################################

def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(
        description="Test AuthNZ system with different database backends"
    )
    parser.add_argument(
        "--backend",
        choices=["sqlite", "postgresql", "both"],
        default="sqlite",
        help="Database backend to test"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--config-test",
        action="store_true",
        help="Test configuration detection"
    )

    args = parser.parse_args()

    # Test configuration detection
    if args.config_test:
        print("\n" + "="*60)
        print("Testing Configuration Detection")
        print("="*60)

        # Test with SQLite
        os.environ["TLDW_USER_DB_BACKEND"] = "sqlite"
        os.environ["DATABASE_URL"] = "sqlite:///test.db"

        config = AuthDatabaseConfig()
        config.print_config()

        # Test with PostgreSQL
        os.environ["TLDW_USER_DB_BACKEND"] = "postgresql"
        os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/test"

        config.reset()
        config.print_config()

        return

    # Run backend tests
    backends_to_test = []

    if args.backend == "both":
        backends_to_test = ["sqlite", "postgresql"]
    else:
        backends_to_test = [args.backend]

    all_passed = True

    for backend in backends_to_test:
        if backend == "postgresql":
            # Check if PostgreSQL is available
            try:
                from tldw_Server_API.app.core.DB_Management.backends.postgresql_backend import PostgreSQLBackend
            except ImportError:
                print(f"\n⚠️  PostgreSQL backend not available (psycopg2 not installed)")
                print("   Install with: pip install psycopg2-binary")
                continue

        tester = AuthNZBackendTests(backend, verbose=args.verbose)

        try:
            passed = tester.run_all_tests()
            all_passed = all_passed and passed
        except Exception as e:
            print(f"\n❌ Test suite failed for {backend}: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

    # Final summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")

    if all_passed:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

#
# End of test_authnz_backends.py
########################################################################################################################
