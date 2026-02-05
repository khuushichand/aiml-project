# async_chunker.py
"""
Asynchronous chunking implementation for improved I/O performance.
Provides async/await interfaces for chunking operations.
"""

import asyncio
import copy
from collections import OrderedDict
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional, Union

import aiofiles
from loguru import logger

from tldw_Server_API.app.core.exceptions import ValidationError
from tldw_Server_API.app.core.http_client import RetryPolicy, afetch

from .base import ChunkerConfig, ChunkResult
from .chunker import Chunker
from .exceptions import InvalidInputError
from .templates import TemplateManager
from .utils.metrics import get_metrics


async def _close_response(resp: Any) -> None:
    if resp is None:
        return
    close = getattr(resp, "aclose", None)
    if callable(close):
        await close()
        return
    close = getattr(resp, "close", None)
    if callable(close):
        close()


class AsyncChunker:
    """
    Asynchronous wrapper for the chunking system.
    Provides async interfaces for I/O-bound operations.
    """

    def __init__(
        self,
        config: Optional[ChunkerConfig] = None,
        llm_call_func: Optional[Any] = None,
        llm_config: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize async chunker.

        Args:
            config: Chunker configuration
            llm_call_func: Optional LLM function for LLM-dependent strategies
            llm_config: Optional LLM configuration for LLM-dependent strategies
        """
        self.config = config or ChunkerConfig()
        self._metrics = get_metrics()
        self._closed = False
        self._llm_call_func = llm_call_func
        self._llm_config = llm_config

        # Thread pool for CPU-bound operations
        self._executor = ThreadPoolExecutor(
            max_workers=self.config.max_workers if hasattr(self.config, 'max_workers') else 4
        )

        # Semaphore for rate limiting
        self._semaphore = asyncio.Semaphore(
            self.config.max_concurrent if hasattr(self.config, 'max_concurrent') else 10
        )

        logger.info("AsyncChunker initialized")

    def __del__(self):
        """Safety net to ensure executor is cleaned up if close() was not called."""
        if not self._closed and hasattr(self, '_executor') and self._executor is not None:
            try:
                self._executor.shutdown(wait=False)
                logger.warning("AsyncChunker.__del__: executor was not properly closed, shutting down now")
            except Exception as e:
                logger.debug(f"AsyncChunker.__del__: error during cleanup: {e}")

    def _get_chunker(
        self,
        *,
        llm_call_func: Optional[Any] = None,
        llm_config: Optional[dict[str, Any]] = None,
    ) -> Chunker:
        """Return a fresh Chunker instance per call to avoid shared mutable state."""
        cfg_copy = copy.deepcopy(self.config)
        effective_llm_call = self._llm_call_func if llm_call_func is None else llm_call_func
        effective_llm_cfg = self._llm_config if llm_config is None else llm_config
        return Chunker(config=cfg_copy, llm_call_func=effective_llm_call, llm_config=effective_llm_cfg)

    async def chunk_text(self,
                        text: str,
                        method: Optional[str] = None,
                        max_size: Optional[int] = None,
                        overlap: Optional[int] = None,
                        llm_call_func: Optional[Any] = None,
                        llm_config: Optional[dict[str, Any]] = None,
                        **options) -> list[str]:
        """
        Asynchronously chunk text.

        Args:
            text: Text to chunk
            method: Chunking method
            max_size: Maximum chunk size
            overlap: Overlap between chunks
            llm_call_func: Optional per-call LLM function override
            llm_config: Optional per-call LLM config override
            **options: Additional options

        Returns:
            List of text chunks
        """
        async with self._semaphore:
            loop = asyncio.get_running_loop()

            def _run_chunking():
                chunker = self._get_chunker(llm_call_func=llm_call_func, llm_config=llm_config)
                return chunker.chunk_text(
                    text,
                    method,
                    max_size,
                    overlap,
                    **options,
                )

            return await loop.run_in_executor(self._executor, _run_chunking)

    async def chunk_file(self,
                        file_path: Union[str, Path],
                        method: Optional[str] = None,
                        max_size: Optional[int] = None,
                        overlap: Optional[int] = None,
                        encoding: str = 'utf-8',
                        **options) -> list[str]:
        """
        Asynchronously read and chunk a file.

        Args:
            file_path: Path to file
            method: Chunking method
            max_size: Maximum chunk size
            overlap: Overlap between chunks
            encoding: File encoding
            **options: Additional options

        Returns:
            List of text chunks
        """
        file_path = Path(file_path)

        # Read file asynchronously
        async with aiofiles.open(file_path, encoding=encoding) as f:
            text = await f.read()

        # Chunk the text
        return await self.chunk_text(text, method, max_size, overlap, **options)

    async def chunk_files(self,
                         file_paths: list[Union[str, Path]],
                         method: Optional[str] = None,
                         max_size: Optional[int] = None,
                         overlap: Optional[int] = None,
                         encoding: str = 'utf-8',
                         **options) -> dict[str, list[str]]:
        """
        Asynchronously chunk multiple files.

        Args:
            file_paths: List of file paths
            method: Chunking method
            max_size: Maximum chunk size
            overlap: Overlap between chunks
            encoding: File encoding
            **options: Additional options

        Returns:
            Dictionary mapping file paths to their chunks
        """
        tasks = []
        for file_path in file_paths:
            task = self.chunk_file(
                file_path, method, max_size, overlap, encoding, **options
            )
            tasks.append(task)

        # Process files concurrently
        results = await asyncio.gather(*tasks)

        # Create result dictionary
        return {
            str(file_path): chunks
            for file_path, chunks in zip(file_paths, results)
        }

    async def chunk_stream(self,
                          text_stream: AsyncGenerator[str, None],
                          method: Optional[str] = None,
                          max_size: Optional[int] = None,
                          overlap: Optional[int] = None,
                          buffer_size: int = 10000,
                          llm_call_func: Optional[Any] = None,
                          llm_config: Optional[dict[str, Any]] = None,
                          **options) -> AsyncGenerator[str, None]:
        """
        Stream chunks from an async text generator.

        Args:
            text_stream: Async generator yielding text
            method: Chunking method
            max_size: Maximum chunk size
            overlap: Overlap between chunks
            buffer_size: Size of text buffer
            llm_call_func: Optional per-call LLM function override
            llm_config: Optional per-call LLM config override
            **options: Additional options

        Yields:
            Text chunks as they are generated

        Notes:
            Streaming overlap and boundary behavior is method-aware (e.g.,
            `words` vs `sentences`) and may withhold the final chunk per
            buffer. See “Streaming Overlap Semantics” in
            tldw_Server_API/app/core/Chunking/README.md for reassembly and
            deduplication guidance.
        """
        buffer = ""
        overlap_buffer = ""
        max_size_raw = max_size if max_size is not None else self.config.default_max_size
        try:
            max_size_value = int(max_size_raw)
        except Exception as exc:
            raise InvalidInputError(f"Invalid max_size value: {max_size_raw}") from exc
        if max_size_value <= 0:
            raise InvalidInputError(f"max_size must be positive, got {max_size_value}")
        overlap_default = getattr(self.config, 'default_overlap', 0)
        overlap_raw = overlap if overlap is not None else overlap_default
        try:
            overlap_size = int(overlap_raw)
        except Exception as exc:
            raise InvalidInputError(f"Invalid overlap value: {overlap_raw}") from exc
        if overlap_size < 0:
            overlap_size = 0
        if overlap_size >= max_size_value:
            overlap_size = max_size_value - 1
        overlap = overlap_size
        base_method = method if method is not None else self.config.default_method.value
        normalized_method = Chunker._normalize_method_argument(base_method)
        method_name = normalized_method or str(base_method)
        method_lower = method_name.lower()
        language = options.get('language') or self.config.language
        language_lower = str(language or "").lower()
        space_delimited_methods = {
            'words', 'sentences', 'paragraphs', 'semantic', 'tokens',
            'propositions', 'structure_aware', 'code', 'fixed_size',
        }
        languages_no_space = {'zh', 'zh-cn', 'zh-tw', 'ja', 'th'}
        ws_chars = (' ', '\t', '\n', '\r', '\v', '\f')

        def _needs_space_separator(prefix: str, suffix: str) -> bool:
            if not prefix or not suffix:
                return False
            if suffix[0].isspace() or prefix.endswith(ws_chars):
                return False
            if language_lower in languages_no_space:
                return False
            return method_lower == 'words' or method_lower in space_delimited_methods

        def _should_withhold_last_chunk() -> bool:
            """Whether to carry the final chunk forward instead of emitting it immediately."""
            if overlap_size <= 0:
                return False
            return method_lower != 'words'

        withhold_last = _should_withhold_last_chunk()

        def _coerce_overlap_value(value: Any) -> str:
            """Ensure overlap carry-over stays textual even for structured chunks."""
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                text_val = value.get('text') or value.get('content')
                if isinstance(text_val, str):
                    return text_val
            try:
                return str(value) if value is not None else ""
            except Exception:
                return ""

        async for text_piece in text_stream:
            buffer += text_piece

            # Process buffer only when it's large enough
            if len(buffer) < buffer_size:
                continue

            # Chunk the buffer using precise boundary concatenation
            overlap_text = _coerce_overlap_value(overlap_buffer)
            sep = ' ' if _needs_space_separator(overlap_text, buffer) else ''
            combined = overlap_text + sep + buffer
            chunks = await self.chunk_text(
                combined,
                method, max_size_value, overlap,
                llm_call_func=llm_call_func,
                llm_config=llm_config,
                **options
            )

            # Streaming overlap handling:
            # - words + overlap>0: emit all and carry overlap tail
            # - otherwise: emit all but last, carry the last chunk forward
            if withhold_last:
                for chunk in chunks[:-1]:
                    yield chunk
                withheld = chunks[-1] if chunks else None
                overlap_buffer = _coerce_overlap_value(withheld) if withheld else ""
            else:
                for chunk in chunks:
                    yield chunk
                if chunks:
                    try:
                        chunker = self._get_chunker(llm_call_func=llm_call_func, llm_config=llm_config)
                        overlap_buffer = chunker._compute_overlap_buffer_text(  # noqa: SLF001
                            combined,
                            method_name,
                            overlap_size,
                            language,
                            options,
                        )
                    except Exception:
                        overlap_buffer = _coerce_overlap_value(chunks[-1])
                else:
                    overlap_buffer = ''

            buffer = ""

        # Process remaining buffer; flush overlap-only tail when we withheld the last chunk.
        should_flush = bool(buffer)
        if not should_flush and overlap_buffer and withhold_last:
            should_flush = True
        if should_flush:
            overlap_text = _coerce_overlap_value(overlap_buffer)
            sep = ' ' if _needs_space_separator(overlap_text, buffer) else ''
            combined = overlap_text + sep + buffer
            chunks = await self.chunk_text(
                combined,
                method, max_size_value, overlap,
                llm_call_func=llm_call_func,
                llm_config=llm_config,
                **options
            )
            for chunk in chunks:
                yield chunk

    async def chunk_with_metadata(self,
                                 text: str,
                                 method: Optional[str] = None,
                                 max_size: Optional[int] = None,
                                 overlap: Optional[int] = None,
                                 llm_call_func: Optional[Any] = None,
                                 llm_config: Optional[dict[str, Any]] = None,
                                 **options) -> list[ChunkResult]:
        """
        Asynchronously chunk text and return with metadata.

        Args:
            text: Text to chunk
            method: Chunking method
            max_size: Maximum chunk size
            overlap: Overlap between chunks
            llm_call_func: Optional per-call LLM function override
            llm_config: Optional per-call LLM config override
            **options: Additional options

        Returns:
            List of ChunkResult objects
        """
        async with self._semaphore:
            loop = asyncio.get_running_loop()

            def _run_chunking():
                chunker = self._get_chunker(llm_call_func=llm_call_func, llm_config=llm_config)
                return chunker.chunk_text_with_metadata(
                    text,
                    method,
                    max_size,
                    overlap,
                    **options,
                )

            return await loop.run_in_executor(self._executor, _run_chunking)

    async def chunk_url(self,
                       url: str,
                       method: Optional[str] = None,
                       max_size: Optional[int] = None,
                       overlap: Optional[int] = None,
                       timeout: float = 30.0,
                       **options) -> list[str]:
        """
        Asynchronously fetch and chunk content from URL.

        Args:
            url: URL to fetch content from
            method: Chunking method
            max_size: Maximum chunk size
            overlap: Overlap between chunks
            timeout: HTTP request timeout in seconds (default: 30.0)
            **options: Additional options

        Returns:
            List of text chunks
        """
        resp = None
        retry_policy = RetryPolicy(attempts=1, retry_on_unsafe=False)
        try:
            resp = await afetch(
                method="GET",
                url=url,
                timeout=timeout,
                retry=retry_policy,
            )
            text = resp.text
        finally:
            await _close_response(resp)

        return await self.chunk_text(text, method, max_size, overlap, **options)

    async def process_with_template(self,
                                   text: str,
                                   template_name: str,
                                   **options) -> list[dict[str, Any]]:
        """
        Process text using a template asynchronously.

        Args:
            text: Text to process
            template_name: Name of template to use
            **options: Additional options

        Returns:
            List of processed chunks as dictionaries with 'text' and 'metadata'
        """
        # Get template manager
        if not hasattr(self, '_template_manager'):
            self._template_manager = TemplateManager()

        # Process in executor (ensure keyword options are passed correctly)
        import functools
        loop = asyncio.get_running_loop()
        func = functools.partial(self._template_manager.process, text, template_name, **options)
        chunks = await loop.run_in_executor(self._executor, func)
        return chunks

    async def close(self):
        """Clean up resources."""
        if self._closed:
            return
        self._closed = True
        try:
            self._executor.shutdown(wait=True)
        except RuntimeError as e:
            logger.debug(f"AsyncChunker.close: executor shutdown error (may already be shutdown): {e}")
        logger.info("AsyncChunker closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit. Preserves original exception if close() also raises."""
        try:
            await self.close()
        except Exception as close_error:
            if exc_type is None:
                # No exception in context, so raise the close error
                raise
            # There was an exception in context; log close error and let original propagate
            logger.warning(f"AsyncChunker.__aexit__: error during cleanup (original exception preserved): {close_error}")


class AsyncBatchProcessor:
    """
    Process multiple chunking requests in batches for efficiency.

    Note: Caller must call stop_processing() or use as async context manager
    to ensure proper resource cleanup.
    """

    def __init__(self,
                batch_size: int = 10,
                max_concurrent: int = 5,
                max_results: Optional[int] = 1000):
        """
        Initialize batch processor.

        Args:
            batch_size: Number of items to process per batch
            max_concurrent: Maximum concurrent batches
            max_results: Maximum results to retain (oldest evicted). None for unlimited.
        """
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self._chunker = AsyncChunker()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._results: OrderedDict[str, dict[str, Any]] = OrderedDict()
        if max_results is not None:
            try:
                max_results = int(max_results)
            except Exception as exc:
                raise ValidationError(
                    f"max_results must be an int or None, got {max_results}"
                ) from exc
            if max_results <= 0:
                raise ValidationError(f"max_results must be positive or None, got {max_results}")
        self._max_results = max_results
        self._processing = False
        self._closed = False

        logger.info(f"AsyncBatchProcessor initialized with batch_size={batch_size}")

    def __del__(self):
        """Safety net for cleanup if stop_processing() was not called."""
        if not self._closed and hasattr(self, '_chunker'):
            logger.warning("AsyncBatchProcessor.__del__: processor was not properly stopped")

    async def add_request(self,
                         request_id: str,
                         text: str,
                         method: str = 'words',
                         **options):
        """
        Add a chunking request to the queue.

        Args:
            request_id: Unique request identifier
            text: Text to chunk
            method: Chunking method
            **options: Additional options
        """
        await self._queue.put({
            'id': request_id,
            'text': text,
            'method': method,
            'options': options
        })

    def _store_result(self, request_id: str, payload: dict[str, Any]) -> None:
        """Store a result with eviction of oldest entries when capped."""
        if request_id in self._results:
            self._results.pop(request_id, None)
        self._results[request_id] = payload
        if self._max_results is not None:
            while len(self._results) > self._max_results:
                self._results.popitem(last=False)

    async def process_batch(self, initial_request: Optional[dict[str, Any]] = None):
        """Process a batch of requests."""
        batch: list[dict[str, Any]] = []
        if initial_request is not None:
            batch.append(initial_request)

        # Collect batch
        while len(batch) < self.batch_size:
            try:
                request = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            batch.append(request)

        if not batch:
            return

        # Process batch concurrently
        tasks = []
        for request in batch:
            task = self._chunker.chunk_text(
                request['text'],
                request['method'],
                **request['options']
            )
            tasks.append(task)

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Store results
            for request, result in zip(batch, results, strict=True):
                if isinstance(result, Exception):
                    logger.error(f"Error processing request {request['id']}: {result}")
                    self._store_result(request['id'], {'error': str(result)})
                else:
                    self._store_result(request['id'], {'chunks': result})
        finally:
            for _ in batch:
                try:
                    self._queue.task_done()
                except ValueError:
                    # task_done called too many times; ignore to avoid raising in cleanup
                    pass

    async def start_processing(self):
        """Start processing requests from the queue."""
        self._processing = True

        while self._processing:
            try:
                first = await asyncio.wait_for(self._queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            # Process multiple batches concurrently
            batch_tasks = [self.process_batch(first)]
            for _ in range(self.max_concurrent - 1):
                try:
                    req = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                batch_tasks.append(self.process_batch(req))

            if batch_tasks:
                await asyncio.gather(*batch_tasks)

    async def stop_processing(self):
        """Stop processing requests and clean up resources."""
        if self._closed:
            return
        self._processing = False

        # Process remaining requests
        while True:
            try:
                req = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            await self.process_batch(req)

        try:
            await self._chunker.close()
        except Exception as e:
            logger.warning(f"AsyncBatchProcessor.stop_processing: error closing chunker: {e}")
        self._closed = True

    def get_result(self, request_id: str) -> Optional[dict[str, Any]]:
        """
        Get result for a request.

        Args:
            request_id: Request identifier

        Returns:
            Result dictionary or None if not ready
        """
        return self._results.get(request_id)

    async def wait_for_result(self,
                             request_id: str,
                             timeout: float = 30.0) -> Optional[dict[str, Any]]:
        """
        Wait for a result to be ready.

        Args:
            request_id: Request identifier
            timeout: Maximum wait time in seconds

        Returns:
            Result dictionary or None if timeout
        """
        start_time = asyncio.get_running_loop().time()

        while asyncio.get_running_loop().time() - start_time < timeout:
            result = self.get_result(request_id)
            if result is not None:
                return result
            await asyncio.sleep(0.1)

        return None


async def chunk_parallel(texts: list[str],
                        method: str = 'words',
                        max_size: int = 400,
                        overlap: int = 50,
                        max_concurrent: int = 10,
                        **options) -> list[list[str]]:
    """
    Chunk multiple texts in parallel.

    Args:
        texts: List of texts to chunk
        method: Chunking method
        max_size: Maximum chunk size
        overlap: Overlap between chunks
        max_concurrent: Maximum concurrent operations
        **options: Additional options

    Returns:
        List of chunk lists
    """
    async with AsyncChunker() as chunker:
        # Limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def chunk_with_limit(text):
            async with semaphore:
                return await chunker.chunk_text(
                    text, method, max_size, overlap, **options
                )

        tasks = [chunk_with_limit(text) for text in texts]
        return await asyncio.gather(*tasks)


async def stream_chunks_from_file(file_path: Union[str, Path],
                                 method: str = 'words',
                                 max_size: int = 400,
                                 overlap: int = 50,
                                 chunk_size: int = 1024 * 1024,  # 1MB
                                 **options) -> AsyncGenerator[str, None]:
    """
    Stream chunks from a large file without loading it entirely into memory.

    Args:
        file_path: Path to file
        method: Chunking method
        max_size: Maximum chunk size
        overlap: Overlap between chunks
        chunk_size: Size of file chunks to read
        **options: Additional options

    Yields:
        Text chunks
    """
    async def file_reader():
        async with aiofiles.open(file_path, encoding='utf-8') as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    async with AsyncChunker() as chunker:
        async for chunk in chunker.chunk_stream(
            file_reader(), method, max_size, overlap, **options
        ):
            yield chunk
