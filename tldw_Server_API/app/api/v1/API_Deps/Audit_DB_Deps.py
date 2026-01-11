"""
Manages user-specific audit service instances for dependency injection.
"""

import asyncio
import threading
import weakref
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Set, Union

from fastapi import Depends, HTTPException, status
from loguru import logger

try:
    from cachetools import Cache, LRUCache

    _HAS_CACHETOOLS = True
except ImportError:
    _HAS_CACHETOOLS = False
    logger.warning(
        "cachetools not found. Using bounded fallback LRU. Install with: pip install cachetools"
    )

# Local Imports
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Audit.unified_audit_service import UnifiedAuditService
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.exceptions import (
    ServiceInitializationError,
    ServiceInitializationTimeoutError,
)

#######################################################################################################################

_TRUTHY = {"1", "true", "yes", "y", "on"}
_FALSEY = {"0", "false", "no", "n", "off"}


def _settings_int(
    key: str,
    default: int,
    *,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> int:
    """Coerce a potentially loosely-typed settings value to int with clamping."""
    raw = settings.get(key, default)
    try:
        if isinstance(raw, bool):
            raise TypeError("bool is not a valid int setting")
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning(f"Invalid {key}={raw!r}; using default {default}")
        value = default
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value


def _settings_float(
    key: str,
    default: float,
    *,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> float:
    """Coerce a potentially loosely-typed settings value to float with clamping."""
    raw = settings.get(key, default)
    try:
        if isinstance(raw, bool):
            raise TypeError("bool is not a valid float setting")
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning(f"Invalid {key}={raw!r}; using default {default}")
        value = default
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value


def _settings_bool(key: str, default: bool) -> bool:
    """Coerce a settings value to bool, accepting common string representations."""
    raw = settings.get(key, default)
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    s = str(raw).strip().lower()
    if s in _TRUTHY:
        return True
    if s in _FALSEY:
        return False
    logger.warning(f"Invalid {key}={raw!r}; using default {default}")
    return default


def _schedule_service_stop(user_id: Optional[int], service: UnifiedAuditService, reason: str) -> None:
    """Schedule graceful shutdown of an audit service instance."""
    if service is None:
        return

    if getattr(service, "_tldw_stop_scheduled", False):
        return

    service._tldw_stop_scheduled = True  # type: ignore[attr-defined]
    service_key = id(service)

    with _services_stopping_lock:
        if service_key in _services_stopping:
            return
        _services_stopping.add(service_key)

    def _clear_stopping_flag():
        """Clear the stopping flag after service is stopped."""
        with _services_stopping_lock:
            _services_stopping.discard(service_key)

    async def _stop():
        try:
            await service.stop()
            logger.info(f"Audit service for user {user_id} stopped ({reason}).")
        except Exception as exc:
            logger.error(
                f"Failed to stop audit service for user {user_id} ({reason}): {exc}",
                exc_info=True,
            )
        finally:
            _clear_stopping_flag()

    owner_loop = getattr(service, "owner_loop", None)
    if owner_loop and owner_loop.is_closed():
        owner_loop = None

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if owner_loop and owner_loop is not current_loop:
        future = asyncio.run_coroutine_threadsafe(_stop(), owner_loop)

        def _log_result(fut):
            exc = fut.exception()
            if exc:
                logger.error(
                    f"Failed to stop audit service for user {user_id} ({reason}): {exc}",
                    exc_info=True,
                )

        future.add_done_callback(_log_result)
        return

    if current_loop:
        current_loop.create_task(_stop())
        return

    def _run():
        try:
            asyncio.run(_stop())
        except Exception as e:
            logger.error(
                f"Audit service stop failed for user {user_id} in fallback thread: {type(e).__name__}: {e}"
            )

    threading.Thread(target=_run, name=f"audit-stop-{user_id}", daemon=True).start()


_services_stopping: Set[int] = set()
_services_stopping_lock = threading.Lock()  # Protects _services_stopping service-id set


def _handle_cache_eviction(user_id: Optional[int], service: UnifiedAuditService, reason: str) -> None:
    """Handle cache eviction/removal by scheduling a stop unless manually managed."""
    if service is None:
        return
    logger.debug(f"Evicting audit service for user {user_id} ({reason}).")
    _schedule_service_stop(user_id, service, reason)


class _SmallLRUCache:
    """Minimal LRU cache with eviction callback."""

    def __init__(
        self,
        maxsize: int,
        on_evict: Callable[[Optional[int], UnifiedAuditService, str], None],
    ):
        self.maxsize = maxsize
        self._on_evict = on_evict
        self._data: OrderedDict[Optional[int], UnifiedAuditService] = OrderedDict()

    def get(self, key: Optional[int]) -> Optional[UnifiedAuditService]:
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        return None

    def __setitem__(self, key: Optional[int], value: UnifiedAuditService) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self.maxsize:
            evicted_key, evicted_value = self._data.popitem(last=False)
            self._on_evict(evicted_key, evicted_value, "capacity")

    def pop(
        self,
        key: Optional[int],
        default: Optional[UnifiedAuditService] = None,
    ) -> Optional[UnifiedAuditService]:
        if key in self._data:
            value = self._data.pop(key)
            self._on_evict(key, value, "removed")
            return value
        return default

    def pop_no_callback(
        self,
        key: Optional[int],
        default: Optional[UnifiedAuditService] = None,
    ) -> Optional[UnifiedAuditService]:
        """Pop without triggering eviction callback (for manual shutdown)."""
        return self._data.pop(key, default)

    def keys(self):
        return list(self._data.keys())


if _HAS_CACHETOOLS:

    class _EvictingLRUCache(LRUCache):
        """LRUCache variant that fires a callback whenever items are removed."""

        _MISSING = object()

        def __init__(
            self,
            maxsize: int,
            on_evict: Callable[[Optional[int], UnifiedAuditService, str], None],
        ):
            super().__init__(maxsize=maxsize)
            self._on_evict = on_evict

        def popitem(self):
            key, value = super().popitem()
            self._on_evict(key, value, "capacity")
            return key, value

        def __delitem__(self, key):
            value = self[key]
            super().__delitem__(key)
            self._on_evict(key, value, "removed")

        def pop(self, key, default=_MISSING):
            if key in self:
                value = Cache.pop(self, key)
                self._on_evict(key, value, "removed")
                return value
            if default is self._MISSING:
                raise KeyError(key)
            return default

        def pop_no_callback(self, key, default=None):
            """Pop without triggering eviction callback (for manual shutdown)."""
            if key in self:
                return Cache.pop(self, key)
            return default


# --- Configuration ---
MAX_CACHED_AUDIT_INSTANCES = _settings_int("MAX_CACHED_AUDIT_INSTANCES", 20, min_value=1, max_value=1000)

_CACHE_IMPL = "cachetools.LRUCache" if _HAS_CACHETOOLS else "_SmallLRUCache"
logger.info(
    f"Using {_CACHE_IMPL} for audit service instances (maxsize={MAX_CACHED_AUDIT_INSTANCES})."
)


def _build_cache() -> Any:
    """Construct a cache instance for a single event loop."""
    if _HAS_CACHETOOLS:
        return _EvictingLRUCache(
            maxsize=MAX_CACHED_AUDIT_INSTANCES,
            on_evict=_handle_cache_eviction,
        )
    return _SmallLRUCache(
        MAX_CACHED_AUDIT_INSTANCES,
        on_evict=_handle_cache_eviction,
    )


@dataclass
class _LoopState:
    """Per-event-loop cache and initialization state."""
    cache: Any
    cache_lock: threading.Lock = field(default_factory=threading.Lock)
    init_lock: threading.Lock = field(default_factory=threading.Lock)
    initializing_users: Set[Optional[int]] = field(default_factory=set)
    initializing_events: Dict[Optional[int], asyncio.Event] = field(default_factory=dict)


_STATE_LOCK = threading.Lock()
_STATE_BY_LOOP: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, _LoopState]" = weakref.WeakKeyDictionary()


def _state_for_loop() -> _LoopState:
    """Return (or create) per-loop state for audit services."""
    loop = asyncio.get_running_loop()
    with _STATE_LOCK:
        state = _STATE_BY_LOOP.get(loop)
        if state is None:
            state = _LoopState(cache=_build_cache())
            _STATE_BY_LOOP[loop] = state
        return state


def _all_loop_states() -> list[_LoopState]:
    """Snapshot all known loop states."""
    with _STATE_LOCK:
        return list(_STATE_BY_LOOP.values())

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
        retention_days=_settings_int("AUDIT_RETENTION_DAYS", 30, min_value=1, max_value=3650),
        enable_pii_detection=_settings_bool("AUDIT_ENABLE_PII_DETECTION", True),
        enable_risk_scoring=_settings_bool("AUDIT_ENABLE_RISK_SCORING", True),
        buffer_size=_settings_int("AUDIT_BUFFER_SIZE", 100, min_value=1, max_value=100000),
        flush_interval=_settings_float("AUDIT_FLUSH_INTERVAL", 5.0, min_value=0.1, max_value=3600.0),
    )

    # Initialize the service (creates database, starts background tasks)
    await service.initialize()

    logger.info(f"Audit service initialized successfully for user {user_id}")
    return service


