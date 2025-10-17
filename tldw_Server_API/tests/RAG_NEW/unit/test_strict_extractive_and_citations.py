import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline
from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource


@pytest.mark.unit
class TestStrictExtractiveHardCitations:
    @pytest.mark.asyncio
    async def test_strict_extractive_builds_from_docs_full_coverage(self):
        """When strict_extractive=True, answer is assembled from doc sentences; full coverage should not gate generation."""
        # Stub retrieval to return a single doc with two sentences containing the query term
        doc = Document(
            id="d1",
            content="RAG helps answer questions. It grounds responses in retrieved documents.",
            metadata={"source": "media_db"},
            source=DataSource.MEDIA_DB,
            score=0.9,
        )

        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_ret, \
             patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.build_hard_citations') as mock_hc:
            m = MagicMock()
            m.retrieve = AsyncMock(return_value=[doc])
            mock_ret.return_value = m

            # Full coverage from hard citations -> no gate
            mock_hc.return_value = {"coverage": 1.0, "sentences": []}

            res = await unified_rag_pipeline(
                query="What is RAG?",
                top_k=3,
                enable_generation=True,
                strict_extractive=True,
                require_hard_citations=True,
                low_confidence_behavior="continue",
            )

            assert res.generated_answer is not None and len(res.generated_answer.strip()) > 0
            assert isinstance(res.metadata.get("hard_citations"), dict)
            assert float(res.metadata["hard_citations"].get("coverage", 0.0)) >= 0.99
            # No gating when coverage is complete
            gate = res.metadata.get("generation_gate") if isinstance(res.metadata, dict) else None
            assert not gate, "generation_gate should not be set when coverage is full"

    @pytest.mark.asyncio
    async def test_strict_extractive_missing_coverage_behavior_ask(self):
        """When coverage < 1.0 and require_hard_citations=True with behavior=ask, append a note and mark gate."""
        doc = Document(
            id="d2",
            content="RAG is useful. It provides grounded answers.",
            metadata={"source": "media_db"},
            source=DataSource.MEDIA_DB,
            score=0.85,
        )

        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_ret, \
             patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.build_hard_citations') as mock_hc:
            m = MagicMock()
            m.retrieve = AsyncMock(return_value=[doc])
            mock_ret.return_value = m

            # Incomplete coverage
            mock_hc.return_value = {"coverage": 0.6, "sentences": []}

            res = await unified_rag_pipeline(
                query="RAG",
                top_k=2,
                enable_generation=True,
                strict_extractive=True,
                require_hard_citations=True,
                low_confidence_behavior="ask",
            )

            gate = res.metadata.get("generation_gate") if isinstance(res.metadata, dict) else None
            assert gate and gate.get("reason") == "missing_hard_citations"
            assert res.generated_answer is not None
            assert "[Note]" in res.generated_answer, "Expected appended note for ask behavior"

    @pytest.mark.asyncio
    async def test_strict_extractive_missing_coverage_behavior_decline(self):
        """When coverage < 1.0 and behavior=decline, respond with an explicit insufficiency message."""
        doc = Document(
            id="d3",
            content="RAG can be strict. It adheres to sources.",
            metadata={"source": "media_db"},
            source=DataSource.MEDIA_DB,
            score=0.8,
        )

        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_ret, \
             patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.build_hard_citations') as mock_hc:
            m = MagicMock()
            m.retrieve = AsyncMock(return_value=[doc])
            mock_ret.return_value = m

            mock_hc.return_value = {"coverage": 0.5, "sentences": []}

            res = await unified_rag_pipeline(
                query="strict",
                enable_generation=True,
                strict_extractive=True,
                require_hard_citations=True,
                low_confidence_behavior="decline",
            )

            gate = res.metadata.get("generation_gate") if isinstance(res.metadata, dict) else None
            assert gate and gate.get("reason") == "missing_hard_citations"
            assert res.generated_answer == "Insufficient evidence: missing citations for some statements."

    @pytest.mark.asyncio
    async def test_strict_extractive_env_toggle_default(self, monkeypatch):
        """If env toggles strict extractive on, pipeline should skip AnswerGenerator even when request omits the flag."""
        monkeypatch.setenv("RAG_STRICT_EXTRACTIVE", "1")

        doc = Document(
            id="d4",
            content="RAG enforces grounding. Answers quote retrieved spans.",
            metadata={"source": "media_db"},
            source=DataSource.MEDIA_DB,
            score=0.92,
        )

        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_ret, \
             patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.build_hard_citations') as mock_hc, \
             patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.AnswerGenerator') as mock_gen:
            m = MagicMock()
            m.retrieve = AsyncMock(return_value=[doc])
            mock_ret.return_value = m

            mock_hc.return_value = {"coverage": 1.0, "sentences": []}

            res = await unified_rag_pipeline(
                query="grounded",
                enable_generation=True,
                # Do not pass strict_extractive so it defaults False, expecting env helper to flip it on
                require_hard_citations=True,
            )

            # Env-driven strict mode should avoid LLM generation
            assert mock_gen.call_count == 0
            assert res.generated_answer and "ground" in res.generated_answer.lower()

        monkeypatch.delenv("RAG_STRICT_EXTRACTIVE", raising=False)


