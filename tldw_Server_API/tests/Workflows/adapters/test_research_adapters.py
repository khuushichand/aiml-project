"""Comprehensive tests for research and bibliography adapters.

This module tests all 10 research adapters:
1. run_arxiv_search_adapter - Search arXiv
2. run_arxiv_download_adapter - Download arXiv papers
3. run_pubmed_search_adapter - Search PubMed
4. run_semantic_scholar_search_adapter - Search Semantic Scholar
5. run_google_scholar_search_adapter - Search Google Scholar
6. run_patent_search_adapter - Search patents
7. run_doi_resolve_adapter - Resolve DOI to metadata
8. run_reference_parse_adapter - Parse reference strings
9. run_bibtex_generate_adapter - Generate BibTeX
10. run_literature_review_adapter - Generate literature review
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# =============================================================================
# arXiv Search Adapter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_arxiv_search_adapter_test_mode(monkeypatch):
    """Test arXiv search returns simulated results in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_arxiv_search_adapter,
    )

    config = {"query": "machine learning", "max_results": 5}
    context = {}

    result = await run_arxiv_search_adapter(config, context)

    assert "papers" in result
    assert "total_results" in result
    assert result.get("simulated") is True
    assert result["query"] == "machine learning"
    assert len(result["papers"]) == 1
    paper = result["papers"][0]
    assert "arxiv_id" in paper
    assert "title" in paper
    assert "authors" in paper
    assert "machine learning" in paper["title"]


@pytest.mark.asyncio
async def test_arxiv_search_adapter_test_mode_y(monkeypatch):
    """Test arXiv search treats TEST_MODE=y as enabled."""
    monkeypatch.setenv("TEST_MODE", "y")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_arxiv_search_adapter,
    )

    result = await run_arxiv_search_adapter({"query": "graph theory"}, {})

    assert result.get("simulated") is True
    assert result["query"] == "graph theory"


@pytest.mark.asyncio
async def test_arxiv_search_adapter_empty_query(monkeypatch):
    """Test arXiv search handles empty query gracefully."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_arxiv_search_adapter,
    )

    config = {"query": "", "max_results": 5}
    context = {}

    result = await run_arxiv_search_adapter(config, context)

    assert result["papers"] == []
    assert result.get("error") == "missing_query"


@pytest.mark.asyncio
async def test_arxiv_search_adapter_with_template_context(monkeypatch):
    """Test arXiv search with template substitution from context."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_arxiv_search_adapter,
    )

    config = {"query": "{{ inputs.topic }}", "max_results": 10}
    context = {"inputs": {"topic": "deep learning"}}

    result = await run_arxiv_search_adapter(config, context)

    assert result.get("simulated") is True
    assert "deep learning" in result["query"]


@pytest.mark.asyncio
async def test_arxiv_search_adapter_cancelled(monkeypatch):
    """Test arXiv search respects cancellation."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_arxiv_search_adapter,
    )

    config = {"query": "test", "max_results": 5}
    context = {"is_cancelled": lambda: True}

    result = await run_arxiv_search_adapter(config, context)

    assert result.get("__status__") == "cancelled"


@pytest.mark.asyncio
async def test_arxiv_search_adapter_sort_options(monkeypatch):
    """Test arXiv search with different sort options."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_arxiv_search_adapter,
    )

    config = {
        "query": "neural networks",
        "max_results": 5,
        "sort_by": "submittedDate",
        "sort_order": "ascending",
    }
    context = {}

    result = await run_arxiv_search_adapter(config, context)

    assert result.get("simulated") is True
    assert "papers" in result


# =============================================================================
# arXiv Download Adapter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_arxiv_download_adapter_test_mode(monkeypatch):
    """Test arXiv download returns simulated path in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_arxiv_download_adapter,
    )

    config = {"arxiv_id": "2301.00001"}
    context = {}

    result = await run_arxiv_download_adapter(config, context)

    assert result.get("simulated") is True
    assert result.get("downloaded") is True
    assert "pdf_path" in result
    assert "2301.00001" in result["pdf_path"]
    assert result["arxiv_id"] == "2301.00001"


@pytest.mark.asyncio
async def test_arxiv_download_adapter_with_pdf_url(monkeypatch):
    """Test arXiv download with direct PDF URL."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_arxiv_download_adapter,
    )

    config = {"pdf_url": "https://arxiv.org/pdf/2301.00001.pdf"}
    context = {}

    result = await run_arxiv_download_adapter(config, context)

    assert result.get("simulated") is True
    assert result.get("downloaded") is True


