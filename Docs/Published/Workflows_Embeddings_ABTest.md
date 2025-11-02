# Workflow: Vector Search - Embeddings Model Comparison (A/B Test)

Goal: compare multiple embedding models/providers against the same imported corpus and the same inline QA pairs, using vector-only retrieval metrics to select the best embedding model for your data.

Prerequisites
- Corpus: imported + embedded (per-user collections) or allow the test to build collections
- QA pairs (inline only; not stored as a dataset)
- Auth: `X-API-KEY` or JWT

## Create an Embeddings A/B Test
Define arms (provider/model combos), target media IDs (optional to scope), and queries.

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/evaluations/embeddings/abtest \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d '{
        "name": "vec_abtest_1",
        "config": {
          "arms": [
            {"provider": "huggingface", "model": "sentence-transformers/all-MiniLM-L6-v2"},
            {"provider": "huggingface", "model": "Qwen/Qwen3-Embedding-4B-GGUF"}
          ],
          "media_ids": [101,102,103],
          "retrieval": {"top_k": 10},
          "queries": [
            {"input": {"question": "What is a residual connection?"}, "expected": {"answer": "gradient flow"}},
            {"input": {"question": "Which datasets were evaluated?"}, "expected": {"answer": "ImageNet"}}
          ]
        },
        "run_immediately": false
      }'
```

## Start the Test
```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/evaluations/embeddings/abtest/<TEST_ID>/run \
  -H "X-API-KEY: $API_KEY"
```

## Track Progress (SSE)
```bash
curl -N http://127.0.0.1:8000/api/v1/evaluations/embeddings/abtest/<TEST_ID>/events -H "X-API-KEY: $API_KEY"
```

## Fetch Results
```bash
curl -sS http://127.0.0.1:8000/api/v1/evaluations/embeddings/abtest/<TEST_ID>/results -H "X-API-KEY: $API_KEY" | jq
```
Returns summary metrics per arm (e.g., nDCG, MRR, latency p50/p95) and detailed per-query scores.

## Significance Check
```bash
curl -sS "http://127.0.0.1:8000/api/v1/evaluations/embeddings/abtest/<TEST_ID>/significance?metric=ndcg" \
  -H "X-API-KEY: $API_KEY" | jq
```

## Notes
- This evaluation uses vector-only retrieval quality to compare embedding models. Use the RAG pipeline optimization for end-to-end (retrieval+rerank+generation) tuning.
- Scope by `media_ids` or, if omitted, test across your default per-user collection.
- Export results to CSV/JSON for further analysis using the export endpoint.

## Workflows: Ad-hoc + Schedule (Inline QA + Keyword Collections)

Use the sample workflow at `Samples/Workflows/embeddings_abtest_inline.workflow.json`. It:
- Searches media by your `keyword_filter` collection and plucks `media_ids`
- Creates an Embeddings A/B test with inline QA pairs (`inputs.qa_samples`) and your arms list (`inputs.arms`)
- Starts the test

Run ad-hoc once:

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/workflows/run?mode=async" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{
        "definition": '"$(cat Samples/Workflows/embeddings_abtest_inline.workflow.json)"',
        "inputs": {
          "keyword_filter": ["collection:my-corpus"],
          "qa_samples": [
            {"input": {"question": "What is a residual connection?"}, "expected": {"answer": "It helps gradients flow and stabilizes deep networks."}}
          ],
          "arms": [
            {"provider": "huggingface", "model": "sentence-transformers/all-MiniLM-L6-v2"},
            {"provider": "huggingface", "model": "BAAI/bge-small-en-v1.5"}
          ]
        },
        "secrets": {"api_key": "'$API_KEY'"}
      }'
```

Schedule nightly at 03:00 UTC (save the workflow first if you want a recurring schedule):

```bash
WF_ID=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/workflows \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d @Samples/Workflows/embeddings_abtest_inline.workflow.json | jq -r .id)

curl -sS -X POST http://127.0.0.1:8000/api/v1/scheduler/workflows \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d '{
        "workflow_id": '"$WF_ID"',
        "name": "embeddings abtest nightly",
        "cron": "0 3 * * *",
        "timezone": "UTC",
        "inputs": {"keyword_filter": ["collection:my-corpus"]},
        "run_mode": "async",
        "enabled": true
      }'
```

### Auth Tips (Ad-hoc and Scheduled)

- Ad-hoc (multi-user): pass a short-lived JWT via `secrets.jwt` in the run request. Steps use:
  - `Authorization: {{ secrets.jwt and ('Bearer ' ~ secrets.jwt) or '' }}`
  - `X-API-KEY: {{ secrets.api_key or inputs.api_key or '' }}` (for single-user)

- Scheduled runs: set environment fallbacks on the server:
  - `WORKFLOWS_DEFAULT_BEARER_TOKEN` for multi-user
  - `WORKFLOWS_DEFAULT_API_KEY` for single-user
  - Optional sanity validation before first outbound call (per run):
    - `WORKFLOWS_VALIDATE_DEFAULT_AUTH=true`
    - Optional base override: `WORKFLOWS_INTERNAL_BASE_URL=http://127.0.0.1:8000`
    - The engine uses `GET /api/v1/workflows/auth/check` to verify the token once.

- Virtual keys for schedules: mint a short-lived JWT (scope=workflows) and set it as `WORKFLOWS_DEFAULT_BEARER_TOKEN`.
  - `POST /api/v1/workflows/auth/virtual-key` (admin; multi-user)
    - body: `{ "ttl_minutes": 60, "scope": "workflows", "schedule_id": "..." }`
    - returns `{ token, expires_at, scope, schedule_id }`
  - For stricter isolation, consider enforcing `scope == 'workflows'` and matching `schedule_id` in downstream endpoints.

### JSON Configs as Media (Keyword Collections)

You can ingest `.json` files via `/api/v1/media/add` using `media_type="json"`. They are stored like plaintext documents but kept as a separate `json` media type, making it easy to:
- Keep evaluation settings/QA sets/configs alongside your corpus
- Tag them with keywords (e.g., `collection:my-corpus`, `eval:rag-grid`) and later scope retrieval/evaluations with `keyword_filter`

Example:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/media/add \
  -H "X-API-KEY: $API_KEY" \
  -F "media_type=json" \
  -F "files=@./configs/rag_grid_settings.json" \
  -F "keywords=collection:my-corpus,eval:rag-grid"
```

During evaluations, set `retriever.keyword_filter` (RAG) or choose `media_ids` based on search to restrict to those tagged JSON configs (and other media) in your collection.
