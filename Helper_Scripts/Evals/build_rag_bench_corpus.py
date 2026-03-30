#!/usr/bin/env python3
"""Build the basic RAG benchmark corpus and regenerate retrieval dataset JSONL."""

from __future__ import annotations

import argparse
import json
import mimetypes
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import httpx
from loguru import logger

from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.media_db.api import create_media_database


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


MEDIA_TYPE_BY_EXT = {
    ".pdf": "pdf",
    ".epub": "ebook",
    ".eml": "email",
    ".mbox": "email",
    ".pst": "email",
    ".ost": "email",
    ".mp3": "audio",
    ".wav": "audio",
    ".m4a": "audio",
    ".ogg": "audio",
    ".mp4": "video",
    ".mkv": "video",
    ".mov": "video",
}


def _media_type_for_path(path: Path) -> str:
    return MEDIA_TYPE_BY_EXT.get(path.suffix.lower(), "document")


def group_files_by_type(corpus_dir: Path) -> Dict[str, List[Path]]:
    files: Dict[str, List[Path]] = {}
    for p in corpus_dir.rglob("*"):
        if not p.is_file():
            continue
        media_type = _media_type_for_path(p)
        files.setdefault(media_type, []).append(p)
    return files


def ingest_files(
    client: httpx.Client,
    base_url: str,
    headers: Dict[str, str],
    media_type: str,
    paths: List[Path],
    form_fields: Dict[str, str],
    batch_size: int,
) -> Tuple[int, int]:
    if batch_size <= 0:
        raise ValueError("ingest_files batch_size must be > 0")
    ingested = 0
    failures = 0
    if not paths:
        return ingested, failures

    for i in range(0, len(paths), batch_size):
        batch = paths[i : i + batch_size]
        files: List[Tuple[str, Tuple[str, object, str]]] = []
        data = {"media_type": media_type, **form_fields}
        try:
            for path in batch:
                mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
                files.append(("files", (path.name, path.open("rb"), mime)))
            response = client.post(
                f"{base_url.rstrip('/')}/api/v1/media/add",
                headers=headers,
                data=data,
                files=files,
            )
            response.raise_for_status()
            ingested += len(batch)
        except (httpx.HTTPError, OSError) as exc:
            failures += len(batch)
            logger.warning("Ingest batch failed ({}): {}", media_type, exc)
        finally:
            for _, file_tuple in files:
                try:
                    file_tuple[1].close()
                except OSError as exc:
                    logger.debug("Failed to close file: {}", exc)
    return ingested, failures


def ingest_corpus(
    corpus_root: Path,
    base_url: str,
    headers: Dict[str, str],
    generate_embeddings: bool,
    embedding_provider: Optional[str],
    embedding_model: Optional[str],
    keywords: Optional[str],
    perform_analysis: bool,
    batch_size: int,
    timeout: int,
) -> Dict[str, int]:
    if not corpus_root.exists():
        raise FileNotFoundError(f"Corpus directory not found: {corpus_root}")

    files_by_type = group_files_by_type(corpus_root)
    if not files_by_type:
        raise ValueError(f"No files found under corpus directory: {corpus_root}")

    form_fields: Dict[str, str] = {
        "perform_analysis": "true" if perform_analysis else "false",
        "generate_embeddings": "true" if generate_embeddings else "false",
    }
    if keywords:
        form_fields["keywords"] = keywords
    if embedding_provider:
        form_fields["embedding_provider"] = embedding_provider
    if embedding_model:
        form_fields["embedding_model"] = embedding_model

    results = {"ingested": 0, "failed": 0}
    with httpx.Client(timeout=timeout) as client:
        for media_type, paths in sorted(files_by_type.items()):
            ingested, failures = ingest_files(
                client=client,
                base_url=base_url,
                headers=headers,
                media_type=media_type,
                paths=paths,
                form_fields=form_fields,
                batch_size=batch_size,
            )
            results["ingested"] += ingested
            results["failed"] += failures
    return results


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
    db = create_media_database("rag_bench_corpus", db_path=str(db_path))
    try:
        with db.transaction():
            rows = db.execute_query("SELECT id, title FROM Media WHERE deleted = 0").fetchall()
        for row in rows:
            media_id = row.get("id")
            title = row.get("title")
            if not title:
                continue
            key = _normalize_title(str(title))
            title_map.setdefault(key, []).append(str(media_id))
    finally:
        db.close_connection()
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
        description="Build the basic RAG benchmark corpus, optionally ingest it, and regenerate retrieval JSONL."
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
        help="Path to the per-user media DB for dataset regeneration.",
    )
    parser.add_argument(
        "--user-id",
        default=None,
        help="User id used to derive the per-user media DB when --media-db is omitted.",
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="Namespace to include in the retrieval dataset (default: null).",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Ingest the corpus via /api/v1/media/add after building.",
    )
    parser.add_argument(
        "--base",
        default="http://127.0.0.1:8000",
        help="Base URL for the API when --ingest is enabled.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for single-user auth (X-API-KEY header).",
    )
    parser.add_argument(
        "--jwt",
        default=None,
        help="JWT for multi-user auth (Authorization: Bearer).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Batch size for ingestion uploads.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout in seconds for ingest requests.",
    )
    parser.add_argument(
        "--generate-embeddings",
        action="store_true",
        help="Enable embeddings generation during ingestion.",
    )
    parser.add_argument(
        "--embedding-provider",
        default=None,
        help="Embedding provider to use during ingestion.",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="Embedding model to use during ingestion.",
    )
    parser.add_argument(
        "--keywords",
        default=None,
        help="Comma-separated keywords to tag each ingested item.",
    )
    parser.add_argument(
        "--perform-analysis",
        action="store_true",
        help="Run analysis during ingestion (default: false).",
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

    if args.ingest:
        if args.api_key and args.jwt:
            raise ValueError("Provide only one of --api-key or --jwt.")
        if not args.api_key and not args.jwt:
            raise ValueError("Provide --api-key or --jwt when --ingest is enabled.")

        headers: Dict[str, str] = {}
        if args.api_key:
            headers["X-API-KEY"] = args.api_key
        if args.jwt:
            headers["Authorization"] = f"Bearer {args.jwt}"

        generate_embeddings = args.generate_embeddings or bool(args.embedding_provider or args.embedding_model)
        ingest_results = ingest_corpus(
            corpus_root=corpus_root,
            base_url=args.base,
            headers=headers,
            generate_embeddings=generate_embeddings,
            embedding_provider=args.embedding_provider,
            embedding_model=args.embedding_model,
            keywords=args.keywords,
            perform_analysis=args.perform_analysis,
            batch_size=args.batch_size,
            timeout=args.timeout,
        )
        print(
            "Corpus ingest: "
            f"{ingest_results['ingested']} ingested, {ingest_results['failed']} failed -> {args.base}"
        )

    if not args.skip_dataset:
        if args.media_db:
            db_path = _resolve_path(repo_root, args.media_db)
        elif args.user_id:
            db_path = (
                repo_root
                / "Databases"
                / "user_databases"
                / str(args.user_id)
                / DatabasePaths.MEDIA_DB_NAME
            )
        else:
            raise ValueError("Provide --media-db or --user-id for dataset regeneration.")

        count = write_retrieval_dataset(entries, db_path, output_path, args.namespace)
        print(f"Retrieval dataset: {count} rows -> {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