@pytest.mark.asyncio
async def test_arxiv_download_adapter_missing_id(monkeypatch):
    """Test arXiv download handles missing ID gracefully."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_arxiv_download_adapter,
    )

    config = {}
    context = {}

    result = await run_arxiv_download_adapter(config, context)

    assert result.get("downloaded") is False
    assert result.get("error") == "missing_arxiv_id_or_pdf_url"


@pytest.mark.asyncio
async def test_arxiv_download_adapter_from_context(monkeypatch):
    """Test arXiv download extracts ID from previous step context."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_arxiv_download_adapter,
    )

    config = {}
    context = {"prev": {"arxiv_id": "2301.00002", "pdf_url": ""}}

    result = await run_arxiv_download_adapter(config, context)

    assert result.get("simulated") is True
    assert result.get("downloaded") is True
    assert result["arxiv_id"] == "2301.00002"


@pytest.mark.asyncio
async def test_arxiv_download_adapter_cancelled(monkeypatch):
    """Test arXiv download respects cancellation."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_arxiv_download_adapter,
    )

    config = {"arxiv_id": "2301.00001"}
    context = {"is_cancelled": lambda: True}

    result = await run_arxiv_download_adapter(config, context)

    assert result.get("__status__") == "cancelled"


# =============================================================================
# PubMed Search Adapter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_pubmed_search_adapter_test_mode(monkeypatch):
    """Test PubMed search returns simulated results in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_pubmed_search_adapter,
    )

    config = {"query": "cancer treatment", "max_results": 10}
    context = {}

    result = await run_pubmed_search_adapter(config, context)

    assert "papers" in result
    assert "total_results" in result
    assert result.get("simulated") is True
    assert result["query"] == "cancer treatment"
    assert len(result["papers"]) == 1
    paper = result["papers"][0]
    assert "pmid" in paper
    assert "title" in paper
    assert "authors" in paper
    assert "cancer treatment" in paper["title"]


@pytest.mark.asyncio
async def test_pubmed_search_adapter_empty_query(monkeypatch):
    """Test PubMed search handles empty query gracefully."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_pubmed_search_adapter,
    )

    config = {"query": ""}
    context = {}

    result = await run_pubmed_search_adapter(config, context)

    assert result["papers"] == []
    assert result.get("error") == "missing_query"


@pytest.mark.asyncio
async def test_pubmed_search_adapter_with_template(monkeypatch):
    """Test PubMed search with template substitution."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_pubmed_search_adapter,
    )

    config = {"query": "{{ inputs.disease }}"}
    context = {"inputs": {"disease": "diabetes"}}

    result = await run_pubmed_search_adapter(config, context)

    assert result.get("simulated") is True
    assert "diabetes" in result["query"]


@pytest.mark.asyncio
async def test_pubmed_search_adapter_cancelled(monkeypatch):
    """Test PubMed search respects cancellation."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_pubmed_search_adapter,
    )

    config = {"query": "test"}
    context = {"is_cancelled": lambda: True}

    result = await run_pubmed_search_adapter(config, context)

    assert result.get("__status__") == "cancelled"


# =============================================================================
# Semantic Scholar Search Adapter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_semantic_scholar_search_adapter_test_mode(monkeypatch):
    """Test Semantic Scholar search returns simulated results in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_semantic_scholar_search_adapter,
    )

    config = {"query": "transformer architecture", "max_results": 5}
    context = {}

    result = await run_semantic_scholar_search_adapter(config, context)

    assert "papers" in result
    assert "total_results" in result
    assert result.get("simulated") is True
    assert result["query"] == "transformer architecture"
    assert len(result["papers"]) == 1
    paper = result["papers"][0]
    assert "paper_id" in paper
    assert "title" in paper
    assert "authors" in paper
    assert "citation_count" in paper
    assert "transformer architecture" in paper["title"]


