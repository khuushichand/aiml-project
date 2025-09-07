# UserDatabase.py
# Description: User and authentication database management following MediaDatabase pattern
# Handles user management, RBAC, registration codes, and authentication for the tldw_server
#
# This module provides the UserDatabase class for managing user authentication and
# authorization data, following the same patterns as MediaDatabase for consistency.
#
# Key Features:
# - Thread-local connection management
# - Client ID tracking for multi-instance support
# - Schema versioning and migrations
# - Full RBAC (Role-Based Access Control) implementation
# - Registration code management
# - Audit logging for security events
# - Transaction safety with context managers
#
########################################################################################################################

import hashlib
import json
import os
import sqlite3
import threading
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional, Union
import logging
from uuid import uuid4

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

########################################################################################################################
# Custom Exceptions
########################################################################################################################

class UserDatabaseError(Exception):
    """Base exception for user database related errors."""
    pass

class UserNotFoundError(UserDatabaseError):
    """User not found in database."""
    pass

class DuplicateUserError(UserDatabaseError):
    """User already exists."""
    pass

class InvalidPermissionError(UserDatabaseError):
    """Invalid permission or role."""
    pass

class RegistrationCodeError(UserDatabaseError):
    """Registration code related errors."""
    pass

class AuthenticationError(UserDatabaseError):
    """Authentication related errors."""
    pass

########################################################################################################################
# UserDatabase Class
########################################################################################################################

