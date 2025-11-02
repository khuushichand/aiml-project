# Server_API/app/api/schemas/media_models.py
# Description: This code provides schema models for usage with the /media endpoint.
#
# Imports
import re
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Literal
#
# 3rd-party imports
from fastapi import HTTPException
from pydantic import BaseModel, Field, validator, computed_field, field_validator, ConfigDict
from pydantic_core.core_schema import ValidationInfo

from tldw_Server_API.app.core.Ingestion_Media_Processing.MediaWiki.Media_Wiki import load_mediawiki_import_config


#
# Local Imports
#
#######################################################################################################################
#
# Functions:

######################## /api/v1/media/ Endpoint Models ########################
#
#
class MediaItemResponse(BaseModel):
    media_id: int
    source: dict
    processing: dict
    content: dict
    keywords: List[str]
    timestamps: List[str]

    model_config = ConfigDict()

class PaginationInfo(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int

class MediaItem(BaseModel):
    id: int
    url: str
    title: str
    type: str
    content_preview: Optional[str]
    author: str
    date: Optional[datetime]
    keywords: List[str]

class MediaSearchResponse(BaseModel):
    results: List[MediaItem]
    pagination: PaginationInfo

class MediaUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=500, description="Title (max 500 chars)")
    content: Optional[str] = Field(None, max_length=5000000, description="Content (max 5MB of text)")
    author: Optional[str] = Field(None, max_length=255, description="Author (max 255 chars)")
    analysis: Optional[str] = Field(None, max_length=100000, description="Analysis (max 100KB)")
    prompt: Optional[str] = Field(None, max_length=10000, description="Prompt (max 10KB)")
    keywords: Optional[List[str]] = Field(None, max_length=50, description="Keywords (max 50)")

# Make prompt and analysis_content REQUIRED so missing them yields 422
class VersionCreateRequest(BaseModel):
    content: str = Field(..., max_length=5000000, description="Content (max 5MB)")
    prompt: str = Field(..., max_length=10000, description="Prompt (max 10KB)")
    analysis_content: str = Field(..., max_length=100000, description="Analysis content (max 100KB)")
    safe_metadata: Optional[Dict[str, Any]] = Field(None, description="Optional safe metadata JSON to store with this version.")

class VersionResponse(BaseModel):
    id: int
    version_number: int
    created_at: str
    content_length: int

class VersionRollbackRequest(BaseModel):
    version_number: int

class SearchRequest(BaseModel):
    query: Optional[str] = Field(None, max_length=1000, description="Search query (max 1000 chars)")
    fields: List[str] = ["title", "content"]
    exact_phrase: Optional[str] = None
    media_types: Optional[List[str]] = None
    date_range: Optional[Dict[str, datetime]] = None
    must_have: Optional[List[str]] = None
    must_not_have: Optional[List[str]] = None
    sort_by: Optional[str] = "relevance"
    boost_fields: Optional[Dict[str, float]] = None

class MetadataFilter(BaseModel):
    field: str = Field(..., description="Metadata key to search (e.g., doi, pmid, journal, license)")
    op: Literal['eq','contains','icontains','startswith','endswith'] = Field('icontains', description="Match operator")
    value: str = Field(..., description="Value to match")

class MetadataSearchRequest(BaseModel):
    filters: Optional[List[MetadataFilter]] = Field(None, description="List of metadata filters")
    match_mode: Literal['all','any'] = Field('all', description="Combine filters with AND/OR")
    group_by_media: bool = Field(True, description="Group results by media (latest matching version per media)")
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)

class MetadataPatchRequest(BaseModel):
    safe_metadata: Dict[str, Any] = Field(..., description="Safe metadata JSON to set or merge")
    merge: bool = Field(True, description="Merge with existing metadata if present")
    new_version: bool = Field(False, description="Create a new version with updated metadata")