async def _create_default_audit_service() -> UnifiedAuditService:
    """Create a shared default audit service (no user-specific DB path)."""
    logger.info("Creating default audit service (shared).")
    service = UnifiedAuditService(
        db_path=None,
        retention_days=_settings_int("AUDIT_RETENTION_DAYS", 30, min_value=1, max_value=3650),
        enable_pii_detection=_settings_bool("AUDIT_ENABLE_PII_DETECTION", True),
        enable_risk_scoring=_settings_bool("AUDIT_ENABLE_RISK_SCORING", True),
        buffer_size=_settings_int("AUDIT_BUFFER_SIZE", 100, min_value=1, max_value=100000),
        flush_interval=_settings_float("AUDIT_FLUSH_INTERVAL", 5.0, min_value=0.1, max_value=3600.0),
    )
    await service.initialize()
    logger.info("Default audit service initialized successfully.")
    return service


async def _get_or_create_audit_service_for_key(user_id: Optional[int]) -> UnifiedAuditService:
    """Internal helper to get or create a cached audit service for a cache key."""
    state = _state_for_loop()
    service_instance: Optional[UnifiedAuditService] = None

    # Check cache
    with state.cache_lock:
        service_instance = state.cache.get(user_id)

    if service_instance:
        logger.debug(f"Using cached audit service instance for user_id: {user_id}")
        return service_instance

    key_label = "default" if user_id is None else f"user_id {user_id}"
    logger.info(f"No cached audit service found for {key_label}. Initializing.")

    init_timeout_s = _settings_float("AUDIT_INIT_TIMEOUT_SECONDS", 30.0, min_value=0.1, max_value=300.0)
    deadline = time.monotonic() + init_timeout_s

    # Check if another task is already initializing this service
    wait_event: Optional[asyncio.Event] = None
    should_initialize = False

    while True:
        with state.init_lock:
            if user_id in state.initializing_users:
                if user_id not in state.initializing_events:
                    state.initializing_events[user_id] = asyncio.Event()
                wait_event = state.initializing_events[user_id]
                should_initialize = False
            else:
                state.initializing_users.add(user_id)
                should_initialize = True
                wait_event = None

        if should_initialize:
            break

        if wait_event is None:
            msg = f"Missing wait event for audit service initialization (user {user_id})"
            logger.warning(msg)
            raise ServiceInitializationError(msg)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            msg = f"Timeout waiting for audit service initialization for user {user_id}"
            logger.warning(msg)
            raise ServiceInitializationTimeoutError(msg)

        try:
            await asyncio.wait_for(wait_event.wait(), timeout=remaining)
        except asyncio.TimeoutError as exc:
            msg = f"Timeout waiting for audit service initialization for user {user_id}"
            logger.warning(msg)
            raise ServiceInitializationTimeoutError(msg) from exc

        # Check cache again after waiting
        with state.cache_lock:
            service_instance = state.cache.get(user_id)
            if service_instance:
                return service_instance

    if should_initialize:
        try:
            # Double-check cache in case another request created it
            with state.cache_lock:
                service_instance = state.cache.get(user_id)
                if service_instance:
                    logger.debug(f"Audit service for user {user_id} created concurrently.")
                    return service_instance

            if user_id is None:
                service_instance = await _create_default_audit_service()
            else:
                service_instance = await _create_audit_service_for_user(user_id)

            # Store in cache
            with state.cache_lock:
                state.cache[user_id] = service_instance

            logger.info(f"Audit service created and cached successfully for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to initialize audit service for user {user_id}: {e}", exc_info=True)
            raise
        finally:
            # Clean up initialization tracking and signal waiters
            with state.init_lock:
                state.initializing_users.discard(user_id)
                event = state.initializing_events.pop(user_id, None)
                if event:
                    event.set()

    if service_instance is None:
        # Defensive: should not happen, but avoid returning None.
        raise ServiceInitializationError(f"Could not initialize audit service for user {user_id}")

    return service_instance


