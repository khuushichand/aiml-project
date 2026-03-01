from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tldw_Server_API.app.core.RAG import (
    DataSource,
    list_profiles,
    get_profile,
    get_profile_kwargs,
    apply_profile_to_kwargs,
    get_multi_tenant_safe_kwargs,
    unified_rag_pipeline,
)
from tldw_Server_API.app.core.RAG.rag_service.types import Document


@pytest.mark.unit
class TestRAGProfiles:
    def test_profiles_are_registered(self):
        profiles = list_profiles()
        assert "production" in profiles
        assert "research" in profiles
        assert "cheap" in profiles
        assert "fast" in profiles
        assert "balanced" in profiles
        assert "accuracy" in profiles

    def test_switchable_profile_defaults_match_design_targets(self):
        fast = get_profile_kwargs("fast")
        balanced = get_profile_kwargs("balanced")
        accuracy = get_profile_kwargs("accuracy")

        assert fast["max_generation_tokens"] == 440
        assert fast["generation_prompt"] == "instruction_tuned"
        assert fast["enable_query_decomposition"] is False

        assert balanced["max_generation_tokens"] == 1000
        assert balanced["generation_prompt"] == "multi_hop_compact"
        assert balanced["enable_query_decomposition"] is True
        assert balanced["reranking_strategy"] == "hybrid"

        assert accuracy["max_generation_tokens"] == 2200
        assert accuracy["generation_prompt"] == "expert_synthesis"
        assert accuracy["enable_query_decomposition"] is True
        assert accuracy["reranking_strategy"] == "two_tier"

    def test_get_profile_kwargs_merges_overrides(self):

        base = get_profile_kwargs("cheap")
        assert base["search_mode"] in {"fts", "hybrid"}
        # Override a couple of knobs and ensure they take precedence
        overrides = {"top_k": 3, "enable_generation": False}
        merged = get_profile_kwargs("cheap", overrides=overrides)
        assert merged["top_k"] == 3
        assert merged["enable_generation"] is False

    def test_apply_profile_to_existing_kwargs(self):

        existing = {"search_mode": "vector", "top_k": 5}
        merged = apply_profile_to_kwargs("production", existing)
        # Existing keys should win over profile defaults
        assert merged["search_mode"] == "vector"
        assert merged["top_k"] == 5
        # And some known production default should still be present
        assert merged["enable_security_filter"] is True

    def test_multi_tenant_safe_kwargs_enforces_namespace_and_observability(self):

        ns = "tenant-xyz"
        kwargs = get_multi_tenant_safe_kwargs(ns)
        assert kwargs["index_namespace"] == ns
        assert kwargs["enable_observability"] is False
        # Monitoring should remain on for metrics
        assert kwargs["enable_monitoring"] is True

    def test_multi_tenant_safe_kwargs_requires_namespace(self):

        for bad in ("", "   ", None):
            with pytest.raises(ValueError):
                # type: ignore[arg-type]
                get_multi_tenant_safe_kwargs(bad)  # noqa: PT011

    @pytest.mark.asyncio
    async def test_profile_kwargs_drive_unified_pipeline_retrieval_config(self):
        """Exercise a profile through unified_rag_pipeline and validate mapped knobs."""
        with patch(
            "tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever"
        ) as mock_retriever:
            retriever_instance = MagicMock()
            retriever_instance.retrieve = AsyncMock(
                return_value=[
                    Document(
                        id="doc-1",
                        content="RAG content",
                        metadata={},
                        source=DataSource.MEDIA_DB,
                        score=0.9,
                    )
                ]
            )
            mock_retriever.return_value = retriever_instance

            with patch(
                "tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.AnswerGenerator"
            ) as mock_generator:
                generator_instance = MagicMock()
                generator_instance.generate = AsyncMock(return_value={"answer": "Profile answer"})
                mock_generator.return_value = generator_instance

                kwargs = get_profile_kwargs(
                    "cheap",
                    overrides={
                        "enable_cache": False,
                        "enable_reranking": False,
                        "enable_security_filter": False,
                    },
                )
                result = await unified_rag_pipeline(query="What is RAG?", **kwargs)

                assert result.generated_answer == "Profile answer"
                assert retriever_instance.retrieve.await_count >= 1
                retrieve_kwargs = retriever_instance.retrieve.await_args.kwargs
                config = retrieve_kwargs["config"]
                assert config.max_results == kwargs["top_k"]
                assert config.use_fts is True
                assert config.use_vector is False
