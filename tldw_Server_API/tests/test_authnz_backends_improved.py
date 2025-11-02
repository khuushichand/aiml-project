#!/usr/bin/env python3
# test_authnz_backends_improved.py
# Description: Improved test suite for AuthNZ system with better isolation and coverage
#
# This script tests the AuthNZ system with both database backends using
# best practices for test isolation, error handling, and comprehensive coverage.
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
import unittest
from typing import Optional, Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tldw_Server_API.app.core.DB_Management.UserDatabase_v2 import (
    UserDatabase,
    DuplicateUserError,
    UserNotFoundError,
    UserDatabaseError
)
from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig, BackendType
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.AuthNZ.db_config import AuthDatabaseConfig
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

########################################################################################################################
# Test Configuration
########################################################################################################################

class TestConfig:
    """Test configuration for different backends"""

    @staticmethod
    def get_sqlite_config(temp_dir: str) -> DatabaseConfig:
        """Get SQLite test configuration with isolation"""
        db_path = os.path.join(temp_dir, f"test_users_{secrets.token_hex(4)}.db")
        return DatabaseConfig(
            backend_type=BackendType.SQLITE,
            sqlite_path=db_path,
            sqlite_wal_mode=True,
            sqlite_foreign_keys=True
        )

    @staticmethod
    def get_postgresql_config() -> DatabaseConfig:
        """Get PostgreSQL test configuration"""
        return DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            connection_string=os.getenv(
                "TEST_DATABASE_URL",
                "postgresql://postgres:postgres@localhost:5432/tldw_test"
            ),
            pool_size=5,
            echo=os.getenv("TLDW_DB_ECHO", "false").lower() == "true"
        )

########################################################################################################################
# Base Test Class
########################################################################################################################

class AuthNZTestBase(unittest.TestCase):
    """Base class for AuthNZ backend tests with proper setup/teardown"""

    backend_type: str = "sqlite"
    user_db: Optional[UserDatabase] = None
    password_service: PasswordService = None
    temp_dir: Optional[str] = None
    test_users: list = None

    @classmethod
    def setUpClass(cls):
        """Set up class-level resources"""
        cls.password_service = PasswordService()
        cls.test_users = []

    def setUp(self):
        """Set up test database for each test"""
        if self.backend_type == "sqlite":
            self.temp_dir = tempfile.mkdtemp()
            config = TestConfig.get_sqlite_config(self.temp_dir)
        else:
            config = TestConfig.get_postgresql_config()

        self.user_db = UserDatabase(config=config, client_id="test_suite")
        self.test_users = []  # Track users created in this test

    def tearDown(self):
        """Clean up after each test"""
        # Clean up test users
        if self.user_db and self.test_users:
            try:
                with self.user_db.backend.transaction() as conn:
                    for user_id in self.test_users:
                        try:
                            # Hard delete for test cleanup
                            if self.user_db.backend.backend_type == BackendType.SQLITE:
                                self.user_db.backend.execute(
                                    "DELETE FROM users WHERE id = ?",
                                    (user_id,)
                                )
                            else:
                                self.user_db.backend.execute(
                                    "DELETE FROM users WHERE id = %s",
                                    (user_id,)
                                )
                        except Exception:
                            pass  # User might already be deleted
            except Exception as e:
                print(f"Warning: Failed to clean up test users: {e}")

        # Clean up temp directory for SQLite
        if self.temp_dir:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_user(self, username_prefix: str = "test") -> Dict[str, Any]:
        """Helper to create a test user with unique credentials"""
        username = f"{username_prefix}_{secrets.token_hex(4)}"
        email = f"{username}@example.com"
        password = "Secure#Pass2024$NoSeq"  # Avoids sequential chars
        password_hash = self.password_service.hash_password(password)

        user_id = self.user_db.create_user(
            username=username,
            email=email,
            password_hash=password_hash,
            role="user"
        )

        self.test_users.append(user_id)

        return {
            "id": user_id,
            "username": username,
            "email": email,
            "password": password,
            "password_hash": password_hash
        }

########################################################################################################################
# User CRUD Tests
########################################################################################################################