@pytest.mark.asyncio
async def test_semantic_scholar_search_adapter_empty_query(monkeypatch):
    """Test Semantic Scholar search handles empty query gracefully."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_semantic_scholar_search_adapter,
    )

    config = {"query": ""}
    context = {}

    result = await run_semantic_scholar_search_adapter(config, context)

    assert result["papers"] == []
    assert result.get("error") == "missing_query"


@pytest.mark.asyncio
async def test_semantic_scholar_search_adapter_with_fields(monkeypatch):
    """Test Semantic Scholar search with custom fields."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_semantic_scholar_search_adapter,
    )

    config = {
        "query": "attention mechanism",
        "max_results": 10,
        "fields": ["title", "abstract", "year"],
    }
    context = {}

    result = await run_semantic_scholar_search_adapter(config, context)

    assert result.get("simulated") is True
    assert "papers" in result


@pytest.mark.asyncio
async def test_semantic_scholar_search_adapter_cancelled(monkeypatch):
    """Test Semantic Scholar search respects cancellation."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_semantic_scholar_search_adapter,
    )

    config = {"query": "test"}
    context = {"is_cancelled": lambda: True}

    result = await run_semantic_scholar_search_adapter(config, context)

    assert result.get("__status__") == "cancelled"


# =============================================================================
# Google Scholar Search Adapter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_google_scholar_search_adapter_test_mode(monkeypatch):
    """Test Google Scholar search returns simulated results in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_google_scholar_search_adapter,
    )

    config = {"query": "natural language processing", "max_results": 10}
    context = {}

    result = await run_google_scholar_search_adapter(config, context)

    assert "papers" in result
    assert "total_results" in result
    assert result.get("simulated") is True
    assert result["query"] == "natural language processing"
    assert len(result["papers"]) == 1
    paper = result["papers"][0]
    assert "title" in paper
    assert "authors" in paper
    assert "citation_count" in paper
    assert "natural language processing" in paper["title"]


@pytest.mark.asyncio
async def test_google_scholar_search_adapter_empty_query(monkeypatch):
    """Test Google Scholar search handles empty query gracefully."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_google_scholar_search_adapter,
    )

    config = {"query": ""}
    context = {}

    result = await run_google_scholar_search_adapter(config, context)

    assert result["papers"] == []
    assert result.get("error") == "missing_query"


@pytest.mark.asyncio
async def test_google_scholar_search_adapter_with_template(monkeypatch):
    """Test Google Scholar search with template substitution."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_google_scholar_search_adapter,
    )

    config = {"query": "{{ inputs.research_topic }}"}
    context = {"inputs": {"research_topic": "reinforcement learning"}}

    result = await run_google_scholar_search_adapter(config, context)

    assert result.get("simulated") is True
    assert "reinforcement learning" in result["query"]


@pytest.mark.asyncio
async def test_google_scholar_search_adapter_cancelled(monkeypatch):
    """Test Google Scholar search respects cancellation."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_google_scholar_search_adapter,
    )

    config = {"query": "test"}
    context = {"is_cancelled": lambda: True}

    result = await run_google_scholar_search_adapter(config, context)

    assert result.get("__status__") == "cancelled"


# =============================================================================
# Patent Search Adapter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_patent_search_adapter_test_mode(monkeypatch):
    """Test patent search returns simulated results in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_patent_search_adapter,
    )

    config = {"query": "solar panel efficiency", "max_results": 10}
    context = {}

    result = await run_patent_search_adapter(config, context)

    assert "patents" in result
    assert "total_results" in result
    assert result.get("simulated") is True
    assert result["query"] == "solar panel efficiency"
    assert len(result["patents"]) == 1
    patent = result["patents"][0]
    assert "patent_id" in patent
    assert "title" in patent
    assert "assignee" in patent
    assert "inventors" in patent
    assert "solar panel efficiency" in patent["title"]


@pytest.mark.asyncio
async def test_patent_search_adapter_empty_query(monkeypatch):
    """Test patent search handles empty query gracefully."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_patent_search_adapter,
    )

    config = {"query": ""}
    context = {}

    result = await run_patent_search_adapter(config, context)

    assert result["patents"] == []
    assert result.get("error") == "missing_query"


@pytest.mark.asyncio
async def test_patent_search_adapter_with_template(monkeypatch):
    """Test patent search with template substitution."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_patent_search_adapter,
    )

    config = {"query": "{{ inputs.invention }}"}
    context = {"inputs": {"invention": "battery technology"}}

    result = await run_patent_search_adapter(config, context)

    assert result.get("simulated") is True
    assert "battery technology" in result["query"]