@pytest.mark.unit
class TestNLIGatingBehavior:
    class _FakeOutcome:
        unsupported_ratio = 0.6
        total_claims = 5
        unsupported_count = 3
        fixed = False
        reason = "low_confidence"
        new_answer = None
        claims = None
        summary = None

    class _FakeVerifier:
        def __init__(self, *_, **__):
            pass

        async def verify_and_maybe_fix(self, *_, **__):
            return TestNLIGatingBehavior._FakeOutcome()

    @pytest.mark.asyncio
    async def test_nli_low_confidence_ask_appends_note(self):
        doc = Document(
            id="nli1",
            content="RAG pipelines rely on grounded evidence for answers.",
            metadata={"source": "media_db"},
            source=DataSource.MEDIA_DB,
            score=0.9,
        )

        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_ret, \
             patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.build_hard_citations') as mock_hc, \
             patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.AnswerGenerator') as mock_gen, \
             patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.PostGenerationVerifier', return_value=self._FakeVerifier()):
            m = MagicMock()
            m.retrieve = AsyncMock(return_value=[doc])
            mock_ret.return_value = m
            mock_hc.return_value = {"coverage": 1.0, "sentences": []}

            gen = MagicMock()
            gen.generate = AsyncMock(return_value={"answer": "Grounded draft answer."})
            mock_gen.return_value = gen

            res = await unified_rag_pipeline(
                query="How does RAG ensure fidelity?",
                enable_generation=True,
                enable_post_verification=True,
                adaptive_unsupported_threshold=0.2,
                low_confidence_behavior="ask",
            )

            gate = res.metadata.get("generation_gate") if isinstance(res.metadata, dict) else None
            assert gate and gate.get("reason") == "nli_low_confidence"
            assert pytest.approx(gate.get("unsupported_ratio"), rel=0.0) == 0.6
            assert "[Note] Evidence is insufficient" in (res.generated_answer or "")

    @pytest.mark.asyncio
    async def test_nli_low_confidence_decline_overrides_answer(self):
        doc = Document(
            id="nli2",
            content="Strict verification reduces unsupported claims.",
            metadata={"source": "media_db"},
            source=DataSource.MEDIA_DB,
            score=0.88,
        )

        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_ret, \
             patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.build_hard_citations') as mock_hc, \
             patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.AnswerGenerator') as mock_gen, \
             patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.PostGenerationVerifier', return_value=self._FakeVerifier()):
            m = MagicMock()
            m.retrieve = AsyncMock(return_value=[doc])
            mock_ret.return_value = m
            mock_hc.return_value = {"coverage": 1.0, "sentences": []}

            gen = MagicMock()
            gen.generate = AsyncMock(return_value={"answer": "Candidate answer"})
            mock_gen.return_value = gen

            res = await unified_rag_pipeline(
                query="Explain RAG gating",
                enable_generation=True,
                enable_post_verification=True,
                adaptive_unsupported_threshold=0.2,
                low_confidence_behavior="decline",
            )

            gate = res.metadata.get("generation_gate") if isinstance(res.metadata, dict) else None
            assert gate and gate.get("reason") == "nli_low_confidence"
            assert res.generated_answer == "Insufficient evidence found to answer confidently."
