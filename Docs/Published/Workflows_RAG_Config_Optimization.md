# Workflow: Optimize RAG Settings Against a Baseline QA Set

Goal: given a specified corpus and a baseline set of QA pairs, automatically search for the most effective Retrieval + Reranking + Answer settings, then capture a reproducible preset for day-to-day use.

Two ways to run this:
- API-only (pure Evaluations endpoints; simple and robust)
- Workflows Ad-hoc Run (wraps the same steps in a single workflow run you can schedule/monitor)

Prerequisites
- Server running on `http://127.0.0.1:8000`
- Auth: `X-API-KEY` (single-user) or `Authorization: Bearer <token>`
- Corpus: already ingested and embedded for the target user (see User Guides → Media→Embeddings→RAG→Evals Workflow)
- Baseline QA pairs: a JSON array like:
  ```json
  [
    {"question": "What is a residual connection?", "answer": "It helps gradients flow and stabilizes very deep nets."},
    {"question": "List datasets in the paper", "answer": "ImageNet, CIFAR-10/100, ..."}
  ]
  ```

## API-only: End-to-End via Evaluations
1) Create a dataset
```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/evaluations/datasets \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d '{
        "name": "qa_ds_1",
        "description": "Baseline QA set",
        "samples": [
          {"input": {"question": "What is a residual connection?"}, "expected": {"answer": "It helps gradients flow and stabilizes very deep nets."}},
          {"input": {"question": "List datasets in the paper"}, "expected": {"answer": "ImageNet, CIFAR-10/100"}}
        ]
      }'
```

2) Create an evaluation with rag_pipeline (grid search)
```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/evaluations/ \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d '{
        "name": "rag_cfg_search",
        "eval_type": "model_graded",
        "eval_spec": {
          "sub_type": "rag_pipeline",
          "rag_pipeline": {
            "dataset_id": "<DATASET_ID>",
            "search_strategy": "grid",
            "chunking": {"include_siblings": [false, true]},
            "retrievers": [
              {"search_mode": ["hybrid"], "hybrid_alpha": [0.5, 0.7], "top_k": [8, 12]}
            ],
            "rerankers": [
              {"strategy": ["flashrank", "cross_encoder"], "top_k": [10]}
            ],
            "rag": {"model": ["gpt-4o-mini"], "max_tokens": [300]},
            "advanced": {"fts_level": "chunk", "enable_citations": false, "timeout_seconds": 30}
            "aggregation_weights": {"rag_overall": 1.0, "retrieval_diversity": 0.1}
          }
        }
      }'
```

3) Start a run and poll results
```bash
# Start
curl -sS -X POST http://127.0.0.1:8000/api/v1/evaluations/<EVAL_ID>/runs \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d '{"target_model": "openai"}'

# Poll
curl -sS http://127.0.0.1:8000/api/v1/evaluations/runs/<RUN_ID> -H "X-API-KEY: $API_KEY" | jq
```
Results include `leaderboard` and `best`. Use `best.config` to reproduce or save as a preset.

4) Save the winning preset
```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/evaluations/rag/pipeline/presets \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d '{"name": "baseline_hybrid_xenc", "config": <PASTE best.config JSON>}'
```

Optional: Ephemeral collections and cleanup
- If you prefer isolating the evaluation corpus, set `index_namespace` in `rag_pipeline`, which builds ephemeral collections and cleans them with `POST /api/v1/evaluations/rag/pipeline/cleanup`.

### Embeddings settings (per-user collections)
- For ingestion-time embedding, use `generate_embeddings=true` and optionally `embedding_provider`/`embedding_model` in `/api/v1/media/add`.
- To embed existing media:
  - Batch: `POST /api/v1/media/embeddings/batch` with `media_ids`, `provider`, `model`, `chunk_size`, `chunk_overlap`.
  - Single: `POST /api/v1/media/{media_id}/embeddings` and poll `/{media_id}/embeddings/status`.
These write to per-user collections (e.g., `user_1_media_embeddings`) used by RAG retrieval.

### No-Dataset Path (Inline QA, nothing stored in datasets table)
If you don’t want to create a dataset record, embed your QA pairs inline in the evaluation itself using `rag_pipeline.dataset`. This keeps everything self-contained with no rows in the datasets table.

