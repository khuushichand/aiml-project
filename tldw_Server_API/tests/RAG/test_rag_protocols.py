"""Unit tests for rag_protocols – runtime-checkable Protocol interfaces.

Verifies that:
- Conforming classes satisfy ``isinstance()`` checks (duck typing, no inheritance).
- Non-conforming classes (missing required methods) fail ``isinstance()`` checks.
- The ``LLMProtocol`` no longer requires an ``is_local`` attribute.
"""

from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.core.RAG.rag_service.rag_protocols import (
    CacheProtocol,
    EvaluatorProtocol,
    LLMProtocol,
    RAGPipelineProtocol,
    RerankerProtocol,
    VectorStoreProtocol,
)


# ---------------------------------------------------------------------------
# Conforming mock classes -- no base classes, pure duck typing
# ---------------------------------------------------------------------------


class _MockLLM:
    """Matches LLMProtocol."""

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        return "response"


class _MockVectorStore:
    """Matches VectorStoreProtocol."""

    async def search(
        self,
        query_embedding: list[float],
        k: int = 10,
        **kwargs: Any,
    ) -> list[tuple[Any, float]]:
        return []

    async def add(self, documents: list[Any], **kwargs: Any) -> None:
        pass


class _MockEvaluator:
    """Matches EvaluatorProtocol."""

    async def evaluate(
        self,
        response: str,
        context: str,
        query: str | None = None,
    ) -> float:
        return 1.0


class _MockCache:
    """Matches CacheProtocol."""

    async def get(self, query: str, **kwargs: Any) -> Any | None:
        return None

    async def set(self, query: str, value: Any, **kwargs: Any) -> None:
        pass

    def get_stats(self) -> dict[str, Any]:
        return {"hits": 0, "misses": 0}


class _MockReranker:
    """Matches RerankerProtocol."""

    async def rerank(
        self,
        query: str,
        documents: list[Any],
        top_k: int = 10,
    ) -> list[tuple[Any, float]]:
        return []


class _MockRAGPipeline:
    """Matches RAGPipelineProtocol."""

    async def query(self, question: str) -> Any:
        return {"answer": "42"}


# ---------------------------------------------------------------------------
# Non-conforming classes -- each is missing one or more required methods
# ---------------------------------------------------------------------------


class _BadLLM:
    """Missing ``generate`` method."""

    async def complete(self, prompt: str) -> str:
        return ""


class _BadVectorStoreMissingAdd:
    """Has ``search`` but missing ``add``."""

    async def search(
        self, query_embedding: list[float], k: int = 10, **kwargs: Any
    ) -> list[tuple[Any, float]]:
        return []


class _BadVectorStoreMissingSearch:
    """Has ``add`` but missing ``search``."""

    async def add(self, documents: list[Any], **kwargs: Any) -> None:
        pass


class _BadEvaluator:
    """Missing ``evaluate`` method."""

    async def score(self, response: str, context: str) -> float:
        return 0.0


class _BadCacheMissingSet:
    """Has ``get`` and ``get_stats`` but missing ``set``."""

    async def get(self, query: str, **kwargs: Any) -> Any | None:
        return None

    def get_stats(self) -> dict[str, Any]:
        return {}


class _BadCacheMissingGetStats:
    """Has ``get`` and ``set`` but missing ``get_stats``."""

    async def get(self, query: str, **kwargs: Any) -> Any | None:
        return None

    async def set(self, query: str, value: Any, **kwargs: Any) -> None:
        pass


class _BadReranker:
    """Missing ``rerank`` method."""

    async def sort(self, query: str, docs: list[Any]) -> list[Any]:
        return []


class _BadRAGPipeline:
    """Missing ``query`` method."""

    async def ask(self, question: str) -> Any:
        return {}


# ---------------------------------------------------------------------------
# Conforming-instance tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLLMProtocolConforms:
    def test_conforming_class_is_instance(self) -> None:
        assert isinstance(_MockLLM(), LLMProtocol)

    def test_duck_typed_class_no_inheritance(self) -> None:
        """The mock does not inherit from LLMProtocol."""
        assert LLMProtocol not in type(_MockLLM()).__mro__


@pytest.mark.unit
class TestVectorStoreProtocolConforms:
    def test_conforming_class_is_instance(self) -> None:
        assert isinstance(_MockVectorStore(), VectorStoreProtocol)

    def test_duck_typed_class_no_inheritance(self) -> None:
        assert VectorStoreProtocol not in type(_MockVectorStore()).__mro__


@pytest.mark.unit
class TestEvaluatorProtocolConforms:
    def test_conforming_class_is_instance(self) -> None:
        assert isinstance(_MockEvaluator(), EvaluatorProtocol)

    def test_duck_typed_class_no_inheritance(self) -> None:
        assert EvaluatorProtocol not in type(_MockEvaluator()).__mro__


