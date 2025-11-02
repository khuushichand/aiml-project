# async_embeddings.py
# Async implementation of embeddings creation and management

import asyncio
import aiohttp
import hashlib
import time
import atexit
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from loguru import logger
from tldw_Server_API.app.core.Embeddings.connection_pool import get_pool_manager
from tldw_Server_API.app.core.Embeddings.metrics_integration import get_metrics, track_embedding_request
from tldw_Server_API.app.core.Embeddings.error_recovery import get_recovery_manager
from tldw_Server_API.app.core.Embeddings.rate_limiter import get_async_rate_limiter
from tldw_Server_API.app.core.Embeddings.multi_tier_cache import get_multi_tier_cache
from tldw_Server_API.app.core.Embeddings.request_batching import get_batcher
from tldw_Server_API.app.core.Embeddings.simplified_config import get_config


class AsyncEmbeddingProvider:
    """Base class for async embedding providers"""

    def __init__(self, provider_name: str, api_key: Optional[str] = None):
        self.provider_name = provider_name
        self.api_key = api_key
        self.metrics = get_metrics()
        self.pool_manager = get_pool_manager()
        self.rate_limiter = get_async_rate_limiter()

    async def create_embedding(
        self,
        text: str,
        model: str,
        user_id: Optional[str] = None
    ) -> List[float]:
        """Create embedding asynchronously"""
        raise NotImplementedError

    async def create_embeddings_batch(
        self,
        texts: List[str],
        model: str,
        user_id: Optional[str] = None
    ) -> List[List[float]]:
        """Create embeddings for multiple texts"""
        tasks = [
            self.create_embedding(text, model, user_id)
            for text in texts
        ]
        return await asyncio.gather(*tasks)


class AsyncOpenAIProvider(AsyncEmbeddingProvider):
    """Async OpenAI embeddings provider"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("openai", api_key)
        self.base_url = "https://api.openai.com/v1/embeddings"

    async def create_embedding(
        self,
        text: str,
        model: str = "text-embedding-3-small",
        user_id: Optional[str] = None
    ) -> List[float]:
        """Create embedding using OpenAI API"""
        import time as _time
        t0 = _time.perf_counter()
        status = "success"

        # Check rate limit
        if user_id:
            allowed, retry_after = await self.rate_limiter.check_rate_limit_async(user_id)
            if not allowed:
                status = "rate_limited"
                retry_after_msg = f" Retry after {retry_after}s." if retry_after else ""
                self.metrics.log_request(self.provider_name, model, status=status)
                self.metrics.log_error(self.provider_name, "RateLimitExceeded")
                logger.warning(
                    "Rate limit exceeded for user '{user_id}' on provider '{provider}' model '{model}'.{extra}",
                    user_id=user_id,
                    provider=self.provider_name,
                    model=model,
                    extra=retry_after_msg,
                )
                raise Exception(f"Rate limit exceeded.{retry_after_msg}")

        # Get connection pool for this provider
        pool = self.pool_manager.get_pool(self.provider_name)
        async with pool.acquire_connection() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "input": text,
                "model": model
            }

            try:
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data["data"][0]["embedding"]
            except Exception as e:
                status = "failure"
                self.metrics.log_error(self.provider_name, str(type(e).__name__))
                raise
            finally:
                # Emit metrics with the actual requested model
                elapsed = _time.perf_counter() - t0
                self.metrics.log_request(self.provider_name, model, status=status)
                self.metrics.log_request_latency(self.provider_name, model, elapsed)


class AsyncHuggingFaceProvider(AsyncEmbeddingProvider):
    """Async HuggingFace embeddings provider"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("huggingface", api_key)
        self.base_url = "https://api-inference.huggingface.co/models"
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def create_embedding(
        self,
        text: str,
        model: str = "sentence-transformers/all-MiniLM-L6-v2",
        user_id: Optional[str] = None
    ) -> List[float]:
        """Create embedding using HuggingFace API"""

        # Check rate limit
        if user_id:
            allowed, retry_after = await self.rate_limiter.check_rate_limit_async(user_id)
            if not allowed:
                retry_after_msg = f" Retry after {retry_after}s." if retry_after else ""
                self.metrics.log_request(self.provider_name, model, status="rate_limited")
                self.metrics.log_error(self.provider_name, "RateLimitExceeded")
                logger.warning(
                    "Rate limit exceeded for user '{user_id}' on provider '{provider}' model '{model}'.{extra}",
                    user_id=user_id,
                    provider=self.provider_name,
                    model=model,
                    extra=retry_after_msg,
                )
                raise Exception(f"Rate limit exceeded.{retry_after_msg}")

        url = f"{self.base_url}/{model}"

        # Get connection pool for this provider
        pool = self.pool_manager.get_pool(self.provider_name)
        async with pool.acquire_connection() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "inputs": text,
                "options": {"wait_for_model": True}
            }

            try:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    # Usage is already recorded in check_rate_limit_async

                    # Extract embedding based on response format
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and 'embeddings' in data:
                        return data['embeddings']
                    else:
                        raise ValueError(f"Unexpected response format: {data}")

            except Exception as e:
                self.metrics.log_error(self.provider_name, str(type(e).__name__))
                raise


