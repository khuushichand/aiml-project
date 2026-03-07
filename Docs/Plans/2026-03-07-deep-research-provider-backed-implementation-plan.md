# Deep Research Provider-Backed Collection And Synthesis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace deterministic deep-research collection and synthesis stubs with provider-backed local, web, academic, and synthesis integrations while preserving the existing Jobs/session/artifact contract.

**Architecture:** Add a thin `app/core/Research/providers/` adapter layer, persist bounded provider overrides on each research session, resolve effective provider config during planning, and wire `ResearchBroker` and `ResearchSynthesizer` to those adapters. Keep deterministic synthesis as the fallback path for `TEST_MODE`, parse failures, and provider failures.

**Tech Stack:** FastAPI, Pydantic, SQLite-backed `ResearchSessionsDB`, `MultiDatabaseRetriever`, core web search orchestration, arXiv/PubMed/Crossref helpers, `perform_chat_api_call_async`, pytest, Bandit.

---

### Task 1: Persist Provider Overrides And Resolved Config

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Modify: `tldw_Server_API/app/core/Research/jobs.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/research_runs.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_service.py`
- Modify: `tldw_Server_API/tests/Research/test_research_runs_endpoint.py`

**Step 1: Write the failing tests**

Add tests that verify:
- `POST /api/v1/research/runs` accepts a bounded `provider_overrides` payload
- `ResearchService.create_session(...)` persists the raw overrides with the session
- the planning phase writes `provider_config.json` with resolved defaults plus overrides
- `GET /api/v1/research/runs/{id}/artifacts/provider_config.json` is allowlisted
- an existing `research_sessions` table created before this slice is migrated safely when the DB opens

Example request payload to cover:

```python
payload = {
    "query": "hybrid research test",
    "provider_overrides": {
        "local": {"top_k": 4, "sources": ["media_db"]},
        "web": {"engine": "duckduckgo", "result_count": 3},
        "academic": {"providers": ["arxiv", "pubmed"], "max_results": 2},
        "synthesis": {"provider": "openai", "model": "gpt-4.1-mini", "temperature": 0.2},
    },
}
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`

Expected: FAIL because the schema, session persistence, and planning artifact do not yet support provider overrides.

**Step 3: Write minimal implementation**

