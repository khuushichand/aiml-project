import re
from collections.abc import Mapping
from typing import Any, Optional

_DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
_PMID_RE = re.compile(r"^\d{1,9}$")
_PMCID_RE = re.compile(r"^(?:PMC)?(\d+)$", re.IGNORECASE)
_ARXIV_RE = re.compile(r"^[a-z\-]+(\/\d{7})$|^(\d{4}\.\d{4,5})(v\d+)?$", re.IGNORECASE)


def _norm_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def normalize_safe_metadata(sm: dict[str, Any]) -> dict[str, Any]:
    """Normalize and lightly validate a safe metadata dict.

    - Validates DOI format if provided
    - Normalizes PMID to digits-only string
    - Normalizes PMCID to digits-only string (strips 'PMC' prefix)
    - Normalizes arXiv ID (trims, preserves case where needed)
    - Leaves unknown keys as-is (stringified primitives)

    Raises ValueError on badly malformed DOI/PMID/PMCID.
    """
    out: dict[str, Any] = {}

    # Copy through simple fields
    for key, val in sm.items():
        if key is None:
            continue
        k = str(key).strip()
        if not k:
            continue
        out[k] = val

    # DOI
    _raw_doi = out.get("doi") if "doi" in out else out.get("DOI")
    doi = _norm_str(_raw_doi)
    if _raw_doi is not None and doi is None:
        raise ValueError(f"Invalid DOI format: {_raw_doi}")
    if doi is not None:
        if not _DOI_RE.match(doi):
            raise ValueError(f"Invalid DOI format: {doi}")
        out["doi"] = doi

    # PMID
    pmid = _norm_str(out.get("pmid") or out.get("PMID"))
    if pmid is not None:
        pmid_digits = re.sub(r"\D+", "", pmid)
        if not _PMID_RE.match(pmid_digits):
            raise ValueError(f"Invalid PMID format: {pmid}")
        out["pmid"] = pmid_digits

    # PMCID
    pmcid = _norm_str(out.get("pmcid") or out.get("PMCID"))
    if pmcid is not None:
        m = _PMCID_RE.match(pmcid)
        if not m:
            raise ValueError(f"Invalid PMCID format: {pmcid}")
        out["pmcid"] = m.group(1)

    # arXiv ID
    arx = _norm_str(out.get("arxiv_id") or out.get("arXiv") or out.get("ArXiv"))
    if arx is not None:
        # Basic normalization: trim whitespace
        arx_norm = arx.replace(" ", "")
        # Optional lightweight validation
        if not _ARXIV_RE.match(arx_norm):
            # Not fatal; keep as provided but trimmed
            arx_norm = arx_norm
        out["arxiv_id"] = arx_norm

    # S2 paper id
    s2 = _norm_str(out.get("s2_paper_id") or out.get("paperId"))
    if s2 is not None:
        out["s2_paper_id"] = s2

    return out


def update_version_safe_metadata_in_transaction(
    db: Any,
    dv_id: int,
    safe_metadata_json: Optional[str],
    merged_metadata: Mapping[str, Any],
    connection: Any,
) -> None:
    """
    Update DocumentVersions.safe_metadata (and bump version/last_modified)
    for a specific version and keep the identifier index in sync.

    This helper encapsulates the repeated SQL + identifier upsert logic used
    by the safe-metadata write endpoints.
    """
    # Local imports to avoid introducing heavy import-time dependencies or
    # circular references during module initialization.
    import sqlite3  # noqa: WPS433
    from datetime import datetime  # noqa: WPS433

    from loguru import logger  # noqa: WPS433

    from tldw_Server_API.app.core.DB_Management.backends.base import (  # noqa: WPS433
        BackendType,
    )
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (  # noqa: WPS433
        DatabaseError,
    )

    try:
        now_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    except Exception:  # pragma: no cover - extremely unlikely
        now_ts = None

    if now_ts is not None:
        db.execute_query(
            "UPDATE DocumentVersions SET safe_metadata=?, version=version+1, last_modified=? WHERE id=? AND deleted=0",
            (safe_metadata_json, now_ts, dv_id),
            connection=connection,
        )
    else:
        db.execute_query(
            "UPDATE DocumentVersions SET safe_metadata=?, version=version+1 WHERE id=? AND deleted=0",
            (safe_metadata_json, dv_id),
            connection=connection,
        )

    # Maintain identifier index using backend-specific upsert.
    # Accept both canonical and legacy key variants for robustness.
    try:
        doi = merged_metadata.get("doi") or merged_metadata.get("DOI")
        pmid = merged_metadata.get("pmid") or merged_metadata.get("PMID")
        pmcid = merged_metadata.get("pmcid") or merged_metadata.get("PMCID")
        arxiv = (
            merged_metadata.get("arxiv_id")
            or merged_metadata.get("arxiv")
            or merged_metadata.get("ArXiv")
        )
        s2id = merged_metadata.get("s2_paper_id") or merged_metadata.get("paperId")
        backend = db.backend_type() if callable(db.backend_type) else db.backend_type
        if backend == BackendType.POSTGRESQL:
            ident_sql = (
                "INSERT INTO DocumentVersionIdentifiers (dv_id, doi, pmid, pmcid, arxiv_id, s2_paper_id) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (dv_id) DO UPDATE SET "
                "doi = EXCLUDED.doi, pmid = EXCLUDED.pmid, pmcid = EXCLUDED.pmcid, "
                "arxiv_id = EXCLUDED.arxiv_id, s2_paper_id = EXCLUDED.s2_paper_id"
            )
        else:
            ident_sql = (
                "INSERT OR REPLACE INTO DocumentVersionIdentifiers (dv_id, doi, pmid, pmcid, arxiv_id, s2_paper_id) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            )
        db.execute_query(
            ident_sql,
            (dv_id, doi, pmid, pmcid, arxiv, s2id),
            connection=connection,
        )
    except (sqlite3.OperationalError, DatabaseError) as exc:
        # Missing identifier table or unsupported upsert is not fatal.
        logger.debug(
            "Identifier index update skipped (missing table/unsupported upsert) for dv_id=%s: %s",
            dv_id,
            exc,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(
            "Identifier index update failed for dv_id=%s: %s",
            dv_id,
            exc,
            exc_info=True,
        )
