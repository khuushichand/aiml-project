#!/usr/bin/env python3
"""
Validate dual-read parity between legacy and normalized email search paths.

Compares:
- Legacy: `search_media_db(..., media_types=['email'])`
- Normalized: `search_email_messages(...)`

The tool runs sampled queries, computes overlap metrics, and emits a JSON report
that can be used as a cutover gate artifact for EMAIL-M3-002.

Examples:
  python Helper_Scripts/checks/email_search_dual_read_parity.py \
    --db-path /path/to/Media_DB_v2.db \
    --tenant-id user:1 \
    --query-mix-file Helper_Scripts/checks/fixtures/email_dual_read_query_mix.sample.json \
    --out .benchmarks/email_dual_read_parity_report.json

  python Helper_Scripts/checks/email_search_dual_read_parity.py \
    --db-path /path/to/Media_DB_v2.db \
    --tenant-id user:1 \
    --auto-query-count 25 \
    --limit 100
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

_HELPERS_ROOT = Path(__file__).resolve()
for _parent in [_HELPERS_ROOT, *_HELPERS_ROOT.parents]:
    if _parent.name == "Helper_Scripts":
        _parent_str = str(_parent)
        if _parent_str not in sys.path:
            sys.path.insert(0, _parent_str)
        break

from common.repo_utils import ensure_repo_root

ensure_repo_root()

if TYPE_CHECKING:
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def _load_media_database_class():
    try:
        from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase as media_db_cls
    except Exception:
        print(
            "tldw_Server_API not available; run from repo root or set PYTHONPATH.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    return media_db_cls


_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9@._-]{2,}")
_TITLE_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'_-]{1,}")
_STOPWORDS = {
    "and",
    "are",
    "but",
    "for",
    "from",
    "have",
    "has",
    "inbox",
    "into",
    "its",
    "not",
    "or",
    "subject",
    "that",
    "the",
    "this",
    "with",
    "you",
    "your",
}


@dataclass(frozen=True)
class ParityQueryCase:
    name: str
    legacy_query: str
    normalized_query: str
    notes: str = ""


@dataclass(frozen=True)
class ParityThresholds:
    min_precision: float
    min_recall: float
    min_jaccard: float
    max_total_delta_ratio: float
    min_pass_rate: float
    max_query_errors: int
    min_backfill_coverage: float


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp_01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_ratio(numerator: float, denominator: float) -> float:
    den = float(denominator)
    if den <= 0:
        return 0.0
    return float(numerator) / den


def _normalize_query_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_id_list(raw_ids: list[Any]) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for raw in raw_ids:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _extract_terms_from_text(text: str, *, max_terms: int = 200) -> list[str]:
    counts: dict[str, int] = {}
    for token in _TOKEN_RE.findall(str(text or "")):
        candidate = token.strip("._-").lower()
        if len(candidate) < 3:
            continue
        if candidate.isdigit():
            continue
        if candidate in _STOPWORDS:
            continue
        counts[candidate] = counts.get(candidate, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [item[0] for item in ranked[: max(1, int(max_terms))]]


def _extract_title_phrase(text: str) -> str | None:
    words = _TITLE_WORD_RE.findall(str(text or ""))
    cleaned = [word.strip().strip("._-") for word in words if len(word.strip().strip("._-")) >= 3]
    if len(cleaned) < 2:
        return None
    phrase = f"{cleaned[0]} {cleaned[1]}"
    return f'"{phrase}"'


def _parse_query_mix_payload(payload: Any) -> list[ParityQueryCase]:
    if not isinstance(payload, list):
        raise ValueError("query mix payload must be a JSON array")  # noqa: TRY003

    out: list[ParityQueryCase] = []
    for idx, row in enumerate(payload):
        if not isinstance(row, dict):
            raise ValueError(f"query mix entry {idx} must be an object")  # noqa: TRY003

        name = _normalize_query_text(row.get("name")) or f"query_{idx + 1:03d}"
        shared_query = _normalize_query_text(row.get("query"))
        legacy_query = _normalize_query_text(row.get("legacy_query")) or shared_query
        normalized_query = _normalize_query_text(row.get("normalized_query")) or shared_query
        notes = _normalize_query_text(row.get("notes"))

        if not legacy_query:
            raise ValueError(f"query mix entry {idx} missing legacy query text")  # noqa: TRY003
        if not normalized_query:
            raise ValueError(f"query mix entry {idx} missing normalized query text")  # noqa: TRY003

        out.append(
            ParityQueryCase(
                name=name,
                legacy_query=legacy_query,
                normalized_query=normalized_query,
                notes=notes,
            )
        )

    if not out:
        raise ValueError("query mix payload contained zero queries")  # noqa: TRY003
    return out


def _load_query_mix_file(path: Path) -> list[ParityQueryCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _parse_query_mix_payload(payload)


def _sample_auto_query_rows(db: Any, *, row_limit: int) -> list[dict[str, Any]]:
    limit_int = max(1, int(row_limit))
    with db.transaction() as conn:
        rows = db._fetchall_with_connection(  # noqa: SLF001 - helper script uses DB internals
            conn,
            (
                "SELECT title, content, author "
                "FROM Media "
                "WHERE deleted = 0 AND lower(COALESCE(type, '')) = 'email' "
                "ORDER BY last_modified DESC, id DESC "
                "LIMIT ?"
            ),
            (limit_int,),
        )
    return rows


def _build_auto_query_cases(
    rows: list[dict[str, Any]],
    *,
    query_count: int,
) -> list[ParityQueryCase]:
    target = max(1, int(query_count))
    term_counts: dict[str, int] = {}
    phrase_seen: set[str] = set()
    phrases: list[str] = []

    for row in rows:
        title = str((row or {}).get("title") or "")
        content = str((row or {}).get("content") or "")
        author = str((row or {}).get("author") or "")

        phrase = _extract_title_phrase(title)
        if phrase and phrase not in phrase_seen:
            phrase_seen.add(phrase)
            phrases.append(phrase)

        combined = " ".join([title, author, content[:5000]])
        for term in _extract_terms_from_text(combined, max_terms=300):
            term_counts[term] = term_counts.get(term, 0) + 1

    ranked_terms = [
        term for term, _count in sorted(term_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    selected_queries: list[str] = []
    for phrase in phrases:
        if len(selected_queries) >= target:
            break
        selected_queries.append(phrase)
    for term in ranked_terms:
        if len(selected_queries) >= target:
            break
        selected_queries.append(term)

    if not selected_queries:
        selected_queries = ["email"]

    return [
        ParityQueryCase(
            name=f"auto_{idx + 1:03d}",
            legacy_query=query,
            normalized_query=query,
            notes="auto-generated from legacy email media corpus",
        )
        for idx, query in enumerate(selected_queries[:target])
    ]


def _legacy_search(
    *,
    db: Any,
    query: str,
    limit: int,
    legacy_fields: list[str],
) -> tuple[list[int], int]:
    rows, total = db.search_media_db(
        search_query=query,
        search_fields=legacy_fields,
        media_types=["email"],
        page=1,
        results_per_page=limit,
        include_trash=False,
        include_deleted=False,
    )
    ids = _normalize_id_list([row.get("id") for row in rows if isinstance(row, dict)])
    return ids, int(total)


def _normalized_search(
    *,
    db: Any,
    query: str,
    tenant_id: str | None,
    limit: int,
) -> tuple[list[int], int]:
    rows, total = db.search_email_messages(
        query=query,
        tenant_id=tenant_id,
        include_deleted=False,
        limit=limit,
        offset=0,
    )
    ids = _normalize_id_list([row.get("media_id") for row in rows if isinstance(row, dict)])
    return ids, int(total)


def _evaluate_case_metrics(
    *,
    legacy_ids: list[int],
    normalized_ids: list[int],
    legacy_total: int,
    normalized_total: int,
    thresholds: ParityThresholds,
    diff_limit: int,
) -> dict[str, Any]:
    legacy_set = set(legacy_ids)
    normalized_set = set(normalized_ids)
    overlap = legacy_set & normalized_set
    union = legacy_set | normalized_set
    only_legacy = [mid for mid in legacy_ids if mid not in normalized_set]
    only_normalized = [mid for mid in normalized_ids if mid not in legacy_set]

    if not legacy_set and not normalized_set:
        precision = 1.0
        recall = 1.0
        jaccard = 1.0
    else:
        precision = _safe_ratio(len(overlap), len(normalized_set)) if normalized_set else 0.0
        recall = _safe_ratio(len(overlap), len(legacy_set)) if legacy_set else 0.0
        jaccard = _safe_ratio(len(overlap), len(union)) if union else 0.0

    total_delta = abs(int(legacy_total) - int(normalized_total))
    total_denom = max(1, int(legacy_total), int(normalized_total))
    total_delta_ratio = _safe_ratio(float(total_delta), float(total_denom))

    reasons: list[str] = []
    if precision < thresholds.min_precision:
        reasons.append(f"precision<{thresholds.min_precision:.2f}")
    if recall < thresholds.min_recall:
        reasons.append(f"recall<{thresholds.min_recall:.2f}")
    if jaccard < thresholds.min_jaccard:
        reasons.append(f"jaccard<{thresholds.min_jaccard:.2f}")
    if total_delta_ratio > thresholds.max_total_delta_ratio:
        reasons.append(f"total_delta_ratio>{thresholds.max_total_delta_ratio:.2f}")

    return {
        "legacy_total": int(legacy_total),
        "normalized_total": int(normalized_total),
        "legacy_top_ids": legacy_ids,
        "normalized_top_ids": normalized_ids,
        "overlap_count": int(len(overlap)),
        "precision": float(precision),
        "recall": float(recall),
        "jaccard": float(jaccard),
        "total_delta": int(total_delta),
        "total_delta_ratio": float(total_delta_ratio),
        "only_legacy_ids": only_legacy[: max(1, int(diff_limit))],
        "only_normalized_ids": only_normalized[: max(1, int(diff_limit))],
        "pass": len(reasons) == 0,
        "fail_reasons": reasons,
    }


def _fetch_dataset_profile(db: Any, *, tenant_id: str | None) -> dict[str, Any]:
    with db.transaction() as conn:
        legacy_row = db._fetchone_with_connection(  # noqa: SLF001 - helper script uses DB internals
            conn,
            (
                "SELECT COUNT(*) AS total "
                "FROM Media "
                "WHERE deleted = 0 AND lower(COALESCE(type, '')) = 'email'"
            ),
            tuple(),
        )
        legacy_total = int((legacy_row or {}).get("total", 0) or 0)

        if tenant_id:
            normalized_row = db._fetchone_with_connection(  # noqa: SLF001
                conn,
                "SELECT COUNT(*) AS total FROM email_messages WHERE tenant_id = ?",
                (tenant_id,),
            )
        else:
            normalized_row = db._fetchone_with_connection(  # noqa: SLF001
                conn,
                "SELECT COUNT(*) AS total FROM email_messages",
                tuple(),
            )
        normalized_total = int((normalized_row or {}).get("total", 0) or 0)

    if legacy_total <= 0:
        coverage = 1.0 if normalized_total <= 0 else 0.0
    else:
        coverage = _safe_ratio(float(normalized_total), float(legacy_total))

    return {
        "legacy_email_media_total": legacy_total,
        "normalized_email_message_total": normalized_total,
        "normalized_to_legacy_coverage_ratio": float(coverage),
    }


def _build_gate_summary(
    *,
    query_results: list[dict[str, Any]],
    profile: dict[str, Any],
    thresholds: ParityThresholds,
) -> dict[str, Any]:
    total_queries = len(query_results)
    error_results = [row for row in query_results if row.get("error")]
    passed_results = [row for row in query_results if bool(row.get("pass"))]
    failed_results = [row for row in query_results if not bool(row.get("pass"))]
    pass_rate = _safe_ratio(float(len(passed_results)), float(total_queries)) if total_queries > 0 else 0.0

    fail_reasons: list[str] = []
    if total_queries <= 0:
        fail_reasons.append("no_queries_executed")
    if pass_rate < thresholds.min_pass_rate:
        fail_reasons.append(f"pass_rate<{thresholds.min_pass_rate:.2f}")
    if len(error_results) > thresholds.max_query_errors:
        fail_reasons.append(f"query_errors>{thresholds.max_query_errors}")

    coverage_ratio = float(profile.get("normalized_to_legacy_coverage_ratio") or 0.0)
    if coverage_ratio < thresholds.min_backfill_coverage:
        fail_reasons.append(f"coverage_ratio<{thresholds.min_backfill_coverage:.2f}")

    worst_jaccard = min((float(row.get("jaccard") or 0.0) for row in query_results), default=1.0)
    worst_precision = min((float(row.get("precision") or 0.0) for row in query_results), default=1.0)
    worst_recall = min((float(row.get("recall") or 0.0) for row in query_results), default=1.0)

    return {
        "total_queries": int(total_queries),
        "passed_queries": int(len(passed_results)),
        "failed_queries": int(len(failed_results)),
        "error_queries": int(len(error_results)),
        "pass_rate": float(pass_rate),
        "worst_jaccard": float(worst_jaccard),
        "worst_precision": float(worst_precision),
        "worst_recall": float(worst_recall),
        "gate_passed": len(fail_reasons) == 0,
        "gate_fail_reasons": fail_reasons,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate dual-read parity between legacy and normalized email search paths."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        required=True,
        help="Path to Media DB (SQLite file).",
    )
    parser.add_argument("--client-id", type=str, default="email-parity-validator")
    parser.add_argument(
        "--tenant-id",
        type=str,
        default=None,
        help="Tenant id used by normalized email search. Defaults to MediaDatabase client scope.",
    )
    parser.add_argument(
        "--query-mix-file",
        type=Path,
        default=None,
        help=(
            "JSON array of queries: [{name, query}] or "
            "[{name, legacy_query, normalized_query, notes?}]."
        ),
    )
    parser.add_argument(
        "--auto-query-count",
        type=int,
        default=20,
        help="Auto-generated query count when --query-mix-file is omitted.",
    )
    parser.add_argument(
        "--auto-sample-rows",
        type=int,
        default=300,
        help="Number of email media rows to sample for auto query generation.",
    )
    parser.add_argument("--limit", type=int, default=100, help="Result limit per path for overlap comparison.")
    parser.add_argument(
        "--legacy-fields",
        type=str,
        default="title,content,author",
        help="Comma-separated legacy search fields used by search_media_db.",
    )
    parser.add_argument(
        "--diff-limit",
        type=int,
        default=25,
        help="Maximum number of differing IDs to include in query-level report fields.",
    )
    parser.add_argument("--min-precision", type=float, default=0.70)
    parser.add_argument("--min-recall", type=float, default=0.70)
    parser.add_argument("--min-jaccard", type=float, default=0.50)
    parser.add_argument("--max-total-delta-ratio", type=float, default=0.40)
    parser.add_argument("--min-pass-rate", type=float, default=0.95)
    parser.add_argument("--max-query-errors", type=int, default=0)
    parser.add_argument(
        "--min-backfill-coverage",
        type=float,
        default=0.95,
        help="Minimum normalized/legacy row ratio required for gate pass.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(".benchmarks/email_dual_read_parity_report.json"),
        help="Output JSON report path.",
    )
    parser.add_argument("--print-json", action="store_true")
    parser.add_argument(
        "--allow-gate-fail",
        action="store_true",
        help="Always return exit code 0 even if gate conditions fail.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    started_at = time.perf_counter()

    db_path = args.db_path.expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    limit = max(1, int(args.limit))
    diff_limit = max(1, int(args.diff_limit))
    legacy_fields = [field.strip() for field in str(args.legacy_fields).split(",") if field.strip()]
    if not legacy_fields:
        legacy_fields = ["title", "content", "author"]

    thresholds = ParityThresholds(
        min_precision=_clamp_01(args.min_precision),
        min_recall=_clamp_01(args.min_recall),
        min_jaccard=_clamp_01(args.min_jaccard),
        max_total_delta_ratio=_clamp_01(args.max_total_delta_ratio),
        min_pass_rate=_clamp_01(args.min_pass_rate),
        max_query_errors=max(0, int(args.max_query_errors)),
        min_backfill_coverage=_clamp_01(args.min_backfill_coverage),
    )

    media_db_cls = _load_media_database_class()
    db = media_db_cls(db_path=db_path, client_id=args.client_id)
    try:
        if args.query_mix_file is not None:
            query_cases = _load_query_mix_file(args.query_mix_file.expanduser().resolve())
            query_mix_source = "file"
        else:
            rows = _sample_auto_query_rows(db, row_limit=max(1, int(args.auto_sample_rows)))
            query_cases = _build_auto_query_cases(rows, query_count=max(1, int(args.auto_query_count)))
            query_mix_source = "auto"

        profile = _fetch_dataset_profile(db, tenant_id=args.tenant_id)
        query_results: list[dict[str, Any]] = []

        for case in query_cases:
            row: dict[str, Any] = {
                "name": case.name,
                "legacy_query": case.legacy_query,
                "normalized_query": case.normalized_query,
                "notes": case.notes,
            }
            try:
                legacy_ids, legacy_total = _legacy_search(
                    db=db,
                    query=case.legacy_query,
                    limit=limit,
                    legacy_fields=legacy_fields,
                )
                normalized_ids, normalized_total = _normalized_search(
                    db=db,
                    query=case.normalized_query,
                    tenant_id=args.tenant_id,
                    limit=limit,
                )
                row.update(
                    _evaluate_case_metrics(
                        legacy_ids=legacy_ids,
                        normalized_ids=normalized_ids,
                        legacy_total=legacy_total,
                        normalized_total=normalized_total,
                        thresholds=thresholds,
                        diff_limit=diff_limit,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - keep report generation resilient
                row.update(
                    {
                        "pass": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "fail_reasons": ["query_error"],
                    }
                )
            query_results.append(row)
    finally:
        db.close_connection()

    gate = _build_gate_summary(
        query_results=query_results,
        profile=profile,
        thresholds=thresholds,
    )
    report = {
        "report_version": 1,
        "generated_at": _iso_utc_now(),
        "duration_seconds": round(time.perf_counter() - started_at, 4),
        "environment": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
        },
        "inputs": {
            "db_path": str(db_path),
            "client_id": str(args.client_id),
            "tenant_id": str(args.tenant_id) if args.tenant_id else None,
            "limit": limit,
            "legacy_fields": legacy_fields,
            "query_mix_source": query_mix_source,
            "query_mix_file": str(args.query_mix_file) if args.query_mix_file else None,
        },
        "thresholds": asdict(thresholds),
        "dataset_profile": profile,
        "gate": gate,
        "queries": query_results,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info(
        (
            "Dual-read parity complete. pass_rate={:.3f} gate_passed={} "
            "queries={} errors={} out={}"
        ),
        float(gate["pass_rate"]),
        bool(gate["gate_passed"]),
        int(gate["total_queries"]),
        int(gate["error_queries"]),
        args.out,
    )

    if args.print_json:
        print(json.dumps(report, indent=2))

    if bool(gate.get("gate_passed")) or bool(args.allow_gate_fail):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
