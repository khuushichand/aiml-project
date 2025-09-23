# paper_search_schemas.py
# Pydantic models and FastAPI request forms for provider-specific paper search.

from typing import Optional, Dict, Any, List
from fastapi import Query
from pydantic import BaseModel


class BioRxivPaper(BaseModel):
    doi: str
    title: str
    authors: Optional[str] = None
    category: Optional[str] = None
    date: Optional[str] = None  # YYYY-MM-DD
    abstract: Optional[str] = None
    server: Optional[str] = None  # biorxiv | medrxiv
    version: Optional[int] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None


class BioRxivSearchResponse(BaseModel):
    query_echo: Dict[str, Any]
    items: List[BioRxivPaper]
    total_results: int
    page: int
    results_per_page: int
    total_pages: int


class BioRxivSearchRequestForm:
    def __init__(
        self,
        q: Optional[str] = Query(None, description="Keyword query to search titles/abstracts."),
        server: str = Query("biorxiv", description="Source server: biorxiv or medrxiv"),
        from_date: Optional[str] = Query(
            None, description="Start date YYYY-MM-DD. Defaults to last 30 days if omitted."
        ),
        to_date: Optional[str] = Query(
            None, description="End date YYYY-MM-DD. Defaults to today if omitted."
        ),
        category: Optional[str] = Query(None, description="Optional subject category to filter."),
        recent_days: Optional[int] = Query(None, ge=1, description="Use most recent N days (alternative to date range)."),
        recent_count: Optional[int] = Query(None, ge=1, description="Use most recent N posts (alternative to date range)."),
        page: int = Query(1, ge=1, description="Page number (1-indexed)."),
        results_per_page: int = Query(10, ge=1, le=100, description="Results per page (max 100)."),
    ):
        self.q = q
        self.server = server
        self.from_date = from_date
        self.to_date = to_date
        self.category = category
        self.recent_days = recent_days
        self.recent_count = recent_count
        self.page = page
        self.results_per_page = results_per_page


class BioRxivPublishedRecord(BaseModel):
    biorxiv_doi: str
    published_doi: Optional[str] = None
    published_journal: Optional[str] = None
    preprint_platform: Optional[str] = None
    preprint_title: Optional[str] = None
    preprint_authors: Optional[str] = None
    preprint_category: Optional[str] = None
    preprint_date: Optional[str] = None
    published_date: Optional[str] = None
    preprint_abstract: Optional[str] = None
    preprint_author_corresponding: Optional[str] = None
    preprint_author_corresponding_institution: Optional[str] = None


class BioRxivPubsSearchResponse(BaseModel):
    query_echo: Dict[str, Any]
    items: List[BioRxivPublishedRecord]
    total_results: int
    page: int
    results_per_page: int
    total_pages: int


class BioRxivPubsSearchRequestForm:
    def __init__(
        self,
        server: str = Query("biorxiv", description="Server: biorxiv or medrxiv"),
        from_date: Optional[str] = Query(None, description="YYYY-MM-DD start (if recent params omitted)"),
        to_date: Optional[str] = Query(None, description="YYYY-MM-DD end (if recent params omitted)"),
        recent_days: Optional[int] = Query(None, ge=1, description="Use most recent N days."),
        recent_count: Optional[int] = Query(None, ge=1, description="Use most recent N posts."),
        q: Optional[str] = Query(None, description="Client-side filter over title/abstract/authors"),
        include_abstracts: bool = Query(True, description="Include preprint_abstract field in results"),
        page: int = Query(1, ge=1),
        results_per_page: int = Query(10, ge=1, le=100),
    ):
        self.server = server
        self.from_date = from_date
        self.to_date = to_date
        self.recent_days = recent_days
        self.recent_count = recent_count
        self.q = q
        self.include_abstracts = include_abstracts
        self.page = page
        self.results_per_page = results_per_page


# End of paper_search_schemas.py
