"""Research and academic adapters.

This module includes adapters for research operations:
- deep_research: Launch a deep research session
- deep_research_wait: Wait for a deep research session
- deep_research_load_bundle: Load references from a completed deep research session
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

from tldw_Server_API.app.core.Workflows.adapters.research.bibliography import (
    run_bibtex_generate_adapter,
    run_doi_resolve_adapter,
    run_literature_review_adapter,
    run_reference_parse_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.research.launch import (
    run_deep_research_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.research.wait import (
    run_deep_research_wait_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.research.load_bundle import (
    run_deep_research_load_bundle_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.research.search import (
    run_arxiv_download_adapter,
    run_arxiv_search_adapter,
    run_google_scholar_search_adapter,
    run_patent_search_adapter,
    run_pubmed_search_adapter,
    run_semantic_scholar_search_adapter,
)

__all__ = [
    "run_deep_research_adapter",
    "run_deep_research_wait_adapter",
    "run_deep_research_load_bundle_adapter",
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
