# Document References Endpoint
# Extract and enrich bibliography/references from documents
#
from __future__ import annotations

import asyncio
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.schemas.document_references import (
    DocumentReferencesResponse,
    ReferenceEntry,
)
from tldw_Server_API.app.api.v1.utils.cache import cache_response, get_cached_response
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase, get_latest_transcription

router = APIRouter(tags=["Document Workspace"])


# Maximum number of references to enrich (to avoid long response times)
MAX_ENRICHMENT_REFS = 20
# Delay between Semantic Scholar API calls (to avoid rate limiting)
SEMANTIC_SCHOLAR_DELAY = 0.2  # 200ms = max 5 requests/sec

# Reference section detection patterns
REFERENCES_PARSER_VERSION = "3"
REFERENCE_SECTION_PATTERNS = [
    # Common headings (optional numbering/roman numerals, optional colon)
    r"(?im)^\s*(?:\d+|[IVXLC]+)?(?:\.\d+)?\s*references?\s*:?\s*$",
    r"(?im)^\s*(?:\d+|[IVXLC]+)?(?:\.\d+)?\s*bibliography\s*:?\s*$",
    r"(?im)^\s*(?:\d+|[IVXLC]+)?(?:\.\d+)?\s*works\s+cited\s*:?\s*$",
    r"(?im)^\s*(?:\d+|[IVXLC]+)?(?:\.\d+)?\s*literature\s+cited\s*:?\s*$",
    r"(?im)^\s*(?:\d+|[IVXLC]+)?(?:\.\d+)?\s*cited\s+references?\s*:?\s*$",
    # Markdown-style headings
    r"(?im)^#+\s*references?\s*$",
    r"(?im)^#+\s*bibliography\s*$",
]

# Looser fallback headings (allow trailing text like "References and Notes")
REFERENCE_SECTION_FALLBACK_PATTERNS = [
    r"(?im)^\s*(?:\d+|[IVXLC]+)?(?:\.\d+)?\s*references?\b.*$",
    r"(?im)^\s*(?:\d+|[IVXLC]+)?(?:\.\d+)?\s*bibliography\b.*$",
    r"(?im)^\s*(?:\d+|[IVXLC]+)?(?:\.\d+)?\s*works\s+cited\b.*$",
    r"(?im)^\s*(?:\d+|[IVXLC]+)?(?:\.\d+)?\s*literature\s+cited\b.*$",
    r"(?im)^\s*(?:\d+|[IVXLC]+)?(?:\.\d+)?\s*cited\s+references?\b.*$",
]

# DOI/arXiv extraction patterns
DOI_PATTERN = r"(?:https?://(?:dx\.)?doi\.org/)?10\.\d{4,}/[^\s\]\)>\"']+"
ARXIV_PATTERN = r"(?:arXiv[:\s]*)?(\d{4}\.\d{4,5})(?:v\d+)?"
ARXIV_OLD_PATTERN = r"(?:arXiv[:\s]*)?([a-z-]+(?:\.[A-Z]{2})?/\d{7})"
URL_PATTERN = r"https?://[^\s\]\)>\"']+"

# Year extraction pattern
YEAR_PATTERN = r"\b(19\d{2}|20[0-2]\d)\b"


def _get_db_scope(db: MediaDatabase) -> str:
    """Return a stable scope identifier for the active MediaDatabase."""
    return getattr(db, "db_path_str", None) or str(getattr(db, "db_path", ""))


def _build_references_cache_key(
    media_id: int,
    *,
    enrich: bool,
    user_id: str,
    db_scope: str,
) -> str:
    scope_str = f"user:{user_id}:db:{db_scope}"
    enrich_flag = "enrich" if enrich else "basic"
    return (
        f"cache:/api/v1/media/{media_id}/references:"
        f"{scope_str}:{enrich_flag}:v{REFERENCES_PARSER_VERSION}"
    )