class UserDatabase:
    """
    Manages SQLite connection and operations for user authentication and authorization,
    following the MediaDatabase pattern for consistency across the project.
    """
    
    _CURRENT_SCHEMA_VERSION = 1
    
    def __init__(self, db_path: Union[str, Path], client_id: str):
        """
        Initialize UserDatabase instance.
        
        Args:
            db_path: Path to the SQLite database file
            client_id: Identifier for the client/instance making changes
        """
        self.db_path = Path(db_path)
        self.client_id = client_id
        self._local = threading.local()
        self._lock = threading.Lock()
        
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database schema
        self._initialize_schema()
        
        logger.info(f"UserDatabase initialized at {self.db_path} for client {client_id}")
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Get or create a thread-local database connection.
        
        Returns:
            sqlite3.Connection: Thread-local connection to the database
        """
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self._local.conn.execute("PRAGMA foreign_keys = ON")
            logger.debug(f"Created new connection for thread {threading.current_thread().name}")
        return self._local.conn
    
    def close_connection(self):
        """Close the thread-local database connection if it exists."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
            logger.debug(f"Closed connection for thread {threading.current_thread().name}")
    
    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions.
        
        Yields:
            sqlite3.Connection: Database connection with transaction
        """
        conn = self.get_connection()
        in_transaction = conn.in_transaction
        
        try:
            if not in_transaction:
                conn.execute("BEGIN")
                logger.debug("Started transaction")
            
            yield conn
            
            if not in_transaction:
                conn.commit()
                logger.debug("Committed transaction")
                
        except Exception as e:
            if not in_transaction:
                logger.error(f"Transaction failed, rolling back: {e}")
                try:
                    conn.rollback()
                    logger.debug("Rollback successful")
                except sqlite3.Error as rb_err:
                    logger.error(f"Rollback failed: {rb_err}")
            raise
    
    def _initialize_schema(self):
        """Initialize database schema if needed."""
        conn = self.get_connection()
        
        # Read schema file
        schema_path = Path(__file__).parent.parent.parent.parent / "Databases" / "SQLite" / "Schema" / "users_auth_schema.sql"
        
        if not schema_path.exists():
            # Fallback to embedded schema
            logger.warning(f"Schema file not found at {schema_path}, using embedded schema")
            self._create_embedded_schema(conn)
        else:
            try:
                with open(schema_path, 'r') as f:
                    schema_sql = f.read()
                conn.executescript(schema_sql)
                conn.commit()
                logger.info("Database schema initialized from file")
            except Exception as e:
                logger.error(f"Failed to load schema from file: {e}")
                self._create_embedded_schema(conn)
    
    def _create_embedded_schema(self, conn: sqlite3.Connection):
        """Create database schema from embedded SQL."""
        # This is a fallback - the actual schema should be loaded from file
        schema_sql = """
        -- Basic users table (minimal fallback schema)
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            is_system BOOLEAN NOT NULL DEFAULT 0
        );
        
        -- Basic default roles
        INSERT OR IGNORE INTO roles (name, description, is_system) VALUES 
            ('admin', 'Administrator', 1),
            ('user', 'Standard User', 1),
            ('viewer', 'Read-only User', 1),
            ('custom', 'Custom Role', 1);
        """
        conn.executescript(schema_sql)
        conn.commit()
        logger.info("Embedded fallback schema created")
    
    ########################################################################################################################
    # User Management Methods
    ########################################################################################################################
    
    def create_user(self, username: str, email: str, password_hash: str, 
                   role: str = 'user', **kwargs) -> int:
        """
        Create a new user.
        
        Args:
            username: Unique username
            email: User email address
            password_hash: Hashed password
            role: Initial role (default: 'user')
            **kwargs: Additional user fields
            
        Returns:
            int: User ID of created user
            
        Raises:
            DuplicateUserError: If username or email already exists
        """
        with self.transaction() as conn:
            try:
                cursor = conn.execute("""
                    INSERT INTO users (username, email, password_hash, metadata)
                    VALUES (?, ?, ?, ?)
                """, (username, email, password_hash, json.dumps(kwargs)))
                
                user_id = cursor.lastrowid
                
                # Assign default role
                role_id = self._get_role_id(role)
                if role_id:
                    conn.execute("""
                        INSERT INTO user_roles (user_id, role_id)
                        VALUES (?, ?)
                    """, (user_id, role_id))
                
                # Log the creation
                self._audit_log(conn, 'user_created', user_id, None, 
                              {'username': username, 'email': email, 'role': role})
                
                logger.info(f"Created user {username} with ID {user_id}")
                return user_id
                
            except sqlite3.IntegrityError as e:
                if 'username' in str(e):
                    raise DuplicateUserError(f"Username '{username}' already exists")
                elif 'email' in str(e):
                    raise DuplicateUserError(f"Email '{email}' already exists")
                raise UserDatabaseError(f"Failed to create user: {e}")
    
    def get_user(self, user_id: Optional[int] = None, username: Optional[str] = None, 
                 email: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get user by ID, username, or email.
        
        Args:
            user_id: User ID
            username: Username
            email: Email address
            
        Returns:
            Dict containing user data or None if not found
        """
        conn = self.get_connection()
        
        if user_id:
            cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        elif username:
            cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
        elif email:
            cursor = conn.execute("SELECT * FROM users WHERE email = ?", (email,))
        else:
            return None
        
        row = cursor.fetchone()
        if row:
            user_dict = dict(row)
            # Add roles
            user_dict['roles'] = self.get_user_roles(user_dict['id'])
            return user_dict
        return None
    
    def update_user(self, user_id: int, **updates) -> bool:
        """
        Update user information.
        
        Args:
            user_id: User ID to update
            **updates: Fields to update
            
        Returns:
            bool: True if update successful
        """
        with self.transaction() as conn:
            # Build update query
            allowed_fields = ['email', 'is_active', 'is_verified', 'metadata']
            set_clause = []
            values = []
            
            for field, value in updates.items():
                if field in allowed_fields:
                    set_clause.append(f"{field} = ?")
                    values.append(value if field != 'metadata' else json.dumps(value))
            
            if not set_clause:
                return False
            
            values.append(user_id)
            query = f"UPDATE users SET {', '.join(set_clause)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            
            cursor = conn.execute(query, values)
            
            if cursor.rowcount > 0:
                self._audit_log(conn, 'user_updated', user_id, None, updates)
                return True
            return False
    
    def delete_user(self, user_id: int) -> bool:
        """
        Delete a user (soft delete by setting is_active = 0).
        
        Args:
            user_id: User ID to delete
            
        Returns:
            bool: True if deletion successful
        """
        return self.update_user(user_id, is_active=False)
    
    ########################################################################################################################
    # Role and Permission Management
    ########################################################################################################################
    
    def get_user_roles(self, user_id: int) -> List[str]:
        """
        Get all roles assigned to a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of role names
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            SELECT r.name 
            FROM roles r
            JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = ? AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
        """, (user_id,))
        
        return [row['name'] for row in cursor.fetchall()]
    
    def assign_role(self, user_id: int, role_name: str, granted_by: Optional[int] = None,
                   expires_at: Optional[datetime] = None) -> bool:
        """
        Assign a role to a user.
        
        Args:
            user_id: User ID
            role_name: Name of role to assign
            granted_by: ID of user granting the role
            expires_at: Optional expiration datetime
            
        Returns:
            bool: True if assignment successful
        """
        with self.transaction() as conn:
            role_id = self._get_role_id(role_name)
            if not role_id:
                raise InvalidPermissionError(f"Role '{role_name}' does not exist")
            
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO user_roles (user_id, role_id, granted_by, expires_at)
                    VALUES (?, ?, ?, ?)
                """, (user_id, role_id, granted_by, expires_at))
                
                self._audit_log(conn, 'role_assigned', user_id, granted_by,
                              {'role': role_name, 'expires_at': expires_at.isoformat() if expires_at else None})
                return True
                
            except sqlite3.Error as e:
                logger.error(f"Failed to assign role: {e}")
                return False
    
    def revoke_role(self, user_id: int, role_name: str, revoked_by: Optional[int] = None) -> bool:
        """
        Revoke a role from a user.
        
        Args:
            user_id: User ID
            role_name: Name of role to revoke
            revoked_by: ID of user revoking the role
            
        Returns:
            bool: True if revocation successful
        """
        with self.transaction() as conn:
            role_id = self._get_role_id(role_name)
            if not role_id:
                return False
            
            cursor = conn.execute("""
                DELETE FROM user_roles 
                WHERE user_id = ? AND role_id = ?
            """, (user_id, role_id))
            
            if cursor.rowcount > 0:
                self._audit_log(conn, 'role_revoked', user_id, revoked_by, {'role': role_name})
                return True
            return False
    
    def get_user_permissions(self, user_id: int) -> List[str]:
        """
        Get all permissions for a user (from roles and direct assignments).
        
        Args:
            user_id: User ID
            
        Returns:
            List of permission names
        """
        conn = self.get_connection()
        
        # Get permissions from roles
        cursor = conn.execute("""
            SELECT DISTINCT p.name
            FROM permissions p
            JOIN role_permissions rp ON p.id = rp.permission_id
            JOIN user_roles ur ON rp.role_id = ur.role_id
            WHERE ur.user_id = ? AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
        """, (user_id,))
        
        permissions = set(row['name'] for row in cursor.fetchall())
        
        # Get direct permissions (add granted, remove revoked)
        cursor = conn.execute("""
            SELECT p.name, up.granted
            FROM permissions p
            JOIN user_permissions up ON p.id = up.permission_id
            WHERE up.user_id = ? AND (up.expires_at IS NULL OR up.expires_at > CURRENT_TIMESTAMP)
        """, (user_id,))
        
        for row in cursor.fetchall():
            if row['granted']:
                permissions.add(row['name'])
            else:
                permissions.discard(row['name'])
        
        return list(permissions)
    
    def has_permission(self, user_id: int, permission: str) -> bool:
        """
        Check if user has a specific permission.
        
        Args:
            user_id: User ID
            permission: Permission name to check
            
        Returns:
            bool: True if user has permission
        """
        permissions = self.get_user_permissions(user_id)
        return permission in permissions
    
    def has_role(self, user_id: int, role: str) -> bool:
        """
        Check if user has a specific role.
        
        Args:
            user_id: User ID
            role: Role name to check
            
        Returns:
            bool: True if user has role
        """
        roles = self.get_user_roles(user_id)
        return role in roles
    
    ########################################################################################################################
    # Registration Code Management
    ########################################################################################################################
    
    def create_registration_code(self, created_by: Optional[int] = None, 
                                expires_in_days: int = 7,
                                max_uses: int = 1,
                                role: str = 'user') -> str:
        """
        Create a new registration code.
        
        Args:
            created_by: User ID who created the code
            expires_in_days: Days until code expires
            max_uses: Maximum number of times code can be used
            role: Default role to assign to users who register with this code
            
        Returns:
            str: The generated registration code
        """
        code = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        
        with self.transaction() as conn:
            role_id = self._get_role_id(role)
            
            conn.execute("""
                INSERT INTO registration_codes (code, created_by, expires_at, max_uses, role_id)
                VALUES (?, ?, ?, ?, ?)
            """, (code, created_by, expires_at, max_uses, role_id))
            
            self._audit_log(conn, 'registration_code_created', None, created_by,
                          {'code': code[:8] + '...', 'max_uses': max_uses, 'role': role})
            
            logger.info(f"Created registration code {code[:8]}... with {max_uses} uses")
            return code
    
    def validate_registration_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Validate a registration code.
        
        Args:
            code: Registration code to validate
            
        Returns:
            Dict with code info if valid, None if invalid
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            SELECT rc.*, r.name as role_name
            FROM registration_codes rc
            LEFT JOIN roles r ON rc.role_id = r.id
            WHERE rc.code = ? 
            AND rc.is_active = 1
            AND rc.expires_at > CURRENT_TIMESTAMP
            AND rc.times_used < rc.max_uses
        """, (code,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def use_registration_code(self, code: str, user_id: int, ip_address: Optional[str] = None,
                             user_agent: Optional[str] = None) -> bool:
        """
        Mark a registration code as used.
        
        Args:
            code: Registration code
            user_id: User ID who used the code
            ip_address: IP address of registration
            user_agent: User agent string
            
        Returns:
            bool: True if code was successfully used
        """
        with self.transaction() as conn:
            # Get code info
            cursor = conn.execute("""
                SELECT id, times_used FROM registration_codes
                WHERE code = ? AND is_active = 1
            """, (code,))
            
            row = cursor.fetchone()
            if not row:
                return False
            
            code_id = row['id']
            
            # Update usage count
            conn.execute("""
                UPDATE registration_codes 
                SET times_used = times_used + 1
                WHERE id = ?
            """, (code_id,))
            
            # Record usage
            conn.execute("""
                INSERT INTO registration_code_usage (code_id, user_id, ip_address, user_agent)
                VALUES (?, ?, ?, ?)
            """, (code_id, user_id, ip_address, user_agent))
            
            self._audit_log(conn, 'registration_code_used', user_id, None,
                          {'code': code[:8] + '...', 'ip': ip_address})
            
            return True
    
    ########################################################################################################################
    # Authentication Methods
    ########################################################################################################################
    
    def record_login(self, user_id: int, ip_address: Optional[str] = None,
                    user_agent: Optional[str] = None) -> bool:
        """
        Record a successful login.
        
        Args:
            user_id: User ID
            ip_address: IP address of login
            user_agent: User agent string
            
        Returns:
            bool: True if recorded successfully
        """
        with self.transaction() as conn:
            conn.execute("""
                UPDATE users 
                SET last_login = CURRENT_TIMESTAMP,
                    failed_login_attempts = 0,
                    locked_until = NULL
                WHERE id = ?
            """, (user_id,))
            
            self._audit_log(conn, 'login_success', user_id, None,
                          {'ip': ip_address, 'user_agent': user_agent})
            return True
    
    def record_failed_login(self, username: str, ip_address: Optional[str] = None) -> int:
        """
        Record a failed login attempt.
        
        Args:
            username: Username that failed to login
            ip_address: IP address of attempt
            
        Returns:
            int: Number of failed attempts
        """
        with self.transaction() as conn:
            cursor = conn.execute("""
                UPDATE users 
                SET failed_login_attempts = failed_login_attempts + 1
                WHERE username = ?
                RETURNING failed_login_attempts, id
            """, (username,))
            
            row = cursor.fetchone()
            if row:
                attempts = row['failed_login_attempts']
                user_id = row['id']
                
                # Lock account after 5 attempts
                if attempts >= 5:
                    lock_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                    conn.execute("""
                        UPDATE users SET locked_until = ? WHERE id = ?
                    """, (lock_until, user_id))
                
                self._audit_log(conn, 'login_failed', None, None,
                              {'username': username, 'ip': ip_address, 'attempts': attempts})
                
                return attempts
            return 0
    
    def is_account_locked(self, user_id: int) -> bool:
        """
        Check if user account is locked.
        
        Args:
            user_id: User ID
            
        Returns:
            bool: True if account is locked
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            SELECT locked_until FROM users 
            WHERE id = ? AND locked_until > CURRENT_TIMESTAMP
        """, (user_id,))
        
        return cursor.fetchone() is not None
    
    ########################################################################################################################
    # Helper Methods
    ########################################################################################################################
    
    def _get_role_id(self, role_name: str) -> Optional[int]:
        """Get role ID by name."""
        conn = self.get_connection()
        cursor = conn.execute("SELECT id FROM roles WHERE name = ?", (role_name,))
        row = cursor.fetchone()
        return row['id'] if row else None
    
    def _audit_log(self, conn: sqlite3.Connection, event_type: str, 
                  user_id: Optional[int], target_user_id: Optional[int],
                  details: Optional[Dict[str, Any]] = None):
        """
        Create an audit log entry.
        
        Args:
            conn: Database connection
            event_type: Type of event
            user_id: User performing action
            target_user_id: User being acted upon
            details: Additional event details
        """
        try:
            conn.execute("""
                INSERT INTO auth_audit_log (event_type, user_id, target_user_id, details)
                VALUES (?, ?, ?, ?)
            """, (event_type, user_id, target_user_id, 
                 json.dumps(details) if details else None))
        except sqlite3.Error as e:
            logger.error(f"Failed to create audit log: {e}")
    
    ########################################################################################################################
    # Session and Token Management
    ########################################################################################################################
    
    def create_session(self, user_id: int, expires_in_hours: int = 24,
                      ip_address: Optional[str] = None,
                      user_agent: Optional[str] = None) -> str:
        """
        Create a new user session.
        
        Args:
            user_id: User ID
            expires_in_hours: Hours until session expires
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            str: Session ID/token
        """
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
        
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO user_sessions (id, user_id, expires_at, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, user_id, expires_at, ip_address, user_agent))
            
            return session_id
    
    def validate_session(self, session_id: str) -> Optional[int]:
        """
        Validate a session and return user ID if valid.
        
        Args:
            session_id: Session ID to validate
            
        Returns:
            User ID if session is valid, None otherwise
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            SELECT user_id FROM user_sessions
            WHERE id = ? AND is_active = 1 AND expires_at > CURRENT_TIMESTAMP
        """, (session_id,))
        
        row = cursor.fetchone()
        
        if row:
            # Update last activity
            conn.execute("""
                UPDATE user_sessions SET last_activity = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (session_id,))
            conn.commit()
            
            return row['user_id']
        return None
    
    def invalidate_session(self, session_id: str) -> bool:
        """
        Invalidate a session.
        
        Args:
            session_id: Session ID to invalidate
            
        Returns:
            bool: True if session was invalidated
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            UPDATE user_sessions SET is_active = 0
            WHERE id = ?
        """, (session_id,))
        conn.commit()
        
        return cursor.rowcount > 0
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.
        
        Returns:
            int: Number of sessions cleaned up
        """
        conn = self.get_connection()
        cursor = conn.execute("""
            DELETE FROM user_sessions
            WHERE expires_at < CURRENT_TIMESTAMP
        """)
        conn.commit()
        
        count = cursor.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} expired sessions")
        
        return count

#
# End of UserDatabase.py
########################################################################################################################