@pytest.mark.asyncio
async def test_patent_search_adapter_cancelled(monkeypatch):
    """Test patent search respects cancellation."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_patent_search_adapter,
    )

    config = {"query": "test"}
    context = {"is_cancelled": lambda: True}

    result = await run_patent_search_adapter(config, context)

    assert result.get("__status__") == "cancelled"


# =============================================================================
# DOI Resolve Adapter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_doi_resolve_adapter_test_mode(monkeypatch):
    """Test DOI resolve returns simulated metadata in test mode."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_doi_resolve_adapter,
    )

    config = {"doi": "10.1234/example"}
    context = {}

    result = await run_doi_resolve_adapter(config, context)

    assert "metadata" in result
    assert result.get("resolved") is True
    assert result.get("simulated") is True
    metadata = result["metadata"]
    assert "doi" in metadata
    assert "title" in metadata
    assert "authors" in metadata
    assert metadata["doi"] == "10.1234/example"


@pytest.mark.asyncio
async def test_doi_resolve_adapter_with_prefix(monkeypatch):
    """Test DOI resolve handles various DOI formats."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_doi_resolve_adapter,
    )

    # Test with https://doi.org/ prefix
    config = {"doi": "https://doi.org/10.1234/example"}
    context = {}

    result = await run_doi_resolve_adapter(config, context)

    assert result.get("resolved") is True
    assert result["metadata"]["doi"] == "10.1234/example"

    # Test with doi: prefix
    config = {"doi": "doi:10.1234/example2"}
    result = await run_doi_resolve_adapter(config, context)

    assert result.get("resolved") is True
    assert result["metadata"]["doi"] == "10.1234/example2"


@pytest.mark.asyncio
async def test_doi_resolve_adapter_missing_doi(monkeypatch):
    """Test DOI resolve handles missing DOI gracefully."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_doi_resolve_adapter,
    )

    config = {}
    context = {}

    result = await run_doi_resolve_adapter(config, context)

    assert result.get("resolved") is False
    assert result.get("error") == "missing_doi"
    assert result["metadata"] == {}


@pytest.mark.asyncio
async def test_doi_resolve_adapter_from_context(monkeypatch):
    """Test DOI resolve extracts DOI from previous step context."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_doi_resolve_adapter,
    )

    config = {}
    context = {"prev": {"doi": "10.5678/fromcontext"}}

    result = await run_doi_resolve_adapter(config, context)

    assert result.get("resolved") is True
    assert result["metadata"]["doi"] == "10.5678/fromcontext"


@pytest.mark.asyncio
async def test_doi_resolve_adapter_cancelled(monkeypatch):
    """Test DOI resolve respects cancellation."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_doi_resolve_adapter,
    )

    config = {"doi": "10.1234/example"}
    context = {"is_cancelled": lambda: True}

    result = await run_doi_resolve_adapter(config, context)

    assert result.get("__status__") == "cancelled"


# =============================================================================
# Reference Parse Adapter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_reference_parse_adapter_basic(monkeypatch):
    """Test reference parsing with mocked LLM call."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_reference_parse_adapter,
    )

    # Mock the chat service to return structured JSON
    async def mock_chat(*args, **kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"authors": ["Smith, J.", "Doe, A."], "title": "Test Paper", "journal": "Test Journal", "year": "2023", "volume": "1", "pages": "1-10"}'
                    }
                }
            ]
        }

    import tldw_Server_API.app.core.Chat.chat_service as chat_svc
    monkeypatch.setattr(chat_svc, "perform_chat_api_call_async", mock_chat)

    config = {
        "citation": "Smith, J. & Doe, A. (2023). Test Paper. Test Journal, 1, 1-10.",
        "provider": "openai",
        "model": "gpt-4",
    }
    context = {}

    result = await run_reference_parse_adapter(config, context)

    assert "parsed" in result
    parsed = result["parsed"]
    assert parsed.get("title") == "Test Paper"
    assert "Smith" in str(parsed.get("authors"))


@pytest.mark.asyncio
async def test_reference_parse_adapter_empty_citation(monkeypatch):
    """Test reference parse handles empty citation gracefully."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_reference_parse_adapter,
    )

    config = {"citation": ""}
    context = {}

    result = await run_reference_parse_adapter(config, context)

    assert result["parsed"] == {}
    assert result.get("error") == "missing_citation"


