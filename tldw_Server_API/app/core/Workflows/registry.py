from __future__ import annotations

import builtins
from dataclasses import dataclass

from tldw_Server_API.app.core.Workflows.capabilities import StepCapability
from tldw_Server_API.app.core.Workflows.capabilities import get_step_capability


@dataclass
class StepType:
    name: str
    description: str

    @property
    def capability(self) -> StepCapability:
        return get_step_capability(self.name)


class StepTypeRegistry:
    """Static step type registry for v0.1 stub."""

    def __init__(self) -> None:
        self._steps: dict[str, StepType] = {
            "media_ingest": StepType("media_ingest", "Ingest and process media (download, extract, chunk, index)"),
            "prompt": StepType("prompt", "Render a templated prompt without calling an LLM"),
            "llm": StepType("llm", "Invoke an LLM chat completion and return text/output"),
            "rag_search": StepType("rag_search", "Run a unified RAG search and return documents"),
            "kanban": StepType("kanban", "Read/write Kanban boards, lists, and cards"),
            "mcp_tool": StepType("mcp_tool", "Invoke an MCP tool with arguments"),
            "acp_stage": StepType("acp_stage", "Execute an ACP-backed planning/implementation/testing stage"),
            "tts": StepType("tts", "Text-to-speech: synthesize audio from text and persist as artifact"),
            "webhook": StepType("webhook", "POST payload to a webhook with HMAC signing and SSRF protections"),
            "delay": StepType("delay", "Pause the workflow for a fixed time (ms)"),
            "log": StepType("log", "Log a templated message at a chosen level"),
            "wait_for_human": StepType("wait_for_human", "Pause for human approval or edits"),
            "wait_for_approval": StepType("wait_for_approval", "Pause until an approval decision is made"),
            "branch": StepType("branch", "Evaluate a condition and jump to the next step by id"),
            "map": StepType("map", "Fan-out over a list and apply a step with optional concurrency; returns results list"),
            "process_media": StepType("process_media", "Process media using internal services without persistence (ephemeral)"),
            "policy_check": StepType("policy_check", "Detect PII/blocked terms/length to gate content flow"),
            "rss_fetch": StepType("rss_fetch", "Fetch RSS/Atom feeds and return items for downstream steps"),
            "atom_fetch": StepType("atom_fetch", "Alias for rss_fetch (Atom feeds)"),
            "embed": StepType("embed", "Create embeddings for text and upsert into Chroma collection"),
            "translate": StepType("translate", "Translate text to a target language via provider-agnostic chat"),
            "stt_transcribe": StepType("stt_transcribe", "Transcribe audio to text with optional diarization"),
            "notify": StepType("notify", "Send a simple notification via webhook (Slack/email)"),
            "diff_change_detector": StepType("diff_change_detector", "Compare previous vs current content and flag changes"),
            "notes": StepType("notes", "CRUD operations on user notes (create, get, list, update, delete, search)"),
            "prompts": StepType("prompts", "Manage prompts library (get, list, create, update, search)"),
            "chunking": StepType("chunking", "Chunk text using various strategies (words, sentences, tokens, etc.)"),
            "web_search": StepType("web_search", "Perform web search using various engines (google, bing, duckduckgo, etc.)"),
            "collections": StepType("collections", "Manage reading list collections (save, update, list, search)"),
            "chatbooks": StepType("chatbooks", "Export and import chatbooks (conversations, notes, prompts)"),
            "evaluations": StepType("evaluations", "Run LLM evaluations (geval, rag, response_quality)"),
            "claims_extract": StepType("claims_extract", "Extract and search claims from text"),
            "character_chat": StepType("character_chat", "Chat with AI characters using character cards"),
            "moderation": StepType("moderation", "Check or redact text content for safety"),
            "sandbox_exec": StepType("sandbox_exec", "Execute code in isolated sandbox environment"),
            "image_gen": StepType("image_gen", "Generate images from text prompts"),
            "summarize": StepType("summarize", "Summarize text using LLM with optional chunking"),
            "query_expand": StepType("query_expand", "Expand search queries using multiple strategies"),
            "rerank": StepType("rerank", "Rerank documents using various scoring strategies"),
            "citations": StepType("citations", "Generate academic citations from documents"),
            "ocr": StepType("ocr", "Run OCR on images to extract text"),
            "pdf_extract": StepType("pdf_extract", "Extract text and metadata from PDF files"),
            "voice_intent": StepType("voice_intent", "Parse voice/text input into actionable intents"),
            # Tier 1: Research Automation
            "query_rewrite": StepType("query_rewrite", "Rewrite search queries for better retrieval results"),
            "hyde_generate": StepType("hyde_generate", "Generate hypothetical document for similarity search (HyDE)"),
            "semantic_cache_check": StepType("semantic_cache_check", "Check semantic cache for similar queries"),
            "search_aggregate": StepType("search_aggregate", "Aggregate and deduplicate results from multiple searches"),
            "entity_extract": StepType("entity_extract", "Extract named entities (people, places, orgs, dates) from text"),
            "bibliography_generate": StepType("bibliography_generate", "Generate formatted citations from sources"),
            "document_table_extract": StepType("document_table_extract", "Extract tables from documents as JSON/CSV"),
            "audio_diarize": StepType("audio_diarize", "Speaker diarization - separate audio by speaker"),
            # Tier 2: Learning/Education
            "flashcard_generate": StepType("flashcard_generate", "Generate flashcards from content using LLM"),
            "quiz_generate": StepType("quiz_generate", "Generate quiz questions from content"),
            "quiz_evaluate": StepType("quiz_evaluate", "Evaluate quiz answers and provide feedback"),
            "outline_generate": StepType("outline_generate", "Generate hierarchical outline from content"),
            "glossary_extract": StepType("glossary_extract", "Extract key terms and definitions"),
            "mindmap_generate": StepType("mindmap_generate", "Generate mindmap structure from content"),
            "eval_readability": StepType("eval_readability", "Calculate readability scores (Flesch, etc.)"),
            # Tier 3: Data Processing
            "json_transform": StepType("json_transform", "Transform JSON using JQ/JMESPath expressions"),
            "json_validate": StepType("json_validate", "Validate JSON against schema"),
            "csv_to_json": StepType("csv_to_json", "Convert CSV data to JSON records"),
            "json_to_csv": StepType("json_to_csv", "Convert JSON records to CSV"),
            "regex_extract": StepType("regex_extract", "Extract text matching regex patterns"),
            "text_clean": StepType("text_clean", "Clean and normalize text"),
            "xml_transform": StepType("xml_transform", "Transform XML using XPath queries"),
            "template_render": StepType("template_render", "Render Jinja2 template with variables"),
            "batch": StepType("batch", "Batch items into chunks for processing"),
            # Tier 4: Workflow Orchestration
            "workflow_call": StepType("workflow_call", "Call another workflow as sub-workflow"),
            "parallel": StepType("parallel", "Execute multiple steps in parallel"),
            "cache_result": StepType("cache_result", "Cache step result for reuse"),
            "retry": StepType("retry", "Wrap step with retry logic"),
            "checkpoint": StepType("checkpoint", "Save workflow state for recovery"),
            # Tier 5: External Integrations
            "s3_upload": StepType("s3_upload", "Upload content to S3-compatible storage"),
            "s3_download": StepType("s3_download", "Download content from S3-compatible storage"),
            "github_create_issue": StepType("github_create_issue", "Create a GitHub issue"),
            "podcast_rss_publish": StepType("podcast_rss_publish", "Publish/merge podcast RSS feed entries"),
            # Tier 6: Agentic Support
            "llm_with_tools": StepType("llm_with_tools", "LLM call that can invoke tools"),
            "llm_critique": StepType("llm_critique", "Run LLM critique on content (Constitutional AI)"),
            "context_build": StepType("context_build", "Build context from multiple sources"),
            # Phase 2: Group A - Individual Utility Nodes
            "document_merge": StepType("document_merge", "Merge multiple documents into one"),
            "document_diff": StepType("document_diff", "Compare two documents, output diff"),
            "markdown_to_html": StepType("markdown_to_html", "Convert markdown to HTML"),
            "html_to_markdown": StepType("html_to_markdown", "Convert HTML to clean markdown"),
            "keyword_extract": StepType("keyword_extract", "Extract keywords from text"),
            "sentiment_analyze": StepType("sentiment_analyze", "Analyze sentiment (+/-/neutral with score)"),
            "language_detect": StepType("language_detect", "Detect language of text"),
            "topic_model": StepType("topic_model", "Extract topics from text corpus"),
            "token_count": StepType("token_count", "Count tokens using model tokenizer"),
            "context_window_check": StepType("context_window_check", "Check if content fits in context window"),
            "llm_compare": StepType("llm_compare", "Run same prompt through multiple LLMs, compare"),
            "image_describe": StepType("image_describe", "Describe image using VLM/multimodal LLM"),
            "report_generate": StepType("report_generate", "Generate structured report from content"),
            "newsletter_generate": StepType("newsletter_generate", "Generate newsletter from content/items"),
            "audio_briefing_compose": StepType("audio_briefing_compose", "Compose multi-voice audio briefing script from article summaries"),
            "slides_generate": StepType("slides_generate", "Generate slide deck structure"),
            "diagram_generate": StepType("diagram_generate", "Generate diagram (mermaid/graphviz)"),
            "email_send": StepType("email_send", "Send email via SMTP"),
            "screenshot_capture": StepType("screenshot_capture", "Capture screenshot of URL"),
            "schedule_workflow": StepType("schedule_workflow", "Schedule workflow for future execution"),
            "timing_start": StepType("timing_start", "Start a named timer"),
            "timing_stop": StepType("timing_stop", "Stop timer, return elapsed time"),
            # Phase 2: Group B - Audio & Video Processing
            "multi_voice_tts": StepType("multi_voice_tts", "Multi-voice TTS with per-section synthesis, concatenation, and normalization"),
            "audio_normalize": StepType("audio_normalize", "Normalize audio volume levels"),
            "audio_concat": StepType("audio_concat", "Concatenate multiple audio files"),
            "audio_trim": StepType("audio_trim", "Trim audio by start/end timestamps"),
            "audio_convert": StepType("audio_convert", "Convert audio format (mp3, wav, ogg)"),
            "audio_extract": StepType("audio_extract", "Extract audio track from video"),
            "audio_mix": StepType("audio_mix", "Mix multiple audio tracks"),
            "video_thumbnail": StepType("video_thumbnail", "Generate thumbnail from video"),
            "video_trim": StepType("video_trim", "Trim video by timestamps"),
            "video_concat": StepType("video_concat", "Concatenate video files"),
            "video_convert": StepType("video_convert", "Convert video format/codec"),
            "video_extract_frames": StepType("video_extract_frames", "Extract frames as images"),
            "subtitle_generate": StepType("subtitle_generate", "Generate subtitles from audio/video"),
            "subtitle_translate": StepType("subtitle_translate", "Translate subtitle file"),
            "subtitle_burn": StepType("subtitle_burn", "Burn subtitles into video"),
            # Phase 2: Group C - Research & Academic
            "arxiv_search": StepType("arxiv_search", "Search arXiv for papers"),
            "arxiv_download": StepType("arxiv_download", "Download paper PDF from arXiv"),
            "pubmed_search": StepType("pubmed_search", "Search PubMed for biomedical papers"),
            "semantic_scholar_search": StepType("semantic_scholar_search", "Search Semantic Scholar"),
            "google_scholar_search": StepType("google_scholar_search", "Search Google Scholar"),
            "patent_search": StepType("patent_search", "Search patent databases"),
            "doi_resolve": StepType("doi_resolve", "Resolve DOI to metadata"),
            "reference_parse": StepType("reference_parse", "Parse citation string to structured"),
            "bibtex_generate": StepType("bibtex_generate", "Generate BibTeX entry"),
            "literature_review": StepType("literature_review", "Generate literature review summary"),
        }

    def list(self) -> builtins.list[StepType]:
        return list(self._steps.values())

    def has(self, name: str) -> bool:
        return name in self._steps