@pytest.mark.unit
class TestCacheProtocolConforms:
    def test_conforming_class_is_instance(self) -> None:
        assert isinstance(_MockCache(), CacheProtocol)

    def test_duck_typed_class_no_inheritance(self) -> None:
        assert CacheProtocol not in type(_MockCache()).__mro__


@pytest.mark.unit
class TestRerankerProtocolConforms:
    def test_conforming_class_is_instance(self) -> None:
        assert isinstance(_MockReranker(), RerankerProtocol)

    def test_duck_typed_class_no_inheritance(self) -> None:
        assert RerankerProtocol not in type(_MockReranker()).__mro__


@pytest.mark.unit
class TestRAGPipelineProtocolConforms:
    def test_conforming_class_is_instance(self) -> None:
        assert isinstance(_MockRAGPipeline(), RAGPipelineProtocol)

    def test_duck_typed_class_no_inheritance(self) -> None:
        assert RAGPipelineProtocol not in type(_MockRAGPipeline()).__mro__


# ---------------------------------------------------------------------------
# Non-conforming-instance tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLLMProtocolRejects:
    def test_missing_generate(self) -> None:
        assert not isinstance(_BadLLM(), LLMProtocol)

    def test_empty_class(self) -> None:
        assert not isinstance(object(), LLMProtocol)


@pytest.mark.unit
class TestVectorStoreProtocolRejects:
    def test_missing_add(self) -> None:
        assert not isinstance(_BadVectorStoreMissingAdd(), VectorStoreProtocol)

    def test_missing_search(self) -> None:
        assert not isinstance(_BadVectorStoreMissingSearch(), VectorStoreProtocol)

    def test_empty_class(self) -> None:
        assert not isinstance(object(), VectorStoreProtocol)


@pytest.mark.unit
class TestEvaluatorProtocolRejects:
    def test_missing_evaluate(self) -> None:
        assert not isinstance(_BadEvaluator(), EvaluatorProtocol)

    def test_empty_class(self) -> None:
        assert not isinstance(object(), EvaluatorProtocol)


@pytest.mark.unit
class TestCacheProtocolRejects:
    def test_missing_set(self) -> None:
        assert not isinstance(_BadCacheMissingSet(), CacheProtocol)

    def test_missing_get_stats(self) -> None:
        assert not isinstance(_BadCacheMissingGetStats(), CacheProtocol)

    def test_empty_class(self) -> None:
        assert not isinstance(object(), CacheProtocol)


@pytest.mark.unit
class TestRerankerProtocolRejects:
    def test_missing_rerank(self) -> None:
        assert not isinstance(_BadReranker(), RerankerProtocol)

    def test_empty_class(self) -> None:
        assert not isinstance(object(), RerankerProtocol)


@pytest.mark.unit
class TestRAGPipelineProtocolRejects:
    def test_missing_query(self) -> None:
        assert not isinstance(_BadRAGPipeline(), RAGPipelineProtocol)

    def test_empty_class(self) -> None:
        assert not isinstance(object(), RAGPipelineProtocol)


# ---------------------------------------------------------------------------
# LLMProtocol: is_local attribute no longer required
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLLMProtocolNoIsLocal:
    """Verify that ``is_local`` is not part of the protocol contract.

    Earlier revisions of the protocol required an ``is_local: bool``
    attribute. This was removed; confirm the protocol does not enforce it.
    """

    def test_class_without_is_local_conforms(self) -> None:
        """A class with only ``generate`` should satisfy LLMProtocol."""
        assert isinstance(_MockLLM(), LLMProtocol)
        assert not hasattr(_MockLLM(), "is_local")

    def test_class_with_is_local_still_conforms(self) -> None:
        """Extra attributes should not break conformance."""

        class _LLMWithIsLocal:
            is_local: bool = True

            async def generate(self, prompt: str, **kwargs: Any) -> str:
                return "local response"

        assert isinstance(_LLMWithIsLocal(), LLMProtocol)


# ---------------------------------------------------------------------------
# Cross-protocol: arbitrary plain class with multiple conformances
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMultiProtocolConformance:
    """A single class can satisfy multiple protocols simultaneously."""

    def test_class_conforms_to_multiple_protocols(self) -> None:

        class _MultiTool:
            async def generate(self, prompt: str, **kwargs: Any) -> str:
                return ""

            async def evaluate(
                self, response: str, context: str, query: str | None = None
            ) -> float:
                return 0.5

        obj = _MultiTool()
        assert isinstance(obj, LLMProtocol)
        assert isinstance(obj, EvaluatorProtocol)
        # But not the others
        assert not isinstance(obj, VectorStoreProtocol)
        assert not isinstance(obj, CacheProtocol)
        assert not isinstance(obj, RerankerProtocol)
        assert not isinstance(obj, RAGPipelineProtocol)
