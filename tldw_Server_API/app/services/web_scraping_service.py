# /Server_API/app/services/web_scraping_service.py
#
# Enhanced Web Scraping Service
# This replaces the placeholder with a production-ready implementation
#
# Imports
import asyncio
import json
from typing import Optional, List, Dict, Any
#
# Third-party Libraries
from fastapi import HTTPException
#
# Local Imports
from tldw_Server_API.app.services.ephemeral_store import ephemeral_storage
from tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib import analyze
from tldw_Server_API.app.core.DB_Management.DB_Manager import create_media_database
from tldw_Server_API.app.core.Chunking.chunker import Chunker
from tldw_Server_API.app.core.DB_Management.db_path_utils import get_user_media_db_path
# Import the enhanced service
from tldw_Server_API.app.services.enhanced_web_scraping_service import (
    get_web_scraping_service, shutdown_web_scraping_service
)
# Keep legacy imports for fallback
from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import (
    scrape_and_summarize_multiple,
    scrape_from_sitemap,
    scrape_by_url_level,
    recursive_scrape
)
#
########################################################################################################################
#
# Functions:

async def process_web_scraping_task(
    scrape_method: str,
    url_input: str,
    url_level: Optional[int],
    max_pages: int,
    max_depth: int,
    summarize_checkbox: bool,
    custom_prompt: Optional[str],
    api_name: Optional[str],
    api_key: Optional[str],
    keywords: str,
    custom_titles: Optional[str],
    system_prompt: Optional[str],
    temperature: float,
    custom_cookies: Optional[List[Dict[str, Any]]],
    mode: str = "persist",
    user_id: Optional[int] = None,
    user_agent: Optional[str] = None,
    custom_headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Enhanced web scraping with production features:
    - Concurrent scraping with rate limiting
    - Job queue management with priority
    - Cookie/session management
    - Progress tracking and resumability
    - Content deduplication
    - Robust error handling and retries

    This function delegates to the enhanced service while maintaining
    backward compatibility with the existing API.
    """
    # Try to use enhanced service
    try:
        service = get_web_scraping_service()

        # Determine priority based on number of URLs or max_pages
        priority = "normal"
        if scrape_method == "Individual URLs":
            url_count = len([u for u in url_input.split('\n') if u.strip()])
            if url_count > 10:
                priority = "high"
        elif max_pages > 50:
            priority = "high"

        # Call enhanced service
        result = await service.process_web_scraping_task(
            scrape_method=scrape_method,
            url_input=url_input,
            url_level=url_level,
            max_pages=max_pages,
            max_depth=max_depth,
            summarize_checkbox=summarize_checkbox,
            custom_prompt=custom_prompt,
            api_name=api_name,
            api_key=api_key,
            keywords=keywords,
            custom_titles=custom_titles,
            system_prompt=system_prompt,
            temperature=temperature,
            custom_cookies=custom_cookies,
            mode=mode,
            priority=priority,
            user_id=user_id,
            user_agent=user_agent,
            custom_headers=custom_headers
        )

        return result

    except Exception as e:
        # Log error with full details
        import logging
        import traceback
        logging.error(f"Enhanced scraping service failed: {str(e)}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
        logging.warning(f"Falling back to legacy implementation")

        # Fallback to legacy implementation
        try:
            # 1) Perform scraping based on method
            if scrape_method == "Individual URLs":
                # For multi-line text input, your existing function supports that
                result_list = await scrape_and_summarize_multiple(
                    urls=url_input,
                    custom_prompt_arg=custom_prompt,
                    api_name=api_name,
                    api_key=api_key,
                    keywords=keywords,
                    custom_article_titles=custom_titles,
                    system_prompt=system_prompt,
                    summarize_checkbox=summarize_checkbox,
                    custom_cookies=custom_cookies,
                    temperature=temperature
                )
            elif scrape_method == "Sitemap":
                # Synchronous approach in your code, might need `asyncio.to_thread`
                result_list = await asyncio.to_thread(scrape_from_sitemap, url_input)
            elif scrape_method == "URL Level":
                if url_level is None:
                    raise ValueError("`url_level` must be provided when scraping method is 'URL Level'")
                result_list = await asyncio.to_thread(scrape_by_url_level, url_input, url_level)
            elif scrape_method == "Recursive Scraping":
                # Call your existing "recursive_scrape(...)"
                # That returns a list of dict { url, title, content, extraction_successful, ... }
                # Then optionally summarize if requested
                result_list = await recursive_scrape(
                    base_url=url_input,
                    max_pages=max_pages,
                    max_depth=max_depth,
                    progress_callback=lambda x: None,  # no-op
                    delay=1.0,
                    custom_cookies=custom_cookies
                )
            else:
                raise ValueError(f"Unknown scrape method: {scrape_method}")

            # 2) Summarize after the fact, if the method doesn't handle it
            #    (For "Individual URLs," you already did so inside scrape_and_summarize_multiple.)
            #    For the others, if summarize_checkbox is True:
            if summarize_checkbox and scrape_method != "Individual URLs":
                # ensure all results are a list of dicts with 'content'
                for article in result_list:
                    content = article.get("content", "")
                    if content:
                        summary = analyze(
                            input_data=content,
                            custom_prompt_arg=custom_prompt or "",
                            api_name=api_name,
                            api_key=api_key,
                            temp=temperature,
                            system_message=system_prompt or ""
                        )
                        article["summary"] = summary
                    else:
                        article["summary"] = "No content to summarize."

            # 3) If "persist" mode, insert into DB; if ephemeral, store ephemeral
            #    (We can store all articles in the DB or ephemeral. Typically you'd store each as a new "media" row.)
            if mode == "ephemeral":
                # Just store the entire "result_list" in ephemeral, returning the ephemeral ID.
                # Or store each article individually. Up to you. We'll do one ephemeral object:
                ephemeral_id = ephemeral_storage.store_data({"articles": result_list})
                return {
                    "status": "ephemeral-ok",
                    "media_id": ephemeral_id,
                    "total_articles": len(result_list),
                    "results": result_list
                }
            else:
                # Get the database path and create instance
                # Default to user_id 1 if not provided (single-user mode)
                effective_user_id = 1  # Default for legacy fallback
                db_path = get_user_media_db_path(effective_user_id)
                db = create_media_database(
                    client_id="webscraping_legacy_service",
                    db_path=db_path,
                )

                # Persist each article in the DB
                media_ids = []
                try:
                    for article in result_list:
                        # Construct info_dict
                        info_dict = {
                            "title": article.get("title", "Untitled"),
                            "author": "Unknown",
                            "source": article.get("url", ""),
                            "scrape_method": scrape_method
                        }
                        # We'll treat article['content'] as the main text
                        # If there's a summary, store it in summary field
                        summary = article.get("summary", "No summary available")
                        # "Segments" is how your DB manager expects text. We'll store one big chunk:
                        segments = [{"Text": article.get("content", "")}]

                        # Combine content and metadata
                        content_text = article.get("content", "")

                        # Fix the function call to match the actual signature
                        # Build safe metadata
                        safe_meta = {
                            "title": article.get("title"),
                            "author": article.get("author"),
                            "url": article.get("url"),
                            "source": "web",
                        }
                        safe_metadata_json = json.dumps({k: v for k, v in safe_meta.items() if v is not None}, ensure_ascii=False)

                        # Build plaintext chunks for FTS-first retrieval
                        try:
                            ck = Chunker()
                            # Use sane defaults in fallback path
                            flat = ck.chunk_text_hierarchical_flat(content_text, method='sentences')
                            kind_map = {
                                'paragraph': 'text',
                                'list_unordered': 'list',
                                'list_ordered': 'list',
                                'code_fence': 'code',
                                'table_md': 'table',
                                'header_line': 'heading',
                                'header_atx': 'heading',
                            }
                            chunks_for_sql = []
                            for it in flat:
                                md = it.get('metadata') or {}
                                ctype = kind_map.get(str(md.get('paragraph_kind') or '').lower(), 'text')
                                small = {}
                                if md.get('ancestry_titles'):
                                    small['ancestry_titles'] = md.get('ancestry_titles')
                                if md.get('section_path'):
                                    small['section_path'] = md.get('section_path')
                                chunks_for_sql.append({
                                    'text': it.get('text',''),
                                    'start_char': md.get('start_offset'),
                                    'end_char': md.get('end_offset'),
                                    'chunk_type': ctype,
                                    'metadata': small,
                                })
                        except Exception:
                            chunks_for_sql = []

                        media_id, media_uuid, message = db.add_media_with_keywords(
                            url=article.get("url", ""),
                            title=article.get("title", "Untitled"),
                            media_type="web_document",
                            content=content_text,
                            keywords=keywords.split(",") if keywords else [],
                            prompt=(system_prompt or "") + "\n\n" + (custom_prompt or "") if (system_prompt or custom_prompt) else None,
                            analysis_content=article.get("summary", None),
                            safe_metadata=safe_metadata_json,
                            transcription_model="web-scraping-import",
                            author=article.get("author", None),
                            ingestion_date=None,
                            overwrite=False,
                            chunks=chunks_for_sql
                        )
                        if media_id:
                            media_ids.append(media_id)
                finally:
                    # Close database connection
                    db.close_connection()

                return {
                    "status": "persist-ok",
                    "media_ids": media_ids,
                    "total_articles": len(result_list)
                }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
