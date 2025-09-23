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
        page: int = Query(1, ge=1, description="Page number (1-indexed)."),
        results_per_page: int = Query(10, ge=1, le=100, description="Results per page (max 100)."),
    ):
        self.q = q
        self.server = server
        self.from_date = from_date
        self.to_date = to_date
        self.category = category
        self.page = page
        self.results_per_page = results_per_page


# End of paper_search_schemas.py
