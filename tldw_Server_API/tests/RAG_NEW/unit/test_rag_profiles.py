import pytest

from tldw_Server_API.app.core.RAG import (
    list_profiles,
    get_profile,
    get_profile_kwargs,
    apply_profile_to_kwargs,
    get_multi_tenant_safe_kwargs,
)


@pytest.mark.unit
class TestRAGProfiles:
    def test_profiles_are_registered(self):
        profiles = list_profiles()
        assert "production" in profiles
        assert "research" in profiles
        assert "cheap" in profiles

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
