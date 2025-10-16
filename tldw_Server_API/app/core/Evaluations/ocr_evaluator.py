from __future__ import annotations

from dataclasses import dataclass
import asyncio as _asyncio
from typing import Dict, Any, List, Optional, Tuple, Union

from loguru import logger


def _levenshtein(seq_a: List[str], seq_b: List[str]) -> int:
    """Compute Levenshtein edit distance between two token sequences."""
    n, m = len(seq_a), len(seq_b)
    if n == 0:
        return m
    if m == 0:
        return n
    # initialize matrix
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    # compute distances
    for i in range(1, n + 1):
        ai = seq_a[i - 1]
        for j in range(1, m + 1):
            bj = seq_b[j - 1]
            cost = 0 if ai == bj else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # deletion
                dp[i][j - 1] + 1,      # insertion
                dp[i - 1][j - 1] + cost  # substitution
            )
    return dp[n][m]


def char_error_rate(hyp: str, ref: str) -> float:
    """Character Error Rate (CER) using Levenshtein distance over characters."""
    hyp_chars = list(hyp or "")
    ref_chars = list(ref or "")
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    dist = _levenshtein(hyp_chars, ref_chars)
    return dist / max(1, len(ref_chars))


def word_error_rate(hyp: str, ref: str) -> float:
    """Word Error Rate (WER) using Levenshtein distance over whitespace tokens."""
    hyp_toks = (hyp or "").split()
    ref_toks = (ref or "").split()
    if not ref_toks:
        return 0.0 if not hyp_toks else 1.0
    dist = _levenshtein(hyp_toks, ref_toks)
    return dist / max(1, len(ref_toks))


@dataclass
class OCREvalItem:
    id: str
    # Source can be a PDF path or bytes, or pre-extracted text for offline testing
    pdf_path: Optional[str] = None
    pdf_bytes: Optional[bytes] = None
    extracted_text: Optional[str] = None
    ground_truth_text: Optional[str] = None


