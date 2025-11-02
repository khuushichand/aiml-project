# tts_resource_manager.py
# Description: Resource management for TTS operations including connection pooling, memory management, and cleanup
#
# Imports
import asyncio
import gc
import psutil
import time
import weakref
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional, AsyncGenerator, Set, Callable, TYPE_CHECKING
import threading
from dataclasses import dataclass, field
from enum import Enum
#
# Third-party Imports
import httpx
from loguru import logger
#
# Local Imports
from .tts_exceptions import (
    TTSResourceError,
    TTSInsufficientMemoryError,
    TTSInsufficientStorageError,
    TTSModelLoadError,
    TTSNetworkError
)
#
# Conditional imports for type checking
if TYPE_CHECKING:
    from .adapters.base import TTSAdapter
#
#######################################################################################################################
#
# Resource Management System

class ResourceType(Enum):
    """Types of resources managed by the system"""
    HTTP_CONNECTION = "http_connection"
    MODEL_INSTANCE = "model_instance"
    STREAMING_SESSION = "streaming_session"
    TEMP_FILE = "temp_file"
    MEMORY_BUFFER = "memory_buffer"


@dataclass
class ResourceMetrics:
    """Metrics for resource usage tracking"""
    created_at: float
    last_used: float
    use_count: int = 0
    memory_usage: int = 0  # bytes
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_usage(self):
        """Update usage statistics"""
        self.last_used = time.time()
        self.use_count += 1


class StreamingSession:
    """Manages a streaming TTS session with proper cleanup"""

    def __init__(
        self,
        session_id: str,
        provider: str,
        cleanup_callback: Optional[Callable] = None
    ):
        """
        Initialize streaming session.

        Args:
            session_id: Unique session identifier
            provider: TTS provider name
            cleanup_callback: Optional cleanup function
        """
        self.session_id = session_id
        self.provider = provider
        self.cleanup_callback = cleanup_callback
        self.created_at = time.time()
        self.last_activity = time.time()
        self.is_active = True
        self.chunks_sent = 0
        self.bytes_sent = 0
        self.error_count = 0
        self._cleanup_tasks: Set[asyncio.Task] = set()

    # Backward-compat properties used by tests
    @property
    def bytes_streamed(self) -> int:
        return self.bytes_sent

    @bytes_streamed.setter
    def bytes_streamed(self, value: int) -> None:
        self.bytes_sent = value

    @property
    def start_time(self) -> float:
        return self.created_at

    @start_time.setter
    def start_time(self, value: float) -> None:
        self.created_at = value

    async def track_activity(self, chunk_size: int = 0):
        """Track session activity"""
        self.last_activity = time.time()
        if chunk_size > 0:
            self.chunks_sent += 1
            self.bytes_sent += chunk_size

    async def add_cleanup_task(self, coro):
        """Add cleanup task to be executed when session closes"""
        task = asyncio.create_task(coro)
        self._cleanup_tasks.add(task)
        task.add_done_callback(self._cleanup_tasks.discard)

    async def close(self):
        """Close the streaming session and cleanup resources"""
        if not self.is_active:
            return

        self.is_active = False

        try:
            # Execute cleanup callback
            if self.cleanup_callback:
                if asyncio.iscoroutinefunction(self.cleanup_callback):
                    await self.cleanup_callback()
                else:
                    self.cleanup_callback()

            # Wait for cleanup tasks
            if self._cleanup_tasks:
                await asyncio.gather(*self._cleanup_tasks, return_exceptions=True)

            logger.debug(
                f"Streaming session {self.session_id} closed: "
                f"chunks={self.chunks_sent}, bytes={self.bytes_sent}, "
                f"duration={time.time() - self.created_at:.2f}s"
            )

        except Exception as e:
            logger.error(f"Error closing streaming session {self.session_id}: {e}")

    def is_expired(self, timeout: float = 300) -> bool:
        """Check if session has expired"""
        return time.time() - self.last_activity > timeout


