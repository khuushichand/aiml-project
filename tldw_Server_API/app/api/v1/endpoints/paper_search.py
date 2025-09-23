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
)
from tldw_Server_API.app.core.Third_Party import Arxiv as Arxiv
from tldw_Server_API.app.core.Third_Party import Semantic_Scholar as Semantic_Scholar
from tldw_Server_API.app.core.Third_Party import BioRxiv as BioRxiv
from tldw_Server_API.app.core.Third_Party import PubMed as PubMed


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
