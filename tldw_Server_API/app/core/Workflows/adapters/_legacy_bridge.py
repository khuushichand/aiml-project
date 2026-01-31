"""Bridge module for registering legacy adapters.

This module handles the registration of adapters that haven't been migrated yet
from the original adapters.py file to the new submodule structure.

The registration is deferred to avoid circular imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tldw_Server_API.app.core.Workflows.adapters._registry import AdapterRegistry

_registered = False


def register_legacy_adapters(registry: "AdapterRegistry") -> None:
    """Register all legacy adapters from the original adapters.py file.

    This function is called once during module initialization to register
    any adapters that haven't been migrated to the new submodule structure yet.

    Args:
        registry: The adapter registry to register adapters with.
    """
    global _registered
    if _registered:
        return

    try:
        # Import the legacy adapters module (renamed to avoid conflict with this package)
        from tldw_Server_API.app.core.Workflows import _adapters_legacy as legacy

        # Audio adapters
        _register_if_missing(registry, "tts", legacy.run_tts_adapter, "audio", "Text-to-speech synthesis", True, ["audio", "speech"])
        _register_if_missing(registry, "stt_transcribe", legacy.run_stt_transcribe_adapter, "audio", "Speech-to-text transcription", False, ["audio", "speech"])
        _register_if_missing(registry, "audio_normalize", legacy.run_audio_normalize_adapter, "audio", "Normalize audio levels", True, ["audio"])
        _register_if_missing(registry, "audio_concat", legacy.run_audio_concat_adapter, "audio", "Concatenate audio files", True, ["audio"])
        _register_if_missing(registry, "audio_trim", legacy.run_audio_trim_adapter, "audio", "Trim audio files", True, ["audio"])
        _register_if_missing(registry, "audio_convert", legacy.run_audio_convert_adapter, "audio", "Convert audio format", True, ["audio"])
        _register_if_missing(registry, "audio_extract", legacy.run_audio_extract_adapter, "audio", "Extract audio from video", True, ["audio"])
        _register_if_missing(registry, "audio_mix", legacy.run_audio_mix_adapter, "audio", "Mix multiple audio tracks", False, ["audio"])
        _register_if_missing(registry, "audio_diarize", legacy.run_audio_diarize_adapter, "audio", "Speaker diarization", False, ["audio"])

        # Video adapters
        _register_if_missing(registry, "video_trim", legacy.run_video_trim_adapter, "video", "Trim video files", True, ["video"])
        _register_if_missing(registry, "video_concat", legacy.run_video_concat_adapter, "video", "Concatenate video files", False, ["video"])
        _register_if_missing(registry, "video_convert", legacy.run_video_convert_adapter, "video", "Convert video format", False, ["video"])
        _register_if_missing(registry, "video_thumbnail", legacy.run_video_thumbnail_adapter, "video", "Generate video thumbnail", True, ["video"])
        _register_if_missing(registry, "video_extract_frames", legacy.run_video_extract_frames_adapter, "video", "Extract frames from video", True, ["video"])
        _register_if_missing(registry, "subtitle_generate", legacy.run_subtitle_generate_adapter, "video", "Generate subtitles from audio", False, ["video", "subtitles"])
        _register_if_missing(registry, "subtitle_translate", legacy.run_subtitle_translate_adapter, "video", "Translate subtitles", True, ["video", "subtitles"])
        _register_if_missing(registry, "subtitle_burn", legacy.run_subtitle_burn_adapter, "video", "Burn subtitles into video", False, ["video", "subtitles"])

        # Media adapters
        _register_if_missing(registry, "media_ingest", legacy.run_media_ingest_adapter, "media", "Ingest media files", True, ["media", "ingest"])
        _register_if_missing(registry, "process_media", legacy.run_process_media_adapter, "media", "Process media files", False, ["media", "processing"])
        _register_if_missing(registry, "pdf_extract", legacy.run_pdf_extract_adapter, "media", "Extract content from PDF", True, ["media", "document"])
        _register_if_missing(registry, "ocr", legacy.run_ocr_adapter, "media", "Optical character recognition", True, ["media", "ocr"])
        _register_if_missing(registry, "document_table_extract", legacy.run_document_table_extract_adapter, "media", "Extract tables from documents", False, ["media", "document"])

        # RAG adapters
        _register_if_missing(registry, "rag_search", legacy.run_rag_search_adapter, "rag", "Execute RAG search", True, ["rag", "search"])
        _register_if_missing(registry, "web_search", legacy.run_web_search_adapter, "rag", "Web search", True, ["rag", "search", "web"])
        _register_if_missing(registry, "rss_fetch", legacy.run_rss_fetch_adapter, "rag", "Fetch RSS/Atom feeds", True, ["rag", "feed"])
        _register_if_missing(registry, "atom_fetch", legacy.run_rss_fetch_adapter, "rag", "Fetch Atom feeds (alias)", True, ["rag", "feed"])
        _register_if_missing(registry, "query_rewrite", legacy.run_query_rewrite_adapter, "rag", "Rewrite search queries", True, ["rag", "query"])
        _register_if_missing(registry, "query_expand", legacy.run_query_expand_adapter, "rag", "Expand search queries", True, ["rag", "query"])
        _register_if_missing(registry, "hyde_generate", legacy.run_hyde_generate_adapter, "rag", "Generate hypothetical documents (HyDE)", True, ["rag", "query"])
        _register_if_missing(registry, "semantic_cache_check", legacy.run_semantic_cache_check_adapter, "rag", "Check semantic cache", True, ["rag", "cache"])
        _register_if_missing(registry, "search_aggregate", legacy.run_search_aggregate_adapter, "rag", "Aggregate search results", False, ["rag", "search"])

        # Knowledge adapters
        _register_if_missing(registry, "notes", legacy.run_notes_adapter, "knowledge", "Manage notes", True, ["knowledge", "notes"])
        _register_if_missing(registry, "prompts", legacy.run_prompts_adapter, "knowledge", "Manage prompts", True, ["knowledge", "prompts"])
        _register_if_missing(registry, "collections", legacy.run_collections_adapter, "knowledge", "Manage collections", True, ["knowledge", "collections"])
        _register_if_missing(registry, "chunking", legacy.run_chunking_adapter, "knowledge", "Chunk text content", True, ["knowledge", "chunking"])
        _register_if_missing(registry, "claims_extract", legacy.run_claims_extract_adapter, "knowledge", "Extract claims from text", True, ["knowledge", "extraction"])
        _register_if_missing(registry, "voice_intent", legacy.run_voice_intent_adapter, "knowledge", "Voice intent detection", False, ["knowledge", "voice"])

        # Content adapters
        _register_if_missing(registry, "summarize", legacy.run_summarize_adapter, "content", "Summarize text content", True, ["content", "summarization"])
        _register_if_missing(registry, "citations", legacy.run_citations_adapter, "content", "Generate citations", True, ["content", "citations"])
        _register_if_missing(registry, "image_gen", legacy.run_image_gen_adapter, "content", "Generate images", True, ["content", "image"])
        _register_if_missing(registry, "image_describe", legacy.run_image_describe_adapter, "content", "Describe images", True, ["content", "image"])
        _register_if_missing(registry, "rerank", legacy.run_rerank_adapter, "content", "Rerank search results", False, ["content", "ranking"])
        _register_if_missing(registry, "flashcard_generate", legacy.run_flashcard_generate_adapter, "content", "Generate flashcards", True, ["content", "education"])
        _register_if_missing(registry, "quiz_generate", legacy.run_quiz_generate_adapter, "content", "Generate quizzes", True, ["content", "education"])
        _register_if_missing(registry, "outline_generate", legacy.run_outline_generate_adapter, "content", "Generate content outlines", True, ["content", "generation"])
        _register_if_missing(registry, "mindmap_generate", legacy.run_mindmap_generate_adapter, "content", "Generate mind maps", True, ["content", "visualization"])
        _register_if_missing(registry, "glossary_extract", legacy.run_glossary_extract_adapter, "content", "Extract glossary terms", True, ["content", "extraction"])
        _register_if_missing(registry, "slides_generate", legacy.run_slides_generate_adapter, "content", "Generate presentation slides", True, ["content", "generation"])
        _register_if_missing(registry, "report_generate", legacy.run_report_generate_adapter, "content", "Generate reports", True, ["content", "generation"])
        _register_if_missing(registry, "newsletter_generate", legacy.run_newsletter_generate_adapter, "content", "Generate newsletters", True, ["content", "generation"])
        _register_if_missing(registry, "diagram_generate", legacy.run_diagram_generate_adapter, "content", "Generate diagrams", True, ["content", "visualization"])
        _register_if_missing(registry, "bibliography_generate", legacy.run_bibliography_generate_adapter, "content", "Generate bibliography", True, ["content", "citations"])

        # Text adapters
        _register_if_missing(registry, "html_to_markdown", legacy.run_html_to_markdown_adapter, "text", "Convert HTML to Markdown", True, ["text", "conversion"])
        _register_if_missing(registry, "markdown_to_html", legacy.run_markdown_to_html_adapter, "text", "Convert Markdown to HTML", True, ["text", "conversion"])
        _register_if_missing(registry, "json_transform", legacy.run_json_transform_adapter, "text", "Transform JSON data", True, ["text", "json"])
        _register_if_missing(registry, "json_validate", legacy.run_json_validate_adapter, "text", "Validate JSON data", True, ["text", "json"])
        _register_if_missing(registry, "csv_to_json", legacy.run_csv_to_json_adapter, "text", "Convert CSV to JSON", True, ["text", "conversion"])
        _register_if_missing(registry, "json_to_csv", legacy.run_json_to_csv_adapter, "text", "Convert JSON to CSV", True, ["text", "conversion"])
        _register_if_missing(registry, "xml_transform", legacy.run_xml_transform_adapter, "text", "Transform XML data", True, ["text", "xml"])
        _register_if_missing(registry, "template_render", legacy.run_template_render_adapter, "text", "Render Jinja templates", True, ["text", "template"])
        _register_if_missing(registry, "regex_extract", legacy.run_regex_extract_adapter, "text", "Extract with regex patterns", True, ["text", "extraction"])
        _register_if_missing(registry, "text_clean", legacy.run_text_clean_adapter, "text", "Clean and normalize text", True, ["text", "cleaning"])
        _register_if_missing(registry, "keyword_extract", legacy.run_keyword_extract_adapter, "text", "Extract keywords", True, ["text", "nlp"])
        _register_if_missing(registry, "sentiment_analyze", legacy.run_sentiment_analyze_adapter, "text", "Analyze sentiment", True, ["text", "nlp"])
        _register_if_missing(registry, "language_detect", legacy.run_language_detect_adapter, "text", "Detect language", True, ["text", "nlp"])
        _register_if_missing(registry, "topic_model", legacy.run_topic_model_adapter, "text", "Topic modeling", True, ["text", "nlp"])
        _register_if_missing(registry, "entity_extract", legacy.run_entity_extract_adapter, "text", "Extract named entities", True, ["text", "nlp"])
        _register_if_missing(registry, "token_count", legacy.run_token_count_adapter, "text", "Count tokens", True, ["text", "utility"])

        # Integration adapters
        _register_if_missing(registry, "webhook", legacy.run_webhook_adapter, "integration", "Send webhooks", True, ["integration", "webhook"])
        _register_if_missing(registry, "notify", legacy.run_notify_adapter, "integration", "Send notifications", True, ["integration", "notification"])
        _register_if_missing(registry, "mcp_tool", legacy.run_mcp_tool_adapter, "integration", "Execute MCP tools", True, ["integration", "mcp"])
        _register_if_missing(registry, "s3_upload", legacy.run_s3_upload_adapter, "integration", "Upload to S3", True, ["integration", "storage"])
        _register_if_missing(registry, "s3_download", legacy.run_s3_download_adapter, "integration", "Download from S3", True, ["integration", "storage"])
        _register_if_missing(registry, "github_create_issue", legacy.run_github_create_issue_adapter, "integration", "Create GitHub issue", True, ["integration", "github"])
        _register_if_missing(registry, "email_send", legacy.run_email_send_adapter, "integration", "Send email", False, ["integration", "email"])
        _register_if_missing(registry, "kanban", legacy.run_kanban_adapter, "integration", "Manage Kanban boards", True, ["integration", "kanban"])
        _register_if_missing(registry, "chatbooks", legacy.run_chatbooks_adapter, "integration", "Manage chatbooks", False, ["integration", "chatbooks"])
        _register_if_missing(registry, "character_chat", legacy.run_character_chat_adapter, "integration", "Character chat", True, ["integration", "chat"])

        # Evaluation adapters - now in adapters/evaluation/eval.py
        # _register_if_missing(registry, "evaluations", legacy.run_evaluations_adapter, "evaluation", "Run evaluations", True, ["evaluation", "testing"])
        # _register_if_missing(registry, "quiz_evaluate", legacy.run_quiz_evaluate_adapter, "evaluation", "Evaluate quiz answers", True, ["evaluation", "education"])
        # _register_if_missing(registry, "eval_readability", legacy.run_eval_readability_adapter, "evaluation", "Evaluate readability", True, ["evaluation", "readability"])
        # _register_if_missing(registry, "context_window_check", legacy.run_context_window_check_adapter, "evaluation", "Check context window", True, ["evaluation", "utility"])

        # Research adapters
        _register_if_missing(registry, "arxiv_search", legacy.run_arxiv_search_adapter, "research", "Search arXiv", True, ["research", "academic"])
        _register_if_missing(registry, "arxiv_download", legacy.run_arxiv_download_adapter, "research", "Download from arXiv", False, ["research", "academic"])
        _register_if_missing(registry, "pubmed_search", legacy.run_pubmed_search_adapter, "research", "Search PubMed", True, ["research", "academic"])
        _register_if_missing(registry, "semantic_scholar_search", legacy.run_semantic_scholar_search_adapter, "research", "Search Semantic Scholar", True, ["research", "academic"])
        _register_if_missing(registry, "google_scholar_search", legacy.run_google_scholar_search_adapter, "research", "Search Google Scholar", True, ["research", "academic"])
        _register_if_missing(registry, "patent_search", legacy.run_patent_search_adapter, "research", "Search patents", True, ["research", "patents"])
        _register_if_missing(registry, "doi_resolve", legacy.run_doi_resolve_adapter, "research", "Resolve DOI", True, ["research", "citations"])
        _register_if_missing(registry, "reference_parse", legacy.run_reference_parse_adapter, "research", "Parse references", True, ["research", "citations"])
        _register_if_missing(registry, "bibtex_generate", legacy.run_bibtex_generate_adapter, "research", "Generate BibTeX", True, ["research", "citations"])
        _register_if_missing(registry, "literature_review", legacy.run_literature_review_adapter, "research", "Generate literature review", True, ["research", "academic"])

        # Utility adapters
        _register_if_missing(registry, "diff_change_detector", legacy.run_diff_change_adapter, "utility", "Detect changes/diffs", True, ["utility", "diff"])
        _register_if_missing(registry, "document_diff", legacy.run_document_diff_adapter, "utility", "Document diff", True, ["utility", "diff"])
        _register_if_missing(registry, "document_merge", legacy.run_document_merge_adapter, "utility", "Merge documents", True, ["utility", "merge"])
        _register_if_missing(registry, "timing_start", legacy.run_timing_start_adapter, "utility", "Start timing", True, ["utility", "timing"])
        _register_if_missing(registry, "timing_stop", legacy.run_timing_stop_adapter, "utility", "Stop timing", True, ["utility", "timing"])
        _register_if_missing(registry, "context_build", legacy.run_context_build_adapter, "utility", "Build context", True, ["utility", "context"])
        _register_if_missing(registry, "sandbox_exec", legacy.run_sandbox_exec_adapter, "utility", "Execute in sandbox", False, ["utility", "execution"])
        _register_if_missing(registry, "screenshot_capture", legacy.run_screenshot_capture_adapter, "utility", "Capture screenshot", False, ["utility", "screenshot"])
        _register_if_missing(registry, "schedule_workflow", legacy.run_schedule_workflow_adapter, "utility", "Schedule workflow", False, ["utility", "scheduling"])
        _register_if_missing(registry, "embed", legacy.run_embed_adapter, "utility", "Generate embeddings", True, ["utility", "embeddings"])

        _registered = True
    except ImportError as e:
        # Legacy module not available yet, skip registration
        pass


def _register_if_missing(
    registry: "AdapterRegistry",
    name: str,
    func,
    category: str,
    description: str,
    parallelizable: bool,
    tags: list,
) -> None:
    """Register an adapter if it's not already registered."""
    if name not in registry:
        registry.register(
            name,
            category=category,
            description=description,
            parallelizable=parallelizable,
            tags=tags,
        )(func)
