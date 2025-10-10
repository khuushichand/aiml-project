# paper_search.py
# Provider-specific paper search endpoints under /api/v1/paper-search/*

import asyncio
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.research_schemas import (
    ArxivSearchRequestForm,
    ArxivSearchResponse,
    ArxivPaper,
    SemanticScholarSearchRequestForm,
    SemanticScholarSearchResponse,
    SemanticScholarPaper,
)
from tldw_Server_API.app.api.v1.schemas.paper_search_schemas import (
    BioRxivSearchRequestForm,
    BioRxivSearchResponse,
    BioRxivPaper,
    BioRxivPubsSearchRequestForm,
    BioRxivPubsSearchResponse,
    BioRxivPublishedRecord,
    PubMedSearchRequestForm,
    PubMedSearchResponse,
    PubMedPaper,
    PMCOAIListResponse,
    PMCOAIIdentifiersResponse,
    PMCOAIListSetsResponse,
    PMCOAIIdentifyResponse,
    PMCOAQueryResponse,
    PMCOAIdentifyResponse,
    PMCOAIRecord,
    PMCOAIHeader,
    PMCOARecord,
)
from tldw_Server_API.app.core.Third_Party import Arxiv as Arxiv
from tldw_Server_API.app.core.Third_Party import Semantic_Scholar as Semantic_Scholar
from tldw_Server_API.app.core.Third_Party import BioRxiv as BioRxiv
from tldw_Server_API.app.core.Third_Party import PubMed as PubMed
from tldw_Server_API.app.core.Third_Party import PMC_OAI as PMC_OAI
from tldw_Server_API.app.core.Third_Party import PMC_OA as PMC_OA
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


router = APIRouter()