Implement:
- a new `provider_overrides` field on `ResearchRunCreateRequest`
- persistence in `ResearchSessionsDB` using a dedicated `provider_overrides_json` column
- session row hydration for `provider_overrides_json`
- additive SQLite migration logic in `ResearchSessionsDB._ensure_schema()` using `PRAGMA table_info(...)` and `ALTER TABLE ... ADD COLUMN` so existing session DBs continue to work
- `ResearchService.create_session(...)` support for the new argument
- planning-phase write of `provider_config.json`
- allowlist update in `ResearchService._ALLOWED_ARTIFACT_NAMES`

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/app/core/Research/service.py tldw_Server_API/app/core/Research/jobs.py tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py tldw_Server_API/app/api/v1/endpoints/research_runs.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py
git commit -m "feat(research): persist provider-backed run config"
```

### Task 2: Add Provider Config Resolver And Collection Adapters

**Files:**
- Create: `tldw_Server_API/app/core/Research/providers/__init__.py`
- Create: `tldw_Server_API/app/core/Research/providers/config.py`
- Create: `tldw_Server_API/app/core/Research/providers/local.py`
- Create: `tldw_Server_API/app/core/Research/providers/web.py`
- Create: `tldw_Server_API/app/core/Research/providers/academic.py`
- Create: `tldw_Server_API/tests/Research/test_research_provider_config.py`
- Create: `tldw_Server_API/tests/Research/test_research_provider_adapters.py`

**Step 1: Write the failing tests**

Add tests that verify:
- provider overrides are allowlisted and clamped
- defaults are supplied when overrides are absent
- local provider normalizes `MultiDatabaseRetriever` documents into lane records
- web provider wraps the core web search stack and normalizes top results
- academic provider wraps arXiv/PubMed/Crossref helpers and normalizes papers
- `TEST_MODE` paths return deterministic records without live network calls
- local provider resolves per-user database paths via `DatabasePaths` before constructing `MultiDatabaseRetriever`

Example assertions:

```python
assert resolved["web"]["result_count"] == 3
assert resolved["academic"]["providers"] == ["arxiv", "pubmed"]
assert all("title" in item for item in records)
assert all("snippet" in item or "summary" in item for item in records)
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_provider_config.py tldw_Server_API/tests/Research/test_research_provider_adapters.py -v`

Expected: FAIL because the provider package does not exist yet.

**Step 3: Write minimal implementation**

Implement:
- config resolver that returns a structure like:

```python
{
    "local": {"top_k": 5, "sources": ["media_db"]},
    "web": {"engine": "duckduckgo", "result_count": 5},
    "academic": {"providers": ["arxiv", "pubmed", "crossref"], "max_results": 5},
    "synthesis": {"provider": None, "model": None, "temperature": 0.2},
}
```

- `LocalResearchProvider.search(...)`
- `WebResearchProvider.search(...)`
- `AcademicResearchProvider.search(...)`

Implementation notes:
- `LocalResearchProvider` should construct `MultiDatabaseRetriever` with explicit `db_paths` resolved from `DatabasePaths.get_media_db_path(...)`, `DatabasePaths.get_chacha_db_path(...)`, `DatabasePaths.get_prompts_db_path(...)`, and `DatabasePaths.get_kanban_db_path(...)` as needed by the selected sources
- keep v1 conservative by defaulting local retrieval to `["media_db"]` unless the override explicitly opts into more sources
- `WebResearchProvider` should call `perform_websearch(...)` directly rather than `generate_and_search(...)` so collection stays single-query and does not reintroduce broad subquery expansion
- each provider should return normalized `list[dict[str, Any]]` records ready for `ResearchBroker`

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_provider_config.py tldw_Server_API/tests/Research/test_research_provider_adapters.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/providers/__init__.py tldw_Server_API/app/core/Research/providers/config.py tldw_Server_API/app/core/Research/providers/local.py tldw_Server_API/app/core/Research/providers/web.py tldw_Server_API/app/core/Research/providers/academic.py tldw_Server_API/tests/Research/test_research_provider_config.py tldw_Server_API/tests/Research/test_research_provider_adapters.py
git commit -m "feat(research): add collection provider adapters"
```

### Task 3: Wire Provider-Backed Collection Into The Broker And Worker

**Files:**
- Modify: `tldw_Server_API/app/core/Research/broker.py`
- Modify: `tldw_Server_API/app/core/Research/jobs.py`
- Modify: `tldw_Server_API/app/core/Research/models.py` if lane error metadata needs to be made explicit
- Modify: `tldw_Server_API/tests/Research/test_research_broker.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_worker.py`

**Step 1: Write the failing tests**

Add tests that verify:
- `ResearchBroker` uses configured providers instead of deterministic internal stubs
- `local_first` skips external lanes when local coverage is sufficient
- lane failures are recorded as gaps/collection metadata without killing the run when another lane succeeds
- planning writes `provider_config.json` and collecting consumes it

Example expectations:

```python
assert result.collection_metrics["lane_counts"]["local"] >= 1
assert "lane_errors" in collection_summary
assert session.phase in {"awaiting_source_review", "synthesizing"}
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_broker.py tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`

Expected: FAIL because the broker still uses deterministic lane methods.

**Step 3: Write minimal implementation**

Implement:
- constructor injection for `LocalResearchProvider`, `WebResearchProvider`, and `AcademicResearchProvider`
- loading `provider_config.json` during collection
- `lane_errors` capture in collection summary when a provider raises
- hard failure only when every enabled lane fails and zero sources are collected

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_broker.py tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/broker.py tldw_Server_API/app/core/Research/jobs.py tldw_Server_API/app/core/Research/models.py tldw_Server_API/tests/Research/test_research_broker.py tldw_Server_API/tests/Research/test_research_jobs_worker.py
git commit -m "feat(research): use provider-backed collecting"
```

### Task 4: Add Provider-Backed Synthesis With Deterministic Fallback

**Files:**
- Create: `tldw_Server_API/app/core/Research/providers/synthesis.py`
- Modify: `tldw_Server_API/app/core/Research/synthesizer.py`
- Modify: `tldw_Server_API/app/core/Research/jobs.py`
- Modify: `tldw_Server_API/tests/Research/test_research_synthesizer.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_worker.py`

**Step 1: Write the failing tests**

Add tests that verify:
- a synthesis provider can return structured JSON and produce outline/claims/report artifacts
- unknown `source_id` references are rejected
- parse failures or provider exceptions fall back to deterministic synthesis
- fallback reason is recorded in `synthesis_summary.json`
- the async synthesis path is awaited correctly by the worker and does not preserve the old synchronous call contract by accident

Example structured output fixture:

```python
{
    "outline_sections": [
        {"title": "Background", "focus_area": "background", "source_ids": ["src_a"], "note_ids": ["note_a"]}
    ],
    "claims": [
        {"text": "Supported claim", "focus_area": "background", "source_ids": ["src_a"], "citations": [{"source_id": "src_a"}], "confidence": 0.81}
    ],
    "report_sections": [
        {"title": "Background", "markdown": "Evidence-backed section text."}
    ],
    "unresolved_questions": [],
    "summary": {"mode": "llm_backed"},
}
```

**Step 2: Run tests to verify they fail**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_synthesizer.py tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`