class HTTPConnectionPool:
    """HTTP connection pool for API-based TTS providers"""

    def __init__(
        self,
        max_connections: int = 10,
        max_keepalive_connections: int = 5,
        keepalive_expiry: float = 30.0,
        timeout: float = 60.0
    ):
        """
        Initialize HTTP connection pool.

        Args:
            max_connections: Maximum total connections
            max_keepalive_connections: Maximum keep-alive connections
            keepalive_expiry: Keep-alive timeout in seconds
            timeout: Request timeout in seconds
        """
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections
        self.keepalive_expiry = keepalive_expiry
        self.timeout = timeout

        # Connection pools per provider
        self._pools: Dict[str, httpx.AsyncClient] = {}
        self._pool_metrics: Dict[str, ResourceMetrics] = {}
        self._lock = asyncio.Lock()

        # Backward-compatibility: tests reference `_clients`; alias to `_pools`.
    @property
    def _clients(self) -> Dict[str, httpx.AsyncClient]:
        return self._pools

    async def get_client(self, provider: str, base_url: Optional[str] = None) -> httpx.AsyncClient:
        """
        Get or create HTTP client for provider.

        Args:
            provider: Provider name
            base_url: Optional base URL for the client

        Returns:
            HTTP client instance
        """
        async with self._lock:
            if provider not in self._pools:
                client = httpx.AsyncClient(
                    limits=httpx.Limits(
                        max_connections=self.max_connections,
                        max_keepalive_connections=self.max_keepalive_connections,
                        keepalive_expiry=self.keepalive_expiry
                    ),
                    timeout=httpx.Timeout(self.timeout),
                    base_url=base_url
                )

                self._pools[provider] = client
                self._pool_metrics[provider] = ResourceMetrics(
                    created_at=time.time(),
                    last_used=time.time(),
                    metadata={"provider": provider, "base_url": base_url}
                )

                logger.debug(f"Created HTTP connection pool for {provider}")

            # Update metrics
            metrics = self._pool_metrics[provider]
            metrics.update_usage()

            return self._pools[provider]

    async def close_pool(self, provider: str):
        """Close connection pool for specific provider"""
        async with self._lock:
            if provider in self._pools:
                await self._pools[provider].aclose()
                del self._pools[provider]
                del self._pool_metrics[provider]
                logger.debug(f"Closed HTTP connection pool for {provider}")

    async def close_client(self, provider: str):
        """Close a specific client (alias for close_pool)"""
        await self.close_pool(provider)

    async def close_all(self):
        """Close all connection pools"""
        async with self._lock:
            tasks = []
            for provider, client in self._pools.items():
                tasks.append(client.aclose())

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            self._pools.clear()
            self._pool_metrics.clear()
            logger.info("Closed all HTTP connection pools")

    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get connection pool statistics"""
        stats = {}
        for provider, metrics in self._pool_metrics.items():
            stats[provider] = {
                "created_at": metrics.created_at,
                "last_used": metrics.last_used,
                "use_count": metrics.use_count,
                "is_active": metrics.is_active,
                "metadata": metrics.metadata
            }
        return stats


class MemoryMonitor:
    """Memory monitoring and management for local TTS models"""

    def __init__(
        self,
        memory_threshold: float = 0.80,  # 80% of total memory
        check_interval: float = 30.0,    # Check every 30 seconds
        cleanup_threshold: float = 0.90,  # Force cleanup at 90%
        warning_threshold: Optional[float] = None,  # Alias for memory_threshold (for tests)
        critical_threshold: Optional[float] = None  # Alias for cleanup_threshold (for tests)
    ):
        """
        Initialize memory monitor.

        Args:
            memory_threshold: Memory usage threshold (0.0-1.0)
            check_interval: Monitoring check interval in seconds
            cleanup_threshold: Force cleanup threshold (0.0-1.0)
        """
        # Handle aliases from tests
        if warning_threshold is not None:
            memory_threshold = warning_threshold / 100.0
        if critical_threshold is not None:
            cleanup_threshold = critical_threshold / 100.0

        self.memory_threshold = memory_threshold
        self.check_interval = check_interval
        self.cleanup_threshold = cleanup_threshold

        # Store as percentages for compatibility
        self.warning_threshold = memory_threshold * 100
        self.critical_threshold = cleanup_threshold * 100

        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._model_references: Set[weakref.ReferenceType] = set()
        self._last_check_time = 0
        self._last_memory_usage = None
        self._cleanup_callbacks: List[Callable] = []

        # Get system memory info
        self.total_memory = psutil.virtual_memory().total

    def register_model(self, model_instance: Any, cleanup_callback: Optional[Callable] = None):
        """
        Register a model instance for memory monitoring.

        Args:
            model_instance: Model instance to monitor
            cleanup_callback: Optional cleanup function for the model
        """
        # Use weak reference to avoid circular references
        weak_ref = weakref.ref(model_instance)
        self._model_references.add(weak_ref)

        if cleanup_callback:
            self._cleanup_callbacks.append(cleanup_callback)

        logger.debug(f"Registered model for memory monitoring: {type(model_instance).__name__}")

    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage statistics (with simple caching and robust fallbacks)"""
        now = time.time()
        if (
            self._last_memory_usage is not None
            and (now - self._last_check_time) < self.check_interval
        ):
            return self._last_memory_usage

        memory = psutil.virtual_memory()
        process = psutil.Process()
        mb = 1024 * 1024

        def _as_int(value, default=0):
            try:
                return int(value)
            except (TypeError, ValueError):
                try:
                    return int(float(value))
                except (TypeError, ValueError):
                    return default

        def _as_float(value, default=0.0):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        total_raw = getattr(memory, "total", 0)
        available_raw = getattr(memory, "available", 0)
        used_raw = getattr(memory, "used", None)
        if used_raw is None and total_raw and available_raw is not None:
            used_raw = total_raw - available_raw
        free_raw = getattr(memory, "free", None)
        if free_raw is None:
            free_raw = available_raw
        percent_raw = getattr(memory, "percent", None)
        if percent_raw is None and total_raw:
            try:
                percent_raw = (used_raw / total_raw) * 100
            except Exception:
                percent_raw = 0

        total = _as_int(total_raw)
        available = _as_int(available_raw)
        used = _as_int(used_raw, default=max(total - available, 0))
        free = _as_int(free_raw, default=available)
        percent = _as_float(percent_raw)

        # Compute warning/critical from the same percent value to avoid extra psutil calls
        usage_ratio = (percent / 100.0) if percent is not None else 0.0
        stats = {
            "total": total,
            "available": available,
            "used": used,
            "percent": percent,
            "free": free,
            "total_mb": total // mb if total else 0,
            "available_mb": available // mb if available else 0,
            "used_mb": used // mb if used else 0,
            "free_mb": free // mb if free else 0,
            "process_mb": _as_int(process.memory_info().rss) // mb,
            "threshold": self.memory_threshold * 100,
            "cleanup_threshold": self.cleanup_threshold * 100,
            "is_warning": usage_ratio > self.memory_threshold,
            "is_critical": usage_ratio > self.cleanup_threshold,
        }

        self._last_memory_usage = stats
        self._last_check_time = now
        return stats

    def is_memory_critical(self) -> bool:
        """Check if memory usage is critical"""
        try:
            percent = float(psutil.virtual_memory().percent)
        except (TypeError, ValueError):
            percent = 0.0
        usage = percent / 100.0
        return usage > self.cleanup_threshold

    def is_memory_high(self) -> bool:
        """Check if memory usage is high"""
        try:
            percent = float(psutil.virtual_memory().percent)
        except (TypeError, ValueError):
            percent = 0.0
        usage = percent / 100.0
        return usage > self.memory_threshold

    def is_memory_warning(self) -> bool:
        """Check if memory usage is at warning level (alias for is_memory_high)"""
        return self.is_memory_high()

    async def force_cleanup(self):
        """Force memory cleanup"""
        logger.warning("Forcing memory cleanup due to high usage")

        # Run cleanup callbacks
        for callback in self._cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"Error in cleanup callback: {e}")

        # Clean up dead references
        self._model_references = {ref for ref in self._model_references if ref() is not None}

        # Force garbage collection
        gc.collect()

        # Check if cleanup was effective
        if self.is_memory_critical():
            raise TTSInsufficientMemoryError(
                "Memory usage remains critical after cleanup",
                details=self.get_memory_usage()
            )

    async def start_monitoring(self):
        """Start memory monitoring"""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Memory monitoring started")

    async def stop_monitoring(self):
        """Stop memory monitoring"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Memory monitoring stopped")

    async def _monitor_loop(self):
        """Memory monitoring loop"""
        while self._monitoring:
            try:
                if self.is_memory_critical():
                    await self.force_cleanup()
                elif self.is_memory_high():
                    logger.warning(f"High memory usage: {psutil.virtual_memory().percent:.1f}%")

                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")
                await asyncio.sleep(self.check_interval)


class StreamingSessionManager:
    """Manages streaming audio sessions"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.sessions: Dict[str, StreamingSession] = {}
        self.max_sessions = self.config.get("max_streaming_sessions", 10)
        self._lock = threading.Lock()

    # Tests reference `_sessions`; expose alias to `sessions`.
    @property
    def _sessions(self) -> Dict[str, StreamingSession]:
        return self.sessions

    async def create_session(self, provider: str, session_id: Optional[str] = None, **kwargs) -> str:
        """Create a new streaming session

        Args:
            provider: TTS provider name
            session_id: Optional session ID, will be generated if not provided
            **kwargs: Additional session parameters

        Returns:
            Session ID
        """
        if session_id is None:
            import uuid
            session_id = str(uuid.uuid4())

        with self._lock:
            if len(self.sessions) >= self.max_sessions:
                # Clean up old sessions
                self._cleanup_old_sessions()

            if len(self.sessions) >= self.max_sessions:
                raise TTSResourceError("Maximum streaming sessions reached")

            session = StreamingSession(session_id=session_id, provider=provider, **kwargs)
            self.sessions[session_id] = session
            return session_id

    async def get_session(self, session_id: str) -> Optional[StreamingSession]:
        """Get an existing session"""
        return self.sessions.get(session_id)

    async def update_session(self, session_id: str, bytes_sent: int = 0, chunks_sent: int = 0) -> bool:
        """Update session statistics

        Args:
            session_id: Session ID
            bytes_sent: Additional bytes sent
            chunks_sent: Additional chunks sent

        Returns:
            True if session was updated, False if not found
        """
        session = self.sessions.get(session_id)
        if session:
            session.bytes_sent += bytes_sent
            session.chunks_sent += chunks_sent
            session.last_activity = time.time()
            return True
        return False

    async def close_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Close a streaming session and return stats

        Args:
            session_id: Session ID

        Returns:
            Session statistics or None if not found
        """
        with self._lock:
            session = self.sessions.pop(session_id, None)
        if not session:
            return None

        await session.close()
        duration = time.time() - session.created_at
        return {
            "session_id": session_id,
            "provider": session.provider,
            "duration": duration,
            "bytes_streamed": session.bytes_sent,
            "chunks_sent": session.chunks_sent,
            "error_count": session.error_count
        }

    def end_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """End a streaming session and return stats"""
        with self._lock:
            session = self.sessions.pop(session_id, None)
        if not session:
            return None

        # Dispatch asynchronous close; if the caller awaits elsewhere it can
        # manage completion, otherwise we best-effort kick it off.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running loop; close synchronously.
            try:
                asyncio.run(session.close())
            except RuntimeError:
                # Fallback: mark inactive without cleanup.
                logger.warning("Could not run session.close(); marking session inactive")
                session.is_active = False
        else:
            asyncio.create_task(session.close())
            session.is_active = False
        stats = {
            "session_id": session_id,
            "provider": session.provider,
            "duration": time.time() - session.created_at,
            "bytes_streamed": session.bytes_sent,
            "chunks_sent": session.chunks_sent,
            "error_count": session.error_count
        }
        return stats

    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        with self._lock:
            self._cleanup_old_sessions()

    def _cleanup_old_sessions(self):
        """Internal method to clean up old sessions"""
        current_time = time.time()
        expired = []

        for sid, session in self.sessions.items():
            if current_time - session.start_time > 3600:  # 1 hour timeout
                expired.append(sid)

        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        for sid in expired:
            session = self.sessions.pop(sid)
            if loop and loop.is_running():
                asyncio.create_task(session.close())
            else:
                try:
                    asyncio.run(session.close())
                except RuntimeError:
                    logger.warning(f"Unable to close session {sid} during cleanup")
                    session.is_active = False

    async def get_active_sessions(self) -> List[StreamingSession]:
        """Get list of active session objects"""
        return [s for s in self.sessions.values() if s.is_active]

    async def cleanup_inactive(self, max_age_seconds: int = 3600) -> None:
        """Remove inactive sessions older than the given age."""
        cutoff = time.time() - max_age_seconds
        with self._lock:
            to_remove = [
                sid for sid, s in self.sessions.items()
                if (not s.is_active) and (s.start_time < cutoff)
            ]
            for sid in to_remove:
                self.sessions.pop(sid, None)


class TTSResourceManager:
    """Central resource manager for TTS operations"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize TTS resource manager.

        Args:
            config: Resource management configuration
        """
        self.config = config or {}

        # Initialize components
        self.connection_pool = HTTPConnectionPool(
            max_connections=self.config.get("max_http_connections", self.config.get("max_connections", 10)),
            max_keepalive_connections=self.config.get("max_keepalive_connections", 5),
            keepalive_expiry=self.config.get("keepalive_expiry", 30.0),
            timeout=self.config.get("http_timeout", self.config.get("connection_timeout", 60.0))
        )

        self.memory_monitor = MemoryMonitor(
            memory_threshold=self.config.get("memory_threshold", 0.80),
            check_interval=self.config.get("memory_check_interval", 30.0),
            cleanup_threshold=self.config.get("memory_cleanup_threshold", 0.90),
            warning_threshold=self.config.get("memory_warning_threshold"),
            critical_threshold=self.config.get("memory_critical_threshold")
        )

        # Streaming session management
        self.session_manager = StreamingSessionManager(self.config)
        self._streaming_sessions: Dict[str, StreamingSession] = {}
        self._session_cleanup_task: Optional[asyncio.Task] = None
        self._session_timeout = self.config.get("streaming_session_timeout", 300)  # 5 minutes

        # Model instance tracking
        self._model_instances: Dict[str, weakref.ReferenceType] = {}
        self._registered_models: Dict[str, weakref.ReferenceType] = {}

        # Resource cleanup
        self._cleanup_handlers: Dict[ResourceType, List[Callable]] = {}

        logger.info("TTS Resource Manager initialized")

    async def initialize(self):
        """Initialize resource management"""
        # Start memory monitoring
        await self.memory_monitor.start_monitoring()

        # Start session cleanup task
        self._session_cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())

        logger.info("TTS Resource Manager started")

    async def shutdown(self):
        """Shutdown resource manager and cleanup all resources"""
        logger.info("Shutting down TTS Resource Manager")

        # Stop monitoring
        await self.memory_monitor.stop_monitoring()

        # Stop session cleanup
        if self._session_cleanup_task:
            self._session_cleanup_task.cancel()
            try:
                await self._session_cleanup_task
            except asyncio.CancelledError:
                pass

        # Close all streaming sessions
        sessions = list(self._streaming_sessions.values())
        for session in sessions:
            await session.close()
        self._streaming_sessions.clear()

        # Close connection pools
        await self.connection_pool.close_all()

        # Run cleanup handlers
        for resource_type, handlers in self._cleanup_handlers.items():
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler()
                    else:
                        handler()
                except Exception as e:
                    logger.error(f"Error in {resource_type} cleanup handler: {e}")

        logger.info("TTS Resource Manager shutdown complete")

    @asynccontextmanager
    async def streaming_session(self, session_id: str, provider: str, cleanup_callback: Optional[Callable] = None):
        """
        Context manager for streaming sessions.

        Args:
            session_id: Unique session identifier
            provider: TTS provider name
            cleanup_callback: Optional cleanup callback
        """
        session = StreamingSession(session_id, provider, cleanup_callback)
        self._streaming_sessions[session_id] = session

        try:
            logger.debug(f"Started streaming session {session_id} for {provider}")
            yield session
        finally:
            await session.close()
            self._streaming_sessions.pop(session_id, None)
            logger.debug(f"Closed streaming session {session_id}")

    async def get_http_client(self, provider: str, base_url: Optional[str] = None) -> httpx.AsyncClient:
        """Get HTTP client for provider"""
        return await self.connection_pool.get_client(provider, base_url)

    def register_model(self, provider: str, model_instance: Any, cleanup_callback: Optional[Callable] = None):
        """Register model instance for resource management"""
        self._model_instances[provider] = weakref.ref(model_instance)
        self.memory_monitor.register_model(model_instance, cleanup_callback)
        # Track explicit registered models as expected by tests
        self._registered_models[provider] = {"model": model_instance, "cleanup": cleanup_callback}

    def register_cleanup_handler(self, resource_type: ResourceType, handler: Callable):
        """Register cleanup handler for resource type"""
        if resource_type not in self._cleanup_handlers:
            self._cleanup_handlers[resource_type] = []
        self._cleanup_handlers[resource_type].append(handler)

    async def _cleanup_expired_sessions(self):
        """Cleanup expired streaming sessions"""
        while True:
            try:
                current_time = time.time()
                expired_sessions = []

                for session_id, session in self._streaming_sessions.items():
                    if session.is_expired(self._session_timeout):
                        expired_sessions.append(session_id)

                for session_id in expired_sessions:
                    session = self._streaming_sessions.pop(session_id, None)
                    if session:
                        await session.close()
                        logger.info(f"Cleaned up expired streaming session {session_id}")

                # Sleep for cleanup interval
                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")
                await asyncio.sleep(60)

    async def unregister_model(self, provider: str):
        """Unregister a model instance and run its cleanup callback"""
        entry = self._registered_models.pop(provider, None)
        if entry is not None:
            cleanup_cb = entry.get("cleanup")
            if cleanup_cb:
                try:
                    if asyncio.iscoroutinefunction(cleanup_cb):
                        await cleanup_cb()
                    else:
                        cleanup_cb()
                except Exception as e:
                    logger.error(f"Error in model cleanup for {provider}: {e}")
            logger.debug(f"Unregistered model for provider: {provider}")

    async def create_streaming_session(self, provider: str) -> str:
        """Create a new streaming session

        Args:
            provider: Provider name

        Returns:
            Session ID
        """
        return await self.session_manager.create_session(provider)

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive resource statistics in test-expected shape"""
        mem = self.memory_monitor.get_memory_usage()
        connections = {
            "active": len(self.connection_pool._clients),
            "providers": list(self.connection_pool._clients.keys())
        }
        models = {
            "registered": list(self._registered_models.keys())
        }
        sessions = {
            "active": len(self.session_manager._sessions),
            "ids": list(self.session_manager._sessions.keys())
        }
        return {
            "memory": mem,
            "connections": connections,
            "models": models,
            "sessions": sessions
        }

    async def cleanup_all(self):
        """Cleanup all resources: models, clients, and sessions"""
        # Cleanup registered models
        # Make a copy of keys to avoid mutation during iteration
        for provider in list(self._registered_models.keys()):
            try:
                await self.unregister_model(provider)
            except Exception as e:
                logger.error(f"Error cleaning model {provider}: {e}")

        # Close all sessions managed by the session manager
        for sid in list(self.session_manager._sessions.keys()):
            try:
                await self.session_manager.close_session(sid)
            except Exception as e:
                logger.error(f"Error closing session {sid}: {e}")

        # Close all HTTP clients
        await self.connection_pool.close_all()

    def get_resource_stats(self) -> Dict[str, Any]:
        """Get resource usage statistics"""
        return {
            "http_connections": self.connection_pool.get_stats(),
            "memory": self.memory_monitor.get_memory_usage(),
            "streaming_sessions": {
                "active": len(self._streaming_sessions),
                "sessions": [
                    {
                        "id": session.session_id,
                        "provider": session.provider,
                        "duration": time.time() - session.created_at,
                        "chunks_sent": session.chunks_sent,
                        "bytes_sent": session.bytes_sent
                    }
                    for session in self._streaming_sessions.values()
                ]
            },
            "model_instances": {
                provider: ref() is not None
                for provider, ref in self._model_instances.items()
            }
        }


