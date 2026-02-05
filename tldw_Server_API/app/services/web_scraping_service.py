# /Server_API/app/services/web_scraping_service.py
#
# Enhanced Web Scraping Service
# This replaces the placeholder with a production-ready implementation
#
# Imports
import asyncio
import json
import logging
from typing import Any, Optional

#
# Third-party Libraries
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.schemas.media_request_models import ScrapeMethod
from tldw_Server_API.app.core.Chunking.chunker import Chunker
from tldw_Server_API.app.core.DB_Management.DB_Manager import create_media_database
from tldw_Server_API.app.core.DB_Management.db_path_utils import get_user_media_db_path
from tldw_Server_API.app.core.LLM_Calls.Summarization_General_Lib import analyze

# Keep legacy imports for fallback
from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import (
    recursive_scrape,
    scrape_and_summarize_multiple,
    scrape_article,
    scrape_by_url_level,
    scrape_from_sitemap,
)

# Import the enhanced service
from tldw_Server_API.app.services.enhanced_web_scraping_service import (
    get_web_scraping_service,
)

#
# Local Imports
from tldw_Server_API.app.services.ephemeral_store import ephemeral_storage

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
    custom_cookies: Optional[list[dict[str, Any]]],
    mode: str = "persist",
    user_id: Optional[int] = None,
    user_agent: Optional[str] = None,
    custom_headers: Optional[dict[str, str]] = None,
    # Crawl overrides from UI / WebScrapingRequest
    crawl_strategy: Optional[str] = None,
    include_external: Optional[bool] = None,
    score_threshold: Optional[float] = None,
) -> dict[str, Any]:
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

    Parameters:
    - crawl_strategy: Optional crawl strategy override for enhanced crawling.
      Normalized to lowercase and validated against: "best_first", "best-first", "bestfirst".
    - include_external: Optional flag to allow following external links during crawl.
      Forwarded as-is to the enhanced service when provided.
    - score_threshold: Optional relevance threshold in [0.0, 1.0] for URL scoring.
      Coerced to float and validated to be within the closed interval [0.0, 1.0].
    - custom_headers: Optional HTTP headers to use for outbound scraping requests.
      Forwarded as-is to the enhanced service and used for session keying.

    Fallback behaviour:
    - When the enhanced service is unavailable, a legacy implementation is used.
    - For the "Recursive Scraping" method, advanced crawl options
      (`custom_headers`, `crawl_strategy`, `include_external`, `score_threshold`)
      are not supported by the legacy path; if any of these are provided when
      the fallback is active, the request is rejected with an explicit error
      instead of silently ignoring them.
    """
    # Normalize and validate crawl overrides before dispatch
    normalized_crawl_strategy: Optional[str] = None
    if crawl_strategy is not None:
        normalized_crawl_strategy = crawl_strategy.strip().lower()
        allowed_strategies = {"best_first", "best-first", "bestfirst"}
        if normalized_crawl_strategy not in allowed_strategies:
            raise ValueError(
                f"Invalid crawl_strategy '{crawl_strategy}'. "
                "Valid options are: 'best_first', 'best-first', 'bestfirst'."
            )

    normalized_score_threshold: Optional[float] = None
    if score_threshold is not None:
        try:
            normalized_score_threshold = float(score_threshold)
        except (TypeError, ValueError):
            raise ValueError(
                f"score_threshold must be a float between 0.0 and 1.0; got {score_threshold!r}."
            )
        if not 0.0 <= normalized_score_threshold <= 1.0:
            raise ValueError(
                f"score_threshold must be between 0.0 and 1.0 inclusive; got {normalized_score_threshold}."
            )

    if normalized_crawl_strategy is not None:
        crawl_strategy = normalized_crawl_strategy
    if normalized_score_threshold is not None:
        score_threshold = normalized_score_threshold

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
            custom_headers=custom_headers,
            crawl_strategy=crawl_strategy,
            include_external=include_external,
            score_threshold=score_threshold,
        )

        return result

    except Exception as e:
        # Log error with full details
        import logging
        import traceback
        logging.exception(f"Enhanced scraping service failed: {str(e)}")
        logging.exception(f"Full traceback: {traceback.format_exc()}")
        logging.warning("Falling back to legacy implementation")

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
                # Legacy recursive scraping cannot honor advanced crawl flags that
                # are supported only by the enhanced service. Make this explicit.
                advanced_flags = {
                    "custom_headers": custom_headers if custom_headers else None,
                    "crawl_strategy": (crawl_strategy or "").strip() or None,
                    "include_external": include_external
                    if include_external is not None
                    else None,
                    "score_threshold": score_threshold
                    if score_threshold is not None
                    else None,
                }
                unsupported = [name for name, value in advanced_flags.items() if value is not None]
                if unsupported:
                    detail = (
                        "Enhanced web scraping options are only available when the enhanced "
                        "scraping service is running. The legacy fallback for 'Recursive "
                        "Scraping' does not support the following parameters: "
                        f"{', '.join(sorted(unsupported))}."
                    )
                    raise HTTPException(status_code=400, detail=detail)

                # Call the existing async recursive_scrape implementation.
                # It returns a list of dicts:
                # { url, title, content, extraction_successful, ... }
                recursive_kwargs: dict[str, Any] = {
                    "base_url": url_input,
                    "max_pages": max_pages,
                    "max_depth": max_depth,
                    "progress_callback": (lambda x: None),  # no-op
                    "delay": 1.0,
                    "custom_cookies": custom_cookies,
                }
                # Only override user-agent if explicitly provided, otherwise keep
                # the legacy default inside recursive_scrape.
                if user_agent:
                    recursive_kwargs["user_agent"] = user_agent

                result_list = await recursive_scrape(**recursive_kwargs)
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
                if user_id is None:
                    raise HTTPException(
                        status_code=400,
                        detail="user_id is required for legacy persistence in multi-user mode.",
                    )
                effective_user_id = user_id
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

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


async def ingest_web_content_orchestrate(
    request: Any,
    db: Any,
    usage_log: Any,
) -> Optional[list[dict[str, Any]]]:
    """
    Shared helper for `/media/ingest-web-content` side effects and, for
    selected scrape methods, the scraping + summarization:
      - ScrapeMethod.INDIVIDUAL: per-URL scrape + summary
      - ScrapeMethod.SITEMAP: sitemap scrape + summary
    """

    # Log usage for web scraping ingest
    try:
        usage_log.log_event(
            "webscrape.ingest",
            tags=[str(getattr(request, "scrape_method", "") or "")],
            metadata={
                "url_count": len(getattr(request, "urls", []) or []),
                "perform_analysis": bool(
                    getattr(request, "perform_analysis", False)
                ),
            },
        )
    except Exception:
        pass

    # Topic monitoring (non-blocking): URLs and provided titles
    try:
        from tldw_Server_API.app.core.Monitoring.topic_monitoring_service import (
            get_topic_monitoring_service,
        )

        mon = get_topic_monitoring_service()
        uid = getattr(db, "client_id", None) if hasattr(db, "client_id") else None
        for u in (getattr(request, "urls", []) or [])[:10]:
            if u:
                mon.schedule_evaluate_and_alert(
                    user_id=str(uid) if uid else None,
                    text=str(u),
                    source="ingestion.web",
                    scope_type="user",
                    scope_id=str(uid) if uid else None,
                )
        for t in (getattr(request, "titles", []) or [])[:10]:
            if t:
                mon.schedule_evaluate_and_alert(
                    user_id=str(uid) if uid else None,
                    text=str(t),
                    source="ingestion.web",
                    scope_type="user",
                    scope_id=str(uid) if uid else None,
                )
    except Exception:
        # Do not let monitoring failures break ingestion.
        pass

    scrape_method = getattr(request, "scrape_method", None)

    async def maybe_summarize_one(article: dict[str, Any]) -> dict[str, Any]:
        """
        Shared summarization helper for sitemap/individual scraping.
        Mirrors the legacy `_legacy_media.ingest_web_content` behaviour.
        """
        if not getattr(request, "perform_analysis", False):
            article["analysis"] = None
            return article

        content = article.get("content", "")
        if not content:
            article["analysis"] = "No content to analyze."
            return article

        analysis_results = analyze(
            input_data=content,
            custom_prompt_arg=getattr(request, "custom_prompt", None)
            or "Summarize this article.",
            api_name=getattr(request, "api_name", None),
            temp=0.7,
            system_message=getattr(request, "system_prompt", None)
            or "Act as a professional summarizer.",
        )
        article["analysis"] = analysis_results

        if getattr(request, "perform_rolling_summarization", False):
            logging.info("Performing rolling summarization (placeholder).")
        if getattr(request, "perform_confabulation_check_of_analysis", False):
            logging.info("Performing confabulation check of analysis (placeholder).")

        return article

    def parse_cookies() -> Optional[list[dict[str, Any]]]:
        """
        Parse cookies from the request when `use_cookies` is enabled.
        Mirrors the legacy JSON parsing + 400 semantics, but ensures that
        malformed or incorrectly-typed cookie payloads yield a 400 instead
        of bubbling up as a 500 error.
        """
        custom_cookies_list: Optional[list[dict[str, Any]]] = None
        if getattr(request, "use_cookies", False) and getattr(
            request, "cookies", None
        ):
            raw_cookies = request.cookies
            try:
                parsed = json.loads(raw_cookies)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="Invalid JSON format for cookies"
                )

            if isinstance(parsed, dict):
                custom_cookies_list = [parsed]
            elif isinstance(parsed, list):
                if not all(isinstance(item, dict) for item in parsed):
                    raise HTTPException(
                        status_code=400, detail="Invalid cookies format"
                    )
                custom_cookies_list = parsed
            else:
                raise HTTPException(
                    status_code=400, detail="Invalid cookies format"
                )

        return custom_cookies_list

    # INDIVIDUAL URLs: per-URL scrape + summarization
    if scrape_method == ScrapeMethod.INDIVIDUAL:
        urls = getattr(request, "urls", []) or []
        if not urls:
            return []

        titles = getattr(request, "titles", None) or []
        authors = getattr(request, "authors", None) or []
        keywords = getattr(request, "keywords", None) or []
        num_urls = len(urls)

        if len(titles) < num_urls:
            titles += ["Untitled"] * (num_urls - len(titles))
        if len(authors) < num_urls:
            authors += ["Unknown"] * (num_urls - len(authors))
        if len(keywords) < num_urls:
            keywords += ["no_keyword_set"] * (num_urls - len(keywords))

        custom_cookies_list = parse_cookies()

        results: list[dict[str, Any]] = []
        for i, url in enumerate(urls):
            title_ = titles[i]
            author_ = authors[i]
            kw_ = keywords[i]

            article_data = await scrape_article(url, custom_cookies=custom_cookies_list)
            if not article_data or not article_data.get("extraction_successful"):
                logging.warning(f"Failed to scrape: {url}")
                continue

            article_data["title"] = title_ or article_data.get("title")
            article_data["author"] = author_ or article_data.get("author")
            article_data["keywords"] = kw_

            article_data = await maybe_summarize_one(article_data)
            results.append(article_data)

        return results

    # SITEMAP: scrape sitemap URL, then summarize each article
    if scrape_method == ScrapeMethod.SITEMAP:
        urls = getattr(request, "urls", []) or []
        if not urls:
            return []

        sitemap_url = urls[0]

        def scrape_in_thread() -> list[dict[str, Any]]:
            return scrape_from_sitemap(sitemap_url)

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, scrape_in_thread)

        if not results:
            logging.warning("No articles returned from sitemap scraping.")
            return []

        summarized: list[dict[str, Any]] = []
        for r in results:
            # Legacy path expects dict-like articles; skip anything else defensively.
            if not isinstance(r, dict):
                continue
            summarized_article = await maybe_summarize_one(r)
            summarized.append(summarized_article)

        return summarized

    # URL LEVEL: route to enhanced service (friendly ingest)
    if scrape_method == ScrapeMethod.URL_LEVEL:
        urls = getattr(request, "urls", []) or []
        if not urls:
            return []

        base_url = urls[0]
        level = getattr(request, "url_level", None) or 2

        custom_cookies_list = parse_cookies()

        try:
            from tldw_Server_API.app.api.v1.endpoints import media as media_mod

            scrape_task = getattr(
                media_mod, "process_web_scraping_task", process_web_scraping_task
            )
        except Exception:  # pragma: no cover - defensive fallback
            scrape_task = process_web_scraping_task

        try:
            service_result = await scrape_task(
                scrape_method="URL Level",
                url_input=base_url,
                url_level=level,
                max_pages=getattr(request, "max_pages", None) or 10,
                max_depth=level,
                summarize_checkbox=bool(
                    getattr(request, "perform_analysis", False)
                ),
                custom_prompt=getattr(request, "custom_prompt", None),
                api_name=getattr(request, "api_name", None),
                api_key=None,
                keywords=",".join(request.keywords or [])
                if isinstance(getattr(request, "keywords", None), list)
                else (getattr(request, "keywords", None) or ""),
                custom_titles=None,
                system_prompt=getattr(request, "system_prompt", None),
                temperature=0.7,
                custom_cookies=custom_cookies_list,
                mode="ephemeral",
                user_agent=getattr(request, "user_agent", None)
                if hasattr(request, "user_agent")
                else None,
                custom_headers=None,
                crawl_strategy=getattr(request, "crawl_strategy", None),
                include_external=getattr(request, "include_external", None),
                score_threshold=getattr(request, "score_threshold", None),
            )
            articles: list[dict[str, Any]] = []
            if isinstance(service_result, dict):
                if service_result.get("articles"):
                    articles = service_result["articles"]
                elif service_result.get("results"):
                    articles = service_result["results"]

            for r in articles:
                if (
                    isinstance(r, dict)
                    and "summary" in r
                    and "analysis" not in r
                ):
                    r["analysis"] = r.get("summary")

            return articles
        except Exception as exc:  # pragma: no cover - propagate for legacy handler
            logging.exception(f"Enhanced URL Level crawl failed: {exc}")
            raise

    # RECURSIVE SCRAPING: route to enhanced service (friendly ingest)
    if scrape_method == ScrapeMethod.RECURSIVE:
        urls = getattr(request, "urls", []) or []
        if not urls:
            return []

        base_url = urls[0]
        max_pages = getattr(request, "max_pages", None) or 10
        max_depth = getattr(request, "max_depth", None) or 3

        custom_cookies_list = parse_cookies()

        try:
            from tldw_Server_API.app.api.v1.endpoints import media as media_mod

            scrape_task = getattr(
                media_mod, "process_web_scraping_task", process_web_scraping_task
            )
        except Exception:  # pragma: no cover - defensive fallback
            scrape_task = process_web_scraping_task

        try:
            service_result = await scrape_task(
                scrape_method="Recursive Scraping",
                url_input=base_url,
                url_level=None,
                max_pages=max_pages,
                max_depth=max_depth,
                summarize_checkbox=bool(
                    getattr(request, "perform_analysis", False)
                ),
                custom_prompt=getattr(request, "custom_prompt", None),
                api_name=getattr(request, "api_name", None),
                api_key=None,
                keywords=",".join(request.keywords or [])
                if isinstance(getattr(request, "keywords", None), list)
                else (getattr(request, "keywords", None) or ""),
                custom_titles=None,
                system_prompt=getattr(request, "system_prompt", None),
                temperature=0.7,
                custom_cookies=custom_cookies_list,
                mode="ephemeral",
                user_agent=getattr(request, "user_agent", None)
                if hasattr(request, "user_agent")
                else None,
                custom_headers=None,
                crawl_strategy=getattr(request, "crawl_strategy", None),
                include_external=getattr(request, "include_external", None),
                score_threshold=getattr(request, "score_threshold", None),
            )
            articles: list[dict[str, Any]] = []
            if isinstance(service_result, list):
                articles = service_result
            elif isinstance(service_result, dict):
                if service_result.get("articles"):
                    articles = service_result.get("articles") or []
                elif service_result.get("results"):
                    articles = service_result.get("results") or []

            for r in articles:
                if (
                    isinstance(r, dict)
                    and "summary" in r
                    and "analysis" not in r
                ):
                    r["analysis"] = r.get("summary")

            return articles
        except Exception as exc:  # pragma: no cover - propagate for legacy handler
            logging.exception(f"Enhanced recursive crawl failed: {exc}")
            raise

    # Other methods (or unrecognized) still handled in `_legacy_media`.
    return None