Create the evaluation with inline QA samples (and optional `advanced` block for full pipeline options):
```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/evaluations/ \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d '{
        "name": "rag_cfg_search_inline",
        "eval_type": "model_graded",
        "eval_spec": {
          "sub_type": "rag_pipeline",
          "rag_pipeline": {
            "dataset": [
              {"input": {"question": "What is a residual connection?"}, "expected": {"answer": "It helps gradients flow and stabilizes very deep nets."}},
              {"input": {"question": "List datasets in the paper"}, "expected": {"answer": "ImageNet, CIFAR-10/100"}}
            ],
            "search_strategy": "grid",
            "retrievers": [{"search_mode": ["hybrid"], "hybrid_alpha": [0.5, 0.7], "top_k": [8, 12]}],
            "rerankers": [{"strategy": ["flashrank", "cross_encoder"], "top_k": [10]}],
            "rag": {"model": ["gpt-4o-mini"], "max_tokens": [300]},
            "advanced": {"fts_level": "chunk", "include_sibling_chunks": true, "enable_enhanced_chunking": true, "timeout_seconds": 30}
          }
        }
      }'
```

Then start a run and poll results as usual (steps 3-4 above). The evaluation holds the QA inline; no dataset row is created.

Alternative: keep your evaluation static and supply QA only when starting a run (no eval changes). Provide `dataset_override` in the run body:
```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/evaluations/<EVAL_ID>/runs \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d '{
        "target_model": "openai",
        "dataset_override": {
          "samples": [
            {"input": {"question": "What is a residual connection?"}, "expected": {"answer": "It helps gradients flow and stabilizes very deep nets."}},
            {"input": {"question": "List datasets in the paper"}, "expected": {"answer": "ImageNet, CIFAR-10/100"}}
          ]
        }
      }'
```
This evaluates without creating a dataset record and without embedding QA in the evaluation definition.

## Workflows: Single-Run Automation (Ad-hoc)
Use a self-contained workflow that performs: create dataset → create evaluation → start run → (optional) save preset.

1) Prepare the ad-hoc definition (definition.json)
```json
{
  "name": "optimize-rag-config",
  "version": 1,
  "on_completion_webhook": null,
  "steps": [
    {"id": "log_start", "type": "log", "config": {"message": "Starting RAG config optimization"}},

    {"id": "create_dataset", "type": "webhook", "config": {
      "url": "http://127.0.0.1:8000/api/v1/evaluations/datasets",
      "method": "POST",
      "headers": {"Content-Type": "application/json", "X-API-KEY": "{{ inputs.api_key }}"},
      "body": {
        "name": "{{ inputs.dataset_name }}",
        "description": "Baseline QA",
        "samples": {{ inputs.qa_samples | tojson }}
      },
      "capture": "dataset"
    }},

    {"id": "create_eval", "type": "webhook", "config": {
      "url": "http://127.0.0.1:8000/api/v1/evaluations/",
      "method": "POST",
      "headers": {"Content-Type": "application/json", "X-API-KEY": "{{ inputs.api_key }}"},
      "body": {
        "name": "rag_cfg_search",
        "eval_type": "model_graded",
        "eval_spec": {
          "sub_type": "rag_pipeline",
          "rag_pipeline": {
            "dataset_id": "{{ steps.create_dataset.response.id }}",
            "search_strategy": "grid",
            "chunking": {"include_siblings": [false, true]},
            "retrievers": [{"search_mode": ["hybrid"], "hybrid_alpha": [0.5, 0.7], "top_k": [8, 12]}],
            "rerankers": [{"strategy": ["flashrank", "cross_encoder"], "top_k": [10]}],
            "rag": {"model": ["{{ inputs.rag_model }}"], "max_tokens": [300]}
          }
        }
      },
      "capture": "evaluation"
    }},

    {"id": "start_run", "type": "webhook", "config": {
      "url": "http://127.0.0.1:8000/api/v1/evaluations/{{ steps.create_eval.response.id }}/runs",
      "method": "POST",
      "headers": {"Content-Type": "application/json", "X-API-KEY": "{{ inputs.api_key }}"},
      "body": {"target_model": "openai"},
      "capture": "run"
    }},

    {"id": "delay", "type": "delay", "config": {"milliseconds": 5000}},

    {"id": "fetch_run", "type": "webhook", "config": {
      "url": "http://127.0.0.1:8000/api/v1/evaluations/runs/{{ steps.start_run.response.id }}",
      "method": "GET",
      "headers": {"X-API-KEY": "{{ inputs.api_key }}"},
      "capture": "run_state"
    }},

    {"id": "maybe_save_preset", "type": "webhook", "config": {
      "url": "http://127.0.0.1:8000/api/v1/evaluations/rag/pipeline/presets",
      "method": "POST",
      "headers": {"Content-Type": "application/json", "X-API-KEY": "{{ inputs.api_key }}"},
      "body": {
        "name": "{{ inputs.preset_name }}",
        "config": {{ steps.fetch_run.response.results.best.config | tojson }}
      }
    }}
  ]
}
```
Notes:
- The engine templates values from `inputs`. The `capture` fields make later steps reference earlier JSON responses (e.g., `steps.create_dataset.response.id`).
- If egress is restricted, allow localhost in egress policy.
- For long runs, replace the single `delay`+`fetch_run` with a polling loop (or rely on Evaluations webhooks).

