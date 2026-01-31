"""Workflow constants.

This module provides backward-compatible exports for workflow constants.
"""

from __future__ import annotations

from typing import Set

# Parallelizable step types for use in map operations.
# This is the source of truth - the registry's parallelizable flag is derived from this.
# When adding new adapters to the registry with parallelizable=True, also add them here.
MAP_SUBSTEP_TYPES: Set[str] = {
    # Core adapters
    "prompt",
    "log",
    "delay",
    "llm",
    "translate",
    "embed",
    "rag_search",
    "media_ingest",
    "mcp_tool",
    "webhook",
    "notify",
    "kanban",
    "notes",
    "prompts",
    "chunking",
    "web_search",
    "rss_fetch",
    "atom_fetch",
    "collections",
    "evaluations",
    "claims_extract",
    "character_chat",
    "moderation",
    "policy_check",
    "image_gen",
    "summarize",
    "query_expand",
    "citations",
    "ocr",
    "pdf_extract",
    "diff_change_detector",
    "tts",
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
    "llm_compare",
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
    # Note: The following are intentionally NOT included:
    # - email_send: side effects should be sequential
    # - screenshot_capture: resource intensive
    # - schedule_workflow: scheduling should be controlled
    # - audio_mix: resource intensive
    # - video_concat: resource intensive
    # - video_convert: resource intensive
    # - subtitle_generate: uses STT, resource intensive
    # - subtitle_burn: resource intensive
    # - arxiv_download: network I/O should be controlled
    # - chatbooks: not parallelizable
    # - sandbox_exec: code execution should be sequential for safety
    # - rerank: reranking needs full document context for relative scoring
    # - voice_intent: may use LLM, should be sequential
    # - audio_diarize: resource intensive
    # - document_table_extract: resource intensive
    # - search_aggregate: aggregates results, should be sequential
    # - workflow_call: sub-workflow execution should be controlled
    # - parallel: nesting parallel would be complex
    # - cache_result: cache operations should be sequential
    # - retry: retry wrapper is control flow
    # - checkpoint: state saving should be sequential
    # - batch: batching is control flow
    # - llm_with_tools: tool execution should be controlled
    # - process_media: resource intensive
    # - stt_transcribe: resource intensive
}
