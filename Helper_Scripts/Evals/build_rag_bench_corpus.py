#!/usr/bin/env python3
"""Build the basic RAG benchmark corpus and regenerate retrieval dataset JSONL."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase

@dataclass(frozen=True)
class ManifestEntry:
    source: Path
    dest: Path
    query: str


def _resolve_path(repo_root: Path, raw_path: str) -> Path:
    """Resolve a path relative to the repo root unless it's absolute."""
    path = Path(raw_path)
    return path if path.is_absolute() else repo_root / path


def _normalize_title(value: str) -> str:
    """Normalize titles for case-insensitive matching."""
    return value.strip().lower()


def load_manifest(manifest_path: Path, repo_root: Path) -> List[ManifestEntry]:
    """Load manifest entries from a JSONL file."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    entries: List[ManifestEntry] = []
    seen_dest: set[Path] = set()
    for line_no, line in enumerate(manifest_path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {line_no}: {exc}") from exc

        for key in ("source", "dest", "query"):
            if key not in payload:
                raise ValueError(f"Manifest line {line_no} missing '{key}'")

        source = _resolve_path(repo_root, payload["source"])
        dest = Path(payload["dest"])
        query = payload["query"]
        if dest in seen_dest:
            raise ValueError(f"Duplicate dest in manifest: {dest}")
        seen_dest.add(dest)
        entries.append(ManifestEntry(source=source, dest=dest, query=query))

    if not entries:
        raise ValueError(f"No entries found in manifest: {manifest_path}")
    return entries


def build_corpus(entries: Iterable[ManifestEntry], corpus_root: Path, overwrite: bool) -> Dict[str, int]:
    """Copy sources into the corpus folder with normalized filenames."""
    copied = 0
    skipped = 0
    for entry in entries:
        if not entry.source.exists():
            raise FileNotFoundError(f"Source not found: {entry.source}")
        dest_path = corpus_root / entry.dest
        resolved_root = corpus_root.resolve(strict=False)
        resolved_dest = dest_path.resolve(strict=False)
        try:
            resolved_dest.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError(f"Invalid dest path outside corpus root: {entry.dest}") from exc
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_path.exists() and not overwrite:
            skipped += 1
            continue
        shutil.copy2(entry.source, dest_path)
        copied += 1
    return {"copied": copied, "skipped": skipped}


def _load_media_title_map(db_path: Path) -> Dict[str, List[str]]:
    """Return a normalized title -> list of media ids mapping."""
    if not db_path.exists():
        raise FileNotFoundError(f"Media DB not found: {db_path}")

    title_map: Dict[str, List[str]] = {}
    db = MediaDatabase(db_path=str(db_path), client_id="rag_bench_corpus")
    with db.transaction():
        rows = db.execute_query("SELECT id, title FROM Media WHERE deleted = 0").fetchall()
    for row in rows:
        media_id = row.get("id")
        title = row.get("title")
        if not title:
            continue
        key = _normalize_title(str(title))
        title_map.setdefault(key, []).append(str(media_id))
    return title_map


def _resolve_media_id(entry: ManifestEntry, title_map: Dict[str, List[str]]) -> str:
    """Resolve a manifest entry to a single media id."""
    candidates: List[str] = []
    for token in (entry.dest.name, entry.dest.stem):
        ids = title_map.get(_normalize_title(token), [])
        candidates.extend(ids)

    unique_ids = sorted(set(candidates))
    if len(unique_ids) == 1:
        return unique_ids[0]
    if not unique_ids:
        raise ValueError(f"No Media title match for dest '{entry.dest}'")
    raise ValueError(f"Multiple Media title matches for dest '{entry.dest}': {unique_ids}")


def write_retrieval_dataset(
    entries: Iterable[ManifestEntry],
    db_path: Path,
    output_path: Path,
    namespace: Optional[str],
) -> int:
    """Write rag_retrieval_v1.jsonl from manifest entries and Media DB ids."""
    title_map = _load_media_title_map(db_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            media_id = _resolve_media_id(entry, title_map)
            record = {
                "query": entry.query,
                "relevant_doc_ids": [media_id],
                "namespace": namespace,
            }
            handle.write(json.dumps(record, ensure_ascii=True))
            handle.write("\n")
            count += 1
    return count


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the basic RAG benchmark corpus and regenerate retrieval JSONL."
    )
    parser.add_argument(
        "--manifest",
        default="Docs/RAG/Benchmarks/basic_rag_bench_v1_manifest.jsonl",
        help="Path to the JSONL manifest.",
    )
    parser.add_argument(
        "--corpus-dir",
        default="Docs/RAG/Benchmarks/corpus/basic_rag_bench_v1",
        help="Destination directory for the normalized corpus.",
    )
    parser.add_argument(
        "--output",
        default="Docs/RAG/Benchmarks/rag_retrieval_v1.jsonl",
        help="Output path for the retrieval dataset JSONL.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Override repo root (defaults to the parent of Helper_Scripts).",
    )
    parser.add_argument(
        "--media-db",
        default=None,
        help="Path to Media_DB_v2.db for dataset regeneration.",
    )
    parser.add_argument(
        "--user-id",
        default=None,
        help="User id used to derive Media_DB_v2.db when --media-db is omitted.",
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="Namespace to include in the retrieval dataset (default: null).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite corpus files if they already exist.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip corpus build and only regenerate the dataset.",
    )
    parser.add_argument(
        "--skip-dataset",
        action="store_true",
        help="Skip dataset regeneration and only build the corpus.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    repo_root = Path(args.repo_root) if args.repo_root else Path(__file__).resolve().parents[2]

    manifest_path = _resolve_path(repo_root, args.manifest)
    corpus_root = _resolve_path(repo_root, args.corpus_dir)
    output_path = _resolve_path(repo_root, args.output)

    entries = load_manifest(manifest_path, repo_root)

    if not args.skip_build:
        results = build_corpus(entries, corpus_root, overwrite=args.overwrite)
        print(f"Corpus build: {results['copied']} copied, {results['skipped']} skipped -> {corpus_root}")

    if not args.skip_dataset:
        if args.media_db:
            db_path = _resolve_path(repo_root, args.media_db)
        elif args.user_id:
            db_path = repo_root / "Databases" / "user_databases" / str(args.user_id) / "Media_DB_v2.db"
        else:
            raise ValueError("Provide --media-db or --user-id for dataset regeneration.")

        count = write_retrieval_dataset(entries, db_path, output_path, args.namespace)
        print(f"Retrieval dataset: {count} rows -> {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