2) Run ad-hoc with inputs
```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/workflows/run?mode=async" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{
        "definition": '"$(cat definition.json)"',
        "inputs": {
          "api_key": "'$API_KEY'",
          "dataset_name": "qa_ds_1",
          "qa_samples": [
            {"input": {"question": "What is a residual connection?"}, "expected": {"answer": "It helps gradients flow and stabilizes very deep nets."}},
            {"input": {"question": "List datasets in the paper"}, "expected": {"answer": "ImageNet, CIFAR-10/100"}}
          ],
          "rag_model": "gpt-4o-mini",
          "preset_name": "baseline_hybrid_xenc"
        }
      }'
```

## Advanced: Tables/VLM and Agentic Toggles

For table-heavy corpora or scans, enable table processing and Vision-assisted late chunking. Pair that with post-verification and bounded adaptive re-runs to improve robustness on low confidence.

Use these keys under `rag_pipeline.advanced`:

```json
{
  "fts_level": "chunk",
  "enable_table_processing": true,
  "table_method": "markdown",
  "enable_vlm_late_chunking": true,
  "vlm_backend": "gpt-4o",
  "vlm_detect_tables_only": true,
  "vlm_max_pages": 3,
  "enable_post_verification": true,
  "adaptive_rerun_on_low_confidence": true,
  "adaptive_rerun_include_generation": true,
  "adaptive_rerun_time_budget_sec": 10,
  "timeout_seconds": 45,
  "highlight_results": true
}
```

Scope retrieval to a keyword collection using `retriever.keyword_filter` (e.g., `collection:tables-demo`). Example retriever block:

```json
{"search_mode": ["hybrid"], "hybrid_alpha": [0.5, 0.7], "top_k": [8,12], "keyword_filter": ["collection:tables-demo"], "fts_level": ["chunk"]}
```

## Ready-to-Paste Evaluation JSON

An inline-QA RAG grid with VLM late chunking and agentic toggles is provided at `Samples/Evals/rag_grid_inline_qa.json`. Post it directly:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/evaluations/ \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d @Samples/Evals/rag_grid_inline_qa.json
```

Then start a run as usual:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/evaluations/<EVAL_ID>/runs \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d '{"target_model": "openai"}'
```

## Ad-hoc + Schedule: RAG grid and Embeddings A/B (Inline QA, Keyword Collections)

Use the combined sample workflow at `Samples/Workflows/rag_and_embeddings_opt.workflow.json`. It:
- Creates a RAG inline-QA evaluation constrained by your `keyword_filter` collection
- Starts the RAG run
- Searches media by keywords to derive `media_ids`
- Creates and starts an Embeddings A/B test against those IDs

Notes:
- The Workflows `webhook` step supports `method`, `headers`, and `body` with minimal templating.
- Inject structured JSON from the workflow context using `JSON:<path>` references:
  - `JSON:inputs.qa_samples`
  - `JSON:inputs.keyword_filter`
  - `JSON:prev.response_json.items|pluck:id` (pluck a field from a list)
- Provide the API key at run time via `secrets` (preferred) or set `inputs.api_key` in the definition.