@pytest.mark.asyncio
async def test_reference_parse_adapter_with_template(monkeypatch):
    """Test reference parse with template substitution."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_reference_parse_adapter,
    )

    async def mock_chat(*args, **kwargs):
        return {
            "choices": [
                {"message": {"content": '{"title": "Parsed Title", "year": "2024"}'}}
            ]
        }

    import tldw_Server_API.app.core.Chat.chat_service as chat_svc
    monkeypatch.setattr(chat_svc, "perform_chat_api_call_async", mock_chat)

    config = {"citation": "{{ inputs.ref }}"}
    context = {"inputs": {"ref": "Test citation string"}}

    result = await run_reference_parse_adapter(config, context)

    assert "parsed" in result


@pytest.mark.asyncio
async def test_reference_parse_adapter_cancelled(monkeypatch):
    """Test reference parse respects cancellation."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_reference_parse_adapter,
    )

    config = {"citation": "test citation"}
    context = {"is_cancelled": lambda: True}

    result = await run_reference_parse_adapter(config, context)

    assert result.get("__status__") == "cancelled"


@pytest.mark.asyncio
async def test_reference_parse_adapter_invalid_json_response(monkeypatch):
    """Test reference parse handles invalid JSON from LLM gracefully."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_reference_parse_adapter,
    )

    async def mock_chat(*args, **kwargs):
        return {"choices": [{"message": {"content": "This is not valid JSON"}}]}

    import tldw_Server_API.app.core.Chat.chat_service as chat_svc
    monkeypatch.setattr(chat_svc, "perform_chat_api_call_async", mock_chat)

    config = {"citation": "Some citation text"}
    context = {}

    result = await run_reference_parse_adapter(config, context)

    assert result["parsed"] == {}
    assert "raw_text" in result


# =============================================================================
# BibTeX Generate Adapter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_bibtex_generate_adapter_basic(monkeypatch):
    """Test BibTeX generation from metadata."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_bibtex_generate_adapter,
    )

    config = {
        "metadata": {
            "title": "Test Paper Title",
            "authors": ["John Smith", "Jane Doe"],
            "journal": "Test Journal",
            "year": 2023,
            "volume": "10",
            "pages": "1-15",
            "doi": "10.1234/test",
        },
        "entry_type": "article",
    }
    context = {}

    result = await run_bibtex_generate_adapter(config, context)

    assert "bibtex" in result
    assert "@article" in result["bibtex"]
    assert "Test Paper Title" in result["bibtex"]
    assert "John Smith and Jane Doe" in result["bibtex"]
    assert "cite_key" in result


@pytest.mark.asyncio
async def test_bibtex_generate_adapter_custom_cite_key(monkeypatch):
    """Test BibTeX generation with custom citation key."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_bibtex_generate_adapter,
    )

    config = {
        "metadata": {
            "title": "Custom Key Paper",
            "authors": ["Author Name"],
            "year": 2024,
        },
        "entry_type": "inproceedings",
        "cite_key": "customkey2024",
    }
    context = {}

    result = await run_bibtex_generate_adapter(config, context)

    assert "bibtex" in result
    assert "@inproceedings{customkey2024," in result["bibtex"]
    assert result["cite_key"] == "customkey2024"


@pytest.mark.asyncio
async def test_bibtex_generate_adapter_auto_cite_key(monkeypatch):
    """Test BibTeX generation with auto-generated citation key."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_bibtex_generate_adapter,
    )

    config = {
        "metadata": {
            "title": "Auto Key Paper",
            "authors": ["Smith, John"],
            "year": 2023,
        },
    }
    context = {}

    result = await run_bibtex_generate_adapter(config, context)

    assert "bibtex" in result
    # Auto-generated key should be based on last name and year
    assert "smith2023" in result["cite_key"].lower() or "john2023" in result["cite_key"].lower()


