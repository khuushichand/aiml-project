"""Protocol-based interfaces for the RAG pipeline.

Uses Python's ``Protocol`` with ``@runtime_checkable`` for all new interfaces.
Any class matching the method signatures works -- no inheritance required.

Existing ABCs (``VectorStoreAdapter``, ``QueryExpansionStrategy``) are
left untouched; these protocols are for new components going forward.

Benefits over ABCs:
- No inheritance required (duck typing)
- Easier testing (mock objects don't need to inherit from anything)
- Better third-party integration (users can make adapters without
  importing base classes)

Ported from RAGnarok-AI's protocol pattern, adapted for tldw_server2.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProtocol(Protocol):
    """Protocol for LLM providers.

    Any class implementing an async ``generate`` method works.
    The ``embed`` method is optional for providers that also support
    embeddings.
    """

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from a prompt.

        Args:
            prompt: The input prompt for text generation.
            **kwargs: Additional provider-specific options.

        Returns:
            The generated text response.
        """
        ...


@runtime_checkable
class VectorStoreProtocol(Protocol):
    """Protocol for vector store providers.

    Any class implementing ``search`` and ``add`` methods works.
    """

    async def search(
        self,
        query_embedding: list[float],
        k: int = 10,
        **kwargs: Any,
    ) -> list[tuple[Any, float]]:
        """Search for similar documents.

        Args:
            query_embedding: The embedding vector to search with.
            k: Number of results to return. Defaults to 10.
            **kwargs: Additional provider-specific options.

        Returns:
            A list of tuples containing (document, similarity_score),
            sorted by similarity in descending order.
        """
        ...

    async def add(self, documents: list[Any], **kwargs: Any) -> None:
        """Add documents to the vector store.

        Args:
            documents: List of documents to add.
            **kwargs: Additional provider-specific options.
        """
        ...


@runtime_checkable
class EvaluatorProtocol(Protocol):
    """Protocol for metric evaluators.

    Any class implementing this method can be used as an evaluator
    without needing to inherit from a base class.
    """

    async def evaluate(
        self,
        response: str,
        context: str,
        query: str | None = None,
    ) -> float:
        """Evaluate a response against its context.

        Args:
            response: The generated response to evaluate.
            context: The retrieved context used for generation.
            query: Optional original query for relevance evaluation.

        Returns:
            A score between 0.0 and 1.0, where 1.0 is the best.
        """
        ...


@runtime_checkable
class CacheProtocol(Protocol):
    """Protocol for cache implementations.

    Any class with ``get``, ``set``, and ``get_stats`` methods works.
    Signature is intentionally flexible (``**kwargs``) to accommodate
    both key-based and query-based caches.
    """

    async def get(self, query: str, **kwargs: Any) -> Any | None:
        """Retrieve a cached value.

        Args:
            query: Cache key or query string.
            **kwargs: Additional options (e.g. ``use_semantic``).

        Returns:
            The cached value, or None if not found.
        """
        ...

    async def set(self, query: str, value: Any, **kwargs: Any) -> None:
        """Store a value in the cache.

        Args:
            query: Cache key or query string.
            value: Value to cache.
            **kwargs: Additional options (e.g. ``ttl``).
        """
        ...

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics (hits, misses, hit_rate, etc.).

        Returns:
            Dictionary with cache statistics.
        """
        ...


@runtime_checkable
class RerankerProtocol(Protocol):
    """Protocol for reranking implementations.

    Any class with an async ``rerank`` method works.
    """

    async def rerank(
        self,
        query: str,
        documents: list[Any],
        top_k: int = 10,
    ) -> list[tuple[Any, float]]:
        """Rerank documents for a query.

        Args:
            query: The search query.
            documents: List of documents to rerank.
            top_k: Number of top results to return.

        Returns:
            Reranked list of (document, score) tuples.
        """
        ...


@runtime_checkable
class RAGPipelineProtocol(Protocol):
    """Protocol for RAG pipeline implementations."""

    async def query(self, question: str) -> Any:
        """Execute RAG pipeline and return response with retrieved docs.

        Args:
            question: The question or query to answer.

        Returns:
            Response containing the answer and retrieved documents.
        """
        ...
