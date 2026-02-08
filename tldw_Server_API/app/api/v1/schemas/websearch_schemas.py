from typing import Any, Optional

from pydantic import BaseModel, Field

try:
    from pydantic import field_validator
except Exception:
    from pydantic import validator as field_validator  # type: ignore


# Expose engines that are implemented or explicitly stubbed server-side.
# Deprecated/placeholder engines return a processing_error rather than 422.
SUPPORTED_WEBSEARCH_ENGINES = {
    "google",
    "duckduckgo",
    "brave",
    "kagi",
    "tavily",
    "searx",
    "exa",
    "firecrawl",
    "baidu",
    "bing",
    "yandex",
    "sogou",
    "startpage",
    "stract",
    "serper",
    "4chan",
}


class WebSearchRequest(BaseModel):
    query: str = Field(..., description="User query to search the web for")
    engine: str = Field(
        "google",
        description="Search engine to use. Supported: google, duckduckgo, brave, kagi, tavily, searx, serper, exa, firecrawl, 4chan",
    )
    result_count: int = Field(10, ge=1, le=50)
    content_country: str = Field("US")
    search_lang: str = Field("en")
    output_lang: str = Field("en")
    date_range: Optional[str] = None
    safesearch: Optional[str] = None
    site_blacklist: Optional[list[str]] = None
    exactTerms: Optional[str] = None
    excludeTerms: Optional[str] = None
    filter: Optional[str] = None
    geolocation: Optional[str] = None
    search_result_language: Optional[str] = None
    sort_results_by: Optional[str] = None
    # Provider overrides
    searx_url: Optional[str] = None
    searx_json_mode: bool = False
    google_domain: Optional[str] = None
    boards: Optional[list[str]] = Field(
        default=None,
        description="Optional board filters for 4chan engine (e.g., ['g','tv','pol']).",
    )
    max_threads_per_board: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000,
        description="Optional per-board scan cap for 4chan engine.",
    )
    max_archived_threads_per_board: Optional[int] = Field(
        default=None,
        ge=1,
        le=500,
        description="Optional per-board scan cap for archived 4chan threads.",
    )
    include_archived: bool = Field(
        default=False,
        description="When true and engine=4chan, include archived thread search results.",
    )

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
    evidence: list[dict[str, Any]] = Field(default_factory=list, description="Relevant snippets backing the answer")
    confidence: float = Field(..., ge=0.0, le=1.0)
    chunks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Intermediate chunk summaries used during aggregation"
    )


class WebSearchRawResponse(BaseModel):
    web_search_results_dict: dict[str, Any]
    sub_query_dict: dict[str, Any]


class WebSearchAggregateResponse(BaseModel):
    final_answer: Optional[WebSearchFinalAnswer]
    relevant_results: Optional[dict[str, Any]]
    web_search_results_dict: dict[str, Any]
    sub_query_dict: dict[str, Any]
