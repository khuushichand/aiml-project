# embedding_worker.py
# Worker for generating embeddings from chunks

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Union, Tuple
import os
from collections import OrderedDict
from datetime import datetime, timedelta

import numpy as np
from loguru import logger

from ..Embeddings_Server.Embeddings_Create import (
    HFModelCfg,
    ONNXModelCfg,
    OpenAIModelCfg,
    LocalAPICfg,
    create_embeddings_batch,
    resolve_model_storage_base_dir,
)
from ..queue_schemas import (
    EmbeddingData,
    EmbeddingMessage,
    JobStatus,
    StorageMessage,
)
from .base_worker import BaseWorker, WorkerConfig
from fnmatch import fnmatch
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat
from ..messages import normalize_message
from ..hyde import generate_questions, question_hash, normalize_question
from tldw_Server_API.app.core.Metrics import increment_counter
import json as _json


class EmbeddingWorkerConfig(WorkerConfig):
    """Extended configuration for embedding workers"""
    default_model_provider: str = "huggingface"
    default_model_name: str = "dunzhang/stella_en_400M_v5"  # Better default model
    fallback_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"  # Fallback model
    max_batch_size: int = 32
    gpu_id: Optional[int] = None

    # Multi-model support configuration
    enable_model_selection: bool = True
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600  # 1 hour default
    cache_max_size: int = 10000  # Maximum cached embeddings

    # Model selection thresholds
    long_text_threshold: int = 512  # Use different model for long texts
    multilingual_detection: bool = True

    # Available models by category with fallback support
    models_by_category: Dict[str, Dict[str, str]] = {
        "general": {
            "provider": "huggingface",
            "model": "dunzhang/stella_en_400M_v5",
            "fallback": "sentence-transformers/all-MiniLM-L6-v2"
        },
        "multilingual": {
            "provider": "huggingface",
            "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "fallback": "sentence-transformers/all-MiniLM-L6-v2"
        },
        "long_context": {
            "provider": "openai",
            "model": "text-embedding-3-large",
            "fallback": "sentence-transformers/all-mpnet-base-v2"
        },
        "high_quality": {
            "provider": "openai",
            "model": "text-embedding-3-large",
            "fallback": "sentence-transformers/all-mpnet-base-v2"
        }
    }


class EmbeddingCache:
    """LRU cache for embeddings with TTL support"""

    def __init__(self, max_size: int = 10000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, Tuple[List[float], datetime]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def _get_cache_key(self, text: str, model: str) -> str:
        """Generate cache key from text and model"""
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, text: str, model: str) -> Optional[List[float]]:
        """Get embedding from cache if exists and not expired"""
        key = self._get_cache_key(text, model)

        if key in self.cache:
            embedding, timestamp = self.cache[key]

            # Check TTL
            if datetime.now() - timestamp < timedelta(seconds=self.ttl_seconds):
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                self.hits += 1
                return embedding
            else:
                # Expired, remove it
                del self.cache[key]

        self.misses += 1
        return None

    def put(self, text: str, model: str, embedding: List[float]):
        """Store embedding in cache"""
        key = self._get_cache_key(text, model)

        # Remove oldest if at capacity
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)

        self.cache[key] = (embedding, datetime.now())

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "ttl_seconds": self.ttl_seconds
        }

    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0


