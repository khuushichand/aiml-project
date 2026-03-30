# RAG Text Late Chunking Knobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose per-query text late chunking knobs for method, size, overlap, and language without persisting any transient chunks.

**Architecture:** Add the knobs to shared RAG settings and unified request schema, pass them through `RetrievalConfig`, and have the media retriever use config values when late chunking is enabled for a query. Render the controls conditionally in the Knowledge settings UIs so they are clearly query-time retrieval controls rather than ingest controls.

**Tech Stack:** FastAPI/Pydantic, Python dataclasses, React/TypeScript, Vitest, Pytest

---

## Stage 1: Red Tests
**Goal:** Add failing tests proving the request builder forwards the new knobs and the retriever respects custom late-chunk settings.
**Success Criteria:** Targeted UI and Python tests fail for the expected missing-field/pass-through reasons.
**Tests:** `bunx vitest run src/services/__tests__/unified-rag.test.ts`; `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py -k late_chunking_custom -v`
**Status:** Complete

## Stage 2: Backend Wiring
**Goal:** Carry the new query-time chunking knobs through the unified RAG request and retrieval config into the media retriever late-chunk path.
**Success Criteria:** The retriever uses config-provided method/size/overlap/language when kwargs are absent, and no persistence paths are touched.
**Tests:** `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py -v`
**Status:** Complete

## Stage 3: UI Exposure
**Goal:** Add conditional controls for the new knobs in Knowledge settings and KnowledgeQA expert settings.
**Success Criteria:** Controls appear only when text late chunking is enabled and request builder includes the selected values.
**Tests:** `bunx vitest run src/services/__tests__/unified-rag.test.ts`
**Status:** Complete
