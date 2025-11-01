# Evaluations Overview

The Evaluations module provides a unified, OpenAI-compatible API for assessing model outputs, RAG systems, and custom metrics. The production surface is the unified router under `/api/v1/evaluations`.

## Quick Links
- Unified API Reference: ../API-related/Evaluations_API_Unified_Reference.md
- Readiness Summary: Unified_Evaluations_Readiness.md
- Smoke Tests: Smoke_Test_Checklist.md
- Developer Guide: ../Code_Documentation/Evaluations_Developer_Guide.md
- End-User Guide: ../User_Guides/Evaluations_End_User_Guide.md
- Deployment Guides: ../User_Guides/Evaluations_Deployment_Guide.md, ../User_Guides/Evaluations_Production_Deployment_Guide.md

## Primary Endpoints (Unified)
Base path: `/api/v1/evaluations`
- `POST /geval` - Summarization evaluation (G-Eval metrics)
- `POST /rag` - RAG evaluation (relevance, faithfulness, similarity, etc.)
- `POST /response-quality` - General response quality + format compliance
- `POST /batch` - Batch evaluations with parallel workers
- `POST /history` - History retrieval and aggregation
- `POST /custom-metric` - User-defined metric evaluation
- `POST /compare` - Compare evaluation results
- Webhooks: `POST /webhooks`, `GET /webhooks`, `DELETE /webhooks`, `POST /webhooks/test`
- Rate limits: `GET /rate-limits`
- Embeddings A/B test (scaffold): `POST /embeddings/abtest`, `POST /embeddings/abtest/{test_id}/run`, `GET /embeddings/abtest/{test_id}`
- RAG pipeline presets: `POST /rag/pipeline/presets`, `GET /rag/pipeline/presets`
- Health & Metrics: `GET /health`, `GET /metrics` (JSON or Prometheus text via `Accept`)

Authentication
- Single-user: `X-API-KEY` (or Bearer with the same key)
- Multi-user: Bearer JWT

## Storage & Internals
- Default DB: ``Databases/evaluations.db`` (SQLite) via `EvaluationsDatabase`
- Tables: evaluations, evaluation_runs, datasets, internal_evaluations, webhook_registrations, pipeline_presets, ephemeral_collections
- A/B test tables: embedding_abtests, embedding_abtest_arms, embedding_abtest_queries, embedding_abtest_results

Notes
- Legacy evaluation routers are deprecated and not mounted by default; use the unified endpoints above.

Use the sidebar to browse evaluation topics and deeper guides.
