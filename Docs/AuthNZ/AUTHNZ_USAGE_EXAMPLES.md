# AuthNZ System Usage Examples

This document provides practical examples of using the AuthNZ system with both SQLite and PostgreSQL backends.

## Table of Contents
- [Configuration](#configuration)
- [User Management](#user-management)
- [Roles and Permissions](#roles-and-permissions)
- [API Endpoint Protection](#api-endpoint-protection)
- [Registration Codes](#registration-codes)
- [Testing Both Backends](#testing-both-backends)

## Configuration

### SQLite (Default/Development)

```python
# No configuration needed - SQLite is the default
# Or explicitly set:
import os
os.environ["TLDW_USER_DB_BACKEND"] = "sqlite"
os.environ["DATABASE_URL"] = "sqlite:///../Databases/Users.db"

from tldw_Server_API.app.core.AuthNZ.db_config import get_configured_user_database

# Get database instance
user_db = get_configured_user_database()
```

### PostgreSQL (Production)

```python
import os
os.environ["TLDW_USER_DB_BACKEND"] = "postgresql"
os.environ["DATABASE_URL"] = "postgresql://tldw_user:password@localhost:5432/tldw_users"
os.environ["TLDW_DB_POOL_SIZE"] = "20"

from tldw_Server_API.app.core.AuthNZ.db_config import get_configured_user_database

# Get database instance
user_db = get_configured_user_database()
```

## User Management

### Creating a User

```python
from tldw_Server_API.app.core.AuthNZ.db_config import get_configured_user_database
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService

# Initialize services
user_db = get_configured_user_database()
password_service = PasswordService()

# Create a new user
password_hash = password_service.hash_password("SecurePassword123!")
user_id = user_db.create_user(
    username="john_doe",
    email="john@example.com",
    password_hash=password_hash,
    role="user"  # Default role
)

print(f"Created user with ID: {user_id}")
```

### Authenticating a User

```python
# Verify password
user = user_db.get_user(username="john_doe")
if user and password_service.verify_password("SecurePassword123!", user['password_hash']):
    # Record successful login
    user_db.record_login(user['id'], ip_address="192.168.1.1", user_agent="Mozilla/5.0")
    print("Login successful!")
else:
    # Record failed attempt
    attempts = user_db.record_failed_login("john_doe", ip_address="192.168.1.1")
    print(f"Login failed. Attempts: {attempts}")
```

## Roles and Permissions

### Available Default Roles

```python
# The system includes 4 default roles:
# - admin: Full system access
# - user: Standard user permissions
# - viewer: Read-only access
# - custom: No default permissions (must be configured)
```

### Assigning Roles to Users

```python
# Assign admin role to a user
user_db.assign_role(user_id, "admin")

# Assign multiple roles
user_db.assign_role(user_id, "user")
user_db.assign_role(user_id, "custom")

# Check user's roles
roles = user_db.get_user_roles(user_id)
print(f"User roles: {roles}")  # ['admin', 'user', 'custom']

# Check user's permissions
permissions = user_db.get_user_permissions(user_id)
print(f"User has {len(permissions)} permissions")
```

### Creating Custom Roles

```python
# Create a new role
role_id = user_db.create_role(
    name="moderator",
    description="Content moderation permissions"
)

# Add permissions to the role
user_db.grant_permission_to_role(role_id, "media.update")
user_db.grant_permission_to_role(role_id, "media.delete")
user_db.grant_permission_to_role(role_id, "users.read")

# Assign the custom role to a user
user_db.assign_role(user_id, "moderator")
```

## API Endpoint Protection

### Using Permission Decorators

```python
from fastapi import APIRouter, Depends
from tldw_Server_API.app.core.AuthNZ.permissions import (
    PermissionChecker,
    RoleChecker,
    AnyPermissionChecker,
    AllPermissionsChecker
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User

router = APIRouter()

# Require specific permission
@router.get("/api/v1/media/{media_id}")
async def get_media(
    media_id: int,
    user: User = Depends(PermissionChecker("media.read"))
):
    return {"message": f"User {user.username} can read media {media_id}"}

# Require specific role
@router.delete("/api/v1/admin/user/{user_id}")
async def delete_user(
    user_id: int,
    user: User = Depends(RoleChecker("admin"))
):
    return {"message": f"Admin {user.username} deleting user {user_id}"}

# Require any of multiple permissions
@router.put("/api/v1/content/{content_id}")
async def update_content(
    content_id: int,
    user: User = Depends(AnyPermissionChecker(["media.update", "media.create"]))
):
    return {"message": f"User {user.username} can modify content"}

# Require all permissions
@router.post("/api/v1/system/backup")
async def create_backup(
    user: User = Depends(AllPermissionsChecker(["system.backup", "system.maintenance"]))
):
    return {"message": "Creating system backup"}
```

### Using in Non-FastAPI Code

```python
from tldw_Server_API.app.core.AuthNZ.permissions import (
    check_permission,
    check_role,
    require_permission,
    require_role
)

# Check permission manually
def process_media(user: User, media_id: int):
    if not check_permission(user, "media.transcribe"):
        raise PermissionError("User lacks transcription permission")

    # Process the media
    print(f"Processing media {media_id} for user {user.username}")

# Using decorators
@require_permission("system.configure")
def update_system_config(user: User, config: dict):
    # Only users with system.configure permission can call this
    print(f"Updating system configuration")

@require_role("admin")
def admin_only_function(user: User):
    # Only admins can call this
    print(f"Admin function executed by {user.username}")
```

## Registration Codes

### Creating Registration Codes

```python
# Create a registration code for inviting new users
code = user_db.create_registration_code(
    created_by=admin_user_id,
    expires_in_days=7,
    max_uses=5,
    role="user"  # Role to assign to users who use this code
)

print(f"Registration code: {code}")
# Share this code with users you want to invite
```

### Using Registration Codes

```python
# During user registration
def register_user_with_code(username: str, email: str, password: str, reg_code: str):
    # Validate the registration code
    code_info = user_db.validate_registration_code(reg_code)

    if not code_info:
        raise ValueError("Invalid or expired registration code")

    # Create the user
    password_hash = password_service.hash_password(password)
    user_id = user_db.create_user(
        username=username,
        email=email,
        password_hash=password_hash,
        role=code_info['role_name']  # Assign role from code
    )

    # Mark the code as used
    user_db.use_registration_code(
        reg_code,
        user_id,
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0"
    )

    return user_id
```

## Testing Both Backends

### Running the Test Suite

```bash
# Test SQLite backend only
python tldw_Server_API/tests/test_authnz_backends.py --backend sqlite

# Test PostgreSQL backend only
python tldw_Server_API/tests/test_authnz_backends.py --backend postgresql

# Test both backends
python tldw_Server_API/tests/test_authnz_backends.py --backend both

# Test with verbose output
python tldw_Server_API/tests/test_authnz_backends.py --backend both --verbose

# Test configuration detection
python tldw_Server_API/tests/test_authnz_backends.py --config-test
```

### Writing Tests for Your Code

```python
import pytest
from tldw_Server_API.app.core.AuthNZ.db_config import get_configured_user_database
from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig, BackendType

@pytest.fixture
def sqlite_db():
    """Fixture for SQLite database"""
    config = DatabaseConfig(
        backend_type=BackendType.SQLITE,
        sqlite_path=":memory:",  # In-memory for tests
        sqlite_wal_mode=True
    )
    from tldw_Server_API.app.core.DB_Management.UserDatabase_v2 import UserDatabase
    return UserDatabase(config=config, client_id="test")

@pytest.fixture
def postgresql_db():
    """Fixture for PostgreSQL database"""
    config = DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        connection_string="postgresql://test:test@localhost/test_db"
    )
    from tldw_Server_API.app.core.DB_Management.UserDatabase_v2 import UserDatabase
    return UserDatabase(config=config, client_id="test")

def test_user_creation(sqlite_db):
    """Test user creation with SQLite"""
    user_id = sqlite_db.create_user(
        username="test_user",
        email="test@example.com",
        password_hash="hashed_password"
    )
    assert user_id is not None

    user = sqlite_db.get_user(user_id=user_id)
    assert user['username'] == "test_user"
```

## Migration Between Backends

### Migrating from SQLite to PostgreSQL

```python
from tldw_Server_API.app.core.DB_Management.UserDatabase_v2 import UserDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseConfig, BackendType

# Source database (SQLite)
sqlite_config = DatabaseConfig(
    backend_type=BackendType.SQLITE,
    sqlite_path="../Databases/Users.db"
)
sqlite_db = UserDatabase(config=sqlite_config, client_id="migration")

# Target database (PostgreSQL)
pg_config = DatabaseConfig(
    backend_type=BackendType.POSTGRESQL,
    connection_string="postgresql://user:pass@localhost/tldw_users"
)
pg_db = UserDatabase(config=pg_config, client_id="migration")

# Export users from SQLite
users = []
with sqlite_db.backend.transaction() as conn:
    result = sqlite_db.backend.execute("SELECT * FROM users")
    users = result.fetchall()

# Import users to PostgreSQL
for user in users:
    # Recreate user in PostgreSQL
    # (Handle with care - this is a simplified example)
    pg_db.create_user(
        username=user['username'],
        email=user['email'],
        password_hash=user['password_hash'],
        role="user"
    )
```

## Environment Variable Reference

### Common Variables
```bash
# Backend selection
export TLDW_USER_DB_BACKEND=postgresql  # or "sqlite"

# Database URL
export DATABASE_URL=postgresql://user:password@localhost:5432/tldw_users

# Enable SQL logging
export TLDW_DB_ECHO=true
```

### SQLite-Specific
```bash
# Enable Write-Ahead Logging (better concurrency)
export TLDW_SQLITE_WAL_MODE=true

# Enable foreign key constraints
export TLDW_SQLITE_FOREIGN_KEYS=true
```

### PostgreSQL-Specific
```bash
# Connection pool settings
export TLDW_DB_POOL_SIZE=20
export TLDW_DB_MAX_OVERFLOW=40
export TLDW_DB_POOL_TIMEOUT=30
export TLDW_DB_POOL_RECYCLE=3600

# SSL mode
export TLDW_PG_SSLMODE=require  # or "prefer", "disable"
```

## Troubleshooting

### Common Issues

1. **"Database backend not detected"**
   ```python
   # Explicitly set backend
   os.environ["TLDW_USER_DB_BACKEND"] = "postgresql"
   ```

2. **"Connection refused" (PostgreSQL)**
   ```bash
   # Check PostgreSQL is running
   sudo systemctl status postgresql

   # Test connection
   psql -U tldw_user -d tldw_users -h localhost
   ```

3. **"Database is locked" (SQLite)**
   ```python
   # Enable WAL mode for better concurrency
   os.environ["TLDW_SQLITE_WAL_MODE"] = "true"
   ```

4. **Permission denied errors**
   ```python
   # Check user permissions
   from tldw_Server_API.app.core.AuthNZ.db_config import get_configured_user_database

   user_db = get_configured_user_database()
   permissions = user_db.get_user_permissions(user_id)
   print(f"User permissions: {permissions}")

   # Check if specific permission exists
   has_perm = user_db.has_permission(user_id, "media.read")
   print(f"Has media.read: {has_perm}")
   ```

### Debug Mode

Enable detailed logging:

```python
import os
os.environ["TLDW_DB_ECHO"] = "true"

from loguru import logger
logger.add("authnz_debug.log", level="DEBUG")

# Now all SQL queries and operations will be logged
```

## Best Practices

1. **Always use the centralized configuration**:
   ```python
   # Good
   from tldw_Server_API.app.core.AuthNZ.db_config import get_configured_user_database
   user_db = get_configured_user_database()

   # Avoid
   from tldw_Server_API.app.core.DB_Management.UserDatabase_v2 import UserDatabase
   user_db = UserDatabase(...)  # Manual configuration
   ```

2. **Use permission constants**:
   ```python
   from tldw_Server_API.app.core.AuthNZ.permissions import (
       MEDIA_READ, MEDIA_CREATE, USERS_MANAGE_ROLES
   )

   # Use constants instead of strings
   if check_permission(user, MEDIA_READ):
       # ...
   ```

3. **Handle database transactions properly**:
   ```python
   # Always use context managers for transactions
   with user_db.backend.transaction() as conn:
       # Multiple operations in a single transaction
       user_db.create_user(...)
       user_db.assign_role(...)
   ```

4. **Validate registration codes before use**:
   ```python
   # Always validate before using
   code_info = user_db.validate_registration_code(code)
   if not code_info:
       raise ValueError("Invalid code")
   if code_info['times_used'] >= code_info['max_uses']:
       raise ValueError("Code has been used too many times")
   ```

---

For more information, see:
- [Database Configuration Guide](AUTHNZ_DATABASE_CONFIG.md)
- [API Documentation](/docs)
- [Test Suite](tldw_Server_API/tests/test_authnz_backends.py)