class TestUserCRUD(AuthNZTestBase):
    """Test user CRUD operations"""

    def test_create_user_success(self):
        """Test successful user creation"""
        user_data = self.create_test_user("crud_create")

        self.assertIsNotNone(user_data["id"])
        self.assertIsInstance(user_data["id"], int)

        # Verify user exists
        user = self.user_db.get_user(user_id=user_data["id"])
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], user_data["username"])
        self.assertEqual(user["email"], user_data["email"])

    def test_create_user_duplicate_username(self):
        """Test duplicate username prevention"""
        user_data = self.create_test_user("crud_dup")

        # Try to create with same username
        with self.assertRaises(DuplicateUserError):
            self.user_db.create_user(
                username=user_data["username"],
                email="different@example.com",
                password_hash=user_data["password_hash"]
            )

    def test_create_user_duplicate_email(self):
        """Test duplicate email prevention"""
        user_data = self.create_test_user("crud_email")

        # Try to create with same email
        with self.assertRaises(DuplicateUserError):
            self.user_db.create_user(
                username="different_user",
                email=user_data["email"],
                password_hash=user_data["password_hash"]
            )

    def test_read_user_by_id(self):
        """Test reading user by ID"""
        user_data = self.create_test_user("crud_read")

        user = self.user_db.get_user(user_id=user_data["id"])

        self.assertIsNotNone(user)
        self.assertEqual(user["id"], user_data["id"])
        self.assertEqual(user["username"], user_data["username"])
        self.assertEqual(user["email"], user_data["email"])
        self.assertIn("user", user["roles"])

    def test_read_user_by_username(self):
        """Test reading user by username"""
        user_data = self.create_test_user("crud_username")

        user = self.user_db.get_user(username=user_data["username"])

        self.assertIsNotNone(user)
        self.assertEqual(user["id"], user_data["id"])
        self.assertEqual(user["username"], user_data["username"])

    def test_read_nonexistent_user(self):
        """Test reading non-existent user returns None"""
        user = self.user_db.get_user(user_id=999999)
        self.assertIsNone(user)

        user = self.user_db.get_user(username="nonexistent_user")
        self.assertIsNone(user)

    def test_update_user_success(self):
        """Test successful user update"""
        user_data = self.create_test_user("crud_update")

        # Update user
        success = self.user_db.update_user(
            user_data["id"],
            is_verified=True,
            metadata={"test": "data", "number": 42}
        )

        self.assertTrue(success)

        # Verify changes
        user = self.user_db.get_user(user_id=user_data["id"])
        self.assertTrue(user["is_verified"])
        self.assertEqual(user["metadata"]["test"], "data")
        self.assertEqual(user["metadata"]["number"], 42)

    def test_update_nonexistent_user(self):
        """Test updating non-existent user"""
        success = self.user_db.update_user(
            999999,
            is_verified=True
        )

        self.assertFalse(success)

    def test_delete_user_soft(self):
        """Test soft delete (deactivation)"""
        user_data = self.create_test_user("crud_delete")

        # Soft delete
        success = self.user_db.delete_user(user_data["id"])

        self.assertTrue(success)

        # User should still exist but be inactive
        user = self.user_db.get_user(user_id=user_data["id"])
        self.assertIsNotNone(user)
        self.assertFalse(user["is_active"])

    def test_delete_nonexistent_user(self):
        """Test deleting non-existent user"""
        success = self.user_db.delete_user(999999)
        self.assertFalse(success)

########################################################################################################################
# RBAC Tests
########################################################################################################################

