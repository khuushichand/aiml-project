"""Pydantic config models for research adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class ArxivSearchConfig(BaseAdapterConfig):
    """Config for arXiv search adapter."""

    query: str = Field(..., description="Search query (templated)")
    max_results: int = Field(10, ge=1, le=100, description="Maximum results to return")
    sort_by: Literal["relevance", "lastUpdatedDate", "submittedDate"] = Field(
        "relevance", description="Sort order"
    )
    sort_order: Literal["ascending", "descending"] = Field(
        "descending", description="Sort direction"
    )
    categories: list[str] | None = Field(None, description="arXiv categories to filter")
    start_date: str | None = Field(None, description="Start date filter (YYYY-MM-DD)")
    end_date: str | None = Field(None, description="End date filter (YYYY-MM-DD)")


class ArxivDownloadConfig(BaseAdapterConfig):
    """Config for arXiv paper download adapter."""

    arxiv_id: str = Field(..., description="arXiv paper ID (e.g., '2301.00001')")
    format: Literal["pdf", "source"] = Field("pdf", description="Download format")
    output_dir: str | None = Field(None, description="Output directory override")


class PubmedSearchConfig(BaseAdapterConfig):
    """Config for PubMed search adapter."""

    query: str = Field(..., description="Search query (templated)")
    max_results: int = Field(10, ge=1, le=100, description="Maximum results to return")
    sort_by: Literal["relevance", "date"] = Field("relevance", description="Sort order")
    date_range: str | None = Field(None, description="Date range (e.g., '2020:2024')")
    article_types: list[str] | None = Field(None, description="Article types to filter")


class SemanticScholarSearchConfig(BaseAdapterConfig):
    """Config for Semantic Scholar search adapter."""

    query: str = Field(..., description="Search query (templated)")
    max_results: int = Field(10, ge=1, le=100, description="Maximum results to return")
    fields: list[str] | None = Field(
        None, description="Fields to return (title, abstract, authors, etc.)"
    )
    year_range: str | None = Field(None, description="Year range (e.g., '2020-2024')")
    venue: str | None = Field(None, description="Publication venue filter")
    open_access: bool | None = Field(None, description="Filter for open access papers")


class GoogleScholarSearchConfig(BaseAdapterConfig):
    """Config for Google Scholar search adapter."""

    query: str = Field(..., description="Search query (templated)")
    max_results: int = Field(10, ge=1, le=50, description="Maximum results to return")
    year_from: int | None = Field(None, description="Publications from this year")
    year_to: int | None = Field(None, description="Publications until this year")
    sort_by_date: bool = Field(False, description="Sort by date instead of relevance")


class PatentSearchConfig(BaseAdapterConfig):
    """Config for patent search adapter."""

    query: str = Field(..., description="Search query (templated)")
    max_results: int = Field(10, ge=1, le=100, description="Maximum results to return")
    patent_office: Literal["USPTO", "EPO", "WIPO", "all"] | None = Field(
        "all", description="Patent office to search"
    )
    date_range: str | None = Field(None, description="Date range filter")
    classification: str | None = Field(None, description="Patent classification filter")


class DOIResolveConfig(BaseAdapterConfig):
    """Config for DOI resolution adapter."""

    doi: str = Field(..., description="DOI to resolve (templated)")
    include_metadata: bool = Field(True, description="Include full metadata")
    include_references: bool = Field(False, description="Include paper references")
    include_citations: bool = Field(False, description="Include papers citing this work")


class ReferenceParseConfig(BaseAdapterConfig):
    """Config for reference parsing adapter."""

    reference: str = Field(..., description="Reference string to parse (templated)")
    format: Literal["apa", "mla", "chicago", "bibtex", "auto"] = Field(
        "auto", description="Expected reference format"
    )
    resolve_doi: bool = Field(True, description="Attempt to resolve DOI")


class BibtexGenerateConfig(BaseAdapterConfig):
    """Config for BibTeX generation adapter."""

    source: dict[str, Any] = Field(..., description="Source metadata for BibTeX entry")
    entry_type: Literal["article", "book", "inproceedings", "misc", "phdthesis"] | None = Field(
        None, description="BibTeX entry type (auto-detected if not specified)"
    )
    key: str | None = Field(None, description="BibTeX citation key (auto-generated if not specified)")


class LiteratureReviewConfig(BaseAdapterConfig):
    """Config for literature review generation adapter."""

    topic: str = Field(..., description="Research topic (templated)")
    papers: list[dict[str, Any]] | None = Field(
        None, description="Papers to include in review"
    )
    search_query: str | None = Field(None, description="Query to search for additional papers")
    max_papers: int = Field(20, ge=5, le=100, description="Maximum papers to include")
    sections: list[str] | None = Field(
        None, description="Sections to include (introduction, methods, findings, etc.)"
    )
    style: Literal["narrative", "systematic", "scoping"] = Field(
        "narrative", description="Review style"
    )
    provider: str | None = Field(None, description="LLM provider for generation")
    model: str | None = Field(None, description="Model for generation")


class DeepResearchConfig(BaseAdapterConfig):
    """Config for launching a deep research session from workflows."""

    query: str = Field(..., description="Research query (templated)")
    source_policy: Literal[
        "balanced",
        "local_first",
        "external_first",
        "local_only",
        "external_only",
    ] = Field("balanced", description="How local and external sources should be balanced")
    autonomy_mode: Literal["checkpointed", "autonomous"] = Field(
        "checkpointed",
        description="Whether the session pauses at review checkpoints or runs autonomously",
    )
    limits_json: dict[str, Any] | None = Field(
        None,
        description="Optional run limits passed through to the research session",
    )
    provider_overrides: dict[str, Any] | None = Field(
        None,
        description="Optional per-run provider override configuration",
    )
    save_artifact: bool | None = Field(
        True,
        description="Whether to persist the launch payload as a workflow artifact",
    )
