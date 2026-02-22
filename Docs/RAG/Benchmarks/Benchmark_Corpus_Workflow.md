# RAG Benchmark Corpus Workflow

This document describes a repeatable workflow for building a benchmark corpus,
ingesting it, and regenerating retrieval datasets for evaluation.

Quick start (variables reduce copy/paste):

```bash
export CORPUS=basic_rag_bench_v1
export MANIFEST=Docs/RAG/Benchmarks/${CORPUS}_manifest.jsonl
export CORPUS_DIR=Docs/RAG/Benchmarks/corpus/${CORPUS}
export RETRIEVAL_OUT=Docs/RAG/Benchmarks/${CORPUS}_retrieval.jsonl
```

## 1) Choose a Corpus Name

Pick a stable corpus name and reuse it everywhere:

- Example: `basic_rag_bench_v1`

Recommended file locations:

- Manifest: `Docs/RAG/Benchmarks/<corpus>_manifest.jsonl`
- Corpus files: `Docs/RAG/Benchmarks/corpus/<corpus>/`
- Retrieval dataset: `Docs/RAG/Benchmarks/<corpus>_retrieval.jsonl`

If you need a single canonical dataset file for PRDs, you can copy or
symlink the per-corpus retrieval JSONL to
`Docs/RAG/Benchmarks/rag_retrieval_v1.jsonl`.

## 2) Create the Manifest (JSONL)

Each line is a JSON object with `source`, `dest`, and `query`.
`dest` becomes the filename in the corpus folder and is used to map
the ingested Media title back to an ID during dataset generation.

Example:

```json
{"source":"README.md","dest":"tldw_readme.md","query":"What is tldw_server and its core features?"}
{"source":"Docs/Architecture.md","dest":"architecture_overview.md","query":"What is the high-level architecture of the server?"}
```

Guidelines:
- Make `dest` unique and stable.
- One query per doc is fine for a starter set.
- Keep queries focused on content present in the source file.
- Prefer ASCII filenames; avoid spaces and punctuation that might be normalized differently.

## 3) Build the Corpus Folder

Use the helper script to copy `source` files into the normalized corpus
folder (keeps stable filenames for ingestion):

```bash
python Helper_Scripts/Evals/build_rag_bench_corpus.py \
  --manifest "$MANIFEST" \
  --corpus-dir "$CORPUS_DIR" \
  --skip-dataset
```

This step is idempotent. Add `--overwrite` to refresh files.

## 4) Set Up a Dedicated Benchmark User

Single-user mode (recommended for repeatability):

```bash
export AUTH_MODE=single_user
export SINGLE_USER_FIXED_ID=9001
export SINGLE_USER_API_KEY=...
export OPENAI_API_KEY=...
python -m tldw_Server_API.app.core.AuthNZ.initialize
python -m uvicorn tldw_Server_API.app.main:app --reload
```

Multi-user mode:
- Create a dedicated benchmark user and use that API key.
- Note the user id for dataset regeneration.

## 5) Ingest the Corpus (Generate Embeddings)

Option A (recommended): use the helper script to ingest via the API.

```bash
python Helper_Scripts/Evals/build_rag_bench_corpus.py \
  --manifest "$MANIFEST" \
  --corpus-dir "$CORPUS_DIR" \
  --ingest \
  --base http://127.0.0.1:8000 \
  --api-key $SINGLE_USER_API_KEY \
  --generate-embeddings \
  --embedding-provider openai \
  --embedding-model text-embedding-3-large
```

Notes:
- `--perform-analysis` is off by default; add it if you want summaries/claims.
- Add `--keywords "collection:<corpus>"` to tag items for keyword-filtered retrieval.
- For JWT auth, replace `--api-key` with `--jwt`.
- `--generate-embeddings` is implied if you pass `--embedding-provider` or `--embedding-model`.

Option B: manual ingestion using `media/add` with embeddings enabled:

```bash
find Docs/RAG/Benchmarks/corpus/basic_rag_bench_v1 -type f -print0 | \
  xargs -0 -I {} curl -sS -X POST "http://127.0.0.1:8000/api/v1/media/add" \
    -H "X-API-KEY: $SINGLE_USER_API_KEY" \
    -F "media_type=document" \
    -F "generate_embeddings=true" \
    -F "embedding_provider=openai" \
    -F "embedding_model=text-embedding-3-large" \
    -F "files=@{}"
```

Optional scoping tag (for keyword filters):
- Add `-F "keywords=collection:<corpus>"` to each request.

## 6) Regenerate the Retrieval Dataset

Use the helper script to map `dest` titles to Media IDs:

```bash
python Helper_Scripts/Evals/build_rag_bench_corpus.py \
  --manifest "$MANIFEST" \
  --output "$RETRIEVAL_OUT" \
  --user-id 9001 \
  --namespace basic_rag_bench_v1 \
  --skip-build
```

Namespace guidance:
- Use `--namespace` only if you also create a matching vector collection
  (RAG uses `index_namespace` as the collection name).
- If you are using the default per-user collection, omit `--namespace`
  so the dataset writes `null` for `namespace`.

Troubleshooting:
- If dataset generation reports missing or duplicate title matches, ensure
  `dest` matches the ingested Media title. The default title is the file stem
  from the corpus folder. For URL ingestion, use stable titles or adjust the
  manifest to match what the Media DB stores.
- Multi-user mode: pass `--media-db /path/to/Media_DB_v2.db` instead of `--user-id`.

## 7) Evaluation Hooks (Optional)

Groundedness baseline:
- Use `Docs/Deployment/Monitoring/Evals/nightly_rag_eval.jsonl`.

Retrieval baseline:
- Use your generated retrieval dataset JSONL.

References:
- `Docs/Published/User_Guides/Server/Media_to_RAG_Evals_Workflow.md`
- `Docs/RAG/RAG_Benchmarks.md`

## 8) Repeat for a New Corpus

1. Copy the manifest and update `source`, `dest`, and `query`.
2. Re-run the corpus build step.
3. Ingest with a dedicated user (or new user id).
4. Regenerate the retrieval dataset JSONL.
5. Re-run baseline evaluations.

## 9) Script Usage Patterns

Build only:

```bash
python Helper_Scripts/Evals/build_rag_bench_corpus.py --manifest "$MANIFEST" --corpus-dir "$CORPUS_DIR" --skip-dataset
```

Ingest only (corpus already built):

```bash
python Helper_Scripts/Evals/build_rag_bench_corpus.py --corpus-dir "$CORPUS_DIR" --ingest --api-key "$SINGLE_USER_API_KEY"
```

Dataset only:

```bash
python Helper_Scripts/Evals/build_rag_bench_corpus.py --manifest "$MANIFEST" --output "$RETRIEVAL_OUT" --user-id 9001 --skip-build
```

Build + ingest + dataset:

```bash
python Helper_Scripts/Evals/build_rag_bench_corpus.py \
  --manifest "$MANIFEST" \
  --corpus-dir "$CORPUS_DIR" \
  --ingest \
  --api-key "$SINGLE_USER_API_KEY" \
  --generate-embeddings \
  --embedding-provider openai \
  --embedding-model text-embedding-3-large \
  --output "$RETRIEVAL_OUT" \
  --user-id 9001
```