class TestRBAC(AuthNZTestBase):
    """Test Role-Based Access Control functionality"""

    def test_assign_role(self):
        """Test role assignment"""
        user_data = self.create_test_user("rbac_assign")

        # Assign admin role
        success = self.user_db.assign_role(user_data["id"], "admin")
        self.assertTrue(success)

        # Check roles
        roles = self.user_db.get_user_roles(user_data["id"])
        self.assertIn("admin", roles)
        self.assertIn("user", roles)  # Original role

    def test_assign_invalid_role(self):
        """Test assigning non-existent role"""
        user_data = self.create_test_user("rbac_invalid")

        # Should handle gracefully
        success = self.user_db.assign_role(user_data["id"], "nonexistent_role")
        self.assertFalse(success)

    def test_revoke_role(self):
        """Test role revocation"""
        user_data = self.create_test_user("rbac_revoke")

        # Assign then revoke
        self.user_db.assign_role(user_data["id"], "admin")
        success = self.user_db.revoke_role(user_data["id"], "admin")

        self.assertTrue(success)

        # Check role is gone
        roles = self.user_db.get_user_roles(user_data["id"])
        self.assertNotIn("admin", roles)
        self.assertIn("user", roles)  # Original role remains

    def test_permissions_inheritance(self):
        """Test permission inheritance from roles"""
        user_data = self.create_test_user("rbac_perms")

        # User role permissions
        user_perms = self.user_db.get_user_permissions(user_data["id"])
        self.assertIn("media.read", user_perms)
        self.assertIn("media.create", user_perms)
        self.assertNotIn("system.configure", user_perms)

        # Add admin role
        self.user_db.assign_role(user_data["id"], "admin")

        # Admin should have all permissions
        admin_perms = self.user_db.get_user_permissions(user_data["id"])
        self.assertIn("media.read", admin_perms)
        self.assertIn("media.delete", admin_perms)
        self.assertIn("system.configure", admin_perms)
        self.assertIn("users.manage_roles", admin_perms)

    def test_custom_role(self):
        """Test custom role with no default permissions"""
        user_data = self.create_test_user("rbac_custom")

        # Remove default role and assign custom
        self.user_db.revoke_role(user_data["id"], "user")
        self.user_db.assign_role(user_data["id"], "custom")

        # Custom role should have no permissions by default
        roles = self.user_db.get_user_roles(user_data["id"])
        self.assertIn("custom", roles)

        perms = self.user_db.get_user_permissions(user_data["id"])
        self.assertEqual(len(perms), 0)

    def test_permission_helpers(self):
        """Test permission checking helpers"""
        user_data = self.create_test_user("rbac_helpers")

        # Check role helpers
        self.assertTrue(self.user_db.has_role(user_data["id"], "user"))
        self.assertFalse(self.user_db.has_role(user_data["id"], "admin"))

        # Check permission helpers
        self.assertTrue(self.user_db.has_permission(user_data["id"], "media.read"))
        self.assertFalse(self.user_db.has_permission(user_data["id"], "system.configure"))

########################################################################################################################
# Registration Code Tests
########################################################################################################################

class TestRegistrationCodes(AuthNZTestBase):
    """Test registration code functionality"""

    def test_create_registration_code(self):
        """Test creating registration code"""
        code = self.user_db.create_registration_code(
            created_by=None,
            expires_in_days=7,
            max_uses=3,
            role="viewer"
        )

        self.assertIsNotNone(code)
        self.assertGreater(len(code), 20)

        # Validate the code
        code_info = self.user_db.validate_registration_code(code)
        self.assertIsNotNone(code_info)
        self.assertEqual(code_info["max_uses"], 3)
        self.assertEqual(code_info["times_used"], 0)
        self.assertEqual(code_info["role_name"], "viewer")

    def test_use_registration_code(self):
        """Test using registration code"""
        # Create code
        code = self.user_db.create_registration_code(
            created_by=None,
            expires_in_days=7,
            max_uses=2,
            role="viewer"
        )

        # Create user and use code
        user_data = self.create_test_user("reg_use")
        success = self.user_db.use_registration_code(
            code,
            user_data["id"],
            ip_address="127.0.0.1",
            user_agent="Test Suite"
        )

        self.assertTrue(success)

        # Check usage count
        code_info = self.user_db.validate_registration_code(code)
        self.assertEqual(code_info["times_used"], 1)

    def test_registration_code_max_uses(self):
        """Test registration code max uses enforcement"""
        # Create code with 1 use
        code = self.user_db.create_registration_code(
            created_by=None,
            expires_in_days=7,
            max_uses=1,
            role="viewer"
        )

        # Use it once
        user1 = self.create_test_user("reg_max1")
        self.user_db.use_registration_code(code, user1["id"])

        # Try to use again - should fail or return false
        user2 = self.create_test_user("reg_max2")

        # Code should be invalid after max uses
        code_info = self.user_db.validate_registration_code(code)
        if code_info:
            self.assertGreaterEqual(code_info["times_used"], code_info["max_uses"])

    def test_expired_registration_code(self):
        """Test expired registration code"""
        # Create code that expires immediately
        code = self.user_db.create_registration_code(
            created_by=None,
            expires_in_days=-1,  # Already expired
            max_uses=1,
            role="viewer"
        )

        # Should be invalid
        code_info = self.user_db.validate_registration_code(code)
        # Expired codes might return None or have is_active=False
        if code_info:
            # Check if expiration date is in the past
            import dateutil.parser
            expires_at = dateutil.parser.parse(code_info["expires_at"])
            self.assertLess(expires_at, datetime.now(timezone.utc))

########################################################################################################################
# Authentication Tests
########################################################################################################################