def _parse_year_from_date(date_str: str | None) -> int | None:
    if not date_str:
        return None
    match = re.search(r"\b(19\d{2}|20[0-3]\d)\b", date_str)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _find_reference_section(content: str) -> str | None:
    """Find and extract the references section from document content."""
    matches: list[re.Match[str]] = []
    for pattern in REFERENCE_SECTION_PATTERNS:
        matches.extend(re.finditer(pattern, content))
    if not matches:
        for pattern in REFERENCE_SECTION_FALLBACK_PATTERNS:
            matches.extend(re.finditer(pattern, content))
    if not matches:
        # Fallback: look for the last occurrence of the word "References"
        fallback_matches = list(re.finditer(r"(?i)\breferences\b", content))
        if not fallback_matches:
            return None
        match = fallback_matches[-1]
        start = match.end()
        return content[start:].strip()

    # Use the last match to avoid earlier "References" mentions (e.g., TOC).
    match = max(matches, key=lambda m: m.start())

    # Extract everything after the references heading
    start = match.end()
    # Try to find the next section heading to limit scope
    next_section = re.search(r"(?im)^\s*(?:\d+|[IVXLC]+)?(?:\.\d+)?\s*[A-Z][\w\s\-]{2,}$", content[start:])
    if next_section:
        end = start + next_section.start()
        return content[start:end].strip()
    return content[start:].strip()


def _split_references(refs_text: str) -> list[str]:
    """Split references section into individual references."""
    references: list[str] = []
    # Fix common PDF hyphenation across line breaks
    refs_text = re.sub(r"(\w)-\n(\w)", r"\1\2", refs_text)
    refs_text = refs_text.replace("\r\n", "\n").replace("\r", "\n")

    # Try numbered list format: [1], 1., 1), etc.
    numbered_pattern = r"(?m)^\s*(?:\[\d+\]|\d+[\.\)])\s+"
    if re.search(numbered_pattern, refs_text):
        parts = re.split(numbered_pattern, refs_text)
        references = [p.strip() for p in parts if p.strip() and len(p.strip()) > 20]
    else:
        # Try double newline as separator
        parts = re.split(r"\n\s*\n", refs_text)
        references = [p.strip().replace("\n", " ") for p in parts if p.strip() and len(p.strip()) > 20]

    def _looks_like_new_reference(line: str) -> bool:
        if re.match(r"^\s*(?:\[\d+\]|\d+[\.\)])\s+", line):
            return True
        # Author list starting pattern: "Surname, A." or "First Last, ..."
        if re.search(
            r"^[A-Z][A-Za-z'’.\-]+(?:\s+[A-Z][A-Za-z'’.\-]+){0,2},\s*[A-Z]",
            line,
        ):
            return True
        # "Surname et al." pattern
        if re.search(r"^[A-Z][A-Za-z'’.\-]+(?:\s+et\s+al\.)\b", line):
            return True
        return False

    # If still no good split, try single newlines with heuristics
    if len(references) < 5:
        lines = [ln.strip() for ln in refs_text.split("\n")]
        potential_refs = []
        current_ref = ""
        for line in lines:
            if not line:
                if current_ref and len(current_ref) > 30:
                    potential_refs.append(current_ref.strip())
                current_ref = ""
            else:
                # Check if this looks like a new reference (starts with author pattern)
                if current_ref and _looks_like_new_reference(line):
                    if len(current_ref) > 30:
                        potential_refs.append(current_ref.strip())
                    current_ref = line
                else:
                    current_ref = (current_ref + " " + line).strip() if current_ref else line
        if current_ref and len(current_ref) > 30:
            potential_refs.append(current_ref.strip())
        if len(potential_refs) > len(references):
            references = potential_refs

    # Additional pass: split on author-start lines when refs are still few
    if len(references) < 5:
        lines = [ln.strip() for ln in refs_text.split("\n") if ln.strip()]
        potential_refs = []
        current_ref = ""
        for line in lines:
            is_author_line = _looks_like_new_reference(line)
            has_year = re.search(YEAR_PATTERN, current_ref) is not None
            if current_ref and is_author_line and has_year:
                potential_refs.append(current_ref.strip())
                current_ref = line
            else:
                current_ref = (current_ref + " " + line).strip() if current_ref else line
        if current_ref and len(current_ref) > 30:
            potential_refs.append(current_ref.strip())
        if len(potential_refs) > len(references):
            references = potential_refs

    return references[:100]  # Limit to 100 references


def _extract_doi(text: str) -> str | None:
    """Extract DOI from reference text."""
    match = re.search(DOI_PATTERN, text, re.IGNORECASE)
    if match:
        doi = match.group(0)
        # Clean up the DOI
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
        # Remove trailing punctuation
        doi = doi.rstrip(".,;:)")
        return doi
    return None