@pytest.mark.asyncio
async def test_bibtex_generate_adapter_missing_metadata(monkeypatch):
    """Test BibTeX generation handles missing metadata gracefully."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_bibtex_generate_adapter,
    )

    config = {}
    context = {}

    result = await run_bibtex_generate_adapter(config, context)

    assert result["bibtex"] == ""
    assert result.get("error") == "missing_metadata"


@pytest.mark.asyncio
async def test_bibtex_generate_adapter_from_context(monkeypatch):
    """Test BibTeX generation uses metadata from previous step."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_bibtex_generate_adapter,
    )

    config = {"entry_type": "book"}
    context = {
        "prev": {
            "metadata": {
                "title": "Context Paper",
                "authors": ["Context Author"],
                "year": 2022,
                "publisher": "Test Publisher",
            }
        }
    }

    result = await run_bibtex_generate_adapter(config, context)

    assert "bibtex" in result
    assert "@book" in result["bibtex"]
    assert "Context Paper" in result["bibtex"]


@pytest.mark.asyncio
async def test_bibtex_generate_adapter_cancelled(monkeypatch):
    """Test BibTeX generation respects cancellation."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_bibtex_generate_adapter,
    )

    config = {"metadata": {"title": "test"}}
    context = {"is_cancelled": lambda: True}

    result = await run_bibtex_generate_adapter(config, context)

    assert result.get("__status__") == "cancelled"


@pytest.mark.asyncio
async def test_bibtex_generate_adapter_all_fields(monkeypatch):
    """Test BibTeX generation with all available fields."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_bibtex_generate_adapter,
    )

    config = {
        "metadata": {
            "title": "Complete Paper",
            "authors": ["First Author", "Second Author", "Third Author"],
            "journal": "Prestigious Journal",
            "year": 2024,
            "volume": "42",
            "number": "3",
            "pages": "100-150",
            "doi": "10.1234/complete",
            "url": "https://example.com/paper",
            "publisher": "Academic Press",
            "booktitle": "Conference Proceedings",
            "abstract": "This is the abstract of the paper.",
        },
        "entry_type": "article",
    }
    context = {}

    result = await run_bibtex_generate_adapter(config, context)

    bibtex = result["bibtex"]
    assert "title = {Complete Paper}" in bibtex
    assert "journal = {Prestigious Journal}" in bibtex
    assert "volume = {42}" in bibtex
    assert "doi = {10.1234/complete}" in bibtex


# =============================================================================
# Literature Review Adapter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_literature_review_adapter_basic(monkeypatch):
    """Test literature review generation with mocked LLM."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_literature_review_adapter,
    )

    async def mock_chat(*args, **kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": "This literature review covers recent advances in machine learning..."
                    }
                }
            ]
        }

    import tldw_Server_API.app.core.Chat.chat_service as chat_svc
    monkeypatch.setattr(chat_svc, "perform_chat_api_call_async", mock_chat)

    config = {
        "papers": [
            {
                "title": "Paper 1",
                "authors": ["Author A"],
                "year": 2023,
                "summary": "Summary of paper 1",
            },
            {
                "title": "Paper 2",
                "authors": ["Author B"],
                "year": 2024,
                "abstract": "Abstract of paper 2",
            },
        ],
        "topic": "machine learning",
        "style": "brief",
    }
    context = {}

    result = await run_literature_review_adapter(config, context)

    assert "review" in result
    assert result["paper_count"] == 2
    assert result["style"] == "brief"
    assert "machine learning" in result["review"]


@pytest.mark.asyncio
async def test_literature_review_adapter_missing_papers(monkeypatch):
    """Test literature review handles missing papers gracefully."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_literature_review_adapter,
    )

    config = {"topic": "test topic"}
    context = {}

    result = await run_literature_review_adapter(config, context)

    assert result["review"] == ""
    assert result.get("error") == "missing_papers"


@pytest.mark.asyncio
async def test_literature_review_adapter_from_context(monkeypatch):
    """Test literature review uses papers from previous step."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_literature_review_adapter,
    )

    async def mock_chat(*args, **kwargs):
        return {
            "choices": [
                {"message": {"content": "Review from context papers..."}}
            ]
        }

    import tldw_Server_API.app.core.Chat.chat_service as chat_svc
    monkeypatch.setattr(chat_svc, "perform_chat_api_call_async", mock_chat)

    config = {"topic": "neural networks", "style": "detailed"}
    context = {
        "prev": {
            "papers": [
                {"title": "Context Paper", "authors": ["Author"], "year": 2023}
            ]
        }
    }

    result = await run_literature_review_adapter(config, context)

    assert "review" in result
    assert result["paper_count"] == 1


@pytest.mark.asyncio
async def test_literature_review_adapter_styles(monkeypatch):
    """Test literature review with different style options."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_literature_review_adapter,
    )

    async def mock_chat(*args, **kwargs):
        return {"choices": [{"message": {"content": "Style-specific review..."}}]}

    import tldw_Server_API.app.core.Chat.chat_service as chat_svc
    monkeypatch.setattr(chat_svc, "perform_chat_api_call_async", mock_chat)

    papers = [{"title": "Test", "authors": ["A"], "year": 2024}]

    for style in ["brief", "detailed", "comparative"]:
        config = {"papers": papers, "style": style}
        context = {}

        result = await run_literature_review_adapter(config, context)

        assert result["style"] == style
        assert "review" in result


