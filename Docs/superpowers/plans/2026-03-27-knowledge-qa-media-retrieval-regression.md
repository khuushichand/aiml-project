# Knowledge QA Media Retrieval Regression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore Knowledge QA retrieval for natural-language questions against user media when chunk-level retrieval misses and the system falls back to Media DB search.

**Architecture:** Keep the change inside the Media DB fallback retrieval path used by unified RAG. Preserve chunk-first behavior, but make media-level fallback tolerant of question-shaped queries by broadening fallback term selection and removing an over-strict title/content LIKE conjunction when FTS is active.

**Tech Stack:** Python, pytest, SQLite FTS5, FastAPI RAG service

---

## Stage 1: Reproduce and Lock Regression
**Goal:** Add a failing test that matches the local failure mode.
**Success Criteria:** A unit test proves a natural-language query against media fallback returns no documents before the fix.
**Tests:** `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py -k goku -v`
**Status:** Complete

## Stage 2: Fix Media Fallback Querying
**Goal:** Broaden fallback retrieval so natural-language queries can still find relevant media when chunk retrieval is unavailable.
**Success Criteria:** The new regression test passes and existing retrieval fallback tests still pass.
**Tests:** `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py -v`
**Status:** Complete

## Stage 3: Verify Safety
**Goal:** Run focused verification and security scan on touched files.
**Success Criteria:** Targeted pytest passes and Bandit reports no new issues in changed code.
**Tests:** `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_retrieval.py -v` and `python -m bandit -r tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py tldw_Server_API/app/core/DB_Management/media_db/repositories/media_search_repository.py -f json -o /tmp/bandit_knowledge_qa_media_retrieval.json`
**Status:** Complete
