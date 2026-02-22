"""
Tests for the built-in category taxonomy.
"""
from __future__ import annotations

import re

from tldw_Server_API.app.core.Moderation.category_taxonomy import (
    CATEGORY_TAXONOMY,
    get_all_categories,
    get_category_keywords,
    get_category_patterns,
)


class TestCategoryTaxonomy:
    def test_all_categories_have_patterns(self):
        """Every category in the taxonomy should have at least one regex pattern."""
        for name, info in CATEGORY_TAXONOMY.items():
            assert len(info.get("regex_patterns", [])) > 0, f"{name} has no patterns"

    def test_all_categories_have_keywords(self):
        """Every category should have at least one keyword."""
        for name, info in CATEGORY_TAXONOMY.items():
            assert len(info.get("keywords", [])) > 0, f"{name} has no keywords"

    def test_all_categories_have_description(self):
        """Every category should have a description."""
        for name, info in CATEGORY_TAXONOMY.items():
            assert info.get("description"), f"{name} has no description"

    def test_all_categories_have_severity_default(self):
        """Every category should have a severity_default."""
        for name, info in CATEGORY_TAXONOMY.items():
            assert info["severity_default"] in ("info", "warning", "critical"), (
                f"{name} has invalid severity: {info['severity_default']}"
            )


class TestGetCategoryPatterns:
    def test_returns_compiled_regex(self):
        """get_category_patterns should return compiled re.Pattern objects."""
        patterns = get_category_patterns("violence")
        assert len(patterns) > 0
        for pat in patterns:
            assert isinstance(pat, re.Pattern)

    def test_patterns_match_expected_text(self):
        """Violence patterns should match violent keywords."""
        patterns = get_category_patterns("violence")
        text = "He threatened to stab someone with a knife"
        matches = [pat for pat in patterns if pat.search(text)]
        assert len(matches) > 0

    def test_unknown_category_returns_empty(self):
        """Unknown category should return empty list."""
        patterns = get_category_patterns("nonexistent_category")
        assert patterns == []

    def test_pii_patterns_match_ssn(self):
        """PII patterns should match SSN format."""
        patterns = get_category_patterns("pii")
        text = "My SSN is 123-45-6789"
        matches = [pat for pat in patterns if pat.search(text)]
        assert len(matches) > 0

    def test_self_harm_patterns_match(self):
        """Self-harm patterns should match critical content."""
        patterns = get_category_patterns("self_harm")
        text = "I want to hurt myself"
        matches = [pat for pat in patterns if pat.search(text)]
        assert len(matches) > 0


class TestGetCategoryKeywords:
    def test_returns_keyword_list(self):
        """get_category_keywords should return a list of strings."""
        keywords = get_category_keywords("violence")
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        assert all(isinstance(k, str) for k in keywords)

    def test_unknown_category_returns_empty(self):
        keywords = get_category_keywords("nonexistent")
        assert keywords == []


class TestGetAllCategories:
    def test_returns_all_categories(self):
        """get_all_categories should return metadata for all categories."""
        cats = get_all_categories()
        assert len(cats) == len(CATEGORY_TAXONOMY)
        for name, info in cats.items():
            assert "description" in info
            assert "severity_default" in info
            assert "keyword_count" in info
            assert "pattern_count" in info
            assert info["keyword_count"] > 0
            assert info["pattern_count"] > 0
