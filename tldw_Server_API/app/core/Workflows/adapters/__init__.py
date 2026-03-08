"""Workflow adapters submodule.

This module provides a decorator-based registry system for workflow step adapters.
All adapters are registered during import and can be looked up by step type name.

Usage:
    from tldw_Server_API.app.core.Workflows.adapters import get_adapter, registry

    # Get an adapter by name
    adapter = get_adapter("llm")
    if adapter:
        result = await adapter(config, context)

    # Get all parallelizable adapter names
    parallel_adapters = get_parallelizable()

    # Get the full catalog
    catalog = registry.get_catalog()
"""

import asyncio  # Re-export for tests that patch adapters.asyncio

# Re-export exceptions and internal module references for backward compatibility
from tldw_Server_API.app.core.exceptions import AdapterError
from tldw_Server_API.app.core.http_client import create_client as _wf_create_client

# Import all category modules to register their adapters
# Each module's import triggers the @registry.register decorators
from tldw_Server_API.app.core.Workflows.adapters import (
    audio,
    content,
    control,
    evaluation,
    integration,
    knowledge,
    llm,
    media,
    rag,
    research,
    text,
    utility,
    video,
)
from tldw_Server_API.app.core.Workflows.adapters._base import (
    AdapterContext,
    AdapterFunc,
    AdapterResult,
    BaseAdapterConfig,
)
from tldw_Server_API.app.core.Workflows.adapters._common import (
    AsyncFileWriter,
    _artifacts_base_dir,
    _async_file_writer,
    _extract_mcp_policy,
    # Backward compatible underscore-prefixed aliases
    _extract_openai_content,
    _extract_tool_scopes,
    _format_time_srt,
    _format_time_vtt,
    _is_subpath,
    _normalize_str_list,
    _resolve_artifact_filename,
    _resolve_artifacts_dir,
    _resolve_context_user_id,
    _resolve_workflow_file_path,
    _resolve_workflow_file_uri,
    _sanitize_path_component,
    _tool_matches_allowlist,
    _unsafe_file_access_allowed,
    _workflow_file_base_dir,
    artifacts_base_dir,
    extract_mcp_policy,
    extract_openai_content,
    extract_tool_scopes,
    format_time_srt,
    format_time_vtt,
    is_subpath,
    normalize_str_list,
    resolve_artifact_filename,
    resolve_artifacts_dir,
    resolve_context_user_id,
    resolve_workflow_file_path,
    resolve_workflow_file_uri,
    sanitize_path_component,
    tool_matches_allowlist,
    unsafe_file_access_allowed,
    workflow_file_base_dir,
)
from tldw_Server_API.app.core.Workflows.adapters._registry import (
    AdapterRegistry,
    AdapterSpec,
    get_adapter,
    get_parallelizable,
    registry,
)

# Re-export all adapter functions for backward compatibility
# This allows existing code to import like: from ...adapters import run_llm_adapter
# Audio adapters
from tldw_Server_API.app.core.Workflows.adapters.audio import (
    run_audio_concat_adapter,
    run_audio_convert_adapter,
    run_audio_diarize_adapter,
    run_audio_extract_adapter,
    run_audio_mix_adapter,
    run_audio_normalize_adapter,
    run_audio_trim_adapter,
    run_stt_transcribe_adapter,
    run_tts_adapter,
)

# Content adapters
from tldw_Server_API.app.core.Workflows.adapters.content import (
    run_bibliography_generate_adapter,
    run_citations_adapter,
    run_diagram_generate_adapter,
    run_flashcard_generate_adapter,
    run_glossary_extract_adapter,
    run_image_describe_adapter,
    run_image_gen_adapter,
    run_mindmap_generate_adapter,
    run_newsletter_generate_adapter,
    run_outline_generate_adapter,
    run_quiz_generate_adapter,
    run_report_generate_adapter,
    run_rerank_adapter,
    run_slides_generate_adapter,
    run_summarize_adapter,
)

# Control adapters
from tldw_Server_API.app.core.Workflows.adapters.control import (
    run_batch_adapter,
    run_branch_adapter,
    run_cache_result_adapter,
    run_checkpoint_adapter,
    run_delay_adapter,
    run_log_adapter,
    run_map_adapter,
    run_parallel_adapter,
    run_prompt_adapter,
    run_retry_adapter,
    run_workflow_call_adapter,
)

# Evaluation adapters
from tldw_Server_API.app.core.Workflows.adapters.evaluation import (
    run_context_window_check_adapter,
    run_eval_readability_adapter,
    run_evaluations_adapter,
    run_quiz_evaluate_adapter,
)

# Integration adapters
from tldw_Server_API.app.core.Workflows.adapters.integration import (
    run_acp_stage_adapter,
    run_character_chat_adapter,
    run_chatbooks_adapter,
    run_email_send_adapter,
    run_github_create_issue_adapter,
    run_kanban_adapter,
    run_mcp_tool_adapter,
    run_notify_adapter,
    run_podcast_rss_publish_adapter,
    run_s3_download_adapter,
    run_s3_upload_adapter,
    run_webhook_adapter,
)