class EmbeddingWorker(BaseWorker):
    """Worker that generates embeddings from text chunks"""

    def __init__(self, config: EmbeddingWorkerConfig):
        super().__init__(config)
        self.embedding_config = config
        self.storage_queue = config.queue_name.replace("embedding", "storage")

        def _requires_remote_code(model_name: str) -> bool:
            try:
                m = (model_name or "").lower()
                return "stella" in m
            except Exception:
                return False

        # Initialize embedding cache
        self.cache = EmbeddingCache(
            max_size=config.cache_max_size,
            ttl_seconds=config.cache_ttl_seconds
        ) if config.enable_caching else None

        # Model configuration cache
        self.model_configs = {
            "huggingface": HFModelCfg(
                model_name_or_path=config.default_model_name,
                trust_remote_code=_requires_remote_code(config.default_model_name)
            ),
            "openai": OpenAIModelCfg(
                model_name_or_path="text-embedding-3-small"
            ),
            # Add more default configs as needed
        }

        # Performance tracking
        self.model_usage_stats = {}
        self.model_performance = {}

        # Set GPU if specified
        if config.gpu_id is not None:
            import os
            os.environ["CUDA_VISIBLE_DEVICES"] = str(config.gpu_id)

    # Compatibility shim for tests that expect `worker.batch_size`
    @property
    def batch_size(self) -> int:
        return getattr(self.embedding_config, "max_batch_size", 1)

    def _parse_message(self, data: Dict[str, Any]) -> EmbeddingMessage:
        """Parse raw message data into EmbeddingMessage"""
        norm = normalize_message("embedding", data)
        return EmbeddingMessage(**norm)

    def _detect_language(self, text: str) -> str:
        """Detect language of text"""
        try:
            # Simple heuristic - check for non-ASCII characters
            # In production, use langdetect or polyglot
            non_ascii_count = sum(1 for c in text if ord(c) > 127)
            text_length = len(text)

            # If more than 10% non-ASCII, likely non-English
            if text_length > 0 and non_ascii_count / text_length > 0.1:
                return "multilingual"

            # Check for common non-English patterns
            multilingual_indicators = [
                'à', 'è', 'ì', 'ò', 'ù',  # Italian/French
                'ñ', 'á', 'é', 'í', 'ó', 'ú',  # Spanish
                'ä', 'ö', 'ü', 'ß',  # German
                'å', 'æ', 'ø',  # Nordic
                'ą', 'ć', 'ę', 'ł', 'ń', 'ś', 'ź', 'ż',  # Polish
                'а', 'б', 'в', 'г', 'д',  # Cyrillic
                '中', '文', '日', '本',  # CJK
            ]

            if any(char in text.lower() for char in multilingual_indicators):
                return "multilingual"

            return "english"

        except Exception as e:
            logger.warning(f"Language detection failed: {e}")
            return "english"  # Default to English

    def _select_model(self, text: str, metadata: Dict[str, Any]) -> Tuple[str, str]:
        """
        Select appropriate model based on text characteristics.

        Returns:
            Tuple of (provider, model_name)
        """
        if not self.embedding_config.enable_model_selection:
            return (
                self.embedding_config.default_model_provider,
                self.embedding_config.default_model_name
            )

        # Check for explicit model request in metadata
        if "preferred_model" in metadata:
            model_info = metadata["preferred_model"]
            if isinstance(model_info, dict):
                return (model_info.get("provider"), model_info.get("model"))

        # Determine model category based on text characteristics
        text_length = len(text)
        category = "general"

        # Check for long text
        if text_length > self.embedding_config.long_text_threshold:
            category = "long_context"
            logger.debug(f"Selected long_context model for text with {text_length} chars")

        # Check for multilingual content
        elif self.embedding_config.multilingual_detection:
            language = self._detect_language(text)
            if language == "multilingual":
                category = "multilingual"
                logger.debug("Selected multilingual model for non-English text")

        # Check for high quality request
        elif metadata.get("high_quality", False):
            category = "high_quality"
            logger.debug("Selected high quality model per request")

        # Get model for category
        model_info = self.embedding_config.models_by_category.get(
            category,
            self.embedding_config.models_by_category["general"]
        )

        provider = model_info.get("provider", self.embedding_config.default_model_provider)
        model = model_info.get("model", self.embedding_config.default_model_name)

        # Track model usage
        model_key = f"{provider}:{model}"
        self.model_usage_stats[model_key] = self.model_usage_stats.get(model_key, 0) + 1

        return (provider, model)

    async def process_message(self, message: EmbeddingMessage) -> Optional[StorageMessage]:
        """Process embedding message and generate embeddings"""
        logger.bind(job_id=message.job_id, stage="embedding").info(
            f"Processing embedding job {message.job_id} with {len(message.chunks)} chunks"
        )

        start_time = time.time()
        cache_hits = 0
        cache_misses = 0

        try:
            # Update job status
            await self._update_job_status(message.job_id, JobStatus.EMBEDDING)

            # Process chunks in batches
            embedding_data_list = []
            batch_size = message.batch_size or self.embedding_config.max_batch_size

            # Track models used
            models_used = set()

            for i in range(0, len(message.chunks), batch_size):
                batch_chunks = message.chunks[i:i + batch_size]

                # Process each chunk individually for cache lookup and model selection
                for chunk in batch_chunks:
                    embedding = None
                    model_provider = None
                    model_name = None

                    # Select appropriate model for this chunk
                    if self.embedding_config.enable_model_selection:
                        model_provider, model_name = self._select_model(
                            chunk.content,
                            chunk.metadata or {}
                        )
                    else:
                        # Use message-level or default configuration
                        if message.model_provider and message.embedding_model_config:
                            model_provider = message.model_provider
                            model_name = message.embedding_model_config.get("model_name_or_path", self.embedding_config.default_model_name)
                        else:
                            model_config = self._get_model_config(message)
                            model_provider = message.model_provider or self.embedding_config.default_model_provider
                            model_name = model_config.model_name_or_path

                    models_used.add(f"{model_provider}:{model_name}")

                    chunk_metadata_src = dict(chunk.metadata or {})
                    detected_language = chunk_metadata_src.get("language")
                    if not detected_language:
                        try:
                            detected_language = self._detect_language(chunk.content)
                        except Exception:
                            detected_language = None
                    if detected_language:
                        chunk_metadata_src.setdefault("language", detected_language)
                    chunk_cached = False

                    # Check Redis content-hash cache first (cross-run)
                    try:
                        if self.redis_client and chunk_metadata_src:
                            chash = chunk_metadata_src.get("content_hash")
                            if chash:
                                rkey = f"embeddings:contentcache:v1:{model_name}:{chash}"
                                redis_raw = await self.redis_client.get(rkey)
                                if redis_raw:
                                    try:
                                        payload = _json.loads(redis_raw)
                                        vec = payload.get("embedding")
                                        if isinstance(vec, list):
                                            embedding = vec
                                            chunk_cached = True
                                            cache_hits += 1
                                            logger.debug(f"Redis cache hit for chunk {chunk.chunk_id}")
                                    except Exception:
                                        pass
                    except Exception:
                        pass

                    # Then check in-process LRU cache
                    if embedding is None and self.cache and self.embedding_config.enable_caching:
                        cached_embedding = self.cache.get(chunk.content, model_name)
                        if cached_embedding:
                            embedding = cached_embedding
                            chunk_cached = True
                            cache_hits += 1
                            logger.debug(f"LRU cache hit for chunk {chunk.chunk_id}")
                        else:
                            cache_misses += 1

                    # Generate embedding if not cached
                    if embedding is None:
                        # Get appropriate model config
                        if model_provider == "huggingface":
                            patterns = settings.get("TRUSTED_HF_REMOTE_CODE_MODELS", []) or []
                            trust_rc = any(fnmatch(model_name, p) or fnmatch(model_name.lower(), p.lower()) for p in patterns)
                            if trust_rc:
                                logger.info(f"HF trust_remote_code enabled for model '{model_name}'")
                            model_config = HFModelCfg(
                                model_name_or_path=model_name,
                                trust_remote_code=trust_rc
                            )
                        elif model_provider == "openai":
                            model_config = OpenAIModelCfg(
                                model_name_or_path=model_name
                            )
                        else:
                            model_config = self._get_model_config(message)

                        # Generate embedding
                        embeddings = await self._generate_embeddings(
                            [chunk.content],
                            model_config,
                            model_provider
                        )
                        embedding = embeddings[0]

                        # Cache the embedding
                        if self.cache and self.embedding_config.enable_caching:
                            embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
                            self.cache.put(chunk.content, model_name, embedding_list)
                        # Populate Redis cache for content_hash
                        try:
                            if self.redis_client and isinstance(chunk.metadata, dict):
                                chash = chunk.metadata.get("content_hash")
                                if chash:
                                    rkey = f"embeddings:contentcache:v1:{model_name}:{chash}"
                                    vec = embedding.tolist() if hasattr(embedding, 'tolist') else embedding
                                    ttl = int(os.getenv("EMBEDDINGS_CONTENT_CACHE_TTL_SECONDS", "86400") or 86400)
                                    await self.redis_client.set(rkey, _json.dumps({
                                        "embedding": vec,
                                        "dimensions": len(vec),
                                        "model": model_name,
                                        "provider": model_provider,
                                        "ts": int(time.time())
                                    }), ex=ttl)
                        except Exception:
                            pass

                    # Create embedding data object
                    # Tag embedder and content hash in metadata
                    embedder_name = model_provider
                    embedder_version = model_name
                    embedding_data = EmbeddingData(
                        chunk_id=chunk.chunk_id,
                        embedding=embedding if isinstance(embedding, list) else embedding.tolist(),
                        model_used=model_name,
                        dimensions=len(embedding) if isinstance(embedding, list) else len(embedding.tolist()),
                        metadata={
                            **chunk_metadata_src,
                            "kind": "chunk",
                            "model_provider": model_provider,
                            "embedder_name": embedder_name,
                            "embedder_version": embedder_version,
                            "cached": chunk_cached
                        }
                    )
                    embedding_data_list.append(embedding_data)

                    # HYDE/doc2query generation (Option A: inline in embedding worker)
                    hyde_provider = settings.get("HYDE_PROVIDER")
                    hyde_model = settings.get("HYDE_MODEL")
                    try:
                        if bool(settings.get("HYDE_ENABLED", False)):
                            try:
                                hyde_n = int(settings.get("HYDE_QUESTIONS_PER_CHUNK", 0) or 0)
                            except Exception:
                                hyde_n = 0
                            if hyde_n > 0:
                                # Choose language: override from settings unless 'auto'
                                lang_cfg = str(settings.get("HYDE_LANGUAGE", "auto") or "auto").lower()
                                if lang_cfg == "auto":
                                    language = detected_language
                                else:
                                    language = lang_cfg
                                # Provider/model for HYDE question generation
                                hyde_temp = float(settings.get("HYDE_TEMPERATURE", 0.2) or 0.2)
                                hyde_max_tokens = int(settings.get("HYDE_MAX_TOKENS", 96) or 96)
                                hyde_prompt_ver = settings.get("HYDE_PROMPT_VERSION", 1)
                                hyde_labels = {
                                    "provider": hyde_provider or "unknown",
                                    "model": hyde_model or "unknown",
                                    "source": "worker",
                                }

                                questions = generate_questions(
                                    text=chunk.content,
                                    n=hyde_n,
                                    provider=hyde_provider,
                                    model=hyde_model,
                                    temperature=hyde_temp,
                                    max_tokens=hyde_max_tokens,
                                    language=language,
                                    prompt_version=hyde_prompt_ver,
                                )
                                if questions:
                                    increment_counter(
                                        "hyde_questions_generated_total",
                                        len(questions),
                                        labels=hyde_labels,
                                    )
                                    # Embed questions using the same embedder used for the parent chunk
                                    q_embeddings = await self._generate_embeddings(
                                        questions,
                                        model_config,
                                        model_provider,
                                    )
                                    for qi, qtext in enumerate(questions):
                                        try:
                                            qvec = q_embeddings[qi]
                                        except Exception:
                                            continue
                                        qh = question_hash(qtext)
                                        qid = f"{chunk.chunk_id}:q:{qh[:8]}"
                                        meta = {
                                            **chunk_metadata_src,
                                            "kind": "hyde_q",
                                            "parent_chunk_id": chunk.chunk_id,
                                            "hyde_rank": qi,
                                            "question_hash": qh,
                                            "model_provider": model_provider,
                                            "embedder_name": embedder_name,
                                            "embedder_version": embedder_version,
                                            "hyde_prompt_version": hyde_prompt_ver,
                                            "hyde_generator": f"{hyde_provider}:{hyde_model}" if (hyde_provider and hyde_model) else "",
                                        }
                                        if language:
                                            meta["language"] = language
                                        elif detected_language:
                                            meta["language"] = detected_language
                                        # Create embedding data for HYDE question
                                        qvec_list = qvec.tolist() if hasattr(qvec, 'tolist') else qvec
                                        embedding_data_list.append(
                                            EmbeddingData(
                                                chunk_id=qid,
                                                embedding=qvec_list,
                                                model_used=model_name,
                                                dimensions=len(qvec_list) if hasattr(qvec_list, '__len__') else len(qvec),
                                                metadata=meta,
                                            )
                                        )
                                    logger.debug(f"HYDE: added {len(questions)} question embeddings for chunk {chunk.chunk_id}")
                    except Exception as _hyde_err:
                        # Never block the pipeline on HYDE
                        increment_counter(
                            "hyde_generation_failures_total",
                            1,
                            labels={
                                "provider": hyde_provider or "unknown",
                                "model": hyde_model or "unknown",
                                "source": "worker",
                                "reason": type(_hyde_err).__name__,
                            },
                        )
                        logger.debug(f"HYDE generation skipped/failed for chunk {chunk.chunk_id}: {_hyde_err}")

                # Update progress
                progress = 25 + (50 * (i + len(batch_chunks)) / len(message.chunks))
                await self._update_job_progress(
                    message.job_id,
                    progress,
                    chunks_processed=i + len(batch_chunks)
                )

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Log cache statistics
            if self.cache:
                cache_stats = self.cache.get_stats()
                logger.bind(job_id=message.job_id, stage="embedding").info(
                    f"Cache stats for job {message.job_id}: "
                    f"Hits: {cache_hits}, Misses: {cache_misses}, "
                    f"Total hit rate: {cache_stats['hit_rate']:.2%}"
                )

            # Create storage message
            storage_message = StorageMessage(
                job_id=message.job_id,
                user_id=message.user_id,
                media_id=message.media_id,
                priority=message.priority,
                user_tier=message.user_tier,
                created_at=message.created_at,
                idempotency_key=message.idempotency_key,
                dedupe_key=message.dedupe_key,
                operation_id=message.operation_id,
                trace_id=message.trace_id,
                embeddings=embedding_data_list,
                collection_name=f"user_{message.user_id}_media_{message.media_id}",
                total_chunks=len(message.chunks),
                processing_time_ms=processing_time_ms,
                metadata={
                    "models_used": list(models_used),
                    "cache_hits": cache_hits,
                    "cache_misses": cache_misses,
                    "model_selection_enabled": self.embedding_config.enable_model_selection
                }
            )

            logger.bind(job_id=message.job_id, stage="embedding").info(
                f"Generated {len(embedding_data_list)} embeddings for job {message.job_id} "
                f"in {processing_time_ms}ms using models: {', '.join(models_used)}"
            )
            return storage_message

        except Exception as e:
            logger.error(f"Error generating embeddings for job {message.job_id}: {e}")
            raise

    async def _send_to_next_stage(self, result: StorageMessage):
        """Send embeddings to storage queue"""
        target_queue = self.storage_queue
        try:
            if str(os.getenv("EMBEDDINGS_PRIORITY_ENABLED", "false")).lower() in ("1", "true", "yes"):
                # Operator override takes precedence
                pr = None
                try:
                    key = f"embeddings:priority:override:{result.job_id}"
                    pr = await self.redis_client.get(key)
                except Exception:
                    pr = None
                if not pr:
                    p = int(getattr(result, 'priority', 50) or 50)
                    if p >= 75:
                        pr = 'high'
                    elif p <= 25:
                        pr = 'low'
                    else:
                        pr = 'normal'
                target_queue = f"{self.storage_queue}:{pr}"
        except Exception:
            target_queue = self.storage_queue

        payload = model_dump_compat(result)
        # Ensure Redis stream field values are strings (encode nested types as JSON)
        try:
            fields = {k: (v if isinstance(v, str) else _json.dumps(v)) for k, v in payload.items()}
        except Exception:
            fields = {k: str(v) for k, v in payload.items()}
        await self.redis_client.xadd(target_queue, fields)
        logger.debug(f"Sent job {result.job_id} to storage queue")

    def _get_model_config(self, message: EmbeddingMessage) -> Union[HFModelCfg, ONNXModelCfg, OpenAIModelCfg, LocalAPICfg]:
        """Get or create model configuration"""
        if message.embedding_model_config:
            # Use provided config
            provider = message.model_provider
            if provider == "huggingface":
                return HFModelCfg(**message.embedding_model_config)
            elif provider == "onnx":
                return ONNXModelCfg(**message.embedding_model_config)
            elif provider == "openai":
                return OpenAIModelCfg(**message.embedding_model_config)
            elif provider == "local_api":
                return LocalAPICfg(**message.embedding_model_config)

        # Use default config based on user tier
        if message.user_tier == "enterprise":
            return self.model_configs.get("openai", self.model_configs["huggingface"])
        else:
            return self.model_configs["huggingface"]

    async def _generate_embeddings(
        self,
        texts: List[str],
        config: Union[HFModelCfg, ONNXModelCfg, OpenAIModelCfg, LocalAPICfg],
        provider: str
    ) -> List[np.ndarray]:
        """Generate embeddings for a batch of texts with fallback support.

        Adapts to the new Embeddings_Create.create_embeddings_batch signature:
        create_embeddings_batch(texts, user_app_config, model_id_override)
        """
        import asyncio

        loop = asyncio.get_running_loop()

        def _build_app_config(model_id: str, prov: str, cfg_obj: Any) -> Dict[str, Any]:
            # Pass through the typed cfg_obj directly to avoid union misclassification
            app_config = {
                "embedding_config": {
                    "default_model_id": model_id,
                    "model_storage_base_dir": resolve_model_storage_base_dir(),
                    "models": {model_id: cfg_obj},
                }
            }
            # Best-effort hint for HTTP connection pooling/rate limiting to provider wrappers
            try:
                from ..connection_pool import get_pool_manager
                pool = get_pool_manager().get_pool(prov)
                app_config["http_connection_pool"] = pool  # consumers may opt-in to reuse
            except Exception:
                pass
            return app_config

        # Resolve create_embeddings_batch at runtime to respect test patches
        def _resolve_create_fn():
            try:
                # If local alias is a mock (tests), prefer it
                if 'unittest.mock' in str(type(create_embeddings_batch)):
                    return create_embeddings_batch
            except Exception:
                pass
            try:
                # Otherwise, use the module attribute to honor patches at source
                from ..Embeddings_Server import Embeddings_Create as _EC  # type: ignore
                return _EC.create_embeddings_batch
            except Exception:
                return create_embeddings_batch

        create_fn = _resolve_create_fn()

        # Helper: call create_fn using best-effort signature detection via try/except
        def _call_create(fn, batch_texts, model_id, app_cfg, prov, cfg_obj):
            # Prefer new signature first
            try:
                return fn(batch_texts, app_cfg, model_id)
            except TypeError:
                # Try legacy signature: (texts, model_name, provider, api_url, api_key)
                api_url = getattr(cfg_obj, "api_url", None)
                api_key = getattr(cfg_obj, "api_key", None) or os.getenv("OPENAI_API_KEY")
                return fn(batch_texts, model_id, prov, api_url, api_key)

        # Batching and retry logic (adaptive batch sizing)
        max_attempts = 3
        results: List[Any] = []
        # Start with configured max_batch_size or len(texts)
        target_batch = min(getattr(self.embedding_config, "max_batch_size", len(texts)) or len(texts), len(texts))
        # Track a simple moving window of per-item latency
        latency_per_item_ms: float = 0.0
        def _adapt_batch(last_elapsed_s: float, n_items: int) -> int:
            nonlocal latency_per_item_ms, target_batch
            if n_items <= 0:
                return target_batch
            per_item = (last_elapsed_s * 1000.0) / float(n_items)
            # exponential moving average
            if latency_per_item_ms <= 0.0:
                latency_per_item_ms = per_item
            else:
                latency_per_item_ms = 0.7 * latency_per_item_ms + 0.3 * per_item
            # If fast, increase batch modestly; if slow, reduce
            try:
                max_b = max(1, int(getattr(self.embedding_config, "max_batch_size", target_batch) or target_batch))
            except Exception:
                max_b = target_batch
            if latency_per_item_ms < 12.0 and target_batch < max_b:
                target_batch = min(max_b, target_batch + 2)
            elif latency_per_item_ms > 120.0 and target_batch > 1:
                target_batch = max(1, target_batch // 2)
            return target_batch

        idx = 0
        while idx < len(texts):
            # Ensure we do not overshoot
            end = min(idx + target_batch, len(texts))
            batch = texts[idx:end]
            app_cfg = _build_app_config(config.model_name_or_path, provider, config)

            attempt = 0
            while True:
                try:
                    import time as _time
                    t0 = _time.perf_counter()
                    embeddings = await loop.run_in_executor(
                        None,
                        _call_create,
                        create_fn,
                        batch,
                        config.model_name_or_path,
                        app_cfg,
                        provider,
                        config,
                    )
                    t1 = _time.perf_counter()
                    # Append and move to next batch
                    results.extend(embeddings)
                    # Adapt batch size based on observed latency
                    try:
                        _adapt_batch(t1 - t0, len(batch))
                    except Exception:
                        pass
                    idx = end
                    break
                except MemoryError as me:
                    # Reduce batch size and retry
                    logger.warning(f"MemoryError during embedding; reducing batch size from {target_batch}: {me}")
                    if target_batch <= 1:
                        raise
                    target_batch = max(1, target_batch // 2)
                    end = min(idx + target_batch, len(texts))
                    batch = texts[idx:end]
                    app_cfg = _build_app_config(config.model_name_or_path, provider, config)
                    continue
                except Exception as e:
                    attempt += 1
                    # On likely rate-limit/network classes, back off batch size
                    try:
                        if target_batch > 1 and ("rate limit" in str(e).lower() or "429" in str(e).lower()):
                            target_batch = max(1, target_batch // 2)
                            end = min(idx + target_batch, len(texts))
                            batch = texts[idx:end]
                            app_cfg = _build_app_config(config.model_name_or_path, provider, config)
                    except Exception:
                        pass
                    if attempt < max_attempts:
                        logger.warning(f"Embedding attempt {attempt} failed; retrying: {e}")
                        continue
                    # After retries, try fallback if available
                    logger.warning(f"Primary model failed after retries ({provider}:{config.model_name_or_path}): {e}")
                    fallback_model = self.embedding_config.fallback_model_name
                    if fallback_model and fallback_model != config.model_name_or_path:
                        try:
                            # Determine trust_remote_code via allowlist
                            patterns = settings.get("TRUSTED_HF_REMOTE_CODE_MODELS", []) or []
                            trust_rc = any(fnmatch(fallback_model, p) or fnmatch(fallback_model.lower(), p.lower()) for p in patterns)
                            if trust_rc:
                                logger.info(f"HF trust_remote_code enabled for fallback model '{fallback_model}'")
                            fallback_cfg = HFModelCfg(
                                model_name_or_path=fallback_model,
                                trust_remote_code=trust_rc,
                            )
                            app_cfg_fb = _build_app_config(fallback_model, "huggingface", fallback_cfg)
                            fb_embeddings = await loop.run_in_executor(
                                None,
                                _call_create,
                                create_fn,
                                batch,
                                fallback_model,
                                app_cfg_fb,
                                "huggingface",
                                fallback_cfg,
                            )
                            results.extend(fb_embeddings)
                            idx = end
                            break
                        except Exception as fallback_error:
                            logger.error(f"Fallback model also failed: {fallback_error}")
                            raise
                    else:
                        # No fallback available
                        raise

        return results

    async def _update_job_progress(self, job_id: str, percentage: float, chunks_processed: int):
        """Update job progress information"""
        job_key = f"job:{job_id}"
        if not self.redis_client:
            # In unit tests or when Redis is not initialized, skip progress updates
            return
        await self.redis_client.hset(
            job_key,
            mapping={
                "progress_percentage": percentage,
                "chunks_processed": chunks_processed,
            },
        )

    async def _calculate_load(self) -> float:
        """Calculate current worker load based on GPU utilization"""
        try:
            import pynvml
            pynvml.nvmlInit()

            if self.embedding_config.gpu_id is not None:
                handle = pynvml.nvmlDeviceGetHandleByIndex(self.embedding_config.gpu_id)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                return util.gpu / 100.0

        except Exception:
            # Fallback to base implementation if GPU monitoring fails
            pass

        return await super()._calculate_load()

    def get_model_stats(self) -> Dict[str, Any]:
        """Get model usage and performance statistics"""
        stats = {
            "model_usage": self.model_usage_stats,
            "model_performance": self.model_performance,
            "cache_stats": self.cache.get_stats() if self.cache else None,
            "models_available": list(self.embedding_config.models_by_category.keys()),
            "model_selection_enabled": self.embedding_config.enable_model_selection,
            "caching_enabled": self.embedding_config.enable_caching
        }

        # Calculate most used model
        if self.model_usage_stats:
            most_used = max(self.model_usage_stats.items(), key=lambda x: x[1])
            stats["most_used_model"] = {
                "model": most_used[0],
                "count": most_used[1]
            }

        return stats

    async def clear_cache(self):
        """Clear the embedding cache"""
        if self.cache:
            self.cache.clear()
            logger.info("Embedding cache cleared")
            return {"status": "success", "message": "Cache cleared"}
        else:
            return {"status": "info", "message": "Caching is disabled"}

    async def warm_cache(self, texts: List[str], model: Optional[str] = None):
        """Pre-generate embeddings for frequently used texts"""
        if not self.cache:
            return {"status": "error", "message": "Caching is disabled"}

        model_to_use = model or self.embedding_config.default_model_name
        warmed_count = 0

        for text in texts:
            # Check if already cached
            if not self.cache.get(text, model_to_use):
                try:
                    # Generate embedding
                    config = self._get_model_config_for_name(model_to_use)
                    embeddings = await self._generate_embeddings(
                        [text],
                        config,
                        self.embedding_config.default_model_provider
                    )

                    # Cache it
                    embedding_list = embeddings[0].tolist() if isinstance(embeddings[0], np.ndarray) else embeddings[0]
                    self.cache.put(text, model_to_use, embedding_list)
                    warmed_count += 1

                except Exception as e:
                    logger.error(f"Failed to warm cache for text: {e}")

        return {
            "status": "success",
            "warmed_count": warmed_count,
            "total_requested": len(texts)
        }

    def _get_model_config_for_name(self, model_name: str):
        """Get model configuration for a specific model name"""
        def _requires_remote_code(model_name: str) -> bool:
            try:
                m = (model_name or "").lower()
                return "stella" in m
            except Exception:
                return False
        # Check if it's in our known models
        for category, model_info in self.embedding_config.models_by_category.items():
            if model_info.get("model") == model_name:
                provider = model_info.get("provider")
                if provider == "huggingface":
                    return HFModelCfg(model_name_or_path=model_name, trust_remote_code=_requires_remote_code(model_name))
                elif provider == "openai":
                    return OpenAIModelCfg(model_name_or_path=model_name)

        # Default to HuggingFace
        return HFModelCfg(model_name_or_path=model_name, trust_remote_code=_requires_remote_code(model_name))