Expected: FAIL because there is no synthesis adapter or fallback-aware validation yet.

**Step 3: Write minimal implementation**

Implement:
- `SynthesisProvider.summarize(...)` using `perform_chat_api_call_async`
- change `ResearchSynthesizer.synthesize(...)` to an async method and update `jobs.py` to await it
- structured-output parsing via `parse_structured_output(...)` and `StructuredOutputOptions` from `tldw_Server_API/app/core/LLM_Calls/structured_output.py`
- source-id validation in `ResearchSynthesizer`
- deterministic fallback when parsing or validation fails
- `jobs.py` integration so the synthesizing phase uses the resolved provider config

**Step 4: Run tests to verify they pass**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_synthesizer.py tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/providers/synthesis.py tldw_Server_API/app/core/Research/synthesizer.py tldw_Server_API/app/core/Research/jobs.py tldw_Server_API/tests/Research/test_research_synthesizer.py tldw_Server_API/tests/Research/test_research_jobs_worker.py
git commit -m "feat(research): use provider-backed synthesis"
```

### Task 5: Verify Hybrid End-To-End Flow And Run Full Research Regression

**Files:**
- Modify: `tldw_Server_API/tests/e2e/test_deep_research_runs.py`
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_service.py` if artifact assertions need expansion
- Modify: `Docs/Plans/2026-03-07-deep-research-provider-backed-implementation-plan.md`

**Step 1: Write the failing test**

Extend the e2e run to verify:
- `provider_config.json` is written and readable through the artifact endpoint
- collecting uses provider-backed local/web/academic adapters in test mode
- synthesis completes using a provider stub or deterministic fallback
- final `bundle.json` still exports correctly through the research package adapter

**Step 2: Run test to verify it fails**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`

Expected: FAIL until planning, collecting, and synthesis all use the provider-backed path.

**Step 3: Write minimal implementation**

Adjust the remaining worker wiring and artifact exposure details until the full provider-backed e2e path passes.

**Step 4: Run full verification**

Run: `source ../../.venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_provider_config.py tldw_Server_API/tests/Research/test_research_provider_adapters.py tldw_Server_API/tests/Research/test_research_broker.py tldw_Server_API/tests/Research/test_research_artifact_store.py tldw_Server_API/tests/Research/test_research_planner.py tldw_Server_API/tests/Research/test_research_limits.py tldw_Server_API/tests/Research/test_research_checkpoint_service.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_jobs_worker.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py tldw_Server_API/tests/Research/test_research_exporter.py tldw_Server_API/tests/Research/test_research_package_adapter.py tldw_Server_API/tests/Research/test_research_synthesizer.py tldw_Server_API/tests/DB_Management/test_research_db_paths.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`

Expected: PASS

Run: `source ../../.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Research tldw_Server_API/app/api/v1/endpoints/research_runs.py tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py -f json -o /tmp/bandit_deep_research_provider_backed.json`

Expected: JSON report with `0` findings in the touched production paths.

**Step 5: Update plan status and commit**

Add `**Status:** Complete` under each task in this plan file, then commit:

```bash
git add Docs/Plans/2026-03-07-deep-research-provider-backed-implementation-plan.md tldw_Server_API/tests/e2e/test_deep_research_runs.py tldw_Server_API/tests/Research/test_research_jobs_service.py
git commit -m "test(research): verify provider-backed deep research flow"
```
