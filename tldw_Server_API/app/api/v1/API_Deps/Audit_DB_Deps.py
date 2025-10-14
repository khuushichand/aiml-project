# Audit_DB_Deps.py
"""
Manages user-specific audit service instances for dependency injection.
"""

import asyncio
import threading
from pathlib import Path
from typing import Optional, Any
from collections import OrderedDict

from fastapi import Depends, HTTPException, status
from loguru import logger
try:
    from cachetools import LRUCache
    _HAS_CACHETOOLS = True
except ImportError:
    _HAS_CACHETOOLS = False
    logger.warning("cachetools not found. Using bounded fallback LRU. Install with: pip install cachetools")

# Local Imports
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.Audit.unified_audit_service import UnifiedAuditService
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

#######################################################################################################################

class _SmallLRUCache:
    def __init__(self, maxsize: int):
        self.maxsize = maxsize
        self._data: OrderedDict[int, UnifiedAuditService] = OrderedDict()

    def get(self, key: int) -> Optional[UnifiedAuditService]:
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        return None

    def __setitem__(self, key: int, value: UnifiedAuditService) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self.maxsize:
            self._data.popitem(last=False)

    def pop(self, key: int, default: Optional[UnifiedAuditService] = None) -> Optional[UnifiedAuditService]:
        return self._data.pop(key, default) if key in self._data else default

    def keys(self):
        return list(self._data.keys())


# --- Configuration ---
MAX_CACHED_AUDIT_INSTANCES = settings.get("MAX_CACHED_AUDIT_INSTANCES", 20)

if _HAS_CACHETOOLS:
    # Keyed by user ID (int)
    _user_audit_instances: Any = LRUCache(maxsize=MAX_CACHED_AUDIT_INSTANCES)
    logger.info(f"Using cachetools.LRUCache for audit service instances (maxsize={MAX_CACHED_AUDIT_INSTANCES}).")
else:
    # Keyed by user ID (int)
    _user_audit_instances: Any = _SmallLRUCache(MAX_CACHED_AUDIT_INSTANCES)
    logger.info(f"Using fallback _SmallLRUCache for audit service instances (maxsize={MAX_CACHED_AUDIT_INSTANCES}).")

_audit_service_lock = threading.Lock()
_service_initialization_lock = asyncio.Lock()

#######################################################################################################################

# --- Helper Functions ---

async def _create_audit_service_for_user(user_id: int) -> UnifiedAuditService:
    """
    Create a new audit service instance for a specific user.
    
    Args:
        user_id: The user's ID
        
    Returns:
        Initialized UnifiedAuditService instance
    """
    # Get the user-specific audit database path
    db_path = DatabasePaths.get_audit_db_path(user_id)
    
    logger.info(f"Creating audit service for user {user_id} at path: {db_path}")
    
    # Create the service with user-specific database
    service = UnifiedAuditService(
        db_path=str(db_path),
        retention_days=settings.get("AUDIT_RETENTION_DAYS", 30),
        enable_pii_detection=settings.get("AUDIT_ENABLE_PII_DETECTION", True),
        enable_risk_scoring=settings.get("AUDIT_ENABLE_RISK_SCORING", True),
        buffer_size=settings.get("AUDIT_BUFFER_SIZE", 100),
        flush_interval=settings.get("AUDIT_FLUSH_INTERVAL", 5.0)
    )
    
    # Initialize the service (creates database, starts background tasks)
    await service.initialize()
    
    logger.info(f"Audit service initialized successfully for user {user_id}")
    return service

# --- Main Dependency Function ---

async def get_audit_service_for_user(
    current_user: User = Depends(get_request_user)
) -> UnifiedAuditService:
    """
    FastAPI dependency to get the UnifiedAuditService instance for the identified user.
    
    Handles caching, initialization, and lifecycle management.
    Uses configuration values from the 'settings' dictionary.
    
    Args:
        current_user: The User object provided by `get_request_user`.
        
    Returns:
        A UnifiedAuditService instance for the user.
        
    Raises:
        HTTPException: If the service cannot be initialized.
    """
    if not current_user or not isinstance(current_user.id, int):
        logger.error("get_audit_service_for_user called without a valid User object/ID.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="User identification failed for audit service."
        )
    
    user_id = current_user.id
    service_instance: Optional[UnifiedAuditService] = None
    
    # Check cache
    with _audit_service_lock:
        service_instance = _user_audit_instances.get(user_id)
    
    if service_instance:
        # Verify the service is still healthy
        # The UnifiedAuditService should handle its own health checks
        logger.debug(f"Using cached audit service instance for user_id: {user_id}")
        return service_instance
    
    # Instance not cached or unhealthy: create new one
    logger.info(f"No cached audit service found for user_id: {user_id}. Initializing.")
    
    # Use async lock for initialization to prevent concurrent creation
    async with _service_initialization_lock:
        # Double-check cache in case another request created it
        with _audit_service_lock:
            service_instance = _user_audit_instances.get(user_id)
            if service_instance:
                logger.debug(f"Audit service for user {user_id} created concurrently.")
                return service_instance
        
        try:
            # Create and initialize the service
            service_instance = await _create_audit_service_for_user(user_id)
            
            # Store in cache
            with _audit_service_lock:
                _user_audit_instances[user_id] = service_instance
            
            logger.info(f"Audit service created and cached successfully for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize audit service for user {user_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Could not initialize audit service: {str(e)}"
            ) from e
    
    return service_instance

# --- Cleanup Functions ---

async def shutdown_user_audit_service(user_id: int):
    """
    Shutdown audit service for a specific user.
    
    Args:
        user_id: The user's ID
    """
    with _audit_service_lock:
        service = _user_audit_instances.pop(user_id, None)
    
    if service:
        try:
            # UnifiedAuditService exposes stop(), not shutdown()
            await service.stop()
            logger.info(f"Shut down audit service for user {user_id}")
        except Exception as e:
            logger.error(f"Error shutting down audit service for user {user_id}: {e}", exc_info=True)

async def shutdown_all_audit_services():
    """
    Shutdown all cached audit service instances.
    Useful for application shutdown.
    """
    with _audit_service_lock:
        user_ids = list(_user_audit_instances.keys())
        logger.info(f"Shutting down audit services for {len(user_ids)} users...")
    
    for user_id in user_ids:
        await shutdown_user_audit_service(user_id)
    
    logger.info("All audit services shut down successfully.")

# Example of how to register for shutdown event in FastAPI:
# from fastapi import FastAPI
# app = FastAPI()
# @app.on_event("shutdown")
# async def shutdown_event():
#     await shutdown_all_audit_services()

#
# End of Audit_DB_Deps.py
########################################################################################################################