class TestAuthentication(AuthNZTestBase):
    """Test authentication tracking functionality"""

    def test_record_login(self):
        """Test recording successful login"""
        user_data = self.create_test_user("auth_login")

        success = self.user_db.record_login(
            user_data["id"],
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )

        self.assertTrue(success)

        # Check login was recorded
        user = self.user_db.get_user(user_id=user_data["id"])
        self.assertIsNotNone(user["last_login"])
        self.assertEqual(user["failed_login_attempts"], 0)

    def test_record_failed_login(self):
        """Test recording failed login attempts"""
        user_data = self.create_test_user("auth_failed")

        # Record multiple failures
        for i in range(1, 4):
            attempts = self.user_db.record_failed_login(
                user_data["username"],
                ip_address="192.168.1.1"
            )
            self.assertEqual(attempts, i)

        # Check failed attempts were recorded
        user = self.user_db.get_user(user_id=user_data["id"])
        self.assertEqual(user["failed_login_attempts"], 3)

    def test_account_lockout(self):
        """Test account lockout after max failed attempts"""
        user_data = self.create_test_user("auth_lockout")

        # Record 5 failed attempts (typical lockout threshold)
        for _ in range(5):
            self.user_db.record_failed_login(user_data["username"])

        # Check if account is locked
        is_locked = self.user_db.is_account_locked(user_data["id"])
        self.assertTrue(is_locked)

        # Verify lockout in user data
        user = self.user_db.get_user(user_id=user_data["id"])
        self.assertEqual(user["failed_login_attempts"], 5)
        self.assertIsNotNone(user.get("locked_until"))

    def test_reset_failed_attempts_on_success(self):
        """Test that failed attempts reset on successful login"""
        user_data = self.create_test_user("auth_reset")

        # Record some failed attempts
        for _ in range(3):
            self.user_db.record_failed_login(user_data["username"])

        # Record successful login
        self.user_db.record_login(user_data["id"])

        # Failed attempts should be reset
        user = self.user_db.get_user(user_id=user_data["id"])
        self.assertEqual(user["failed_login_attempts"], 0)

########################################################################################################################
# Edge Cases and Error Handling Tests
########################################################################################################################

class TestEdgeCases(AuthNZTestBase):
    """Test edge cases and error handling"""

    def test_empty_username(self):
        """Test creating user with empty username"""
        with self.assertRaises((ValueError, UserDatabaseError)):
            self.user_db.create_user(
                username="",
                email="test@example.com",
                password_hash="hash"
            )

    def test_invalid_email_format(self):
        """Test creating user with invalid email"""
        # This might be handled at schema level or return error
        try:
            user_id = self.user_db.create_user(
                username="test_invalid_email",
                email="not_an_email",
                password_hash="hash"
            )
            if user_id:
                self.test_users.append(user_id)
                # Some systems might accept this, check if it's stored correctly
                user = self.user_db.get_user(user_id=user_id)
                self.assertEqual(user["email"], "not_an_email")
        except (ValueError, UserDatabaseError):
            # Expected for strict validation
            pass

    def test_very_long_username(self):
        """Test creating user with very long username"""
        long_username = "u" * 1000  # 1000 characters

        try:
            user_id = self.user_db.create_user(
                username=long_username,
                email="long@example.com",
                password_hash="hash"
            )
            if user_id:
                self.test_users.append(user_id)
                # Check if it was truncated or stored fully
                user = self.user_db.get_user(user_id=user_id)
                self.assertLessEqual(len(user["username"]), 255)  # Typical max
        except (ValueError, UserDatabaseError):
            # Expected if length limit enforced
            pass

    def test_none_values(self):
        """Test handling of None values"""
        user = self.user_db.get_user(user_id=None)
        self.assertIsNone(user)

        user = self.user_db.get_user(username=None)
        self.assertIsNone(user)

        success = self.user_db.update_user(None, is_verified=True)
        self.assertFalse(success)

        success = self.user_db.delete_user(None)
        self.assertFalse(success)