# Knowledge adapters
from tldw_Server_API.app.core.Workflows.adapters.knowledge import (
    run_chunking_adapter,
    run_claims_extract_adapter,
    run_collections_adapter,
    run_notes_adapter,
    run_prompts_adapter,
    run_voice_intent_adapter,
)

# LLM adapters
from tldw_Server_API.app.core.Workflows.adapters.llm import (
    run_llm_adapter,
    run_llm_compare_adapter,
    run_llm_critique_adapter,
    run_llm_with_tools_adapter,
    run_moderation_adapter,
    run_policy_check_adapter,
    run_translate_adapter,
)

# Media adapters
from tldw_Server_API.app.core.Workflows.adapters.media import (
    run_document_table_extract_adapter,
    run_media_ingest_adapter,
    run_ocr_adapter,
    run_pdf_extract_adapter,
    run_process_media_adapter,
)

# RAG adapters
from tldw_Server_API.app.core.Workflows.adapters.rag import (
    run_hyde_generate_adapter,
    run_query_expand_adapter,
    run_query_rewrite_adapter,
    run_rag_search_adapter,
    run_rss_fetch_adapter,
    run_search_aggregate_adapter,
    run_semantic_cache_check_adapter,
    run_web_search_adapter,
)

# Research adapters
from tldw_Server_API.app.core.Workflows.adapters.research import (
    run_arxiv_download_adapter,
    run_arxiv_search_adapter,
    run_bibtex_generate_adapter,
    run_deep_research_adapter,
    run_deep_research_load_bundle_adapter,
    run_deep_research_wait_adapter,
    run_doi_resolve_adapter,
    run_google_scholar_search_adapter,
    run_literature_review_adapter,
    run_patent_search_adapter,
    run_pubmed_search_adapter,
    run_reference_parse_adapter,
    run_semantic_scholar_search_adapter,
)

# Text adapters
from tldw_Server_API.app.core.Workflows.adapters.text import (
    run_csv_to_json_adapter,
    run_entity_extract_adapter,
    run_html_to_markdown_adapter,
    run_json_to_csv_adapter,
    run_json_transform_adapter,
    run_json_validate_adapter,
    run_keyword_extract_adapter,
    run_language_detect_adapter,
    run_markdown_to_html_adapter,
    run_regex_extract_adapter,
    run_sentiment_analyze_adapter,
    run_template_render_adapter,
    run_text_clean_adapter,
    run_token_count_adapter,
    run_topic_model_adapter,
    run_xml_transform_adapter,
)

# Utility adapters
from tldw_Server_API.app.core.Workflows.adapters.utility import (
    run_context_build_adapter,
    run_diff_change_adapter,
    run_document_diff_adapter,
    run_document_merge_adapter,
    run_embed_adapter,
    run_sandbox_exec_adapter,
    run_schedule_workflow_adapter,
    run_screenshot_capture_adapter,
    run_timing_start_adapter,
    run_timing_stop_adapter,
)

# Video adapters
from tldw_Server_API.app.core.Workflows.adapters.video import (
    run_subtitle_burn_adapter,
    run_subtitle_generate_adapter,
    run_subtitle_translate_adapter,
    run_video_concat_adapter,
    run_video_convert_adapter,
    run_video_extract_frames_adapter,
    run_video_thumbnail_adapter,
    run_video_trim_adapter,
)