async def get_or_create_audit_service_for_user_id(user_id: int) -> UnifiedAuditService:
    """Get (or create) a cached UnifiedAuditService for a concrete user_id.

    This is the core implementation behind the FastAPI dependency
    `get_audit_service_for_user`, but is also usable from non-DI code paths
    where you already have a user id (e.g., post-authentication flows).
    """
    if not isinstance(user_id, int):
        raise TypeError("user_id must be an int")
    return await _get_or_create_audit_service_for_key(user_id)


async def get_or_create_default_audit_service() -> UnifiedAuditService:
    """Return a shared default audit service (used when no user_id is available)."""
    return await _get_or_create_audit_service_for_key(None)


async def get_or_create_audit_service_for_user_id_optional(
    user_id: Optional[Union[int, str]]
) -> UnifiedAuditService:
    """Get an audit service for a user id or fall back to the default service."""
    if user_id is None:
        return await get_or_create_default_audit_service()
    try:
        uid_int = int(user_id)
    except Exception:
        logger.debug(f"Invalid user_id {user_id!r}; using default audit service")
        return await get_or_create_default_audit_service()
    return await get_or_create_audit_service_for_user_id(uid_int)

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
    try:
        return await get_or_create_audit_service_for_user_id(user_id)
    except Exception as e:
        logger.error(
            "Failed to initialize audit service for user {}: {}",
            user_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not initialize audit service.",
        ) from e