class AsyncLocalProvider(AsyncEmbeddingProvider):
    """Async local embeddings provider using sentence-transformers"""

    def __init__(self):
        super().__init__("local", None)
        self.models = {}
        self.executor = ThreadPoolExecutor(max_workers=2)

    async def _load_model(self, model_name: str):
        """Load model if not already loaded"""
        if model_name not in self.models:
            # Run model loading in thread pool to avoid blocking
            loop = asyncio.get_running_loop()

            def load():
                from sentence_transformers import SentenceTransformer
                return SentenceTransformer(model_name)

            self.models[model_name] = await loop.run_in_executor(
                self.executor,
                load
            )

            logger.info(f"Loaded local model: {model_name}")

    async def create_embedding(
        self,
        text: str,
        model: str = "all-MiniLM-L6-v2",
        user_id: Optional[str] = None
    ) -> List[float]:
        """Create embedding using local model"""

        # Load model if needed
        await self._load_model(model)

        # Run encoding in thread pool
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(
            self.executor,
            lambda: self.models[model].encode(text, convert_to_tensor=False)
        )

        return embedding.tolist()


class AsyncEmbeddingService:
    """
    Main async service for creating embeddings.
    Orchestrates providers, caching, batching, and fallbacks.
    """

    def __init__(self, config: Optional[Any] = None):
        """Initialize async embedding service"""
        self.config = config or get_config()
        self.cache = get_multi_tier_cache()
        self.batcher = get_batcher()
        self.recovery_manager = get_recovery_manager()
        self.metrics = get_metrics()
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        # Initialize providers
        self.providers = {}
        self._initialize_providers()

        logger.info("Async embedding service initialized")

    def _initialize_providers(self):
        """Initialize configured providers"""
        for provider_config in self.config.providers:
            if not provider_config.enabled:
                continue

            if provider_config.name == "openai":
                self.providers["openai"] = AsyncOpenAIProvider(
                    api_key=provider_config.api_key
                )
            elif provider_config.name == "huggingface":
                self.providers["huggingface"] = AsyncHuggingFaceProvider(
                    api_key=provider_config.api_key
                )
            elif provider_config.name == "local":
                self.providers["local"] = AsyncLocalProvider()

            logger.info(f"Initialized provider: {provider_config.name}")

    async def create_embedding(
        self,
        text: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        user_id: Optional[str] = None,
        use_cache: bool = True,
        use_batching: bool = True
    ) -> List[float]:
        """
        Create embedding with full async pipeline.

        Args:
            text: Input text
            model: Model to use (optional)
            provider: Provider to use (optional)
            user_id: User identifier for rate limiting
            use_cache: Whether to use caching
            use_batching: Whether to use batching

        Returns:
            Embedding vector
        """
        # Use defaults if not specified
        provider = provider or self.config.default_provider
        model = model or self.config.default_model

        # Create deterministic cache key across processes
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cache_key = f"{provider}:{model}:{text_hash}"

        # Check cache
        if use_cache:
            cached_embedding = await self.cache.get_async(cache_key)
            if cached_embedding is not None:
                self.metrics.log_cache_hit(model)
                return cached_embedding

        # Use batching if enabled
        if use_batching and self.batcher.enabled:
            embedding = await self.batcher.submit_request(
                text=text,
                model=model,
                provider=provider,
                metadata={"user_id": user_id}
            )
        else:
            # Direct provider call
            if provider not in self.providers:
                raise ValueError(f"Provider {provider} not available")

            provider_instance = self.providers[provider]

            try:
                embedding = await provider_instance.create_embedding(
                    text=text,
                    model=model,
                    user_id=user_id
                )
            except Exception as e:
                # Try fallback provider
                embedding = await self._try_fallback_providers(
                    text, model, provider, user_id, e
                )

        # Cache the result
        if use_cache:
            await self.cache.set_async(cache_key, embedding)

        return embedding

    async def create_embeddings_batch(
        self,
        texts: List[str],
        model: Optional[str] = None,
        provider: Optional[str] = None,
        user_id: Optional[str] = None,
        parallel: bool = True
    ) -> List[List[float]]:
        """
        Create embeddings for multiple texts.

        Args:
            texts: List of input texts
            model: Model to use
            provider: Provider to use
            user_id: User identifier
            parallel: Whether to process in parallel

        Returns:
            List of embedding vectors
        """
        if parallel:
            # Process in parallel
            tasks = [
                self.create_embedding(text, model, provider, user_id)
                for text in texts
            ]
            return await asyncio.gather(*tasks)
        else:
            # Process sequentially
            embeddings = []
            for text in texts:
                embedding = await self.create_embedding(
                    text, model, provider, user_id
                )
                embeddings.append(embedding)
            return embeddings

    async def _try_fallback_providers(
        self,
        text: str,
        model: str,
        failed_provider: str,
        user_id: Optional[str],
        original_error: Exception
    ) -> List[float]:
        """Try fallback providers when primary fails"""

        # Get provider config
        provider_config = self.config.get_provider(failed_provider)

        if provider_config and provider_config.fallback_provider:
            fallback = provider_config.fallback_provider

            if fallback in self.providers:
                logger.warning(
                    f"Provider {failed_provider} failed, trying fallback {fallback}"
                )

                try:
                    provider_instance = self.providers[fallback]
                    fallback_model = model
                    fallback_config = self.config.get_provider(fallback)
                    if fallback_config is None:
                        fallback_model = None
                    elif fallback_config.fallback_model:
                        fallback_model = fallback_config.fallback_model
                    else:
                        available_models = fallback_config.models or []
                        if available_models and model not in available_models:
                            fallback_model = available_models[0]
                            logger.debug(
                                "Substituting fallback model '{fallback_model}' for provider '{fallback}' "
                                "(original model '{model}' not available).",
                                fallback_model=fallback_model,
                                fallback=fallback,
                                model=model,
                            )
                    call_kwargs = {"text": text, "user_id": user_id}
                    if fallback_model:
                        call_kwargs["model"] = fallback_model
                    return await provider_instance.create_embedding(**call_kwargs)
                except Exception as e:
                    logger.error(f"Fallback provider {fallback} also failed: {e}")

        # No fallback available or fallback failed
        raise original_error

    async def warmup_providers(self):
        """Warmup all configured providers"""
        warmup_text = "Provider warmup test"

        for provider_name, provider_instance in self.providers.items():
            try:
                start_time = time.time()

                # Try to create a test embedding
                await provider_instance.create_embedding(
                    text=warmup_text,
                    model=self.config.default_model
                )

                elapsed = time.time() - start_time
                logger.info(f"Provider {provider_name} warmed up in {elapsed:.2f}s")

            except Exception as e:
                logger.warning(f"Failed to warmup provider {provider_name}: {e}")

    async def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers"""
        status = {}

        for provider_name, provider_instance in self.providers.items():
            try:
                # Try a test embedding
                test_start = time.time()
                await provider_instance.create_embedding(
                    text="test",
                    model=self.config.default_model
                )
                latency = time.time() - test_start

                status[provider_name] = {
                    "status": "healthy",
                    "latency_ms": int(latency * 1000)
                }
            except Exception as e:
                status[provider_name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }

        return status

    async def shutdown(self):
        """Gracefully shutdown the service"""
        logger.info("Shutting down async embedding service...")

        # Flush batcher queues
        if self.batcher:
            await self.batcher.shutdown()

        # Close connection pools
        pool_manager = get_pool_manager()
        await pool_manager.close_all()

        # Shutdown thread pools in local providers
        for provider in self.providers.values():
            if hasattr(provider, 'executor'):
                try:
                    provider.executor.shutdown(wait=False)
                except Exception:
                    try:
                        provider.executor.shutdown(wait=False)
                    except Exception:
                        pass

        logger.info("Async embedding service shutdown complete")


# Global async service instance
_async_service: Optional[AsyncEmbeddingService] = None
_shutdown_registered = False
_health_check_task: Optional[asyncio.Task] = None


async def _cancel_health_check_task():
    """Cancel and await the periodic health task if it exists."""
    global _health_check_task
    task = _health_check_task
    if task is None:
        return
    try:
        task_loop = task.get_loop()
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if current_loop and task_loop is current_loop:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        else:
            # Different loop or no running loop; request cancellation and return
            try:
                if task_loop.is_running():
                    task_loop.call_soon_threadsafe(task.cancel)
                else:
                    # Loop already stopped; best-effort cancel
                    task.cancel()
            except Exception:
                try:
                    task.cancel()
                except Exception:
                    pass
    finally:
        _health_check_task = None


async def _shutdown_service(service: AsyncEmbeddingService):
    """Shutdown helper that cancels background tasks then stops the service."""
    await _cancel_health_check_task()
    await service.shutdown()


def get_async_embedding_service() -> AsyncEmbeddingService:
    """Get or create the global async embedding service."""
    global _async_service, _shutdown_registered
    if _async_service is None:
        _async_service = AsyncEmbeddingService()
        if not _shutdown_registered:
            try:
                atexit.register(_shutdown_async_embedding_service_sync)
            except Exception as exc:
                logger.warning(f"Failed to register async embedding service shutdown hook: {exc}")
            else:
                _shutdown_registered = True
    return _async_service


def _shutdown_async_embedding_service_sync():
    """Best-effort shutdown for the global async service at interpreter exit."""
    global _async_service
    service = _async_service
    if service is None:
        return

    try:
        loop = getattr(service, "_loop", None)
        if loop and not loop.is_closed():
            if loop.is_running():
                fut = asyncio.run_coroutine_threadsafe(_shutdown_service(service), loop)
                try:
                    fut.result(timeout=15)
                except Exception as exc:
                    try:
                        logger.warning(f"Async embedding service shutdown timed out: {exc}")
                    except Exception:
                        pass
            else:
                loop.run_until_complete(_shutdown_service(service))
        else:
            asyncio.run(_shutdown_service(service))
    except Exception as exc:
        try:
            logger.warning(f"Failed during async embedding service shutdown: {exc}")
        except Exception:
            pass
    finally:
        _async_service = None


# Convenience functions
async def create_embedding_async(
    text: str,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    user_id: Optional[str] = None
) -> List[float]:
    """
    Create a single embedding asynchronously.

    Args:
        text: Input text
        model: Model to use
        provider: Provider to use
        user_id: User identifier

    Returns:
        Embedding vector
    """
    service = get_async_embedding_service()
    return await service.create_embedding(text, model, provider, user_id)


async def create_embeddings_batch_async(
    texts: List[str],
    model: Optional[str] = None,
    provider: Optional[str] = None,
    user_id: Optional[str] = None
) -> List[List[float]]:
    """
    Create embeddings for multiple texts asynchronously.

    Args:
        texts: List of input texts
        model: Model to use
        provider: Provider to use
        user_id: User identifier

    Returns:
        List of embedding vectors
    """
    service = get_async_embedding_service()
    return await service.create_embeddings_batch(texts, model, provider, user_id)


# FastAPI integration example
async def startup_event():
    """FastAPI startup event handler"""
    service = get_async_embedding_service()

    # Warmup providers
    await service.warmup_providers()

    # Start periodic tasks
    global _health_check_task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop:
        _health_check_task = loop.create_task(periodic_health_check())
    else:
        _health_check_task = asyncio.create_task(periodic_health_check())


async def shutdown_event():
    """FastAPI shutdown event handler"""
    service = get_async_embedding_service()
    await _shutdown_service(service)


async def periodic_health_check():
    """Periodic health check for providers"""
    service = get_async_embedding_service()

    while True:
        try:
            await asyncio.sleep(60)  # Check every minute

            status = await service.get_provider_status()

            # Log unhealthy providers
            for provider, info in status.items():
                if info["status"] == "unhealthy":
                    logger.warning(f"Provider {provider} is unhealthy: {info.get('error')}")

        except Exception as e:
            logger.error(f"Error in periodic health check: {e}")
