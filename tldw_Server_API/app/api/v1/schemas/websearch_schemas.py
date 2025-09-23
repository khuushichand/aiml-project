from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class WebSearchRequest(BaseModel):
    query: str = Field(..., description="User query to search the web for")
    engine: str = Field("google", description="Search engine: google, duckduckgo, brave, kagi, searx, tavily, serper, yandex")
    result_count: int = Field(10, ge=1, le=50)
    content_country: str = Field("US")
    search_lang: str = Field("en")
    output_lang: str = Field("en")
    date_range: Optional[str] = None
    safesearch: Optional[str] = None
    site_blacklist: Optional[List[str]] = None
    exactTerms: Optional[str] = None
    excludeTerms: Optional[str] = None
    filter: Optional[str] = None
    geolocation: Optional[str] = None
    search_result_language: Optional[str] = None
    sort_results_by: Optional[str] = None

    subquery_generation: bool = False
    subquery_generation_llm: Optional[str] = None
    user_review: bool = False
    relevance_analysis_llm: Optional[str] = None
    final_answer_llm: Optional[str] = None

    aggregate: bool = Field(False, description="If true, runs relevance + final answer aggregation")


class WebSearchRawResponse(BaseModel):
    web_search_results_dict: Dict[str, Any]
    sub_query_dict: Dict[str, Any]


class WebSearchAggregateResponse(BaseModel):
    final_answer: Optional[str]
    relevant_results: Optional[Dict[str, Any]]
    web_search_results_dict: Dict[str, Any]
    sub_query_dict: Dict[str, Any]