__all__ = [
    # Compatibility exports
    "asyncio",
    "AdapterError",
    "_wf_create_client",
    "_artifacts_base_dir",
    "_async_file_writer",
    "_extract_mcp_policy",
    "_extract_openai_content",
    "_extract_tool_scopes",
    "_format_time_srt",
    "_format_time_vtt",
    "_is_subpath",
    "_normalize_str_list",
    "_resolve_artifact_filename",
    "_resolve_artifacts_dir",
    "_resolve_context_user_id",
    "_resolve_workflow_file_path",
    "_resolve_workflow_file_uri",
    "_sanitize_path_component",
    "_tool_matches_allowlist",
    "_unsafe_file_access_allowed",
    "_workflow_file_base_dir",
    # Registry
    "registry",
    "get_adapter",
    "get_parallelizable",
    "AdapterSpec",
    "AdapterRegistry",
    # Base types
    "AdapterContext",
    "BaseAdapterConfig",
    "AdapterFunc",
    "AdapterResult",
    # Common utilities
    "extract_openai_content",
    "sanitize_path_component",
    "is_subpath",
    "resolve_context_user_id",
    "artifacts_base_dir",
    "resolve_artifacts_dir",
    "resolve_artifact_filename",
    "unsafe_file_access_allowed",
    "workflow_file_base_dir",
    "resolve_workflow_file_path",
    "resolve_workflow_file_uri",
    "normalize_str_list",
    "extract_mcp_policy",
    "tool_matches_allowlist",
    "extract_tool_scopes",
    "format_time_srt",
    "format_time_vtt",
    "AsyncFileWriter",
    # Category modules
    "control",
    "llm",
    "audio",
    "video",
    "media",
    "rag",
    "knowledge",
    "content",
    "text",
    "integration",
    "evaluation",
    "research",
    "utility",
    # Audio adapter exports
    "run_tts_adapter",
    "run_stt_transcribe_adapter",
    "run_audio_normalize_adapter",
    "run_audio_concat_adapter",
    "run_audio_trim_adapter",
    "run_audio_convert_adapter",
    "run_audio_extract_adapter",
    "run_audio_mix_adapter",
    "run_audio_diarize_adapter",
    # Video adapter exports
    "run_video_thumbnail_adapter",
    "run_video_trim_adapter",
    "run_video_concat_adapter",
    "run_video_convert_adapter",
    "run_video_extract_frames_adapter",
    "run_subtitle_generate_adapter",
    "run_subtitle_translate_adapter",
    "run_subtitle_burn_adapter",
    # Media adapter exports
    "run_media_ingest_adapter",
    "run_process_media_adapter",
    "run_pdf_extract_adapter",
    "run_ocr_adapter",
    "run_document_table_extract_adapter",
    # RAG adapter exports
    "run_rag_search_adapter",
    "run_web_search_adapter",
    "run_rss_fetch_adapter",
    "run_query_rewrite_adapter",
    "run_query_expand_adapter",
    "run_hyde_generate_adapter",
    "run_semantic_cache_check_adapter",
    "run_search_aggregate_adapter",
    # Knowledge adapter exports
    "run_notes_adapter",
    "run_prompts_adapter",
    "run_collections_adapter",
    "run_chunking_adapter",
    "run_claims_extract_adapter",
    "run_voice_intent_adapter",
    # Content adapter exports
    "run_summarize_adapter",
    "run_citations_adapter",
    "run_bibliography_generate_adapter",
    "run_image_gen_adapter",
    "run_image_describe_adapter",
    "run_rerank_adapter",
    "run_flashcard_generate_adapter",
    "run_quiz_generate_adapter",
    "run_outline_generate_adapter",
    "run_glossary_extract_adapter",
    "run_mindmap_generate_adapter",
    "run_report_generate_adapter",
    "run_newsletter_generate_adapter",
    "run_slides_generate_adapter",
    "run_diagram_generate_adapter",
    # Text adapter exports
    "run_html_to_markdown_adapter",
    "run_markdown_to_html_adapter",
    "run_json_transform_adapter",
    "run_json_validate_adapter",
    "run_csv_to_json_adapter",
    "run_json_to_csv_adapter",
    "run_xml_transform_adapter",
    "run_template_render_adapter",
    "run_regex_extract_adapter",
    "run_text_clean_adapter",
    "run_keyword_extract_adapter",
    "run_sentiment_analyze_adapter",
    "run_language_detect_adapter",
    "run_topic_model_adapter",
    "run_entity_extract_adapter",
    "run_token_count_adapter",
    # Integration adapter exports
    "run_webhook_adapter",
    "run_notify_adapter",
    "run_mcp_tool_adapter",
    "run_acp_stage_adapter",
    "run_s3_upload_adapter",
    "run_s3_download_adapter",
    "run_podcast_rss_publish_adapter",
    "run_github_create_issue_adapter",
    "run_kanban_adapter",
    "run_chatbooks_adapter",
    "run_character_chat_adapter",
    "run_email_send_adapter",
    # Evaluation adapter exports
    "run_evaluations_adapter",
    "run_quiz_evaluate_adapter",
    "run_eval_readability_adapter",
    "run_context_window_check_adapter",
    # Research adapter exports
    "run_arxiv_search_adapter",
    "run_arxiv_download_adapter",
    "run_pubmed_search_adapter",
    "run_semantic_scholar_search_adapter",
    "run_google_scholar_search_adapter",
    "run_patent_search_adapter",
    "run_deep_research_adapter",
    "run_deep_research_wait_adapter",
    "run_deep_research_load_bundle_adapter",
    "run_doi_resolve_adapter",
    "run_reference_parse_adapter",
    "run_bibtex_generate_adapter",
    "run_literature_review_adapter",
    # Utility adapter exports
    "run_diff_change_adapter",
    "run_document_diff_adapter",
    "run_document_merge_adapter",
    "run_context_build_adapter",
    "run_embed_adapter",
    "run_sandbox_exec_adapter",
    "run_screenshot_capture_adapter",
    "run_schedule_workflow_adapter",
    "run_timing_start_adapter",
    "run_timing_stop_adapter",
    # Control adapter exports
    "run_prompt_adapter",
    "run_delay_adapter",
    "run_log_adapter",
    "run_branch_adapter",
    "run_map_adapter",
    "run_parallel_adapter",
    "run_batch_adapter",
    "run_cache_result_adapter",
    "run_retry_adapter",
    "run_checkpoint_adapter",
    "run_workflow_call_adapter",
    # LLM adapter exports
    "run_llm_adapter",
    "run_llm_with_tools_adapter",
    "run_llm_compare_adapter",
    "run_llm_critique_adapter",
    "run_moderation_adapter",
    "run_policy_check_adapter",
    "run_translate_adapter",
]