Run the ad-hoc once with inline inputs/secrets:

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/workflows/run?mode=async" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{
        "definition": '"$(cat Samples/Workflows/rag_and_embeddings_opt.workflow.json)"',
        "inputs": {
          "keyword_filter": ["collection:tables-demo"],
          "qa_samples": [
            {"input": {"question": "What is a residual connection?"}, "expected": {"answer": "It helps gradients flow and stabilizes deep networks."}}
          ]
        },
        "secrets": {"api_key": "'$API_KEY'"}
      }'
```

Schedule it nightly at 02:00 using the Workflows scheduler (first, save the workflow):

```bash
# Save and capture workflow id
WF_ID=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/workflows \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d @Samples/Workflows/rag_and_embeddings_opt.workflow.json | jq -r .id)

# Create a schedule (skip overlaps, UTC)
curl -sS -X POST http://127.0.0.1:8000/api/v1/scheduler/workflows \
  -H "X-API-KEY: $API_KEY" -H "Content-Type: application/json" \
  -d '{
        "workflow_id": '"$WF_ID"',
        "name": "rag+embeddings nightly",
        "cron": "0 2 * * *",
        "timezone": "UTC",
        "inputs": {"keyword_filter": ["collection:tables-demo"]},
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

## Outputs
- The evaluation run’s `results` contain a `leaderboard` and a `best` object with the best performing configuration.
- Saving a preset lets you reuse the winning config in production/search endpoints and the WebUI.

## Tips for effective grids
- Start small for latency: 2-3 values per knob; expand only after first signal.
- Retrieval: try `hybrid_alpha` in [0.5, 0.7, 0.8], `top_k` in [8, 12, 16].
- Rerankers: `flashrank` (fast) vs `cross_encoder` (higher quality); cap `rerank_top_k` ≈ 10-20.
- Long docs: prefer `fts_level=chunk`, `include_sibling_chunks=true`.
- If tables matter: enable VLM late chunking in RAG/agentic strategies.

## Advanced Options Reference (Pass-through)

These keys are accepted under `rag_pipeline.advanced` and are passed directly to the unified RAG pipeline. Use them to fine-tune retrieval, reranking, generation, and guardrails.

- Search/Expansion/Cache
  - `expand_query: bool` - enable query expansion.
  - `expansion_strategies: string[]` - acronym|synonym|domain|entity.
  - `spell_check: bool` - correct typos before retrieval.
  - `enable_cache: bool` - semantic/rewrite cache.
  - `cache_threshold: number` - similarity threshold for cache hits.
  - `adaptive_cache: bool` - smarter cache policy per query.

- Security/Filters
  - `enable_security_filter: bool` - enable policy checks.
  - `detect_pii: bool` - detect personally identifiable information.
  - `redact_pii: bool` - redact PII in contexts/answers.
  - `sensitivity_level: "public"|"internal"|"confidential"|"restricted"` - policy level.
  - `content_filter: bool` - content safety filtering.

- Tables/VLM
  - `enable_table_processing: bool` - parse/serialize tables.
  - `table_method: "markdown"|"html"|"hybrid"` - output format for table serialization.
  - `enable_vlm_late_chunking: bool` - vision-assisted chunking of PDFs/images late in pipeline.
  - `vlm_backend: string` - VLM model/provider (e.g., gpt-4o).
  - `vlm_detect_tables_only: bool` - only detect tables (faster); otherwise detect figures too.
  - `vlm_max_pages: number|null` - maximum analyzed pages.
  - `vlm_late_chunk_top_k_docs: number` - how many docs to VLM-chunk.

- Context/Chunking
  - `enable_enhanced_chunking: bool` - retrieval-time chunk expansion helpers.
  - `chunk_type_filter: string[]` - filter chunk types: text|code|table|list.
  - `enable_parent_expansion: bool` - include parent chunk context.
  - `parent_context_size: number` - characters from parent.
  - `include_parent_document: bool` - include a parent document preview.
  - `sibling_window: number` - neighbor chunk window size.
  - `include_sibling_chunks: bool` - include neighbor chunks (note: if `chunking.include_siblings` is set, it takes precedence over this advanced value in the grid execution).

- Advanced Retrieval
  - `enable_multi_vector_passages: bool` - split passages into sub-spans.
  - `mv_span_chars: number` - characters per span.
  - `mv_stride: number` - sliding stride.
  - `mv_max_spans: number` - span cap per doc.
  - `mv_flatten_to_spans: bool` - treat spans as top-level units.
  - `enable_numeric_table_boost: bool` - boost numeric/table content.