# Global resource manager instance
_resource_manager: Optional[TTSResourceManager] = None
_manager_lock = asyncio.Lock()


async def get_resource_manager(config: Optional[Dict[str, Any]] = None) -> TTSResourceManager:
    """
    Get or create the global TTS resource manager.

    Args:
        config: Configuration for resource management

    Returns:
        TTSResourceManager instance
    """
    global _resource_manager

    if _resource_manager is None:
        async with _manager_lock:
            if _resource_manager is None:
                _resource_manager = TTSResourceManager(config)
                await _resource_manager.initialize()
                logger.info("Global TTS Resource Manager created")

    return _resource_manager


async def close_resource_manager():
    """Close the global resource manager"""
    global _resource_manager

    if _resource_manager:
        await _resource_manager.shutdown()
        _resource_manager = None
        logger.info("Global TTS Resource Manager closed")


# Alias for compatibility
reset_resource_manager = close_resource_manager


# Context manager for resource management
@asynccontextmanager
async def managed_resources(config: Optional[Dict[str, Any]] = None):
    """Context manager for TTS resource management"""
    manager = await get_resource_manager(config)
    try:
        yield manager
    finally:
        # Don't close the global manager, just ensure it's cleaned up properly
        pass

#
# End of tts_resource_manager.py
#######################################################################################################################
