#!/usr/bin/env python3
"""
ingest_rag_eval_workflow.py

End-to-end workflow to:
  1) Ingest a corpus directory of files
  2) Generate embeddings per media item
  3) Create a dataset from a baseline QA set
  4) Create and run a rag_pipeline evaluation (grid/random search)
  5) Print the best configuration and optional preset save

Usage (single-user mode):
  python Helper_Scripts/Evals/ingest_rag_eval_workflow.py \
    --base http://127.0.0.1:8000 \
    --api-key $SINGLE_USER_API_KEY \
    --corpus-dir ./my_docs \
    --qa ./qa_baseline.json \
    --save-preset best_rag_preset

QA file schema (JSON array):
  [ {"question": "...", "answer": "..."}, ... ]

Notes:
  - Requires the server running locally
  - Works with JWT by passing --jwt instead of --api-key
  - Designed to be resilient; prints partial results on failure
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


DEFAULT_GRID = {
    "chunking": {"include_siblings": [False, True]},
    "retrievers": [
        {"search_mode": ["hybrid"], "hybrid_alpha": [0.5, 0.7], "top_k": [8, 12]}
    ],
    "rerankers": [
        {"strategy": ["flashrank", "cross_encoder"], "top_k": [10]}
    ],
    "rag": {"model": ["gpt-4o-mini"], "max_tokens": [300]},
}


MEDIA_TYPE_BY_EXT = {
    ".pdf": "pdf",
    ".epub": "ebook",
    ".eml": "email",
    ".mp3": "audio",
    ".wav": "audio",
    ".m4a": "audio",
    ".ogg": "audio",
    ".mp4": "video",
    ".mkv": "video",
    ".mov": "video",
}


@dataclass
class ApiClient:
    base: str
    headers: Dict[str, str]
    timeout: int = 60

    def url(self, path: str) -> str:
        return f"{self.base.rstrip('/')}{path}"

    def get(self, path: str, **kw) -> requests.Response:
        return requests.get(self.url(path), headers=self.headers, timeout=self.timeout, **kw)

    def post(self, path: str, **kw) -> requests.Response:
        return requests.post(self.url(path), headers=self.headers, timeout=self.timeout, **kw)

    def delete(self, path: str, **kw) -> requests.Response:
        return requests.delete(self.url(path), headers=self.headers, timeout=self.timeout, **kw)


def ensure_health(client: ApiClient) -> None:
    try:
        r = client.get("/api/v1/health")
        r.raise_for_status()
    except Exception as e:
        print(f"[WARN] Health check failed: {e}", file=sys.stderr)


def group_files_by_type(corpus_dir: Path) -> Dict[str, List[Path]]:
    files: Dict[str, List[Path]] = {}
    for p in corpus_dir.rglob("*"):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        mtype = MEDIA_TYPE_BY_EXT.get(ext, "document")
        files.setdefault(mtype, []).append(p)
    return files


def ingest_files(client: ApiClient, media_type: str, paths: List[Path]) -> List[int]:
    media_ids: List[int] = []
    if not paths:
        return media_ids

    # Send in batches to avoid giant multipart
    batch_size = 8
    for i in range(0, len(paths), batch_size):
        batch = paths[i : i + batch_size]
        files_param: List[Tuple[str, Tuple[str, Any, Optional[str]]]] = []
        for fp in batch:
            mime = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
            files_param.append(("files", (fp.name, open(fp, "rb"), mime)))
        data = {
            "media_type": media_type,
            "perform_chunking": "true",
            "hierarchical_chunking": "true",
        }
        try:
            r = requests.post(
                client.url("/api/v1/media/add"),
                headers={k: v for k, v in client.headers.items() if k.lower() != "content-type"},
                files=files_param,
                data=data,
                timeout=client.timeout,
            )
            for _, f in files_param:
                try:
                    f[1].close()
                except Exception:
                    pass
            r.raise_for_status()
            payload = r.json()
            # Try to extract db_ids from common shapes
            results = payload.get("results") if isinstance(payload, dict) else payload
            if isinstance(results, list):
                for item in results:
                    mid = item.get("db_id") if isinstance(item, dict) else None
                    if mid is not None:
                        try:
                            media_ids.append(int(mid))
                        except Exception:
                            pass
        except Exception as e:
            print(f"[WARN] Ingest batch failed ({media_type}): {e}", file=sys.stderr)
    return media_ids


def generate_embeddings_and_wait(client: ApiClient, media_id: int, provider: Optional[str], model: Optional[str], poll_sec: float = 2.0, max_wait_sec: int = 180) -> bool:
    try:
        body = {}
        if provider:
            body["embedding_provider"] = provider
        if model:
            body["embedding_model"] = model
        r = client.post(f"/api/v1/media/{media_id}/embeddings", json=body)
        r.raise_for_status()
    except Exception as e:
        print(f"[WARN] Embedding launch failed for media {media_id}: {e}", file=sys.stderr)
        return False

    # Poll status endpoint
    deadline = time.time() + max_wait_sec
    while time.time() < deadline:
        try:
            s = client.get(f"/api/v1/media/{media_id}/embeddings/status")
            if s.status_code == 404:
                # Media not found; abort
                return False
            s.raise_for_status()
            js = s.json()
            if bool(js.get("has_embeddings")):
                return True
        except Exception:
            pass
        time.sleep(poll_sec)
    return False


def load_qa_baseline(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("QA baseline must be a JSON array")
    samples: List[Dict[str, Any]] = []
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            continue
        q = row.get("question") or row.get("query") or row.get("prompt")
        a = row.get("answer") or row.get("gold") or row.get("expected")
        if not q:
            continue
        sample = {"input": {"question": str(q)}, "expected": {"answer": str(a) if a is not None else ""}}
        samples.append(sample)
    if not samples:
        raise ValueError("No valid samples parsed from QA baseline")
    return samples


def create_dataset(client: ApiClient, name: str, samples: List[Dict[str, Any]], description: Optional[str] = None) -> Optional[str]:
    try:
        body = {"name": name, "samples": samples}
        if description:
            body["description"] = description
        r = client.post("/api/v1/evaluations/datasets", json=body)
        r.raise_for_status()
        return r.json().get("id")
    except Exception as e:
        print(f"[ERROR] Failed to create dataset: {e}", file=sys.stderr)
        return None


def create_evaluation(client: ApiClient, name: str, dataset_id: str, grid: Dict[str, Any], strategy: str = "grid", max_trials: Optional[int] = None) -> Optional[str]:
    try:
        rp = {**grid}
        rp["dataset_id"] = dataset_id
        rp["search_strategy"] = strategy
        if max_trials:
            rp["max_trials"] = int(max_trials)
        body = {
            "name": name,
            "eval_type": "model_graded",
            "eval_spec": {
                "sub_type": "rag_pipeline",
                "rag_pipeline": rp,
            },
        }
        r = client.post("/api/v1/evaluations/", json=body)
        r.raise_for_status()
        return r.json().get("id")
    except Exception as e:
        print(f"[ERROR] Failed to create evaluation: {e}", file=sys.stderr)
        return None


def start_run(client: ApiClient, eval_id: str, target_model: str = "openai") -> Optional[str]:
    try:
        r = client.post(f"/api/v1/evaluations/{eval_id}/runs", json={"target_model": target_model})
        r.raise_for_status()
        return r.json().get("id")
    except Exception as e:
        print(f"[ERROR] Failed to start run: {e}", file=sys.stderr)
        return None


def wait_for_run(client: ApiClient, run_id: str, poll_sec: float = 3.0, max_wait_sec: int = 1800) -> Dict[str, Any]:
    deadline = time.time() + max_wait_sec
    last: Dict[str, Any] = {}
    while time.time() < deadline:
        try:
            r = client.get(f"/api/v1/evaluations/runs/{run_id}")
            r.raise_for_status()
            js = r.json()
            last = js
            status = (js.get("status") or "").lower()
            if status in {"completed", "failed", "cancelled"}:
                return js
        except Exception:
            pass
        time.sleep(poll_sec)
    return last


def print_leaderboard(results: Dict[str, Any]) -> None:
    lb = (results or {}).get("leaderboard") or []
    if not isinstance(lb, list) or not lb:
        print("No leaderboard in results.")
        return
    # Sort by overall desc if present; else by config_score
    def _score(row: Dict[str, Any]) -> float:
        try:
            if "overall" in row:
                return float(row["overall"])
            agg = row.get("aggregate") or {}
            return float(agg.get("config_score") or 0.0)
        except Exception:
            return 0.0

    top = sorted(lb, key=_score, reverse=True)[:5]
    print("\nTop configurations:")
    for i, row in enumerate(top, 1):
        cfg_id = row.get("config_id")
        overall = row.get("overall")
        latency = row.get("latency_ms")
        print(f" {i}. {cfg_id}: overall={overall}, latency_ms={latency}")

    best = (results or {}).get("best")
    if isinstance(best, dict):
        print("\nBest configuration summary:")
        print(json.dumps(best, indent=2))


def save_preset(client: ApiClient, name: str, best_config: Dict[str, Any]) -> bool:
    try:
        config = best_config.get("config") or {}
        body = {"name": name, "config": config}
        r = client.post("/api/v1/evaluations/rag/pipeline/presets", json=body)
        r.raise_for_status()
        print(f"Saved preset '{name}'.")
        return True
    except Exception as e:
        print(f"[WARN] Failed to save preset: {e}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest corpus, embed, and run RAG evaluations.")
    ap.add_argument("--base", default=os.getenv("TLDS_BASE_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--api-key", default=os.getenv("SINGLE_USER_API_KEY"))
    ap.add_argument("--jwt", default=None, help="Use JWT instead of API key")
    ap.add_argument("--corpus-dir", required=True)
    ap.add_argument("--qa", required=True, help="Path to baseline QA JSON array")
    ap.add_argument("--embedding-provider", default=None)
    ap.add_argument("--embedding-model", default=None)
    ap.add_argument("--search-strategy", choices=["grid", "random"], default="grid")
    ap.add_argument("--max-trials", type=int, default=None)
    ap.add_argument("--save-preset", default=None, help="Optional preset name to save the best config")
    ap.add_argument("--rag-model", default=None, help="Override generation model used in rag_pipeline grid")
    args = ap.parse_args()

    if not args.api_key and not args.jwt:
        print("Provide --api-key or --jwt", file=sys.stderr)
        return 2

    headers = {"Content-Type": "application/json"}
    if args.jwt:
        headers["Authorization"] = f"Bearer {args.jwt}"
    else:
        headers["X-API-KEY"] = args.api_key

    client = ApiClient(base=args.base, headers=headers)
    ensure_health(client)

    corpus = Path(args.corpus_dir)
    if not corpus.exists():
        print(f"Corpus dir not found: {corpus}", file=sys.stderr)
        return 2

    media_ids: List[int] = []
    grouped = group_files_by_type(corpus)
    for mtype, files in grouped.items():
        if not files:
            continue
        print(f"Ingesting {len(files)} {mtype} file(s)...")
        mids = ingest_files(client, mtype, files)
        print(f" - Ingested -> {len(mids)} media IDs")
        media_ids.extend(mids)

    if not media_ids:
        print("No media ingested; exiting.", file=sys.stderr)
        return 1

    # Embeddings per media
    ok_count = 0
    for mid in media_ids:
        print(f"Generating embeddings for media {mid}...")
        ok = generate_embeddings_and_wait(
            client,
            media_id=mid,
            provider=args.embedding_provider,
            model=args.embedding_model,
        )
        print(f" - {'OK' if ok else 'FAILED'}")
        if ok:
            ok_count += 1
    if ok_count == 0:
        print("Embeddings generation failed for all items; continuing to evaluation but results may be poor.", file=sys.stderr)

    # Dataset from QA baseline
    ds_samples = load_qa_baseline(Path(args.qa))
    ds_name = f"qa_{int(time.time())}"
    print(f"Creating dataset '{ds_name}' with {len(ds_samples)} samples...")
    dataset_id = create_dataset(client, ds_name, ds_samples, description="Auto-imported QA baseline")
    if not dataset_id:
        return 1

    # Evaluation & run
    eval_name = f"rag_cfg_search_{int(time.time())}"
    grid = json.loads(json.dumps(DEFAULT_GRID))  # deep copy
    if args.rag_model:
        grid.setdefault("rag", {})["model"] = [args.rag_model]
    print(f"Creating evaluation '{eval_name}'...")
    eval_id = create_evaluation(client, eval_name, dataset_id, grid, strategy=args.search_strategy, max_trials=args.max_trials)
    if not eval_id:
        return 1
    print("Starting run...")
    run_id = start_run(client, eval_id)
    if not run_id:
        return 1
    run = wait_for_run(client, run_id)
    status = (run.get("status") or "").lower()
    print(f"Run {run_id} status: {status}")
    results = run.get("results") or {}
    if results:
        print_leaderboard(results)
        best = results.get("best") if isinstance(results, dict) else None
        if best and args.save_preset:
            save_preset(client, args.save_preset, best)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
