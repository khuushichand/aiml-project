# request_batching.py
# Request batching for improved throughput

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from collections import deque
import uuid

from loguru import logger
from tldw_Server_API.app.core.Embeddings.simplified_config import get_config, ProviderConfig
from tldw_Server_API.app.core.Embeddings.metrics_integration import get_metrics
from tldw_Server_API.app.core.Embeddings.rate_limiter import get_async_rate_limiter


@dataclass
class BatchRequest:
    """Represents a single request in a batch"""
    request_id: str
    text: str
    model: str
    provider: str
    metadata: Dict[str, Any]
    future: asyncio.Future
    timestamp: float


class RequestBatcher:
    """
    Batches embedding requests for improved throughput.
    Collects requests and processes them in batches.
    """
    
    def __init__(self, config: Optional[Any] = None):
        """
        Initialize request batcher.
        
        Args:
            config: Optional configuration override
        """
        self.config = config or get_config()
        self.metrics = get_metrics()
        self.rate_limiter = get_async_rate_limiter()
        
        # Batching settings
        self.enabled = self.config.batching.enabled
        self.max_batch_size = self.config.batching.max_batch_size
        self.batch_timeout_ms = self.config.batching.batch_timeout_ms
        self.adaptive_batching = self.config.batching.adaptive_batching
        
        # Request queues per model
        self.queues: Dict[str, deque] = {}
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        
        # Statistics
        self.stats = {
            'total_batches': 0,
            'total_requests': 0,
            'average_batch_size': 0,
            'average_wait_time': 0
        }
        
        # Adaptive batching parameters
        self.adaptive_params = {
            'current_batch_size': self.max_batch_size,
            'current_timeout': self.batch_timeout_ms,
            'throughput_history': deque(maxlen=10)
        }
        
        logger.info(
            f"Request batcher initialized: "
            f"enabled={self.enabled}, "
            f"max_batch_size={self.max_batch_size}, "
            f"timeout={self.batch_timeout_ms}ms"
        )
    
    async def submit_request(
        self,
        text: str,
        model: str,
        provider: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Submit a request for batching.
        
        Args:
            text: Input text
            model: Model name
            provider: Provider name
            metadata: Optional metadata
            
        Returns:
            Embedding result when ready
        """
        if not self.enabled:
            # Batching disabled, process immediately
            return await self._process_single(text, model, provider, metadata)
        
        metadata = metadata or {}
        user_id = metadata.get("user_id")

        if (
            user_id
            and getattr(self.config.security, "enable_rate_limiting", False)
        ):
            allowed, retry_after = await self.rate_limiter.check_rate_limit_async(user_id)
            if not allowed:
                tier = "free"
                limiter = getattr(self.rate_limiter, "rate_limiter", None)
                if limiter and getattr(limiter, "user_tiers", None):
                    tier = limiter.user_tiers.get(user_id, "free")
                try:
                    self.metrics.log_rate_limit_hit(user_id, tier)
                except Exception:
                    pass
                retry_after_msg = f" Retry after {retry_after}s." if retry_after else ""
                raise RuntimeError(
                    f"Rate limit exceeded for user '{user_id}'.{retry_after_msg}"
                )

        # Create request
        loop = asyncio.get_running_loop()
        request = BatchRequest(
            request_id=str(uuid.uuid4()),
            text=text,
            model=model,
            provider=provider,
            metadata=metadata,
            future=loop.create_future(),
            timestamp=time.time()
        )
        
        # Get or create queue for this model
        queue_key = f"{provider}:{model}"
        if queue_key not in self.queues:
            self.queues[queue_key] = deque()
            # Start processing task for this queue
            self.processing_tasks[queue_key] = asyncio.create_task(
                self._process_queue(queue_key)
            )
        
        # Add to queue
        self.queues[queue_key].append(request)
        
        # Wait for result
        return await request.future
    
    async def _process_queue(self, queue_key: str):
        """
        Process requests from a queue.
        
        Args:
            queue_key: Queue identifier (provider:model)
        """
        queue = self.queues[queue_key]
        provider, model = queue_key.split(":", 1)
        
        while True:
            try:
                # Collect batch
                batch = await self._collect_batch(queue)
                
                if not batch:
                    # No requests, wait a bit
                    await asyncio.sleep(0.01)
                    continue
                
                # Process batch
                await self._process_batch(batch, provider, model)
                
            except Exception as e:
                logger.error(f"Error processing batch queue {queue_key}: {e}")
                # Don't crash the processing task
                await asyncio.sleep(0.1)
    
    async def _collect_batch(self, queue: deque) -> List[BatchRequest]:
        """
        Collect requests into a batch.
        
        Args:
            queue: Request queue
            
        Returns:
            List of requests to process
        """
        batch = []
        start_time = time.time()
        
        # Determine batch parameters
        if self.adaptive_batching:
            max_size = self.adaptive_params['current_batch_size']
            timeout_ms = self.adaptive_params['current_timeout']
        else:
            max_size = self.max_batch_size
            timeout_ms = self.batch_timeout_ms
        
        timeout_seconds = timeout_ms / 1000.0
        
        # Collect requests until batch is full or timeout
        while len(batch) < max_size:
            if queue:
                batch.append(queue.popleft())
            else:
                # Queue empty, wait for more or timeout
                elapsed = time.time() - start_time
                
                if batch and elapsed >= timeout_seconds:
                    # Timeout reached with partial batch
                    break
                elif not batch:
                    # No requests yet, wait longer
                    await asyncio.sleep(0.001)
                    
                    # Check timeout even for first request
                    if time.time() - start_time > timeout_seconds * 10:
                        break
                else:
                    # Have some requests, wait a bit more
                    remaining = timeout_seconds - elapsed
                    if remaining > 0:
                        await asyncio.sleep(min(0.001, remaining))
                    else:
                        break
        
        return batch
    
    async def _process_batch(
        self,
        batch: List[BatchRequest],
        provider: str,
        model: str
    ):
        """
        Process a batch of requests.
        
        Args:
            batch: List of requests
            provider: Provider name
            model: Model name
        """
        if not batch:
            return
        
        batch_start = time.time()
        
        try:
            # Extract texts
            texts = [req.text for req in batch]
            
            # Log batch metrics
            self.metrics.log_batch_size(provider, len(texts))
            
            # Process batch
            # Import here to avoid circular dependency
            from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import (
                create_embeddings_batch_async as embeddings_create_embeddings_batch_async,
            )
            
            # Create config for batch
            batch_config = self._build_user_app_config(provider, model)
            
            # Get embeddings
            embeddings = await embeddings_create_embeddings_batch_async(
                texts,
                batch_config,
                model_id_override=f"{provider}:{model}"
            )
            
            # Distribute results
            for i, req in enumerate(batch):
                if i < len(embeddings):
                    req.future.set_result(embeddings[i])
                else:
                    req.future.set_exception(
                        ValueError(f"No embedding returned for request {i}")
                    )
            
            # Update statistics
            batch_time = time.time() - batch_start
            wait_times = [batch_start - req.timestamp for req in batch]
            avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0
            
            self.stats['total_batches'] += 1
            self.stats['total_requests'] += len(batch)
            self.stats['average_batch_size'] = (
                self.stats['total_requests'] / self.stats['total_batches']
            )
            self.stats['average_wait_time'] = (
                self.stats['average_wait_time'] * 0.9 + avg_wait * 0.1
            )
            
            # Update adaptive parameters
            if self.adaptive_batching:
                self._update_adaptive_params(len(batch), batch_time)
            
            logger.debug(
                f"Processed batch: size={len(batch)}, "
                f"time={batch_time:.3f}s, "
                f"avg_wait={avg_wait:.3f}s"
            )
            
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            
            # Set error for all requests
            for req in batch:
                if not req.future.done():
                    req.future.set_exception(e)
    
    async def _process_single(
        self,
        text: str,
        model: str,
        provider: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Process a single request without batching.
        
        Args:
            text: Input text
            model: Model name
            provider: Provider name
            metadata: Optional metadata
            
        Returns:
            Embedding result
        """
        # Import here to avoid circular dependency
        from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import create_embedding
        
        config = self._build_user_app_config(provider, model)
        
        return create_embedding(
            text,
            config,
            model_id_override=f"{provider}:{model}"
        )
    
    def _build_user_app_config(self, provider: str, model: str) -> Dict[str, Any]:
        """Construct full user app config for embeddings executor."""
        provider_config = self.config.get_provider(provider)
        if provider_config is None:
            raise ValueError(f"Provider '{provider}' is not configured for embeddings batching.")
        
        model_id = f"{provider}:{model}"
        
        model_entry: Dict[str, Any] = {
            "provider": provider,
            "model_name_or_path": model
        }
        if provider_config.api_key:
            model_entry["api_key"] = provider_config.api_key
        if provider_config.api_url:
            model_entry["api_url"] = provider_config.api_url
        
        user_app_config: Dict[str, Any] = {
            "embedding_config": {
                "default_model_id": model_id,
                "models": {
                    model_id: model_entry
                }
            }
        }
        
        provider_section = self._build_provider_section(provider_config)
        if provider_section:
            user_app_config.update(provider_section)
        
        return user_app_config
    
    @staticmethod
    def _build_provider_section(provider_config: ProviderConfig) -> Optional[Dict[str, Any]]:
        """Build provider-specific top-level config payload (e.g., API keys)."""
        section_key_map = {
            "openai": "openai_api",
            "huggingface": "huggingface_api",
            "local_api": "local_api",
            "local": "local_api"
        }
        
        section_key = section_key_map.get(provider_config.name.lower())
        if not section_key:
            return None
        
        section_payload: Dict[str, Any] = {}
        if provider_config.api_key:
            section_payload["api_key"] = provider_config.api_key
        if provider_config.api_url:
            section_payload["api_url"] = provider_config.api_url
        
        return {section_key: section_payload} if section_payload else None
    
    def _update_adaptive_params(self, batch_size: int, processing_time: float):
        """
        Update adaptive batching parameters based on performance.
        
        Args:
            batch_size: Size of processed batch
            processing_time: Time taken to process
        """
        # Calculate throughput
        throughput = batch_size / processing_time if processing_time > 0 else 0
        self.adaptive_params['throughput_history'].append(throughput)
        
        # Adjust parameters based on throughput trend
        if len(self.adaptive_params['throughput_history']) >= 3:
            recent = list(self.adaptive_params['throughput_history'])[-3:]
            avg_throughput = sum(recent) / len(recent)
            
            # If throughput is decreasing, reduce batch size
            if recent[-1] < avg_throughput * 0.9:
                self.adaptive_params['current_batch_size'] = max(
                    1,
                    int(self.adaptive_params['current_batch_size'] * 0.9)
                )
                logger.debug(
                    f"Reduced batch size to {self.adaptive_params['current_batch_size']}"
                )
            
            # If throughput is increasing, increase batch size
            elif recent[-1] > avg_throughput * 1.1:
                self.adaptive_params['current_batch_size'] = min(
                    self.max_batch_size,
                    int(self.adaptive_params['current_batch_size'] * 1.1)
                )
                logger.debug(
                    f"Increased batch size to {self.adaptive_params['current_batch_size']}"
                )
            
            # Adjust timeout based on batch filling rate
            if batch_size < self.adaptive_params['current_batch_size'] * 0.5:
                # Batches not filling, reduce timeout
                self.adaptive_params['current_timeout'] = max(
                    10,
                    int(self.adaptive_params['current_timeout'] * 0.9)
                )
            elif batch_size >= self.adaptive_params['current_batch_size']:
                # Batches filling completely, can increase timeout
                self.adaptive_params['current_timeout'] = min(
                    1000,
                    int(self.adaptive_params['current_timeout'] * 1.1)
                )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get batching statistics"""
        queue_sizes = {
            key: len(queue) for key, queue in self.queues.items()
        }
        
        return {
            'enabled': self.enabled,
            'total_batches': self.stats['total_batches'],
            'total_requests': self.stats['total_requests'],
            'average_batch_size': self.stats['average_batch_size'],
            'average_wait_time': self.stats['average_wait_time'],
            'queue_sizes': queue_sizes,
            'adaptive_params': self.adaptive_params if self.adaptive_batching else None
        }
    
    async def flush_all_queues(self):
        """Force process all pending requests in queues"""
        for queue_key, queue in self.queues.items():
            if queue:
                provider, model = queue_key.split(":", 1)
                batch = list(queue)
                queue.clear()
                await self._process_batch(batch, provider, model)
    
    async def shutdown(self):
        """Gracefully shutdown the batcher"""
        # Process remaining requests
        await self.flush_all_queues()
        
        # Cancel processing tasks
        for task in self.processing_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.processing_tasks.values(), return_exceptions=True)
        
        logger.info("Request batcher shutdown complete")


# Global batcher instance
_batcher: Optional[RequestBatcher] = None


def get_batcher() -> RequestBatcher:
    """Get or create the global batcher instance."""
    global _batcher
    if _batcher is None:
        _batcher = RequestBatcher()
    return _batcher


# Convenience function for batched requests
async def create_embeddings_batch_async(
    texts: List[str],
    config: Dict[str, Any],
    model_id_override: Optional[str] = None
) -> List[List[float]]:
    """
    Create embeddings with automatic batching.
    
    Args:
        texts: List of input texts
        config: Configuration dictionary
        model_id_override: Optional model override
        
    Returns:
        List of embeddings
    """
    batcher = get_batcher()
    
    # Parse model info
    if model_id_override and ":" in model_id_override:
        provider, model = model_id_override.split(":", 1)
    else:
        # Use defaults from config
        provider = config.get("embedding_config", {}).get("default_provider", "openai")
        model = config.get("embedding_config", {}).get("default_model", "text-embedding-3-small")
    
    # Submit requests
    tasks = []
    for text in texts:
        task = batcher.submit_request(text, model, provider)
        tasks.append(task)
    
    # Wait for all results
    results = await asyncio.gather(*tasks)
    
    return results