# --- Cleanup Functions ---

async def shutdown_user_audit_service(user_id: int):
    """
    Shutdown audit service for a specific user.

    Args:
        user_id: The user's ID
    """
    services: list[UnifiedAuditService] = []

    for state in _all_loop_states():
        with state.cache_lock:
            existing = state.cache.get(user_id)
            if existing:
                pop_no_cb = getattr(state.cache, "pop_no_callback", None)
                if callable(pop_no_cb):
                    service = pop_no_cb(user_id, None)
                else:
                    service = state.cache.pop(user_id, None)
                if service:
                    services.append(service)

        with state.init_lock:
            state.initializing_users.discard(user_id)
            event = state.initializing_events.pop(user_id, None)
            if event:
                event.set()

    if not services:
        return

    async def _stop_service(service: UnifiedAuditService) -> None:
        owner_loop = getattr(service, "owner_loop", None)
        if owner_loop and owner_loop.is_closed():
            owner_loop = None

        try:
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            if owner_loop and current_loop is not owner_loop:
                future = asyncio.run_coroutine_threadsafe(service.stop(), owner_loop)
                await asyncio.wrap_future(future)
            else:
                await service.stop()
            logger.info(f"Shut down audit service for user {user_id}")
        except Exception as e:
            logger.error(
                f"Error shutting down audit service for user {user_id}: {e}",
                exc_info=True,
            )

    await asyncio.gather(*[_stop_service(s) for s in services], return_exceptions=True)

async def shutdown_all_audit_services():
    """
    Shutdown all cached audit service instances.
    Useful for application shutdown.
    """
    services: list[UnifiedAuditService] = []
    total_instances = 0

    for state in _all_loop_states():
        with state.cache_lock:
            keys = list(state.cache.keys())
            total_instances += len(keys)
            for key in keys:
                pop_no_cb = getattr(state.cache, "pop_no_callback", None)
                if callable(pop_no_cb):
                    service = pop_no_cb(key, None)
                else:
                    service = state.cache.pop(key, None)
                if service:
                    services.append(service)

        with state.init_lock:
            for event in state.initializing_events.values():
                event.set()
            state.initializing_events.clear()
            state.initializing_users.clear()

    logger.info(f"Shutting down audit services for {total_instances} instances...")

    async def _stop_service(service: UnifiedAuditService) -> None:
        owner_loop = getattr(service, "owner_loop", None)
        if owner_loop and owner_loop.is_closed():
            owner_loop = None

        try:
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            if owner_loop and current_loop is not owner_loop:
                future = asyncio.run_coroutine_threadsafe(service.stop(), owner_loop)
                await asyncio.wrap_future(future)
            else:
                await service.stop()
        except Exception as e:
            logger.error(f"Error shutting down audit service: {e}", exc_info=True)

    if services:
        await asyncio.gather(*[_stop_service(s) for s in services], return_exceptions=True)

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