@pytest.mark.asyncio
async def test_literature_review_adapter_cancelled(monkeypatch):
    """Test literature review respects cancellation."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_literature_review_adapter,
    )

    config = {"papers": [{"title": "Test", "authors": [], "year": 2024}]}
    context = {"is_cancelled": lambda: True}

    result = await run_literature_review_adapter(config, context)

    assert result.get("__status__") == "cancelled"


@pytest.mark.asyncio
async def test_literature_review_adapter_with_template(monkeypatch):
    """Test literature review with template substitution for topic."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_literature_review_adapter,
    )

    async def mock_chat(*args, **kwargs):
        return {"choices": [{"message": {"content": "Review on AI..."}}]}

    import tldw_Server_API.app.core.Chat.chat_service as chat_svc
    monkeypatch.setattr(chat_svc, "perform_chat_api_call_async", mock_chat)

    config = {
        "papers": [{"title": "AI Paper", "authors": ["Researcher"], "year": 2024}],
        "topic": "{{ inputs.research_area }}",
    }
    context = {"inputs": {"research_area": "artificial intelligence"}}

    result = await run_literature_review_adapter(config, context)

    assert "review" in result


# =============================================================================
# Integration Tests - Testing Adapter Chaining
# =============================================================================


@pytest.mark.asyncio
async def test_search_to_bibtex_chain(monkeypatch):
    """Test chaining arXiv search to BibTeX generation."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_arxiv_search_adapter,
        run_bibtex_generate_adapter,
    )

    # Step 1: Search
    search_config = {"query": "quantum computing", "max_results": 1}
    context = {}

    search_result = await run_arxiv_search_adapter(search_config, context)

    assert search_result.get("simulated") is True
    assert len(search_result["papers"]) == 1

    paper = search_result["papers"][0]

    # Step 2: Generate BibTeX from search result
    bibtex_config = {
        "metadata": {
            "title": paper["title"],
            "authors": paper["authors"],
            "year": 2023,
            "doi": paper.get("doi"),
        },
        "entry_type": "article",
    }

    bibtex_result = await run_bibtex_generate_adapter(bibtex_config, context)

    assert "bibtex" in bibtex_result
    assert paper["title"] in bibtex_result["bibtex"]


@pytest.mark.asyncio
async def test_doi_resolve_to_bibtex_chain(monkeypatch):
    """Test chaining DOI resolve to BibTeX generation."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_doi_resolve_adapter,
        run_bibtex_generate_adapter,
    )

    # Step 1: Resolve DOI
    resolve_config = {"doi": "10.1234/testdoi"}
    context = {}

    resolve_result = await run_doi_resolve_adapter(resolve_config, context)

    assert resolve_result.get("resolved") is True

    # Step 2: Generate BibTeX using metadata from context
    bibtex_config = {"entry_type": "article"}
    context_with_prev = {"prev": resolve_result}

    bibtex_result = await run_bibtex_generate_adapter(bibtex_config, context_with_prev)

    assert "bibtex" in bibtex_result
    assert "10.1234/testdoi" in bibtex_result["bibtex"]