def _extract_arxiv_id(text: str) -> str | None:
    """Extract arXiv ID from reference text."""
    # New format: YYMM.NNNNN
    match = re.search(ARXIV_PATTERN, text, re.IGNORECASE)
    if match:
        return match.group(1)
    # Old format: category/NNNNNNN
    match = re.search(ARXIV_OLD_PATTERN, text, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_url(text: str) -> str | None:
    """Extract URL from reference text."""
    # First try to find DOI URL
    doi = _extract_doi(text)
    if doi:
        return f"https://doi.org/{doi}"
    # Look for arXiv URL
    arxiv_id = _extract_arxiv_id(text)
    if arxiv_id:
        return f"https://arxiv.org/abs/{arxiv_id}"
    # Look for any URL
    match = re.search(URL_PATTERN, text)
    if match:
        return match.group(0).rstrip(".,;:)")
    return None


def _extract_year(text: str) -> int | None:
    """Extract publication year from reference text."""
    years = re.findall(YEAR_PATTERN, text)
    if years:
        # Prefer years in parentheses (common citation format)
        for match in re.finditer(r"\((\d{4})\)", text):
            year = int(match.group(1))
            if 1900 <= year <= 2030:
                return year
        # Fall back to first year found
        return int(years[0])
    return None


def _parse_reference_basic(raw_text: str) -> ReferenceEntry:
    """Parse a reference string into structured fields using heuristics."""
    doi = _extract_doi(raw_text)
    arxiv_id = _extract_arxiv_id(raw_text)
    url = _extract_url(raw_text)
    year = _extract_year(raw_text)

    # Try to extract title (often in quotes or after authors)
    title = None
    # Look for quoted title
    title_match = re.search(r'"([^"]{10,200})"', raw_text)
    if title_match:
        title = title_match.group(1).strip()
    elif not title_match:
        # Look for title after authors (pattern: Authors, Year. Title. ...)
        title_match = re.search(r"^\s*[^.]+\.\s*(\d{4})[.\s]+([^.]{10,150})\.", raw_text)
        if title_match:
            title = title_match.group(2).strip()

    # Try to extract authors (usually at the start)
    authors = None
    # Pattern: LastName, F., LastName, F., ... (Year)
    author_match = re.match(r"^((?:[A-Z][a-z]+(?:,\s*[A-Z]\.?)?(?:,?\s+(?:and\s+|&\s*)?)?)+)[\.,]", raw_text)
    if author_match:
        authors = author_match.group(1).strip().rstrip(",")
    else:
        # Pattern: F. LastName, F. LastName, ...
        author_match = re.match(r"^((?:[A-Z]\.?\s*[A-Z][a-z]+(?:,?\s+(?:and\s+|&\s*)?)?)+)[\.,]", raw_text)
        if author_match:
            authors = author_match.group(1).strip().rstrip(",")

    # Try to extract venue (journal/conference)
    venue = None
    # Look for common venue patterns: "In Proceedings of", "Journal of", etc.
    venue_match = re.search(r"(?:In\s+)?(?:Proceedings\s+of\s+)?(?:the\s+)?([A-Z][^,\.]{5,60}(?:Conference|Journal|Symposium|Workshop|Review|Letters|Transactions))", raw_text, re.IGNORECASE)
    if venue_match:
        venue = venue_match.group(1).strip()

    return ReferenceEntry(
        raw_text=raw_text[:1000],  # Limit raw text length
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        doi=doi,
        arxiv_id=arxiv_id,
        url=url,
    )


async def _enrich_with_semantic_scholar(references: list[ReferenceEntry]) -> tuple[list[ReferenceEntry], bool]:
    """Enrich references with Semantic Scholar data.

    Limits enrichment to MAX_ENRICHMENT_REFS to avoid long response times.
    Adds delays between API calls to respect Semantic Scholar rate limits.
    """
    try:
        from tldw_Server_API.app.core.Third_Party.Semantic_Scholar import (
            get_paper_details_semantic_scholar,
            search_papers_semantic_scholar,
        )
    except ImportError:
        logger.warning("Semantic Scholar module not available for enrichment")
        return references, False

    # Limit enrichment to first N references to avoid timeout
    refs_to_enrich = references[:MAX_ENRICHMENT_REFS]
    unenriched_remainder = references[MAX_ENRICHMENT_REFS:]

    enriched = []
    enrichment_performed = False
    api_call_count = 0

    for ref in refs_to_enrich:
        enriched_ref = ref.model_copy()

        # Add delay between API calls (skip first)
        if api_call_count > 0:
            await asyncio.sleep(SEMANTIC_SCHOLAR_DELAY)

        # Try to look up by DOI first
        if ref.doi:
            try:
                api_call_count += 1
                paper_data, err = await asyncio.to_thread(
                    get_paper_details_semantic_scholar,
                    f"DOI:{ref.doi}",
                )
                if paper_data and not err:
                    enriched_ref = _apply_semantic_scholar_data(enriched_ref, paper_data)
                    enrichment_performed = True
                    enriched.append(enriched_ref)
                    continue
            except Exception as e:
                logger.debug("DOI lookup failed for {}: {}", ref.doi, e)

        # Try to look up by arXiv ID
        if ref.arxiv_id:
            if api_call_count > 0:
                await asyncio.sleep(SEMANTIC_SCHOLAR_DELAY)
            try:
                api_call_count += 1
                paper_data, err = await asyncio.to_thread(
                    get_paper_details_semantic_scholar,
                    f"ARXIV:{ref.arxiv_id}",
                )
                if paper_data and not err:
                    enriched_ref = _apply_semantic_scholar_data(enriched_ref, paper_data)
                    enrichment_performed = True
                    enriched.append(enriched_ref)
                    continue
            except Exception as e:
                logger.debug("arXiv lookup failed for {}: {}", ref.arxiv_id, e)

        # Try title search as fallback
        if ref.title:
            if api_call_count > 0:
                await asyncio.sleep(SEMANTIC_SCHOLAR_DELAY)
            try:
                api_call_count += 1
                search_result, err = await asyncio.to_thread(
                    search_papers_semantic_scholar,
                    ref.title,
                    limit=1,
                )
                if search_result and not err:
                    papers = search_result.get("data", [])
                    if papers:
                        # Check if title matches reasonably
                        paper = papers[0]
                        paper_title = (paper.get("title") or "").lower()
                        ref_title = ref.title.lower()
                        # Simple similarity check
                        if ref_title[:30] in paper_title or paper_title[:30] in ref_title:
                            enriched_ref = _apply_semantic_scholar_data(enriched_ref, paper)
                            enrichment_performed = True
            except Exception as e:
                logger.debug("Title search failed for {}: {}", ref.title, e)

        enriched.append(enriched_ref)

    # Append any unenriched references beyond the limit
    enriched.extend(unenriched_remainder)

    return enriched, enrichment_performed


def _apply_semantic_scholar_data(ref: ReferenceEntry, paper: dict[str, Any]) -> ReferenceEntry:
    """Apply Semantic Scholar data to a reference entry."""
    # Update basic fields if not already set
    if not ref.title and paper.get("title"):
        ref.title = paper["title"]

    if not ref.year and paper.get("year"):
        ref.year = paper["year"]

    if not ref.venue and paper.get("venue"):
        ref.venue = paper["venue"]

    if not ref.authors and paper.get("authors"):
        authors = paper.get("authors", [])
        if authors:
            ref.authors = ", ".join([a.get("name", "") for a in authors])

    # Extract DOI from externalIds
    if not ref.doi and paper.get("externalIds"):
        external_ids = paper.get("externalIds", {})
        if external_ids.get("DOI"):
            ref.doi = external_ids["DOI"]
        if not ref.arxiv_id and external_ids.get("ArXiv"):
            ref.arxiv_id = external_ids["ArXiv"]

    # Add enriched fields
    ref.citation_count = paper.get("citationCount")
    ref.semantic_scholar_id = paper.get("paperId")

    if paper.get("openAccessPdf"):
        pdf_info = paper["openAccessPdf"]
        if isinstance(pdf_info, dict) and pdf_info.get("url"):
            ref.open_access_pdf = pdf_info["url"]

    # Update URL if not set
    if not ref.url and paper.get("url"):
        ref.url = paper["url"]

    return ref


def _needs_external_enrichment(ref: ReferenceEntry) -> bool:
    """Return True if any core metadata fields are missing."""
    return any(
        [
            not ref.title,
            not ref.authors,
            not ref.year,
            not ref.venue,
            not ref.url,
            not ref.open_access_pdf,
        ]
    )


def _apply_crossref_data(ref: ReferenceEntry, item: dict[str, Any]) -> ReferenceEntry:
    """Apply Crossref data to a reference entry."""
    if not ref.title and item.get("title"):
        ref.title = item["title"]
    if not ref.authors and item.get("authors"):
        ref.authors = item["authors"]
    if not ref.venue and item.get("journal"):
        ref.venue = item["journal"]
    if not ref.year and item.get("pub_date"):
        ref.year = _parse_year_from_date(item.get("pub_date"))
    if not ref.doi and item.get("doi"):
        ref.doi = item["doi"]
    if not ref.url and item.get("url"):
        ref.url = item["url"]
    if not ref.open_access_pdf and item.get("pdf_url"):
        ref.open_access_pdf = item["pdf_url"]
    return ref


def _apply_arxiv_data(ref: ReferenceEntry, item: dict[str, Any]) -> ReferenceEntry:
    """Apply arXiv data to a reference entry."""
    if not ref.title and item.get("title"):
        ref.title = item["title"]
    if not ref.authors and item.get("authors"):
        ref.authors = item["authors"]
    if not ref.year and item.get("published_date"):
        ref.year = _parse_year_from_date(item.get("published_date"))
    if not ref.arxiv_id and item.get("id"):
        ref.arxiv_id = item["id"]
    if not ref.url and item.get("id"):
        ref.url = f"https://arxiv.org/abs/{item['id']}"
    if not ref.open_access_pdf and item.get("pdf_url"):
        ref.open_access_pdf = item["pdf_url"]
    return ref


async def _enrich_with_crossref(references: list[ReferenceEntry]) -> tuple[list[ReferenceEntry], bool]:
    """Enrich references with Crossref metadata (DOI lookups)."""
    try:
        from tldw_Server_API.app.core.Third_Party.Crossref import get_crossref_by_doi
    except ImportError:
        logger.warning("Crossref module not available for enrichment")
        return references, False

    refs_to_enrich = references[:MAX_ENRICHMENT_REFS]
    unenriched_remainder = references[MAX_ENRICHMENT_REFS:]

    enriched: list[ReferenceEntry] = []
    enrichment_performed = False

    for ref in refs_to_enrich:
        enriched_ref = ref.model_copy()
        if ref.doi and _needs_external_enrichment(enriched_ref):
            try:
                item, err = await asyncio.to_thread(get_crossref_by_doi, ref.doi)
                if item and not err:
                    enriched_ref = _apply_crossref_data(enriched_ref, item)
                    enrichment_performed = True
            except Exception as e:
                logger.debug("Crossref lookup failed for {}: {}", ref.doi, e)
        enriched.append(enriched_ref)

    enriched.extend(unenriched_remainder)
    return enriched, enrichment_performed


async def _enrich_with_arxiv(references: list[ReferenceEntry]) -> tuple[list[ReferenceEntry], bool]:
    """Enrich references with arXiv metadata (ID lookups)."""
    try:
        from tldw_Server_API.app.core.Third_Party.Arxiv import get_arxiv_by_id
    except ImportError:
        logger.warning("arXiv module not available for enrichment")
        return references, False

    refs_to_enrich = references[:MAX_ENRICHMENT_REFS]
    unenriched_remainder = references[MAX_ENRICHMENT_REFS:]

    enriched: list[ReferenceEntry] = []
    enrichment_performed = False

    for ref in refs_to_enrich:
        enriched_ref = ref.model_copy()
        if ref.arxiv_id and _needs_external_enrichment(enriched_ref):
            try:
                item, err = await asyncio.to_thread(get_arxiv_by_id, ref.arxiv_id)
                if item and not err:
                    enriched_ref = _apply_arxiv_data(enriched_ref, item)
                    enrichment_performed = True
            except Exception as e:
                logger.debug("arXiv lookup failed for {}: {}", ref.arxiv_id, e)
        enriched.append(enriched_ref)

    enriched.extend(unenriched_remainder)
    return enriched, enrichment_performed


@router.get(
    "/{media_id:int}/references",
    status_code=status.HTTP_200_OK,
    summary="Get Document References",
    response_model=DocumentReferencesResponse,
    dependencies=[Depends(rbac_rate_limit("media.references"))],
    responses={
        200: {
            "description": "References retrieved (may be empty if document has no references section)"
        },
        404: {"description": "Media item not found"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Server error (database or extraction failure)"},
    },
)
async def get_document_references(
    media_id: int = Path(..., description="The ID of the media item"),
    enrich: bool = Query(
        True,
        description="Enrich references with external API data (citation counts, PDFs)",
    ),
    db: MediaDatabase = Depends(get_media_db_for_user),
    current_user: User = Depends(get_request_user),
) -> DocumentReferencesResponse:
    """
    Extract and return references/bibliography from a document.

    This endpoint parses the document content to find a references section,
    extracts individual references, and optionally enriches them with
    external API data (citation counts, open access PDFs).

    ## Response Pattern (Graceful Degradation)

    Returns HTTP 200 with `has_references=false` when:
    - Document has no identifiable references section
    - Document is empty or has no content

    HTTP errors are reserved for actual failures:
    - **404**: Media ID does not exist
    - **429**: Rate limit exceeded
    - **500**: Database error or extraction crash

    ## Enrichment

    When `enrich=true` (default), the endpoint attempts to look up each
    reference using:
    - Semantic Scholar (DOI/arXiv ID lookup, title search fallback)
    - Crossref (DOI metadata)
    - arXiv (ID metadata)

    Enrichment adds:
    - Citation counts
    - Open access PDF links
    - Semantic Scholar paper IDs
    - Missing metadata (title, authors, year)

    Enrichment is best-effort and gracefully degrades if external APIs fail.
    Enrichment is limited to the first 20 references to avoid long response times.
    """
    user_id = str(getattr(current_user, "id", "anonymous"))
    db_scope = _get_db_scope(db)
    cache_key = _build_references_cache_key(
        media_id,
        enrich=enrich,
        user_id=user_id,
        db_scope=db_scope,
    )
    cached = get_cached_response(cache_key)
    if cached is not None:
        _etag, payload = cached
        logger.debug("Returning cached references for media_id={}", media_id)
        return DocumentReferencesResponse(**payload)

    logger.debug(
        "Extracting references for media_id={}, user_id={}, enrich={}",
        media_id,
        getattr(current_user, "id", "?"),
        enrich,
    )

    # 1. Verify media item exists
    try:
        media = db.get_media_by_id(media_id, include_deleted=False, include_trash=False)
    except Exception as e:
        logger.error("Database error fetching media_id={}: {}", media_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching media item",
        ) from e

    if not media:
        logger.warning(
            "Media not found for references extraction: {} (user: {})",
            media_id,
            getattr(current_user, "id", "?"),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found or is inactive/trashed",
        )

    # 2. Get document content
    content = str(media.get("content") or "")
    if not content.strip():
        content = get_latest_transcription(db, media_id) or ""

    # Normalize escaped and platform-specific newlines
    if "\\n" in content and "\n" not in content:
        content = content.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    content = content.strip()
    if not content:
        logger.debug("No content available for media_id={}", media_id)
        response = DocumentReferencesResponse(
            media_id=media_id,
            has_references=False,
            references=[],
            enrichment_source=None,
        )
        cache_response(cache_key, response.model_dump(), media_id=media_id)
        return response

    # 3. Find references section
    refs_section = _find_reference_section(content)
    if not refs_section:
        logger.debug("No references section found in media_id={}", media_id)
        response = DocumentReferencesResponse(
            media_id=media_id,
            has_references=False,
            references=[],
            enrichment_source=None,
        )
        cache_response(cache_key, response.model_dump(), media_id=media_id)
        return response

    # 4. Parse individual references
    raw_refs = _split_references(refs_section)
    if not raw_refs:
        logger.debug("No individual references parsed from media_id={}", media_id)
        response = DocumentReferencesResponse(
            media_id=media_id,
            has_references=False,
            references=[],
            enrichment_source=None,
        )
        cache_response(cache_key, response.model_dump(), media_id=media_id)
        return response

    # 5. Parse each reference
    references = [_parse_reference_basic(ref) for ref in raw_refs]
    logger.debug("Parsed {} references from media_id={}", len(references), media_id)

    # 6. Enrich with external APIs if requested
    enrichment_sources: set[str] = set()
    if enrich and references:
        try:
            references, enriched = await _enrich_with_semantic_scholar(references)
            if enriched:
                enrichment_sources.add("semantic_scholar")
                logger.debug(
                    "Enriched references with Semantic Scholar for media_id={}",
                    media_id,
                )

            references, enriched = await _enrich_with_crossref(references)
            if enriched:
                enrichment_sources.add("crossref")
                logger.debug(
                    "Enriched references with Crossref for media_id={}",
                    media_id,
                )

            references, enriched = await _enrich_with_arxiv(references)
            if enriched:
                enrichment_sources.add("arxiv")
                logger.debug(
                    "Enriched references with arXiv for media_id={}",
                    media_id,
                )
        except Exception as e:
            logger.warning(
                "Failed to enrich references for media_id={}: {}",
                media_id,
                e,
            )
            # Continue without enrichment

    enrichment_source = ",".join(sorted(enrichment_sources)) if enrichment_sources else None
    response = DocumentReferencesResponse(
        media_id=media_id,
        has_references=len(references) > 0,
        references=references,
        enrichment_source=enrichment_source,
    )
    cache_response(cache_key, response.model_dump(), media_id=media_id)
    return response


__all__ = ["router"]
