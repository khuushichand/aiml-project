"""Pydantic config models for research adapters."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

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
    categories: Optional[List[str]] = Field(None, description="arXiv categories to filter")
    start_date: Optional[str] = Field(None, description="Start date filter (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date filter (YYYY-MM-DD)")


class ArxivDownloadConfig(BaseAdapterConfig):
    """Config for arXiv paper download adapter."""

    arxiv_id: str = Field(..., description="arXiv paper ID (e.g., '2301.00001')")
    format: Literal["pdf", "source"] = Field("pdf", description="Download format")
    output_dir: Optional[str] = Field(None, description="Output directory override")


class PubmedSearchConfig(BaseAdapterConfig):
    """Config for PubMed search adapter."""

    query: str = Field(..., description="Search query (templated)")
    max_results: int = Field(10, ge=1, le=100, description="Maximum results to return")
    sort_by: Literal["relevance", "date"] = Field("relevance", description="Sort order")
    date_range: Optional[str] = Field(None, description="Date range (e.g., '2020:2024')")
    article_types: Optional[List[str]] = Field(None, description="Article types to filter")


class SemanticScholarSearchConfig(BaseAdapterConfig):
    """Config for Semantic Scholar search adapter."""

    query: str = Field(..., description="Search query (templated)")
    max_results: int = Field(10, ge=1, le=100, description="Maximum results to return")
    fields: Optional[List[str]] = Field(
        None, description="Fields to return (title, abstract, authors, etc.)"
    )
    year_range: Optional[str] = Field(None, description="Year range (e.g., '2020-2024')")
    venue: Optional[str] = Field(None, description="Publication venue filter")
    open_access: Optional[bool] = Field(None, description="Filter for open access papers")


class GoogleScholarSearchConfig(BaseAdapterConfig):
    """Config for Google Scholar search adapter."""

    query: str = Field(..., description="Search query (templated)")
    max_results: int = Field(10, ge=1, le=50, description="Maximum results to return")
    year_from: Optional[int] = Field(None, description="Publications from this year")
    year_to: Optional[int] = Field(None, description="Publications until this year")
    sort_by_date: bool = Field(False, description="Sort by date instead of relevance")


class PatentSearchConfig(BaseAdapterConfig):
    """Config for patent search adapter."""

    query: str = Field(..., description="Search query (templated)")
    max_results: int = Field(10, ge=1, le=100, description="Maximum results to return")
    patent_office: Optional[Literal["USPTO", "EPO", "WIPO", "all"]] = Field(
        "all", description="Patent office to search"
    )
    date_range: Optional[str] = Field(None, description="Date range filter")
    classification: Optional[str] = Field(None, description="Patent classification filter")


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

    source: Dict[str, Any] = Field(..., description="Source metadata for BibTeX entry")
    entry_type: Optional[Literal["article", "book", "inproceedings", "misc", "phdthesis"]] = Field(
        None, description="BibTeX entry type (auto-detected if not specified)"
    )
    key: Optional[str] = Field(None, description="BibTeX citation key (auto-generated if not specified)")


class LiteratureReviewConfig(BaseAdapterConfig):
    """Config for literature review generation adapter."""

    topic: str = Field(..., description="Research topic (templated)")
    papers: Optional[List[Dict[str, Any]]] = Field(
        None, description="Papers to include in review"
    )
    search_query: Optional[str] = Field(None, description="Query to search for additional papers")
    max_papers: int = Field(20, ge=5, le=100, description="Maximum papers to include")
    sections: Optional[List[str]] = Field(
        None, description="Sections to include (introduction, methods, findings, etc.)"
    )
    style: Literal["narrative", "systematic", "scoping"] = Field(
        "narrative", description="Review style"
    )
    provider: Optional[str] = Field(None, description="LLM provider for generation")
    model: Optional[str] = Field(None, description="Model for generation")
