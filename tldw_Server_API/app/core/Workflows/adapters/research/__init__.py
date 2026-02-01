"""Research and academic adapters.

This module includes adapters for research operations:
- arxiv_search: Search arXiv
- arxiv_download: Download from arXiv
- pubmed_search: Search PubMed
- semantic_scholar_search: Search Semantic Scholar
- google_scholar_search: Search Google Scholar
- patent_search: Search patents
- doi_resolve: Resolve DOI
- reference_parse: Parse references
- bibtex_generate: Generate BibTeX
- literature_review: Generate literature review
"""

from tldw_Server_API.app.core.Workflows.adapters.research.search import (
    run_arxiv_search_adapter,
    run_arxiv_download_adapter,
    run_pubmed_search_adapter,
    run_semantic_scholar_search_adapter,
    run_google_scholar_search_adapter,
    run_patent_search_adapter,
)

from tldw_Server_API.app.core.Workflows.adapters.research.bibliography import (
    run_doi_resolve_adapter,
    run_reference_parse_adapter,
    run_bibtex_generate_adapter,
    run_literature_review_adapter,
)

__all__ = [
    "run_arxiv_search_adapter",
    "run_arxiv_download_adapter",
    "run_pubmed_search_adapter",
    "run_semantic_scholar_search_adapter",
    "run_google_scholar_search_adapter",
    "run_patent_search_adapter",
    "run_doi_resolve_adapter",
    "run_reference_parse_adapter",
    "run_bibtex_generate_adapter",
    "run_literature_review_adapter",
]