@pytest.mark.asyncio
async def test_search_to_literature_review_chain(monkeypatch):
    """Test chaining search to literature review generation."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_semantic_scholar_search_adapter,
        run_literature_review_adapter,
    )

    async def mock_chat(*args, **kwargs):
        return {
            "choices": [
                {"message": {"content": "Comprehensive review of the papers..."}}
            ]
        }

    import tldw_Server_API.app.core.Chat.chat_service as chat_svc
    monkeypatch.setattr(chat_svc, "perform_chat_api_call_async", mock_chat)

    # Step 1: Search
    search_config = {"query": "deep learning optimization", "max_results": 5}
    context = {}

    search_result = await run_semantic_scholar_search_adapter(search_config, context)

    assert search_result.get("simulated") is True

    # Step 2: Generate literature review
    review_config = {"topic": "deep learning optimization", "style": "detailed"}
    context_with_prev = {"prev": search_result}

    review_result = await run_literature_review_adapter(review_config, context_with_prev)

    assert "review" in review_result
    assert review_result["paper_count"] == 1  # From simulated search


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_literature_review_adapter_llm_error(monkeypatch):
    """Test literature review handles LLM errors gracefully."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_literature_review_adapter,
    )

    async def mock_chat_error(*args, **kwargs):
        raise RuntimeError("LLM service unavailable")

    import tldw_Server_API.app.core.Chat.chat_service as chat_svc
    monkeypatch.setattr(chat_svc, "perform_chat_api_call_async", mock_chat_error)

    config = {
        "papers": [{"title": "Test", "authors": ["Author"], "year": 2024}],
        "topic": "test",
    }
    context = {}

    result = await run_literature_review_adapter(config, context)

    assert result["review"] == ""
    assert "error" in result
    assert "LLM service unavailable" in result["error"]


@pytest.mark.asyncio
async def test_reference_parse_adapter_llm_error(monkeypatch):
    """Test reference parse handles LLM errors gracefully."""
    monkeypatch.setenv("TEST_MODE", "1")

    from tldw_Server_API.app.core.Workflows.adapters.research import (
        run_reference_parse_adapter,
    )

    async def mock_chat_error(*args, **kwargs):
        raise RuntimeError("API timeout")

    import tldw_Server_API.app.core.Chat.chat_service as chat_svc
    monkeypatch.setattr(chat_svc, "perform_chat_api_call_async", mock_chat_error)

    config = {"citation": "Smith, J. (2023). Test."}
    context = {}

    result = await run_reference_parse_adapter(config, context)

    assert result["parsed"] == {}
    assert "error" in result
    assert "API timeout" in result["error"]


# =============================================================================
# Registry Tests - Verify adapters are properly registered
# =============================================================================


def test_research_adapters_registered():
    """Verify all research adapters are registered in the registry."""
    from tldw_Server_API.app.core.Workflows.adapters import registry

    expected_adapters = [
        "arxiv_search",
        "arxiv_download",
        "pubmed_search",
        "semantic_scholar_search",
        "google_scholar_search",
        "patent_search",
        "doi_resolve",
        "reference_parse",
        "bibtex_generate",
        "literature_review",
    ]

    all_adapters = registry.list_adapters()

    for adapter_name in expected_adapters:
        assert adapter_name in all_adapters, f"Missing adapter: {adapter_name}"


def test_research_adapters_have_config_models():
    """Verify all research adapters have config models."""
    from tldw_Server_API.app.core.Workflows.adapters import registry

    research_adapters = [
        "arxiv_search",
        "arxiv_download",
        "pubmed_search",
        "semantic_scholar_search",
        "google_scholar_search",
        "patent_search",
        "doi_resolve",
        "reference_parse",
        "bibtex_generate",
        "literature_review",
    ]

    for adapter_name in research_adapters:
        spec = registry.get_spec(adapter_name)
        assert spec is not None, f"Missing spec for {adapter_name}"
        assert spec.config_model is not None, f"Missing config_model for {adapter_name}"


def test_research_adapters_in_research_category():
    """Verify research adapters are in the research category."""
    from tldw_Server_API.app.core.Workflows.adapters import registry

    expected_adapters = {
        "arxiv_search",
        "arxiv_download",
        "pubmed_search",
        "semantic_scholar_search",
        "google_scholar_search",
        "patent_search",
        "doi_resolve",
        "reference_parse",
        "bibtex_generate",
        "literature_review",
    }

    # Verify each expected adapter is in the research category
    for adapter_name in expected_adapters:
        spec = registry.get_spec(adapter_name)
        assert spec is not None, f"Missing adapter: {adapter_name}"
        assert spec.category == "research", f"{adapter_name} is in category '{spec.category}', expected 'research'"

    # Also verify using get_by_category
    research_adapters = registry.get_by_category("research")
    for adapter_name in expected_adapters:
        assert adapter_name in research_adapters, f"{adapter_name} not found in research category list"
