from __future__ import annotations

from pathlib import Path


_HELPER_SCRIPTS_ROOT = Path(__file__).resolve().parents[3] / "Helper_Scripts"


def _read_script(relative_path: str) -> str:
    return (_HELPER_SCRIPTS_ROOT / relative_path).read_text(encoding="utf-8")


def test_build_rag_bench_corpus_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_script("Evals/build_rag_bench_corpus.py")


def test_email_search_bench_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_script("benchmarks/email_search_bench.py")


def test_email_search_dual_read_parity_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_script("checks/email_search_dual_read_parity.py")


def test_email_legacy_backfill_runner_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in _read_script("checks/email_legacy_backfill_runner.py")
