from __future__ import annotations

MAP_SUBSTEP_TYPES = {
    "prompt",
    "log",
    "delay",
    "rag_search",
    "media_ingest",
    "mcp_tool",
    "webhook",
    "kanban",
    "notes",
    "prompts",
    "chunking",
    "web_search",
    "collections",
    "evaluations",
    "claims_extract",
    "character_chat",
    "moderation",
    "image_gen",
    "summarize",
    "query_expand",
    "citations",
    "ocr",
    "pdf_extract",
    # Tier 1: Research Automation (parallelizable)
    "query_rewrite",
    "hyde_generate",
    "semantic_cache_check",
    "entity_extract",
    "bibliography_generate",
    # Tier 2: Learning/Education (parallelizable)
    "flashcard_generate",
    "quiz_generate",
    "quiz_evaluate",
    "outline_generate",
    "glossary_extract",
    "mindmap_generate",
    "eval_readability",
    # Tier 3: Data Processing (parallelizable)
    "json_transform",
    "json_validate",
    "csv_to_json",
    "json_to_csv",
    "regex_extract",
    "text_clean",
    "xml_transform",
    "template_render",
    # Tier 5: External Integrations (parallelizable)
    "s3_upload",
    "s3_download",
    "github_create_issue",
    # Tier 6: Agentic Support (parallelizable)
    "llm_critique",
    "context_build",
    # Phase 2: Group A - Individual Utility (parallelizable)
    "document_merge",
    "document_diff",
    "markdown_to_html",
    "html_to_markdown",
    "keyword_extract",
    "sentiment_analyze",
    "language_detect",
    "topic_model",
    "token_count",
    "context_window_check",
    "llm_compare",
    "image_describe",
    "report_generate",
    "newsletter_generate",
    "slides_generate",
    "diagram_generate",
    "timing_start",
    "timing_stop",
    # Phase 2: Group B - Audio & Video (parallelizable)
    "audio_normalize",
    "audio_concat",
    "audio_trim",
    "audio_convert",
    "audio_extract",
    "video_thumbnail",
    "video_trim",
    "video_extract_frames",
    "subtitle_translate",
    # Phase 2: Group C - Research & Academic (parallelizable)
    "arxiv_search",
    "pubmed_search",
    "semantic_scholar_search",
    "google_scholar_search",
    "patent_search",
    "doi_resolve",
    "reference_parse",
    "bibtex_generate",
    "literature_review",
    # Note: "email_send" is intentionally NOT included - side effects should be sequential
    # Note: "screenshot_capture" is intentionally NOT included - resource intensive
    # Note: "schedule_workflow" is intentionally NOT included - scheduling should be controlled
    # Note: "audio_mix" is intentionally NOT included - resource intensive
    # Note: "video_concat" is intentionally NOT included - resource intensive
    # Note: "video_convert" is intentionally NOT included - resource intensive
    # Note: "subtitle_generate" is intentionally NOT included - uses STT, resource intensive
    # Note: "subtitle_burn" is intentionally NOT included - resource intensive
    # Note: "arxiv_download" is intentionally NOT included - network I/O should be controlled
    # Note: "chatbooks" is intentionally NOT included - not parallelizable
    # Note: "sandbox_exec" is intentionally NOT included - code execution should be sequential for safety
    # Note: "rerank" is intentionally NOT included - reranking needs full document context for relative scoring
    # Note: "voice_intent" is intentionally NOT included - may use LLM, should be sequential
    # Note: "audio_diarize" is intentionally NOT included - resource intensive
    # Note: "document_table_extract" is intentionally NOT included - resource intensive
    # Note: "search_aggregate" is intentionally NOT included - aggregates results, should be sequential
    # Note: "workflow_call" is intentionally NOT included - sub-workflow execution should be controlled
    # Note: "parallel" is intentionally NOT included - nesting parallel would be complex
    # Note: "cache_result" is intentionally NOT included - cache operations should be sequential
    # Note: "retry" is intentionally NOT included - retry wrapper is control flow
    # Note: "checkpoint" is intentionally NOT included - state saving should be sequential
    # Note: "batch" is intentionally NOT included - batching is control flow
    # Note: "llm_with_tools" is intentionally NOT included - tool execution should be controlled
}