- Reranking Extras
  - `reranking_model: string` - model id/path (e.g., GGUF or HF id) for rerank.
  - `rerank_min_relevance_prob: number|null` - threshold gate for two-tier rerankers.
  - `rerank_sentinel_margin: number|null` - margin for sentinel filtering.

- Citations & Guardrails
  - `enable_citations: bool` - enable citation generation.
  - `citation_style: "apa"|"mla"|"chicago"|"harvard"|"ieee"`.
  - `include_page_numbers: bool` - include page numbers in citations.
  - `enable_chunk_citations: bool` - per-chunk citation annotations.
  - `strict_extractive: bool` - constrain model to extractive answers.
  - `require_hard_citations: bool` - enforce hard citation evidence.
  - `enable_numeric_fidelity: bool` - numeric accuracy guardrails.
  - `numeric_fidelity_behavior: "continue"|"ask"|"decline"|"retry"` - behavior on numeric uncertainty.

- Generation Extras
  - `enable_abstention: bool` - allow the model to abstain.
  - `abstention_behavior: "continue"|"ask"|"decline"` - behavior when abstaining.
  - `enable_multi_turn_synthesis: bool` - multi-pass synthesis.
  - `synthesis_time_budget_sec: number|null` - synthesis time budget.
  - `synthesis_draft_tokens: number|null` - draft step token budget.
  - `synthesis_refine_tokens: number|null` - refine step token budget.

- Post-Verification / Adaptive
  - `enable_post_verification: bool` - verify/model-check the answer.
  - `adaptive_max_retries: number` - max adaptive loops.
  - `adaptive_unsupported_threshold: number` - unsupported content threshold.
  - `adaptive_max_claims: number` - claims extraction limit.
  - `adaptive_time_budget_sec: number|null` - total verification budget.
  - `low_confidence_behavior: "continue"|"ask"|"decline"` - gating policy for low confidence.
  - `adaptive_advanced_rewrites: bool|null` - allow deeper query rewrites.
  - `adaptive_rerun_on_low_confidence: bool` - bounded re-run.
  - `adaptive_rerun_include_generation: bool` - rerun generation as well.
  - `adaptive_rerun_bypass_cache: bool` - bypass caches for the rerun.
  - `adaptive_rerun_time_budget_sec: number|null` - rerun budget.
  - `adaptive_rerun_doc_budget: number|null` - rerun doc cap.

- Observability / Performance
  - `enable_monitoring: bool` - internal metrics.
  - `enable_observability: bool` - tracing/telemetry.
  - `trace_id: string` - propagate a trace id.
  - `enable_performance_analysis: bool` - extra perf probes.
  - `timeout_seconds: number` - per-query timeout.

- Namespace & UX
  - `index_namespace: string` - ephemeral collection namespace for the run (combine with `cleanup_collections` at the top level of `rag_pipeline`).
  - `highlight_results: bool` - annotate highlights in results.
  - `highlight_query_terms: bool` - highlight matched terms.
  - `track_cost: bool` - record estimated cost.
  - `debug_mode: bool` - verbose debug.

- Claims & Factuality
  - `enable_claims: bool` - enable claims extraction/verification.
  - `claim_extractor: string|null` - model/provider for extraction.
  - `claim_verifier: string|null` - model/provider for verification.
  - `claims_top_k: number|null` - documents per claim.
  - `claims_conf_threshold: number|null` - min confidence.
  - `claims_max: number|null` - maximum claims per answer.
  - `nli_model: string|null` - NLI model for fact-checking.
  - `claims_concurrency: number|null` - parallelism cap.

- Date/Media Filtering
  - `enable_date_filter: bool` - enable date range filter.
  - `date_range: object` - e.g., {"from": "2024-01-01", "to": "2024-12-31"}.
  - `filter_media_types: string[]` - restrict to media types.

Hints
- Retrieval-level `fts_level` and `keyword_filter` are set in the `retrievers` block; `fts_level` is not part of `advanced` (it’s passed via the retriever). If both `chunking.include_siblings` and `advanced.include_sibling_chunks` are provided, the chunking block takes precedence during the grid run.