class OCREvaluator:
    """
    Evaluate OCR effectiveness by comparing extracted text to ground-truth.

    Supports:
      - CER (character error rate)
      - WER (word error rate)
      - Coverage (|hyp| / |ref|)
      - Page coverage (when available from PDF processing)
    """

    def __init__(self) -> None:
        # Ensure a default event loop exists for environments where tests call
        # asyncio.get_event_loop().run_until_complete without prior loop setup (e.g., Python 3.13)
        # Prefer get_running_loop (Py3.7+) to avoid deprecation warnings
        try:
            _asyncio.get_running_loop()
        except RuntimeError:
            loop = _asyncio.new_event_loop()
            _asyncio.set_event_loop(loop)

    async def evaluate(
        self,
        items: List[Dict[str, Any]],
        metrics: Optional[List[str]] = None,
        ocr_options: Optional[Dict[str, Any]] = None,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate OCR performance for a batch of items.

        Each item may include:
          - id: str
          - pdf_path: str | pdf_bytes: bytes | extracted_text: str
          - ground_truth_text: str (required for CER/WER/coverage)

        ocr_options forwarded to PDF processing when pdf_path/bytes provided:
          enable_ocr (bool), ocr_backend, ocr_lang, ocr_dpi, ocr_mode, ocr_min_page_text_chars
        """
        want = set([m.lower() for m in (metrics or ["cer", "wer", "coverage", "page_coverage"])])

        results: List[Dict[str, Any]] = []
        macro = {
            "cer": [],
            "wer": [],
            "coverage": [],
            "page_coverage": [],
        }

        # Lazy import to avoid heavy imports when unused
        from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import process_pdf
        import io
        import pymupdf
        from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.registry import get_backend as get_ocr_backend

        for raw in items:
            item = OCREvalItem(
                id=str(raw.get("id", raw.get("name", len(results)))),
                pdf_path=raw.get("pdf_path"),
                pdf_bytes=raw.get("pdf_bytes"),
                extracted_text=raw.get("extracted_text"),
                ground_truth_text=raw.get("ground_truth_text"),
            )

            per: Dict[str, Any] = {"id": item.id}
            ocr_info: Dict[str, Any] = {}

            # Determine hypothesis text
            hyp_text: str = item.extracted_text or ""
            page_texts: List[str] = []
            if not hyp_text:
                if item.pdf_path or item.pdf_bytes:
                    try:
                        # Prefer direct per-page OCR for detailed metrics
                        lang = (ocr_options or {}).get("ocr_lang", "eng")
                        dpi = int((ocr_options or {}).get("ocr_dpi", 300))
                        backend = get_ocr_backend((ocr_options or {}).get("ocr_backend"))
                        if backend is None:
                            logger.warning("No OCR backend available; falling back to PDF processor content")
                            # Fallback: use process_pdf
                            out = process_pdf(
                                file_input=item.pdf_bytes if item.pdf_bytes is not None else item.pdf_path,
                                filename=item.id + (".pdf" if not str(item.id).endswith(".pdf") else ""),
                                parser="pymupdf4llm",
                                enable_ocr=True,
                                ocr_backend=(ocr_options or {}).get("ocr_backend"),
                                ocr_lang=lang,
                                ocr_dpi=dpi,
                                ocr_mode=(ocr_options or {}).get("ocr_mode", "fallback"),
                                ocr_min_page_text_chars=int((ocr_options or {}).get("ocr_min_page_text_chars", 40)),
                                perform_chunking=False,
                                perform_analysis=False,
                                keywords=[],
                            )
                            hyp_text = (out or {}).get("content") or ""
                            ocr_details = (out or {}).get("analysis_details", {}).get("ocr") or {}
                            if ocr_details:
                                ocr_info.update(ocr_details)
                        else:
                            scale = max(dpi, 72) / 72.0
                            # Open PDF
                            doc = None
                            if item.pdf_bytes is not None:
                                doc = pymupdf.open(stream=item.pdf_bytes, filetype="pdf")
                            else:
                                doc = pymupdf.open(item.pdf_path)
                            with doc:
                                total_pages = len(doc)
                                ocr_pages = 0
                                # Small concurrency
                                from concurrent.futures import ThreadPoolExecutor, as_completed
                                import os as _os
                                try:
                                    concurrency_env = int((_os.getenv("OCR_PAGE_CONCURRENCY") or "1"))
                                except Exception:
                                    concurrency_env = 1
                                futures = []
                                idx_map = {}
                                with ThreadPoolExecutor(max_workers=max(1, concurrency_env)) as pool:
                                    for i, page in enumerate(doc, start=1):
                                        mat = pymupdf.Matrix(scale, scale)
                                        pix = page.get_pixmap(matrix=mat, alpha=False)
                                        img_bytes = pix.tobytes("png")
                                        fut = pool.submit(backend.ocr_image, img_bytes, lang)
                                        futures.append(fut)
                                        idx_map[fut] = i
                                    ordered = [""] * total_pages
                                    for fut in as_completed(futures):
                                        text = fut.result() or ""
                                        i = idx_map[fut]
                                        if text.strip():
                                            ocr_pages += 1
                                        ordered[i - 1] = text
                                page_texts.extend(ordered)
                                hyp_text = "\n".join(page_texts)
                                details = {
                                    "backend": getattr(backend, "name", type(backend).__name__),
                                    "dpi": dpi,
                                    "lang": lang,
                                    "total_pages": total_pages,
                                    "ocr_pages": ocr_pages,
                                    "page_concurrency": max(1, concurrency_env),
                                }
                                try:
                                    if hasattr(backend, "describe") and callable(getattr(backend, "describe")):
                                        extra = backend.describe() or {}
                                        if isinstance(extra, dict):
                                            details.update(extra)
                                except Exception:
                                    pass
                                ocr_info.update(details)
                    except Exception as e:
                        logger.error(f"OCR eval PDF per-page processing failed for {item.id}: {e}")
                        hyp_text = ""

            ref_text = item.ground_truth_text or ""

            # Normalize whitespace for fair comparison
            norm_hyp = " ".join(hyp_text.split())
            norm_ref = " ".join(ref_text.split())

            if "cer" in want:
                cer_v = char_error_rate(norm_hyp, norm_ref)
                per["cer"] = cer_v
                macro["cer"].append(cer_v)

            if "wer" in want:
                wer_v = word_error_rate(norm_hyp, norm_ref)
                per["wer"] = wer_v
                macro["wer"].append(wer_v)

            if "coverage" in want:
                cov = (len(norm_hyp) / max(1, len(norm_ref))) if norm_ref else (1.0 if norm_hyp == "" else 0.0)
                per["coverage"] = min(1.0, cov)
                macro["coverage"].append(per["coverage"])

            if "page_coverage" in want:
                # Use analysis_details if available
                if ocr_info and "total_pages" in ocr_info:
                    tp = max(1, int(ocr_info.get("total_pages") or 1))
                    op = int(ocr_info.get("ocr_pages") or 0)
                    pc = max(0.0, min(1.0, op / tp))
                    per["page_coverage"] = pc
                    macro["page_coverage"].append(pc)
                else:
                    per["page_coverage"] = None

            # Per-page metrics if we have page_texts and ground_truth_pages
            gt_pages = raw.get("ground_truth_pages")
            if isinstance(gt_pages, list) and page_texts:
                per_page_metrics = []
                for idx, ptext in enumerate(page_texts[:len(gt_pages)]):
                    hyp_p = " ".join((ptext or "").split())
                    ref_p = " ".join((gt_pages[idx] or "").split())
                    cer_p = char_error_rate(hyp_p, ref_p)
                    wer_p = word_error_rate(hyp_p, ref_p)
                    cov_p = (len(hyp_p) / max(1, len(ref_p))) if ref_p else (1.0 if hyp_p == "" else 0.0)
                    page_entry = {
                        "page": idx + 1,
                        "cer": cer_p,
                        "wer": wer_p,
                        "coverage": cov_p,
                        "hyp_len": len(hyp_p),
                        "gt_len": len(ref_p),
                    }
                    # Page-level thresholds
                    if thresholds:
                        pf = []
                        if "max_cer" in thresholds and cer_p is not None and cer_p > float(thresholds["max_cer"]):
                            pf.append(f"cer>{thresholds['max_cer']}")
                        if "max_wer" in thresholds and wer_p is not None and wer_p > float(thresholds["max_wer"]):
                            pf.append(f"wer>{thresholds['max_wer']}")
                        if "min_coverage" in thresholds and cov_p is not None and cov_p < float(thresholds["min_coverage"]):
                            pf.append(f"coverage<{thresholds['min_coverage']}")
                        page_entry["passed"] = len(pf) == 0
                        if pf:
                            page_entry["failed_reasons"] = pf
                    per_page_metrics.append(page_entry)
                per["per_page_metrics"] = per_page_metrics
                # Aggregate page-level pass rate
                if thresholds:
                    total_pages_scored = len(per_page_metrics)
                    if total_pages_scored:
                        per["per_page_pass_rate"] = sum(1 for m in per_page_metrics if m.get("passed") is True) / total_pages_scored

            if ocr_info:
                per["ocr_details"] = ocr_info

            # Threshold-based pass/fail
            passed = None
            failed_reasons: List[str] = []
            if thresholds:
                if "max_cer" in thresholds and "cer" in per and per["cer"] is not None:
                    if per["cer"] > float(thresholds["max_cer"]):
                        failed_reasons.append(f"cer>{thresholds['max_cer']}")
                if "max_wer" in thresholds and "wer" in per and per["wer"] is not None:
                    if per["wer"] > float(thresholds["max_wer"]):
                        failed_reasons.append(f"wer>{thresholds['max_wer']}")
                if "min_coverage" in thresholds and "coverage" in per and per["coverage"] is not None:
                    if per["coverage"] < float(thresholds["min_coverage"]):
                        failed_reasons.append(f"coverage<{thresholds['min_coverage']}")
                if "min_page_coverage" in thresholds and "page_coverage" in per and per["page_coverage"] is not None:
                    if per["page_coverage"] < float(thresholds["min_page_coverage"]):
                        failed_reasons.append(f"page_coverage<{thresholds['min_page_coverage']}")
                passed = len(failed_reasons) == 0
                per["passed"] = passed
                if failed_reasons:
                    per["failed_reasons"] = failed_reasons

            results.append(per)

        # Summaries
        def _avg(xs: List[float]) -> Optional[float]:
            return round(sum(xs) / len(xs), 6) if xs else None

        total = len(results)
        passed_count = sum(1 for r in results if r.get("passed") is True)
        summary = {
            "avg_cer": _avg(macro["cer"]),
            "avg_wer": _avg(macro["wer"]),
            "avg_coverage": _avg(macro["coverage"]),
            "avg_page_coverage": _avg(macro["page_coverage"]),
            "count": total,
            "pass_rate": (passed_count / total) if total else None,
        }
        # Optional aggregate page pass rate if available
        page_pass_vals = [r.get("per_page_pass_rate") for r in results if r.get("per_page_pass_rate") is not None]
        if page_pass_vals:
            summary["avg_per_page_pass_rate"] = round(sum(page_pass_vals) / len(page_pass_vals), 6)

        return {"summary": summary, "results": results}