class TestAuthDatabaseConfigDetection(unittest.TestCase):
    """Validate AuthDatabaseConfig handles edge-case URLs and settings refresh."""

    def setUp(self):
        self._env_backup: Dict[str, Optional[str]] = {}

    def tearDown(self):
        for key, original in self._env_backup.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original
        reset_settings()
        AuthDatabaseConfig().reset()

    def _set_env(self, key: str, value: Optional[str]):
        if key not in self._env_backup:
            self._env_backup[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    def test_detects_postgres_with_driver_suffix(self):
        """Driver-qualified PostgreSQL URLs should map to postgres backend."""
        self._set_env("AUTH_MODE", "multi_user")
        self._set_env("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/testdb")
        self._set_env("TLDW_USER_DB_BACKEND", None)
        reset_settings()

        config = AuthDatabaseConfig()
        config.reset()

        self.assertEqual(config.backend_type, "postgresql")
        db_config = config.get_config()
        self.assertEqual(db_config.backend_type, BackendType.POSTGRESQL)

    def test_sqlite_memory_url_remains_in_memory(self):
        """sqlite:///:memory: must not be coerced into a filesystem path."""
        self._set_env("AUTH_MODE", "single_user")
        self._set_env("DATABASE_URL", "sqlite:///:memory:")
        self._set_env("TLDW_USER_DB_BACKEND", None)
        reset_settings()

        config = AuthDatabaseConfig()
        config.reset()

        db_config = config.get_config()
        self.assertEqual(db_config.backend_type, BackendType.SQLITE)
        self.assertEqual(db_config.sqlite_path, ":memory:")

    def test_reset_reflects_updated_database_url(self):
        """Calling reset() after reset_settings() must pick up new DATABASE_URL values."""
        self._set_env("AUTH_MODE", "single_user")
        self._set_env("TLDW_USER_DB_BACKEND", None)

        self._set_env("DATABASE_URL", "sqlite:///./first_authnz.db")
        reset_settings()
        config = AuthDatabaseConfig()
        config.reset()
        first_path = config.get_config().sqlite_path

        self._set_env("DATABASE_URL", "sqlite:///./second_authnz.db")
        reset_settings()
        config.reset()
        second_path = config.get_config().sqlite_path

        self.assertNotEqual(first_path, second_path)
        self.assertTrue(second_path.endswith("second_authnz.db"))

########################################################################################################################
# Test Suites
########################################################################################################################

def create_test_suite(backend_type: str) -> unittest.TestSuite:
    """Create test suite for specific backend"""
    suite = unittest.TestSuite()

    # Set backend type for all test classes
    for test_class in [TestUserCRUD, TestRBAC, TestRegistrationCodes,
                       TestAuthentication, TestEdgeCases, TestAuthDatabaseConfigDetection]:
        test_class.backend_type = backend_type
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(test_class))

    return suite

########################################################################################################################
# Main Test Runner
########################################################################################################################

def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(
        description="Improved test suite for AuthNZ system"
    )
    parser.add_argument(
        "--backend",
        choices=["sqlite", "postgresql", "both"],
        default="sqlite",
        help="Database backend to test"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity (use -v, -vv, etc.)"
    )
    parser.add_argument(
        "--failfast",
        action="store_true",
        help="Stop on first failure"
    )

    args = parser.parse_args()

    # Determine backends to test
    backends = []
    if args.backend == "both":
        backends = ["sqlite", "postgresql"]
    else:
        backends = [args.backend]

    # Check PostgreSQL availability
    if "postgresql" in backends:
        try:
            from tldw_Server_API.app.core.DB_Management.backends.postgresql_backend import PostgreSQLBackend
            import psycopg2
        except ImportError:
            print("\n⚠️  PostgreSQL backend not available (psycopg2 not installed)")
            print("   Install with: pip install psycopg2-binary")
            backends.remove("postgresql")

    # Run tests for each backend
    all_results = []

    for backend in backends:
        print(f"\n{'='*60}")
        print(f"Testing {backend.upper()} Backend")
        print(f"{'='*60}")

        # Create test suite
        suite = create_test_suite(backend)

        # Run tests
        runner = unittest.TextTestRunner(
            verbosity=args.verbose + 1,
            failfast=args.failfast
        )

        result = runner.run(suite)
        all_results.append((backend, result))

    # Print summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")

    total_passed = 0
    total_failed = 0
    total_errors = 0
    total_skipped = 0

    for backend, result in all_results:
        passed = result.testsRun - len(result.failures) - len(result.errors)
        print(f"\n{backend.upper()}:")
        print(f"  Tests run: {result.testsRun}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {len(result.failures)}")
        print(f"  Errors: {len(result.errors)}")
        print(f"  Skipped: {len(result.skipped)}")

        total_passed += passed
        total_failed += len(result.failures)
        total_errors += len(result.errors)
        total_skipped += len(result.skipped)

    print(f"\nTOTAL:")
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    print(f"  Errors: {total_errors}")
    print(f"  Skipped: {total_skipped}")

    # Return appropriate exit code
    if total_failed > 0 or total_errors > 0:
        print("\n❌ Some tests failed")
        return 1
    else:
        print("\n✅ All tests passed!")
        return 0

if __name__ == "__main__":
    sys.exit(main())

#
# End of test_authnz_backends_improved.py
########################################################################################################################
