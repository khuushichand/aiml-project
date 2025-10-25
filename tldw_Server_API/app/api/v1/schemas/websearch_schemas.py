from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
try:
    from pydantic import field_validator
except Exception:
    from pydantic import validator as field_validator  # type: ignore


# Only expose engines which are implemented and supported server-side.
# Bing is deprecated in the core and should not be allowed.
SUPPORTED_WEBSEARCH_ENGINES = {"google", "duckduckgo", "brave", "kagi", "tavily", "searx"}


class WebSearchRequest(BaseModel):
    query: str = Field(..., description="User query to search the web for")
    engine: str = Field(
        "google",
        description="Search engine to use. Supported: google, duckduckgo, brave, kagi, tavily, searx",
    )
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

    @field_validator("engine")
    @classmethod
    def validate_engine(cls, value: str) -> str:
        engine = value.lower()
        if engine not in SUPPORTED_WEBSEARCH_ENGINES:
            allowed = ", ".join(sorted(SUPPORTED_WEBSEARCH_ENGINES))
            raise ValueError(f"Unsupported engine '{value}'. Supported engines: {allowed}")
        return engine


class WebSearchFinalAnswer(BaseModel):
    text: str = Field(..., description="Aggregated answer generated from web results")
    evidence: List[Dict[str, Any]] = Field(default_factory=list, description="Relevant snippets backing the answer")
    confidence: float = Field(..., ge=0.0, le=1.0)
    chunks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Intermediate chunk summaries used during aggregation"
    )


class WebSearchRawResponse(BaseModel):
    web_search_results_dict: Dict[str, Any]
    sub_query_dict: Dict[str, Any]


class WebSearchAggregateResponse(BaseModel):
    final_answer: Optional[WebSearchFinalAnswer]
    relevant_results: Optional[Dict[str, Any]]
    web_search_results_dict: Dict[str, Any]
    sub_query_dict: Dict[str, Any]