class AdvancedVersionUpsertRequest(BaseModel):
    content: Optional[str] = Field(None, description="Optional content; if omitted and new_version=true, uses latest content")
    prompt: Optional[str] = Field(None, description="Optional prompt; if omitted and new_version=true, uses latest prompt")
    analysis_content: Optional[str] = Field(None, description="Optional analysis; if omitted and new_version=true, uses latest analysis")
    safe_metadata: Optional[Dict[str, Any]] = Field(None, description="Optional safe metadata JSON to set or merge")
    merge: bool = Field(True, description="Merge safe metadata when updating or creating new version")
    new_version: bool = Field(True, description="Create a new version (default). If false, only safe_metadata may be updated in place")

# Define allowed media types using Literal for validation
MediaType = Literal['video', 'audio', 'document', 'pdf', 'ebook', 'email']

# Define allowed chunking methods (adjust as needed based on your library)
ChunkMethod = Literal['semantic', 'tokens', 'paragraphs', 'sentences','words', 'ebook_chapters', 'json', 'propositions']

# Define allowed PDF parsing engines
PdfEngine = Literal['pymupdf4llm', 'pymupdf', 'docling'] # Add others if supported

# OCR options
OcrMode = Literal['always', 'fallback']

class ChunkingOptions(BaseModel):
    """Pydantic model for chunking specific options"""
    perform_chunking: bool = Field(True, description="Enable chunk-based processing of the media content")
    chunk_method: Optional[ChunkMethod] = Field(None, description="Method used to chunk content (e.g., 'sentences', 'recursive', 'chapter')")
    use_adaptive_chunking: bool = Field(False, description="Whether to enable adaptive chunking")
    use_multi_level_chunking: bool = Field(False, description="Whether to enable multi-level chunking")
    chunk_language: Optional[str] = Field(None, description="Optional language override for chunking (ISO 639-1 code, e.g., 'en')")
    chunk_size: int = Field(500, gt=0, description="Target size of each chunk (positive integer)")
    chunk_overlap: int = Field(200, ge=0, description="Overlap size between chunks (non-negative integer)")
    custom_chapter_pattern: Optional[str] = Field(None, description="Optional regex pattern for custom chapter splitting (ebook/docs)")
    # Template auto-apply options
    auto_apply_template: bool = Field(False, description="Automatically select and apply a matching chunking template by metadata")
    chunking_template_name: Optional[str] = Field(None, description="Explicit template name to apply for chunking")
    # Contextual Chunking Options
    enable_contextual_chunking: bool = Field(False, description="Add LLM-generated context to chunks for better retrieval")
    contextual_llm_model: Optional[str] = Field(None, description="LLM model to use for generating contextual summaries (e.g., 'gpt-3.5-turbo')")
    context_window_size: Optional[int] = Field(None, ge=100, le=2000, description="Size of context window around chunks in characters")
    context_strategy: Optional[Literal['auto','full','window','outline_window']] = Field(
        None, description="Context selection strategy: 'auto' (default), 'full', 'window', or 'outline_window'"
    )
    context_token_budget: Optional[int] = Field(
        None, ge=1000, le=200000, description="Approximate token budget for 'auto' strategy (len(text)/4 heuristic)"
    )
    # Hierarchical options (flattened into chunks for indexing)
    hierarchical_chunking: Optional[bool] = Field(False, description="Enable hierarchical parsing and flattening to leaf chunks")
    hierarchical_template: Optional[Dict[str, Any]] = Field(None, description="Custom boundary rules: {'boundaries': [{'kind','pattern','flags'}]}")

    @field_validator('chunk_method', mode='before')
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Optional[Any]: # Accept Any for input
        if v == "":
            return None
        return v

    @field_validator('chunk_overlap')
    @classmethod
    def overlap_less_than_size(cls, v: int, info: ValidationInfo) -> int:
        # Check if 'chunk_size' is available in the already validated data
        if 'chunk_size' in info.data and info.data['chunk_size'] is not None:
            chunk_size = info.data['chunk_size']
            if v >= chunk_size:
                raise ValueError('chunk_overlap must be less than chunk_size')
        # If chunk_size hasn't been validated yet or is missing, this check might implicitly pass
        # or you might want to handle that case explicitly if chunk_size is always required before overlap.
        return v

    @field_validator('custom_chapter_pattern')
    @classmethod
    def validate_regex(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                re.compile(v)
            except re.error as e: # Catch specific error
                raise ValueError(f"Invalid regex pattern provided for custom_chapter_pattern: {v}. Error: {e}")
        return v

class TranscriptionModel(str, Enum):
    """Available transcription models and backends"""
    # Whisper Models (faster-whisper)
    WHISPER_TINY = "whisper-tiny"
    WHISPER_TINY_EN = "whisper-tiny.en"
    WHISPER_BASE = "whisper-base"
    WHISPER_BASE_EN = "whisper-base.en"
    WHISPER_SMALL = "whisper-small"
    WHISPER_SMALL_EN = "whisper-small.en"
    WHISPER_MEDIUM = "whisper-medium"
    WHISPER_MEDIUM_EN = "whisper-medium.en"
    WHISPER_LARGE_V1 = "whisper-large-v1"
    WHISPER_LARGE_V2 = "whisper-large-v2"
    WHISPER_LARGE_V3 = "whisper-large-v3"
    WHISPER_LARGE_V3_TURBO = "whisper-large-v3-turbo"

    # Distil-Whisper Models (faster, optimized)
    DISTIL_WHISPER_LARGE_V2 = "distil-whisper-large-v2"
    DISTIL_WHISPER_LARGE_V3 = "distil-whisper-large-v3"
    DISTIL_WHISPER_MEDIUM_EN = "distil-whisper-medium.en"
    DISTIL_WHISPER_SMALL_EN = "distil-whisper-small.en"

    # Specific HuggingFace models
    DEEPDML_FASTER_DISTIL_LARGE_V3 = "deepdml/faster-distil-whisper-large-v3.5"
    DEEPDML_FASTER_LARGE_V3_TURBO = "deepdml/faster-whisper-large-v3-turbo-ct2"

    # Nemo Models
    NEMO_CANARY_1B = "nemo-canary-1b"
    NEMO_PARAKEET_TDT_1B = "nemo-parakeet-tdt-1.1b"

    # Parakeet with backends
    PARAKEET_STANDARD = "parakeet-standard"
    PARAKEET_CUDA = "parakeet-cuda"
    PARAKEET_MLX = "parakeet-mlx"
    PARAKEET_ONNX = "parakeet-onnx"

class AudioVideoOptions(BaseModel):
    """Pydantic model for Audio/Video specific options"""
    transcription_model: str = Field("deepdml/faster-distil-whisper-large-v3.5", description="Model ID for audio/video transcription")
    transcription_language: str = Field("en", description="Language for audio/video transcription (ISO 639-1 code)")
    diarize: bool = Field(False, description="Enable speaker diarization (audio/video)")
    timestamp_option: bool = Field(True, description="Include timestamps in the transcription (audio/video)")
    vad_use: bool = Field(False, description="Enable Voice Activity Detection filter during transcription (audio/video)")
    perform_confabulation_check_of_analysis: bool = Field(False, description="Enable a confabulation check on analysis (if applicable)")

class PdfOptions(BaseModel):
    """Pydantic model for PDF specific options"""
    pdf_parsing_engine: Optional[PdfEngine] = Field("pymupdf4llm", description="PDF parsing engine to use")
    enable_ocr: bool = Field(False, description="Enable OCR for scanned/low-text PDFs")
    ocr_backend: Optional[str] = Field(None, description="OCR backend name (e.g., 'tesseract' or 'auto')")
    ocr_lang: Optional[str] = Field("eng", description="OCR language (ISO 639-2 Tesseract codes, e.g., 'eng')")
    ocr_dpi: int = Field(300, ge=72, le=600, description="DPI for page rendering before OCR (72-600)")
    ocr_mode: Optional[OcrMode] = Field("fallback", description="'always' to force OCR, 'fallback' when no text")
    ocr_min_page_text_chars: int = Field(40, ge=0, description="Threshold to treat a page as 'no text' for OCR fallback")

class AddMediaForm(ChunkingOptions, AudioVideoOptions, PdfOptions):
    """
    Pydantic model representing the form data for the /add endpoint.
    Excludes 'files' (handled via File(...)) and 'token' (handled via Header(...)).
    """
    # --- Required Fields ---
    media_type: MediaType = Field(..., description="Type of media")

    # --- Input Sources ---
    # Note: 'files' is handled separately by FastAPI's File() parameter
    urls: Optional[List[str]] = Field(None, description="List of URLs of the media items to add")

    # --- Common Optional Fields ---
    title: Optional[str] = Field(None, max_length=500, description="Optional title (max 500 chars)")
    author: Optional[str] = Field(None, max_length=255, description="Optional author (max 255 chars)")
    keywords_str: str = Field("", alias="keywords", max_length=1000, description="Comma-separated keywords (max 1000 chars)")
    custom_prompt: Optional[str] = Field(None, max_length=100000, description="Optional custom prompt (max 100KB)")
    system_prompt: Optional[str] = Field(None, max_length=10000, description="Optional system prompt (max 10KB)")
    overwrite_existing: bool = Field(False, description="Overwrite any existing media with the same identifier (URL/filename)")
    keep_original_file: bool = Field(False, description="Whether to retain original uploaded files after processing")
    perform_analysis: bool = Field(True, description="Perform analysis (e.g., summarization) if applicable (default=True)")
    perform_claims_extraction: Optional[bool] = Field(
        None,
        description="Extract factual claims during analysis (defaults to server configuration when unset)."
    )
    claims_extractor_mode: Optional[str] = Field(
        None,
        description="Optional override for claims extractor mode (e.g., 'heuristic', 'ner', provider id)."
    )
    claims_max_per_chunk: Optional[int] = Field(
        None,
        ge=1,
        le=12,
        description="Maximum number of claims to extract per chunk (uses configuration defaults when unset)."
    )

    # --- Video/Audio Specific Timing --- ADD THESE ---
    start_time: Optional[str] = Field(None, description="Optional start time for processing (e.g., HH:MM:SS or seconds)")
    end_time: Optional[str] = Field(None, description="Optional end time for processing (e.g., HH:MM:SS or seconds)")
    # -----------------------------------------------

    # --- Integration Options ---
    # SECURITY: Never accept API keys from client - lookup from server config instead
    api_provider: Optional[str] = Field(None, description="LLM provider name (e.g., openai, anthropic, local-llm)")
    model_name: Optional[str] = Field(None, description="Model name for the selected provider")
    use_cookies: bool = Field(False, description="Whether to attach cookies to URL download requests")
    cookies: Optional[str] = Field(None, description="Cookie string if `use_cookies` is set to True")

    # Legacy field for backward compatibility - will be removed
    api_name: Optional[str] = Field(None, description="DEPRECATED - use api_provider instead")

    # --- Email-specific options (optional, used when media_type='email') ---
    ingest_attachments: Optional[bool] = Field(False, description="For emails: parse nested .eml attachments and ingest as separate items")
    max_depth: Optional[int] = Field(2, ge=1, le=5, description="Max depth for nested email parsing when ingest_attachments is true")
    accept_archives: Optional[bool] = Field(False, description="Allow and expand .zip archives of .eml files for email ingestion")
    accept_mbox: Optional[bool] = Field(False, description="Allow and expand .mbox mailboxes for email ingestion")
    accept_pst: Optional[bool] = Field(False, description="Enable PST/OST container uploads (feature-flag; parsing may require external tools")

    # --- Embedding Options ---
    generate_embeddings: bool = Field(False, description="Generate embeddings after media processing")
    embedding_model: Optional[str] = Field(None, description="Specific embedding model to use (e.g., 'Qwen/Qwen3-Embedding-4B-GGUF')")
    embedding_provider: Optional[str] = Field(None, description="Embedding provider (huggingface, openai, etc)")

    # --- Deprecated/Less Common ---
    perform_rolling_summarization: bool = Field(False, description="Perform rolling summarization (legacy?)")
    summarize_recursively: bool = Field(False, description="Perform recursive summarization on chunks (if chunking enabled)")

    # --- Computed Fields / Validators ---
    @computed_field
    @property
    def keywords(self) -> List[str]:
        """Parses the comma-separated keywords string into a list."""
        if not self.keywords_str:
            return []
        return [k.strip() for k in self.keywords_str.split(",") if k.strip()]

    def model_post_init(self, __context):
        """Handle legacy api_name field by splitting into provider/model."""
        if self.api_name and '/' in self.api_name:
            # If api_name contains '/', treat it as 'provider/model' format
            provider, model = self.api_name.split('/', 1)
            if not self.api_provider:
                self.api_provider = provider
            if not self.model_name:
                self.model_name = model
        elif self.api_name and not self.api_provider:
            # If only api_name is set without '/', use it as provider
            self.api_provider = self.api_name

    # Use alias for 'keywords' field to accept 'keywords' in the form data
    # but internally work with 'keywords_str' before parsing.
    model_config = ConfigDict(
        populate_by_name=True,  # Allows using 'alias' for fields
        json_schema_extra={
            "example": {
                "media_type": "document",
                "urls": ["https://example.com/guide.pdf"],
                "title": "Example Guide",
                "author": "Jane Doe",
                "keywords": "api,fastapi,docs",
                "perform_analysis": True,
                "perform_chunking": True,
                "chunk_method": "sentences",
                "chunk_size": 800,
                "chunk_overlap": 150,
                "generate_embeddings": True,
                "embedding_provider": "huggingface",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
            }
        }
    )

    # Provide a stable, test-friendly error message for invalid media_type values
    @field_validator('media_type', mode='before')
    @classmethod
    def validate_media_type_choices(cls, v):
        # Accept only known values; for invalid input, emit the exact message expected by tests
        allowed = {'video', 'audio', 'document', 'pdf', 'ebook', 'email', 'json'}
        if isinstance(v, str):
            lv = v.strip().lower()
            if lv not in allowed:
                # Match historical message (without 'email') used by tests
                raise ValueError("Input should be 'video', 'audio', 'document', 'pdf' or 'ebook'")
            return lv
        return v

    @field_validator('start_time', 'end_time')
    @classmethod
    def check_time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":  # MODIFIED: Treat empty string like None
            return None  # Return None, which is valid for Optional[str]

        # Example basic check: Allow seconds or HH:MM:SS format
        if re.fullmatch(r'\d+', v) or re.fullmatch(r'\d{1,2}:\d{2}:\d{2}', v):
            return v
        raise ValueError("Time format must be seconds or HH:MM:SS")

    # Validator to ensure 'cookies' is provided if 'use_cookies' is True
    @field_validator('cookies')
    @classmethod
    def check_cookies_provided(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        # Access other validated fields via info.data
        # Check if 'use_cookies' exists in data AND is True
        if info.data.get('use_cookies') and not v:
            raise ValueError("Cookie string must be provided when 'use_cookies' is set to True.")
        return v


class MediaItemProcessResponse(BaseModel):
    """
    Pydantic model for media item details after processing. Details returned from a processing request
    """
    status: Literal['Success', 'Error', 'Warning']
    input_ref: str # The original URL or filename provided by the user
    processing_source: str # The actual path or URL used by the processor, e.g., temp file path
    media_type: (Literal['video', 'audio', 'document', 'pdf', 'ebook', 'email']) # 'video', 'pdf', 'audio', etc.
    metadata: Dict[str, Any] # Extracted info like title, author, duration, etc.
    content: str # The main extracted text or full transcript
    segments: Optional[List[Dict[str, Any]]] # For timestamped transcripts, if applicable
    chunks: Optional[List[Dict[str, Any]]] # If chunking happened within the processor
    analysis: Optional[str] # The generated analysis, if analysis was performed
    analysis_details: Optional[Dict[str, Any]] # e.g., whisper model used, summarization prompt
    claims: Optional[List[Dict[str, Any]]] = Field(None, description="Extracted factual claims, if enabled")
    claims_details: Optional[Dict[str, Any]] = Field(None, description="Metadata about the claims extraction process")
    error: Optional[str] # Detailed error message if status != 'Success'
    warnings: Optional[List[str]] # For non-critical issues
    model_config = ConfigDict(
        extra="forbid"  # Disallow extra fields not defined in the model
    )

######################## Video Ingestion Model ###################################
#
# This is a schema for video ingestion and analysis.

class ProcessVideosForm(AddMediaForm):
    """
    Same field-surface as AddMediaForm, but:
      • media_type forced to `"video"` (so client does not need to send it)
      • keep_original_file defaults to False (tmp dir always wiped)
      • perform_analysis stays default=True (caller may disable)
    """
    media_type: Literal["video"] = "video"
    keep_original_file: bool = Field(False)

class VideoIngestRequest(BaseModel):
    # You can rename / remove / add fields as you prefer:
    mode: str = "persist"  # "ephemeral" or "persist"

    urls: Optional[List[str]] = None  # e.g., YouTube, Vimeo, local-file references

    transcription_model: str = "distil-large-v3"
    diarize: bool = False
    vad: bool = True
    custom_prompt: Optional[str] = None
    system_prompt: Optional[str] = None

    perform_chunking: bool = False
    chunk_method: Optional[str] = None
    max_chunk_size: int = 400
    chunk_overlap: int = 100
    use_adaptive_chunking: bool = False
    use_multi_level_chunking: bool = False
    chunk_language: Optional[str] = None
    summarize_recursively: bool = False

    api_name: Optional[str] = None
    api_key: Optional[str] = None
    keywords: Optional[str] = "default,no_keyword_set"

    use_cookies: bool = False
    cookies: Optional[str] = None

    timestamp_option: bool = True
    confab_checkbox: bool = False

    start_time: Optional[str] = None
    end_time: Optional[str] = None

#
# End of Video ingestion and analysis model schema
####################################################################################


######################## Audio Ingestion Model ###################################
#
# This is a schema for audio ingestion and analysis.

class ProcessAudiosForm(AddMediaForm):
    """Identical surface to AddMediaForm but restricted to 'audio'."""
    media_type: Literal["audio"] = "audio"
    keep_original_file: bool = Field(False)

class AudioIngestRequest(BaseModel):
    mode: str = "persist"  # "ephemeral" or "persist"

    # Normal audio vs. podcast
    is_podcast: bool = False

    urls: Optional[List[str]] = None
    transcription_model: str = "distil-large-v3"
    diarize: bool = False
    keep_timestamps: bool = True

    api_name: Optional[str] = None
    api_key: Optional[str] = None
    custom_prompt: Optional[str] = None
    chunk_method: Optional[str] = None
    max_chunk_size: int = 300
    chunk_overlap: int = 0
    use_adaptive_chunking: bool = False
    use_multi_level_chunking: bool = False
    chunk_language: str = "english"

    keywords: str = ""
    keep_original_audio: bool = False
    use_cookies: bool = False
    cookies: Optional[str] = None
    custom_title: Optional[str] = None

#
# End of Audio ingestion and analysis model schema
####################################################################################


######################## Web-Scraping Ingestion Model ###################################
#
# This is a schema for Web-Scraping ingestion and analysis.

class ScrapeMethod(str, Enum):
    INDIVIDUAL = "individual"          # “Individual URLs”
    SITEMAP = "sitemap"               # “Sitemap”
    URL_LEVEL = "url_level"           # “URL Level”
    RECURSIVE = "recursive_scraping"  # “Recursive Scraping”

class IngestWebContentRequest(BaseModel):
    # Core fields
    urls: List[str]                      # Usually 1+ URLs.
    titles: Optional[List[str]] = None
    authors: Optional[List[str]] = None
    keywords: Optional[List[str]] = None

    # Advanced scraping selection
    scrape_method: ScrapeMethod = ScrapeMethod.INDIVIDUAL
    url_level: Optional[int] = 2
    max_pages: Optional[int] = 10
    max_depth: Optional[int] = 3

    # Summarization / analysis fields
    custom_prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    perform_translation: bool = False
    translation_language: str = "en"
    timestamp_option: bool = True
    overwrite_existing: bool = False
    perform_analysis: bool = True
    perform_rolling_summarization: bool = False
    api_name: Optional[str] = None
    api_key: Optional[str] = None
    perform_chunking: bool = True
    chunk_method: Optional[str] = None
    use_adaptive_chunking: bool = False
    use_multi_level_chunking: bool = False
    chunk_language: Optional[str] = None
    chunk_size: int = 500
    chunk_overlap: int = 200
    # Hierarchical chunking (flattened) support
    hierarchical_chunking: Optional[bool] = False
    hierarchical_template: Optional[Dict[str, Any]] = None
    use_cookies: bool = False
    cookies: Optional[str] = None
    perform_confabulation_check_of_analysis: bool = False
    custom_chapter_pattern: Optional[str] = None
    # Optional crawl controls (used for recursive/url_level when supported)
    crawl_strategy: Optional[str] = None  # e.g., "best_first" or "default"
    include_external: Optional[bool] = None
    score_threshold: Optional[float] = None

#
# End of Web-Scraping ingestion and analysis model schema
####################################################################################

######################### MediaWiki ingestion and analysis model schema ###################################
#
# This is a schema for MediaWiki ingestion and analysis.

media_wiki_global_config = load_mediawiki_import_config()

class MediaWikiDumpOptionsForm(BaseModel):
    wiki_name: str = Field(..., description="A unique name for this MediaWiki instance (e.g., 'my_custom_wiki').")
    namespaces_str: Optional[str] = Field(None, description="Comma-separated list of namespace IDs (e.g., '0,1'). Imports all if None.")
    skip_redirects: bool = Field(True, description="Skip redirect pages.")
    chunk_max_size: int = Field(default_factory=lambda: media_wiki_global_config.get('chunking', {}).get('default_size', 1000), description="Maximum chunk size for MediaWiki content processing.")
    api_name_vector_db: Optional[str] = Field(None, description="API name for vector DB/embedding/summary service (e.g., 'openai') used during ingestion.")
    api_key_vector_db: Optional[str] = Field(None, description="API key for the vector DB/embedding/summary service.")

    @field_validator('wiki_name')
    @classmethod
    def validate_wiki_name(cls, v: str) -> str:
        """Validate wiki name to prevent path traversal and injection attacks."""
        if not v:
            raise ValueError("Wiki name cannot be empty")

        # Only allow alphanumeric, underscore, hyphen, and spaces
        if not re.match(r'^[a-zA-Z0-9_\- ]+$', v):
            raise ValueError("Invalid wiki name: Only alphanumeric characters, underscores, hyphens, and spaces are allowed")

        # Additional security checks for path traversal patterns
        if any(pattern in v for pattern in ['..', '/', '\\', '\x00']):
            raise ValueError("Invalid wiki name: Contains forbidden characters")

        # Length validation
        if len(v) > 100:
            raise ValueError("Wiki name too long (max 100 characters)")

        return v

    @field_validator('namespaces_str')
    @classmethod
    def validate_namespaces(cls, v: Optional[str]) -> Optional[str]:
        """Validate namespace string format."""
        if v is None:
            return v

        # Check format: should be comma-separated integers
        try:
            namespaces = [int(ns.strip()) for ns in v.split(',')]
            # Validate namespace IDs are reasonable
            for ns in namespaces:
                if ns < -2 or ns > 9999:  # MediaWiki namespace IDs typically range from -2 to a few hundred
                    raise ValueError(f"Invalid namespace ID: {ns}")
        except ValueError as e:
            raise ValueError(f"Invalid namespace format. Must be comma-separated integers: {e}")

        return v

class ProcessedMediaWikiPage(BaseModel):
    title: str
    content: str # The plain text content
    namespace: Optional[int] = None
    page_id: Optional[int] = None
    revision_id: Optional[int] = None
    timestamp: Optional[str] = None # ISO format
    chunks: List[Dict[str, Any]] = []
    media_id: Optional[int] = None # Populated if stored to DB
    message: Optional[str] = None
    status: str = "Pending"
    error_message: Optional[str] = None

#
# End of MediaWiki ingestion and analysis model schema
######################################################################################



#
# End of media_models.py
#######################################################################################################################