@router.get(
    "/arxiv",
    response_model=ArxivSearchResponse,
    summary="Search arXiv papers",
    tags=["paper-search"],
)
async def paper_search_arxiv(
    search_params: ArxivSearchRequestForm = Depends(),
    token: Optional[str] = Query(None, alias="X-Token"),
):
    """Provider-specific search for arXiv papers with pagination."""
    start_index = (search_params.page - 1) * search_params.results_per_page
    logger.info(
        f"/paper-search/arxiv: query='{search_params.query}', author='{search_params.author}', year='{search_params.year}', page={search_params.page}, size={search_params.results_per_page}"
    )
    loop = asyncio.get_running_loop()
    try:
        papers_list, total_results_from_api, error_message = await loop.run_in_executor(
            None,
            Arxiv.search_arxiv_custom_api,
            search_params.query,
            search_params.author,
            search_params.year,
            start_index,
            search_params.results_per_page,
        )
        if error_message:
            logger.error(f"arXiv provider error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=f"arXiv API request timed out: {error_message}")
            raise HTTPException(status_code=502, detail=f"arXiv API error: {error_message}")
        if papers_list is None:
            raise HTTPException(status_code=500, detail="arXiv search failed to return paper data.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected arXiv search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected arXiv error: {str(e)}")

    total_pages = math.ceil(total_results_from_api / search_params.results_per_page) if search_params.results_per_page > 0 else 0
    if total_results_from_api == 0:
        total_pages = 0
    return ArxivSearchResponse(
        query_echo={
            "query": search_params.query,
            "author": search_params.author,
            "year": search_params.year,
        },
        items=[ArxivPaper(**paper_data) for paper_data in papers_list],
        total_results=total_results_from_api,
        page=search_params.page,
        results_per_page=search_params.results_per_page,
        total_pages=total_pages,
    )


@router.get(
    "/biorxiv",
    response_model=BioRxivSearchResponse,
    summary="Search BioRxiv/MedRxiv papers",
    tags=["paper-search"],
)
async def paper_search_biorxiv(
    search_params: BioRxivSearchRequestForm = Depends(),
):
    """Provider-specific search for BioRxiv/MedRxiv with pagination."""
    offset = (search_params.page - 1) * search_params.results_per_page
    logger.info(
        f"/paper-search/biorxiv: q='{search_params.q}', server='{search_params.server}', page={search_params.page}, size={search_params.results_per_page}"
    )
    loop = asyncio.get_running_loop()
    try:
        items, total_results, error_message = await loop.run_in_executor(
            None,
            BioRxiv.search_biorxiv,
            search_params.q,
            search_params.server,
            search_params.from_date,
            search_params.to_date,
            search_params.category,
            offset,
            search_params.results_per_page,
            search_params.recent_days,
            search_params.recent_count,
        )
        if error_message:
            logger.error(f"BioRxiv provider error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=f"BioRxiv API request timed out: {error_message}")
            raise HTTPException(status_code=502, detail=f"BioRxiv API error: {error_message}")
        if items is None:
            raise HTTPException(status_code=500, detail="BioRxiv search failed to return data.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected BioRxiv search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected BioRxiv error: {str(e)}")

    total_pages = math.ceil(total_results / search_params.results_per_page) if search_params.results_per_page > 0 else 0
    if total_results == 0:
        total_pages = 0
    return BioRxivSearchResponse(
        query_echo={
            "q": search_params.q,
            "server": search_params.server,
            "from_date": search_params.from_date,
            "to_date": search_params.to_date,
            "category": search_params.category,
        },
        items=[BioRxivPaper(**it) for it in items],
        total_results=total_results,
        page=search_params.page,
        results_per_page=search_params.results_per_page,
    total_pages=total_pages,
    )


# -------------------- PMC OAI-PMH Endpoints --------------------

@router.get(
    "/pmc-oai/identify",
    response_model=PMCOAIIdentifyResponse,
    summary="PMC OAI-PMH Identify",
    tags=["paper-search"],
)
async def pmc_oai_identify():
    loop = asyncio.get_running_loop()
    try:
        info, error_message = await loop.run_in_executor(None, PMC_OAI.pmc_oai_identify)
        if error_message:
            logger.error(f"PMC OAI Identify error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=error_message)
            raise HTTPException(status_code=502, detail=error_message)
        if info is None:
            raise HTTPException(status_code=500, detail="PMC OAI Identify returned no data.")
        return PMCOAIIdentifyResponse(info=info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected PMC OAI Identify error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/pmc-oai/list-sets",
    response_model=PMCOAIListSetsResponse,
    summary="PMC OAI-PMH ListSets",
    tags=["paper-search"],
)
async def pmc_oai_list_sets(resumptionToken: Optional[str] = Query(None)):
    loop = asyncio.get_running_loop()
    try:
        items, next_token, error_message = await loop.run_in_executor(None, PMC_OAI.pmc_oai_list_sets, resumptionToken)
        if error_message:
            logger.error(f"PMC OAI ListSets error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=error_message)
            raise HTTPException(status_code=502, detail=error_message)
        if items is None:
            items = []
        return PMCOAIListSetsResponse(query_echo={"resumptionToken": resumptionToken}, items=[
            {
                "setSpec": it.get("setSpec"),
                "setName": it.get("setName"),
            } for it in items
        ], resumption_token=next_token)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected PMC OAI ListSets error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/pmc-oai/list-identifiers",
    response_model=PMCOAIIdentifiersResponse,
    summary="PMC OAI-PMH ListIdentifiers",
    tags=["paper-search"],
)
async def pmc_oai_list_identifiers(
    metadataPrefix: str = Query("oai_dc"),
    from_date: Optional[str] = Query(None, alias="from"),
    until_date: Optional[str] = Query(None, alias="until"),
    set_name: Optional[str] = Query(None, alias="set"),
    resumptionToken: Optional[str] = Query(None),
):
    loop = asyncio.get_running_loop()
    try:
        items, next_token, error_message = await loop.run_in_executor(
            None, PMC_OAI.pmc_oai_list_identifiers, metadataPrefix, from_date, until_date, set_name, resumptionToken
        )
        if error_message:
            logger.error(f"PMC OAI ListIdentifiers error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=error_message)
            raise HTTPException(status_code=502, detail=error_message)
        if items is None:
            items = []
        return PMCOAIIdentifiersResponse(
            query_echo={"metadataPrefix": metadataPrefix, "from": from_date, "until": until_date, "set": set_name, "resumptionToken": resumptionToken},
            items=[PMCOAIHeader(**it) for it in items],
            resumption_token=next_token,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected PMC OAI ListIdentifiers error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/pmc-oai/list-records",
    response_model=PMCOAIListResponse,
    summary="PMC OAI-PMH ListRecords",
    tags=["paper-search"],
)
async def pmc_oai_list_records(
    metadataPrefix: str = Query("oai_dc"),
    from_date: Optional[str] = Query(None, alias="from"),
    until_date: Optional[str] = Query(None, alias="until"),
    set_name: Optional[str] = Query(None, alias="set"),
    resumptionToken: Optional[str] = Query(None),
):
    loop = asyncio.get_running_loop()
    try:
        items, next_token, error_message = await loop.run_in_executor(
            None, PMC_OAI.pmc_oai_list_records, metadataPrefix, from_date, until_date, set_name, resumptionToken
        )
        if error_message:
            logger.error(f"PMC OAI ListRecords error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=error_message)
            raise HTTPException(status_code=502, detail=error_message)
        if items is None:
            items = []
        return PMCOAIListResponse(
            query_echo={"metadataPrefix": metadataPrefix, "from": from_date, "until": until_date, "set": set_name, "resumptionToken": resumptionToken},
            items=[PMCOAIRecord(**it) for it in items],
            resumption_token=next_token,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected PMC OAI ListRecords error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/pmc-oai/get-record",
    response_model=PMCOAIRecord,
    summary="PMC OAI-PMH GetRecord",
    tags=["paper-search"],
)
async def pmc_oai_get_record(identifier: str = Query(...), metadataPrefix: str = Query("oai_dc")):
    loop = asyncio.get_running_loop()
    try:
        item, error_message = await loop.run_in_executor(None, PMC_OAI.pmc_oai_get_record, identifier, metadataPrefix)
        if error_message:
            logger.error(f"PMC OAI GetRecord error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=error_message)
            raise HTTPException(status_code=502, detail=error_message)
        if not item:
            raise HTTPException(status_code=404, detail="Record not found")
        return PMCOAIRecord(**item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected PMC OAI GetRecord error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# -------------------- PMC OA Web Service Endpoints --------------------

@router.get(
    "/pmc-oa/identify",
    response_model=PMCOAIdentifyResponse,
    summary="PMC OA Web Service identification",
    tags=["paper-search"],
)
async def pmc_oa_identify():
    loop = asyncio.get_running_loop()
    try:
        info, error_message = await loop.run_in_executor(None, PMC_OA.pmc_oa_identify)
        if error_message:
            logger.error(f"PMC OA Identify error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=error_message)
            raise HTTPException(status_code=502, detail=error_message)
        if info is None:
            raise HTTPException(status_code=500, detail="PMC OA Identify returned no data.")
        return PMCOAIdentifyResponse(info=info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected PMC OA Identify error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/pmc-oa/query",
    response_model=PMCOAQueryResponse,
    summary="PMC OA Web Service query with resumption",
    tags=["paper-search"],
)
async def pmc_oa_query(
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    until_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    format: Optional[str] = Query(None, description="'pdf' or 'tgz'"),
    resumptionToken: Optional[str] = Query(None),
    id: Optional[str] = Query(None, description="PMC ID like PMC5334499"),
    pdf_only: bool = Query(False, description="Filter results to those with PDF links"),
    license_contains: Optional[str] = Query(None, description="Case-insensitive substring match on license"),
):
    loop = asyncio.get_running_loop()
    try:
        items, next_token, error_message = await loop.run_in_executor(None, PMC_OA.pmc_oa_query, from_date, until_date, format, resumptionToken, id)
        if error_message:
            logger.error(f"PMC OA query error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=error_message)
            raise HTTPException(status_code=502, detail=error_message)
        if items is None:
            items = []
        # Server-side filters
        if pdf_only:
            def has_pdf(it: dict) -> bool:
                for lk in it.get("links", []) or []:
                    if (lk.get("format") or "").lower() == "pdf" or (lk.get("href") or "").lower().endswith(".pdf"):
                        return True
                return False
            items = [it for it in items if has_pdf(it)]
        if license_contains and isinstance(license_contains, str):
            lc = license_contains.lower()
            items = [it for it in items if (it.get("license") or "").lower().find(lc) >= 0]
        return PMCOAQueryResponse(
            query_echo={"from": from_date, "until": until_date, "format": format, "resumptionToken": resumptionToken, "id": id, "pdf_only": pdf_only, "license_contains": license_contains},
            items=[PMCOARecord(**it) for it in items],
            resumption_token=next_token,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected PMC OA query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


from fastapi.responses import StreamingResponse
import io

@router.get(
    "/pmc-oa/fetch-pdf",
    summary="Fetch PMC PDF by PMCID and return as attachment",
    tags=["paper-search"],
)
async def pmc_oa_fetch_pdf(pmcid: str = Query(..., description="PMCID numeric or with 'PMC' prefix")):
    loop = asyncio.get_running_loop()
    try:
        content, filename, error_message = await loop.run_in_executor(None, PMC_OA.download_pmc_pdf, pmcid)
        if error_message:
            logger.error(f"PMC OA fetch-pdf error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=error_message)
            if "http error" in error_message.lower():
                nums = [int(s) for s in error_message.split() if s.isdigit() and 400 <= int(s) < 600]
                code = nums[0] if nums else 502
                raise HTTPException(status_code=code, detail=error_message)
            raise HTTPException(status_code=502, detail=error_message)
        if not content:
            raise HTTPException(status_code=404, detail="PDF not found for PMCID")
        stream = io.BytesIO(content)
        resp = StreamingResponse(stream, media_type="application/pdf")
        resp.headers["Content-Disposition"] = f"attachment; filename=\"{filename or 'article.pdf'}\""
        return resp
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected PMC OA fetch-pdf error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/pmc-oa/ingest-pdf",
    summary="Download PMC PDF by PMCID, process, and persist to DB",
    tags=["paper-search"],
)
async def pmc_oa_ingest_pdf(
    pmcid: str = Query(..., description="PMCID numeric or with 'PMC' prefix"),
    title: Optional[str] = Query(None, description="Optional title override"),
    author: Optional[str] = Query(None, description="Optional author override"),
    keywords: Optional[str] = Query(None, description="Optional comma-separated keywords"),
    perform_chunking: bool = Query(True, description="Enable chunking during processing"),
    parser: Optional[str] = Query("pymupdf4llm", description="PDF parsing backend"),
    # Analysis
    api_name: Optional[str] = Query(None, description="LLM API name for analysis"),
    custom_prompt: Optional[str] = Query(None, description="Custom prompt for analysis"),
    system_prompt: Optional[str] = Query(None, description="System prompt for analysis"),
    enable_ocr: bool = Query(False, description="Enable OCR for scanned PDFs"),
    ocr_backend: Optional[str] = Query(None, description="OCR backend (e.g., 'tesseract', 'auto')"),
    ocr_lang: Optional[str] = Query("eng", description="OCR language code"),
    ocr_dpi: int = Query(300, ge=72, le=600, description="OCR render DPI"),
    ocr_mode: Optional[str] = Query("fallback", description="OCR mode: 'always' or 'fallback'"),
    ocr_min_page_text_chars: int = Query(40, ge=0, le=2000, description="Min text chars/page to skip OCR"),
    chunk_method: Optional[str] = Query(None, description="Chunking method (e.g., 'sentences', 'semantic')"),
    chunk_size: int = Query(500, ge=50, le=4000, description="Target chunk size"),
    chunk_overlap: int = Query(200, ge=0, le=1000, description="Chunk overlap"),
    perform_analysis: bool = Query(True, description="Run analysis/summarization"),
    summarize_recursively: bool = Query(False, description="Enable recursive summarization"),
    enrich_metadata: bool = Query(True, description="Enrich with PMC OAI-PMH oai_dc metadata"),
    db: MediaDatabase = Depends(get_media_db_for_user),
):
    """Convenience endpoint: fetch PMC PDF and ingest into user's Media DB."""
    loop = asyncio.get_running_loop()
    try:
        # 1) Download PDF
        content, filename, error_message = await loop.run_in_executor(None, PMC_OA.download_pmc_pdf, pmcid)
        if error_message:
            logger.error(f"PMC OA download error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=error_message)
            if "http error" in error_message.lower():
                nums = [int(s) for s in error_message.split() if s.isdigit() and 400 <= int(s) < 600]
                code = nums[0] if nums else 502
                raise HTTPException(status_code=code, detail=error_message)
            raise HTTPException(status_code=502, detail=error_message)
        if not content:
            raise HTTPException(status_code=404, detail="PDF not found for PMCID")

        # 2) Process PDF bytes
        # Import locally to ease testing/monkeypatching
        from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import process_pdf_task

        kw_list = None
        if keywords and isinstance(keywords, str):
            kw_list = [k.strip() for k in keywords.split(',') if k.strip()]

        result = await process_pdf_task(
            file_bytes=content,
            filename=filename or f"{pmcid}.pdf",
            parser=parser or "pymupdf4llm",
            title_override=title,
            author_override=author,
            keywords=kw_list,
            perform_chunking=perform_chunking,
            enable_ocr=enable_ocr or None,
            ocr_backend=ocr_backend or None,
            ocr_lang=ocr_lang or None,
            chunk_method=chunk_method,
            max_chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            perform_analysis=perform_analysis,
            api_name=api_name,
            custom_prompt=custom_prompt,
            system_prompt=system_prompt,
            summarize_recursively=summarize_recursively,
            ocr_dpi=ocr_dpi,
            ocr_mode=ocr_mode,
            ocr_min_page_text_chars=ocr_min_page_text_chars,
        )

        # 3) Optional OAI-PMH metadata enrichment (oai_dc)
        enriched_oai = None
        if enrich_metadata:
            try:
                pmcid_num = str(pmcid).strip().lstrip("PMC")
                oai_id = f"oai:pubmedcentral.nih.gov:{pmcid_num}"
                oai_item, oai_err = await loop.run_in_executor(None, PMC_OAI.pmc_oai_get_record, oai_id, "oai_dc")
                if not oai_err and oai_item and isinstance(oai_item.get("metadata"), dict):
                    enriched_oai = oai_item["metadata"]
            except Exception as _oai_ex:
                logger.warning(f"OAI-PMH enrichment failed: {_oai_ex}")

        # 4) Persist to DB
        content_for_db = result.get('transcript') or result.get('content')
        analysis_for_db = result.get('summary') or result.get('analysis')
        metadata_for_db = result.get('metadata') or {}

        # Merge in OAI metadata for title/author/ids if available
        if enriched_oai:
            if enriched_oai.get("title") and not title:
                metadata_for_db["title"] = enriched_oai.get("title")
            creators = enriched_oai.get("creators") or []
            if creators and not author:
                metadata_for_db["author"] = "; ".join(creators)
            for key in ("pmcid", "pmid", "doi", "date", "license_urls", "rights"):
                if enriched_oai.get(key) is not None:
                    metadata_for_db[key] = enriched_oai.get(key)
            try:
                import json
                enrich_txt = json.dumps({"oai_dc": enriched_oai}, ensure_ascii=False, indent=2)
                analysis_for_db = (analysis_for_db + "\n\nOAI Metadata:\n" + enrich_txt) if analysis_for_db else ("OAI Metadata:\n" + enrich_txt)
            except Exception:
                pass
        extracted_keywords = metadata_for_db.get('keywords') or result.get('keywords') or []
        combined_keywords = set(kw_list or [])
        if isinstance(extracted_keywords, list):
            combined_keywords.update(k.strip().lower() for k in extracted_keywords if k and isinstance(k, str))
        final_keywords = sorted(list(combined_keywords))

        db_id = None
        media_uuid = None
        db_msg = "Skipped (no content)"
        if content_for_db:
            try:
                safe_metadata_json = None
                if enriched_oai:
                    try:
                        import json as _json
                        safe_metadata_json = _json.dumps({"oai_dc": enriched_oai}, ensure_ascii=False)
                    except Exception:
                        safe_metadata_json = None
                # Build plaintext chunks for chunk-level FTS if chunking enabled
                chunks_for_sql = None
                try:
                    if perform_chunking:
                        from tldw_Server_API.app.core.Chunking.chunker import Chunker as _Chunker
                        _ck = _Chunker()
                        _flat = _ck.chunk_text_hierarchical_flat(
                            content_for_db,
                            method=chunk_method or "sentences",
                            max_size=chunk_size,
                            overlap=chunk_overlap,
                        )
                        _kind_map = {
                            'paragraph': 'text', 'list_unordered': 'list', 'list_ordered': 'list',
                            'code_fence': 'code', 'table_md': 'table', 'header_line': 'heading', 'header_atx': 'heading'
                        }
                        chunks_for_sql = []
                        for _it in _flat:
                            _md = _it.get('metadata') or {}
                            _ctype = _kind_map.get(str(_md.get('paragraph_kind') or '').lower(), 'text')
                            _small = {}
                            if _md.get('ancestry_titles'):
                                _small['ancestry_titles'] = _md.get('ancestry_titles')
                            if _md.get('section_path'):
                                _small['section_path'] = _md.get('section_path')
                            chunks_for_sql.append({
                                'text': _it.get('text',''),
                                'start_char': _md.get('start_offset'),
                                'end_char': _md.get('end_offset'),
                                'chunk_type': _ctype,
                                'metadata': _small,
                            })
                except Exception:
                    chunks_for_sql = None

                db_id, media_uuid, db_msg = await loop.run_in_executor(
                    None,
                    lambda: db.add_media_with_keywords(
                        url=f"pmcid:{pmcid}",
                        title=metadata_for_db.get('title') or title or (filename or pmcid),
                        media_type="pdf",
                        content=content_for_db,
                        keywords=final_keywords,
                        prompt=None,
                        analysis_content=analysis_for_db,
                        transcription_model=metadata_for_db.get('parser_used') or 'Imported',
                        author=metadata_for_db.get('author') or author,
                        safe_metadata=safe_metadata_json,
                        overwrite=False,
                        chunk_options={
                            "method": chunk_method if chunk_method else "sentences",
                            "max_size": chunk_size,
                            "overlap": chunk_overlap,
                        } if perform_chunking else None,
                        chunks=chunks_for_sql,
                    )
                )
            except Exception as e:
                logger.error(f"DB persistence failed for PMCID {pmcid}: {e}", exc_info=True)
                db_msg = f"DB error: {e}"

        return {
            "pmcid": pmcid,
            "filename": filename,
            "status": result.get("status", "Unknown"),
            "result": result,
            "db_id": db_id,
            "media_uuid": media_uuid,
            "db_message": db_msg,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected PMC OA ingest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _http_session():
    retry_strategy = Retry(total=3, status_forcelist=[429, 500, 502, 503, 504], backoff_factor=1)
    s = requests.Session()
    s.headers.update({"Accept-Encoding": "gzip, deflate"})
    s.mount("https://", HTTPAdapter(max_retries=retry_strategy))
    s.mount("http://", HTTPAdapter(max_retries=retry_strategy))
    return s


@router.post(
    "/arxiv/ingest",
    summary="Download arXiv PDF by arXiv ID, process, and persist",
    tags=["paper-search"],
)
async def arxiv_ingest(
    arxiv_id: str = Query(..., description="arXiv ID, e.g., 1706.03762"),
    keywords: Optional[str] = Query(None, description="Comma-separated keywords"),
    perform_chunking: bool = Query(True),
    parser: Optional[str] = Query("pymupdf4llm"),
    chunk_method: Optional[str] = Query(None),
    chunk_size: int = Query(500, ge=50, le=4000),
    chunk_overlap: int = Query(200, ge=0, le=1000),
    perform_analysis: bool = Query(True),
    custom_prompt: Optional[str] = Query(None),
    system_prompt: Optional[str] = Query(None),
    api_name: Optional[str] = Query(None),
    enable_ocr: bool = Query(False),
    ocr_backend: Optional[str] = Query(None),
    ocr_lang: Optional[str] = Query("eng"),
    ocr_dpi: int = Query(300, ge=72, le=600),
    ocr_mode: Optional[str] = Query("fallback"),
    ocr_min_page_text_chars: int = Query(40, ge=0, le=2000),
    db: MediaDatabase = Depends(get_media_db_for_user),
):
    loop = asyncio.get_running_loop()
    try:
        """Download an arXiv PDF, process it, and persist to the Media DB.

        Example:
          POST /api/v1/paper-search/arxiv/ingest?arxiv_id=1706.03762&perform_analysis=true
        """
        # Metadata & PDF URL
        xml_text = Arxiv.fetch_arxiv_xml(arxiv_id) or ""
        meta = {}
        if xml_text:
            try:
                parsed = Arxiv.parse_arxiv_feed(xml_text.encode("utf-8"))
                if parsed:
                    meta = parsed[0]
            except Exception:
                meta = {}
        pdf_url = Arxiv.fetch_arxiv_pdf_url(arxiv_id)
        if not pdf_url:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        sess = _http_session()
        r = sess.get(pdf_url, timeout=30)
        r.raise_for_status()
        content = r.content

        # Process PDF
        from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import process_pdf_task
        kw_list = [k.strip() for k in (keywords or '').split(',') if k.strip()] if keywords else None
        result = await process_pdf_task(
            file_bytes=content,
            filename=f"{arxiv_id}.pdf",
            parser=parser or "pymupdf4llm",
            keywords=kw_list,
            perform_chunking=perform_chunking,
            chunk_method=chunk_method,
            max_chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            perform_analysis=perform_analysis,
            api_name=api_name,
            custom_prompt=custom_prompt,
            system_prompt=system_prompt,
            enable_ocr=enable_ocr or None,
            ocr_backend=ocr_backend or None,
            ocr_lang=ocr_lang or None,
            ocr_dpi=ocr_dpi,
            ocr_mode=ocr_mode,
            ocr_min_page_text_chars=ocr_min_page_text_chars,
        )

        # Persist with safe_metadata
        content_for_db = result.get('transcript') or result.get('content')
        if not content_for_db:
            raise HTTPException(status_code=500, detail="Processing did not produce content")
        from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata
        sm = normalize_safe_metadata({
            "arxiv_id": arxiv_id,
            "title": meta.get('title'),
            "authors": meta.get('authors'),
            "date": meta.get('published_date'),
            "pdf_url": meta.get('pdf_url') or pdf_url,
            "source": "arxiv",
        })
        import json as _json
        smj = _json.dumps({k: v for k, v in sm.items() if v}, ensure_ascii=False)
        analysis_for_db = result.get('summary') or result.get('analysis')
        title_for_db = meta.get('title') or arxiv_id
        author_for_db = meta.get('authors')

        # Build plaintext chunks for chunk-level FTS if chunking enabled
        chunks_for_sql = None
        try:
            if perform_chunking:
                from tldw_Server_API.app.core.Chunking.chunker import Chunker as _Chunker
                _ck = _Chunker()
                _flat = _ck.chunk_text_hierarchical_flat(
                    content_for_db,
                    method=chunk_method or "sentences",
                    max_size=chunk_size,
                    overlap=chunk_overlap,
                )
                _kind_map = {
                    'paragraph': 'text', 'list_unordered': 'list', 'list_ordered': 'list',
                    'code_fence': 'code', 'table_md': 'table', 'header_line': 'heading', 'header_atx': 'heading'
                }
                chunks_for_sql = []
                for _it in _flat:
                    _md = _it.get('metadata') or {}
                    _ctype = _kind_map.get(str(_md.get('paragraph_kind') or '').lower(), 'text')
                    _small = {}
                    if _md.get('ancestry_titles'):
                        _small['ancestry_titles'] = _md.get('ancestry_titles')
                    if _md.get('section_path'):
                        _small['section_path'] = _md.get('section_path')
                    chunks_for_sql.append({
                        'text': _it.get('text',''),
                        'start_char': _md.get('start_offset'),
                        'end_char': _md.get('end_offset'),
                        'chunk_type': _ctype,
                        'metadata': _small,
                    })
        except Exception:
            chunks_for_sql = None

        media_id, media_uuid, msg = await loop.run_in_executor(
            None,
            lambda: db.add_media_with_keywords(
                url=f"arxiv:{arxiv_id}",
                title=title_for_db,
                media_type="pdf",
                content=content_for_db,
                keywords=kw_list or [],
                prompt=custom_prompt,
                analysis_content=analysis_for_db,
                safe_metadata=smj,
                transcription_model='Imported',
                author=author_for_db,
                overwrite=False,
                chunk_options={"method": chunk_method or "sentences", "max_size": chunk_size, "overlap": chunk_overlap} if perform_chunking else None,
                chunks=chunks_for_sql,
            )
        )
        return {"message": msg, "media_id": media_id, "media_uuid": media_uuid}
    except HTTPException:
        raise
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=getattr(e.response, 'status_code', 502), detail=str(e))
    except Exception as e:
        logger.error(f"arXiv ingest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="arXiv ingest failed")


@router.post(
    "/pubmed/ingest",
    summary="Download PubMed-linked PMC PDF by PMID, process, and persist",
    tags=["paper-search"],
)
async def pubmed_ingest(
    pmid: str = Query(..., description="PubMed PMID"),
    keywords: Optional[str] = Query(None),
    perform_chunking: bool = Query(True),
    parser: Optional[str] = Query("pymupdf4llm"),
    chunk_method: Optional[str] = Query(None),
    chunk_size: int = Query(500, ge=50, le=4000),
    chunk_overlap: int = Query(200, ge=0, le=1000),
    perform_analysis: bool = Query(True),
    custom_prompt: Optional[str] = Query(None),
    system_prompt: Optional[str] = Query(None),
    api_name: Optional[str] = Query(None),
    enable_ocr: bool = Query(False),
    ocr_backend: Optional[str] = Query(None),
    ocr_lang: Optional[str] = Query("eng"),
    ocr_dpi: int = Query(300, ge=72, le=600),
    ocr_mode: Optional[str] = Query("fallback"),
    ocr_min_page_text_chars: int = Query(40, ge=0, le=2000),
    db: MediaDatabase = Depends(get_media_db_for_user),
):
    loop = asyncio.get_running_loop()
    try:
        """Download an OA PMC PDF linked to a PubMed PMID, process it, and persist.

        Example:
          POST /api/v1/paper-search/pubmed/ingest?pmid=12345678&perform_analysis=true
        """
        meta, err = PubMed.get_pubmed_by_id(pmid)
        if err:
            raise HTTPException(status_code=502, detail=err)
        if not meta:
            raise HTTPException(status_code=404, detail="PMID not found")
        pmcid = meta.get('pmcid')
        if not pmcid:
            raise HTTPException(status_code=400, detail="No PMC Open Access PMCID available for this PMID")
        content, filename, d_err = await loop.run_in_executor(None, PMC_OA.download_pmc_pdf, pmcid)
        if d_err or not content:
            raise HTTPException(status_code=502, detail=d_err or "Failed to download PMC PDF")

        from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import process_pdf_task
        kw_list = [k.strip() for k in (keywords or '').split(',') if k.strip()] if keywords else None
        result = await process_pdf_task(
            file_bytes=content,
            filename=filename or f"PMC{pmcid}.pdf",
            parser=parser or "pymupdf4llm",
            keywords=kw_list,
            perform_chunking=perform_chunking,
            chunk_method=chunk_method,
            max_chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            perform_analysis=perform_analysis,
            api_name=api_name,
            custom_prompt=custom_prompt,
            system_prompt=system_prompt,
            enable_ocr=enable_ocr or None,
            ocr_backend=ocr_backend or None,
            ocr_lang=ocr_lang or None,
            ocr_dpi=ocr_dpi,
            ocr_mode=ocr_mode,
            ocr_min_page_text_chars=ocr_min_page_text_chars,
        )
        content_for_db = result.get('transcript') or result.get('content')
        if not content_for_db:
            raise HTTPException(status_code=500, detail="Processing did not produce content")
        from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata
        sm = normalize_safe_metadata({
            "pmid": pmid,
            "pmcid": pmcid,
            "doi": (meta.get('externalIds') or {}).get('DOI') if isinstance(meta.get('externalIds'), dict) else meta.get('doi'),
            "title": meta.get('title'),
            "authors": ', '.join(a.get('name') for a in (meta.get('authors') or []) if a.get('name')) if isinstance(meta.get('authors'), list) else meta.get('authors'),
            "journal": meta.get('journal'),
            "venue": meta.get('journal'),
            "date": meta.get('pub_date'),
            "pmc_url": meta.get('pmc_url'),
            "pdf_url": meta.get('pdf_url'),
            "source": "pubmed",
        })
        import json as _json
        smj = _json.dumps({k: v for k, v in sm.items() if v}, ensure_ascii=False)
        analysis_for_db = result.get('summary') or result.get('analysis')
        title_for_db = meta.get('title') or f"PMID {pmid}"
        author_for_db = sm.get('authors')
        # Build plaintext chunks for chunk-level FTS if chunking enabled
        chunks_for_sql = None
        try:
            if perform_chunking:
                from tldw_Server_API.app.core.Chunking.chunker import Chunker as _Chunker
                _ck = _Chunker()
                _flat = _ck.chunk_text_hierarchical_flat(
                    content_for_db,
                    method=chunk_method or "sentences",
                    max_size=chunk_size,
                    overlap=chunk_overlap,
                )
                _kind_map = {
                    'paragraph': 'text', 'list_unordered': 'list', 'list_ordered': 'list',
                    'code_fence': 'code', 'table_md': 'table', 'header_line': 'heading', 'header_atx': 'heading'
                }
                chunks_for_sql = []
                for _it in _flat:
                    _md = _it.get('metadata') or {}
                    _ctype = _kind_map.get(str(_md.get('paragraph_kind') or '').lower(), 'text')
                    _small = {}
                    if _md.get('ancestry_titles'):
                        _small['ancestry_titles'] = _md.get('ancestry_titles')
                    if _md.get('section_path'):
                        _small['section_path'] = _md.get('section_path')
                    chunks_for_sql.append({
                        'text': _it.get('text',''),
                        'start_char': _md.get('start_offset'),
                        'end_char': _md.get('end_offset'),
                        'chunk_type': _ctype,
                        'metadata': _small,
                    })
        except Exception:
            chunks_for_sql = None

        media_id, media_uuid, msg = await loop.run_in_executor(
            None,
            lambda: db.add_media_with_keywords(
                url=f"pmid:{pmid}",
                title=title_for_db,
                media_type="pdf",
                content=content_for_db,
                keywords=kw_list or [],
                prompt=custom_prompt,
                analysis_content=analysis_for_db,
                safe_metadata=smj,
                transcription_model='Imported',
                author=author_for_db,
                overwrite=False,
                chunk_options={"method": chunk_method or "sentences", "max_size": chunk_size, "overlap": chunk_overlap} if perform_chunking else None,
                chunks=chunks_for_sql,
            )
        )
        return {"message": msg, "media_id": media_id, "media_uuid": media_uuid}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PubMed ingest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="PubMed ingest failed")


@router.post(
    "/semantic-scholar/ingest",
    summary="Download Semantic Scholar open-access PDF by paperId, process, and persist",
    tags=["paper-search"],
)
async def s2_ingest(
    paper_id: str = Query(..., description="Semantic Scholar paperId"),
    keywords: Optional[str] = Query(None),
    perform_chunking: bool = Query(True),
    parser: Optional[str] = Query("pymupdf4llm"),
    chunk_method: Optional[str] = Query(None),
    chunk_size: int = Query(500, ge=50, le=4000),
    chunk_overlap: int = Query(200, ge=0, le=1000),
    perform_analysis: bool = Query(True),
    custom_prompt: Optional[str] = Query(None),
    system_prompt: Optional[str] = Query(None),
    api_name: Optional[str] = Query(None),
    enable_ocr: bool = Query(False),
    ocr_backend: Optional[str] = Query(None),
    ocr_lang: Optional[str] = Query("eng"),
    ocr_dpi: int = Query(300, ge=72, le=600),
    ocr_mode: Optional[str] = Query("fallback"),
    ocr_min_page_text_chars: int = Query(40, ge=0, le=2000),
    db: MediaDatabase = Depends(get_media_db_for_user),
):
    loop = asyncio.get_running_loop()
    try:
        """Download an open-access PDF from Semantic Scholar, process it, and persist.

        Example:
          POST /api/v1/paper-search/semantic-scholar/ingest?paper_id=abcdef&perform_analysis=true
        """
        meta, err = Semantic_Scholar.get_paper_details_semantic_scholar(paper_id)
        if err:
            raise HTTPException(status_code=502, detail=err)
        if not meta:
            raise HTTPException(status_code=404, detail="paperId not found")
        oap = meta.get('openAccessPdf') or {}
        pdf_url = oap.get('url')
        if not pdf_url:
            raise HTTPException(status_code=400, detail="No open access PDF available for this paper")
        sess = _http_session()
        r = sess.get(pdf_url, timeout=30)
        r.raise_for_status()
        content = r.content

        from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import process_pdf_task
        kw_list = [k.strip() for k in (keywords or '').split(',') if k.strip()] if keywords else None
        result = await process_pdf_task(
            file_bytes=content,
            filename=f"{paper_id}.pdf",
            parser=parser or "pymupdf4llm",
            keywords=kw_list,
            perform_chunking=perform_chunking,
            chunk_method=chunk_method,
            max_chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            perform_analysis=perform_analysis,
            api_name=api_name,
            custom_prompt=custom_prompt,
            system_prompt=system_prompt,
            enable_ocr=enable_ocr or None,
            ocr_backend=ocr_backend or None,
            ocr_lang=ocr_lang or None,
            ocr_dpi=ocr_dpi,
            ocr_mode=ocr_mode,
            ocr_min_page_text_chars=ocr_min_page_text_chars,
        )
        content_for_db = result.get('transcript') or result.get('content')
        if not content_for_db:
            raise HTTPException(status_code=500, detail="Processing did not produce content")
        from tldw_Server_API.app.core.Utils.metadata_utils import normalize_safe_metadata
        sm = normalize_safe_metadata({
            "s2_paper_id": paper_id,
            "title": meta.get('title'),
            "authors": ', '.join(a.get('name') for a in (meta.get('authors') or []) if a.get('name')) if isinstance(meta.get('authors'), list) else None,
            "venue": meta.get('venue'),
            "date": meta.get('publicationDate') or meta.get('year'),
            "doi": (meta.get('externalIds') or {}).get('DOI') if isinstance(meta.get('externalIds'), dict) else None,
            "pdf_url": pdf_url,
            "source": "semantic_scholar",
        })
        import json as _json
        smj = _json.dumps({k: v for k, v in sm.items() if v}, ensure_ascii=False)
        analysis_for_db = result.get('summary') or result.get('analysis')
        title_for_db = meta.get('title') or f"S2 {paper_id}"
        author_for_db = sm.get('authors')
        media_id, media_uuid, msg = await loop.run_in_executor(
            None,
            lambda: db.add_media_with_keywords(
                url=f"s2:{paper_id}",
                title=title_for_db,
                media_type="pdf",
                content=content_for_db,
                keywords=kw_list or [],
                prompt=custom_prompt,
                analysis_content=analysis_for_db,
                safe_metadata=smj,
                transcription_model='Imported',
                author=author_for_db,
                overwrite=False,
                chunk_options={"method": chunk_method or "sentences", "max_size": chunk_size, "overlap": chunk_overlap} if perform_chunking else None,
            )
        )
        return {"message": msg, "media_id": media_id, "media_uuid": media_uuid}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Semantic Scholar ingest error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Semantic Scholar ingest failed")


@router.get(
    "/biorxiv/by-doi",
    response_model=BioRxivPaper,
    summary="Get BioRxiv/MedRxiv paper by DOI",
    tags=["paper-search"],
)
async def paper_search_biorxiv_by_doi(
    doi: str = Query(..., description="Preprint DOI (e.g., 10.1101/2021.11.09.467936)"),
    server: str = Query("biorxiv", description="Server: biorxiv or medrxiv"),
):
    """Fetch a single preprint by DOI."""
    loop = asyncio.get_running_loop()
    try:
        item, error_message = await loop.run_in_executor(
            None,
            BioRxiv.get_biorxiv_by_doi,
            doi,
            server,
        )
        if error_message:
            logger.error(f"BioRxiv DOI provider error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=f"BioRxiv API request timed out: {error_message}")
            # Map 404 style errors if provided
            if "HTTP Error: 404" in error_message or "HTTP Error: 400" in error_message:
                raise HTTPException(status_code=404, detail="Paper not found for DOI")
            raise HTTPException(status_code=502, detail=f"BioRxiv API error: {error_message}")
        if not item:
            raise HTTPException(status_code=404, detail="Paper not found for DOI")
        return BioRxivPaper(**item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected BioRxiv DOI error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected BioRxiv DOI error: {str(e)}")


@router.get(
    "/semantic-scholar",
    response_model=SemanticScholarSearchResponse,
    summary="Search Semantic Scholar",
    tags=["paper-search"],
)
async def paper_search_semantic_scholar(
    search_params: SemanticScholarSearchRequestForm = Depends(),
):
    """Thin wrapper routing to existing Semantic Scholar adapter with consistent envelope."""
    offset = (search_params.page - 1) * search_params.results_per_page
    logger.info(
        f"/paper-search/semantic-scholar: query='{search_params.query}', page={search_params.page}, limit={search_params.results_per_page}"
    )
    loop = asyncio.get_running_loop()
    try:
        api_response_data, error_message = await loop.run_in_executor(
            None,
            Semantic_Scholar.search_papers_semantic_scholar,
            search_params.query,
            offset,
            search_params.results_per_page,
            search_params.fields_of_study_list,
            search_params.publication_types_list,
            search_params.year_range,
            search_params.venue_list,
            search_params.min_citations,
            False,
        )
        if error_message:
            logger.error(f"Semantic Scholar provider error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=f"Semantic Scholar API request timed out: {error_message}")
            if "HTTP Error" in error_message:
                # Try to extract status code from error string
                nums = [int(s) for s in error_message.split() if s.isdigit() and 400 <= int(s) < 600]
                code = nums[0] if nums else 502
                raise HTTPException(status_code=code, detail=f"Semantic Scholar API error: {error_message}")
            raise HTTPException(status_code=502, detail=f"Semantic Scholar API error: {error_message}")
        if api_response_data is None or "data" not in api_response_data:
            raise HTTPException(status_code=500, detail="Semantic Scholar search returned invalid data.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected Semantic Scholar search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected Semantic Scholar error: {str(e)}")

    total_results_api = api_response_data.get("total", 0)
    actual_offset_api = api_response_data.get("offset", 0)
    next_offset_api = api_response_data.get("next")

    parsed_papers = []
    for paper_data in api_response_data.get("data", []):
        # Remove openAccessPdf if None to avoid Pydantic error
        if paper_data.get("openAccessPdf") is None:
            paper_data.pop("openAccessPdf", None)
        parsed_papers.append(SemanticScholarPaper(**paper_data))

    total_pages = math.ceil(total_results_api / search_params.results_per_page) if search_params.results_per_page > 0 else 0
    if total_results_api == 0:
        total_pages = 0

    return SemanticScholarSearchResponse(
        query_echo={
            "query": search_params.query,
            "fields_of_study": search_params.fields_of_study_list,
            "publication_types": search_params.publication_types_list,
            "year_range": search_params.year_range,
            "venue": search_params.venue_list,
            "min_citations": search_params.min_citations,
        },
        items=parsed_papers,
        total_results=total_results_api,
        offset=actual_offset_api,
        limit=search_params.results_per_page,
        next_offset=next_offset_api,
        page=search_params.page,
        total_pages=total_pages,
    )


@router.get(
    "/biorxiv-pubs",
    response_model=BioRxivPubsSearchResponse,
    summary="Search published article metadata (bioRxiv/medRxiv)",
    tags=["paper-search"],
)
async def paper_search_biorxiv_pubs(
    search_params: BioRxivPubsSearchRequestForm = Depends(),
):
    offset = (search_params.page - 1) * search_params.results_per_page
    logger.info(
        f"/paper-search/biorxiv-pubs: server='{search_params.server}', page={search_params.page}, size={search_params.results_per_page}"
    )
    loop = asyncio.get_running_loop()
    try:
        items, total_results, error_message = await loop.run_in_executor(
            None,
            BioRxiv.search_biorxiv_pubs,
            search_params.server,
            search_params.from_date,
            search_params.to_date,
            offset,
            search_params.results_per_page,
            search_params.recent_days,
            search_params.recent_count,
            search_params.q,
        )
        if error_message:
            logger.error(f"BioRxiv pubs error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=f"BioRxiv API request timed out: {error_message}")
            raise HTTPException(status_code=502, detail=f"BioRxiv API error: {error_message}")
        if items is None:
            raise HTTPException(status_code=500, detail="BioRxiv pubs search failed to return data.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected BioRxiv pubs search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected BioRxiv pubs error: {str(e)}")

    total_pages = math.ceil(total_results / search_params.results_per_page) if search_params.results_per_page > 0 else 0
    if total_results == 0:
        total_pages = 0
    # Optionally strip abstracts for compact responses
    if not search_params.include_abstracts:
        for it in items:
            if isinstance(it, dict):
                it["preprint_abstract"] = None

    return BioRxivPubsSearchResponse(
        query_echo={
            "server": search_params.server,
            "from_date": search_params.from_date,
            "to_date": search_params.to_date,
            "recent_days": search_params.recent_days,
            "recent_count": search_params.recent_count,
            "q": search_params.q,
            "include_abstracts": search_params.include_abstracts,
        },
        items=[BioRxivPublishedRecord(**it) for it in items],
        total_results=total_results,
        page=search_params.page,
        results_per_page=search_params.results_per_page,
        total_pages=total_pages,
    )


@router.get(
    "/pubmed",
    response_model=PubMedSearchResponse,
    summary="Search PubMed",
    tags=["paper-search"],
)
async def paper_search_pubmed(
    search_params: PubMedSearchRequestForm = Depends(),
):
    """Provider-specific search for PubMed with pagination via E-utilities."""
    offset = (search_params.page - 1) * search_params.results_per_page
    logger.info(
        f"/paper-search/pubmed: q='{search_params.q}', from_year={search_params.from_year}, to_year={search_params.to_year}, free_full_text={search_params.free_full_text}, page={search_params.page}, size={search_params.results_per_page}"
    )
    loop = asyncio.get_running_loop()
    try:
        items, total_results, error_message = await loop.run_in_executor(
            None,
            PubMed.search_pubmed,
            search_params.q,
            offset,
            search_params.results_per_page,
            search_params.from_year,
            search_params.to_year,
            search_params.free_full_text,
        )
        if error_message:
            logger.error(f"PubMed provider error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=f"PubMed API request timed out: {error_message}")
            if "http error" in error_message.lower():
                # Try to extract status code
                nums = [int(s) for s in error_message.split() if s.isdigit() and 400 <= int(s) < 600]
                code = nums[0] if nums else 502
                raise HTTPException(status_code=code, detail=f"PubMed API error: {error_message}")
            raise HTTPException(status_code=502, detail=f"PubMed API error: {error_message}")
        if items is None:
            raise HTTPException(status_code=500, detail="PubMed search failed to return data.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected PubMed search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected PubMed error: {str(e)}")

    total_pages = math.ceil(total_results / search_params.results_per_page) if search_params.results_per_page > 0 else 0
    if total_results == 0:
        total_pages = 0

    return PubMedSearchResponse(
        query_echo={
            "q": search_params.q,
            "from_year": search_params.from_year,
            "to_year": search_params.to_year,
            "free_full_text": search_params.free_full_text,
        },
        items=[PubMedPaper(**it) for it in items],
        total_results=total_results,
        page=search_params.page,
        results_per_page=search_params.results_per_page,
        total_pages=total_pages,
    )


@router.get(
    "/biorxiv-pubs/by-doi",
    response_model=BioRxivPublishedRecord,
    summary="Get published metadata by DOI (bioRxiv/medRxiv)",
    tags=["paper-search"],
)
async def paper_search_biorxiv_pubs_by_doi(
    doi: str = Query(..., description="Preprint or published DOI"),
    server: str = Query("biorxiv", description="Server: biorxiv or medrxiv"),
    include_abstracts: bool = Query(True, description="Include preprint_abstract field in result"),
):
    loop = asyncio.get_running_loop()
    try:
        item, error_message = await loop.run_in_executor(
            None,
            BioRxiv.get_biorxiv_published_by_doi,
            doi,
            server,
        )
        if error_message:
            logger.error(f"BioRxiv pubs by-doi error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=f"BioRxiv API request timed out: {error_message}")
        if not item:
            raise HTTPException(status_code=404, detail="Published record not found for DOI")
        if not include_abstracts and isinstance(item, dict):
            item["preprint_abstract"] = None
        return BioRxivPublishedRecord(**item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected BioRxiv pubs by-doi error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected BioRxiv pubs by-doi error: {str(e)}")


# End of paper_search.py

@router.get(
    "/arxiv/by-id",
    response_model=ArxivPaper,
    summary="Get arXiv paper by arXiv ID",
    tags=["paper-search"],
)
async def paper_search_arxiv_by_id(
    id: str = Query(..., description="arXiv ID, e.g., 1706.03762"),
):
    loop = asyncio.get_running_loop()
    try:
        item, error_message = await loop.run_in_executor(None, Arxiv.get_arxiv_by_id, id)
        if error_message:
            logger.error(f"arXiv by-id provider error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=f"arXiv API request timed out: {error_message}")
            raise HTTPException(status_code=502, detail=f"arXiv API error: {error_message}")
        if not item:
            raise HTTPException(status_code=404, detail="Paper not found for arXiv ID")
        return ArxivPaper(**item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected arXiv by-id error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected arXiv by-id error: {str(e)}")


@router.get(
    "/semantic-scholar/by-id",
    response_model=SemanticScholarPaper,
    summary="Get Semantic Scholar paper by paperId",
    tags=["paper-search"],
)
async def paper_search_semantic_scholar_by_id(
    paper_id: str = Query(..., description="Semantic Scholar paperId"),
):
    loop = asyncio.get_running_loop()
    try:
        data, error_message = await loop.run_in_executor(
            None,
            Semantic_Scholar.get_paper_details_semantic_scholar,
            paper_id,
        )
        if error_message:
            logger.error(f"Semantic Scholar by-id provider error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=f"Semantic Scholar API request timed out: {error_message}")
            if "HTTP Error" in error_message:
                nums = [int(s) for s in error_message.split() if s.isdigit() and 400 <= int(s) < 600]
                code = nums[0] if nums else 502
                raise HTTPException(status_code=code, detail=f"Semantic Scholar API error: {error_message}")
            raise HTTPException(status_code=502, detail=f"Semantic Scholar API error: {error_message}")
        if not data:
            raise HTTPException(status_code=404, detail="Paper not found for paperId")
        if data.get("openAccessPdf") is None:
            data.pop("openAccessPdf", None)
        return SemanticScholarPaper(**data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected Semantic Scholar by-id error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected Semantic Scholar by-id error: {str(e)}")


@router.get(
    "/pubmed/by-id",
    response_model=PubMedPaper,
    summary="Get PubMed record by PMID (with abstract)",
    tags=["paper-search"],
)
async def paper_search_pubmed_by_id(
    pmid: str = Query(..., description="PubMed PMID, e.g., 12345678"),
):
    loop = asyncio.get_running_loop()
    try:
        item, error_message = await loop.run_in_executor(
            None,
            PubMed.get_pubmed_by_id,
            pmid,
        )
        if error_message:
            logger.error(f"PubMed by-id provider error: {error_message}")
            if "timed out" in error_message.lower():
                raise HTTPException(status_code=504, detail=f"PubMed API request timed out: {error_message}")
            if "http error" in error_message.lower():
                nums = [int(s) for s in error_message.split() if s.isdigit() and 400 <= int(s) < 600]
                code = nums[0] if nums else 502
                raise HTTPException(status_code=code, detail=f"PubMed API error: {error_message}")
        if not item:
            raise HTTPException(status_code=404, detail="Record not found for PMID")
        return PubMedPaper(**item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected PubMed by-id error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected PubMed by-id error: {str(e)}")
