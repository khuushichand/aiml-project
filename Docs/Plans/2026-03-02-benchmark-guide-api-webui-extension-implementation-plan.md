# Benchmark Guide (API + WebUI/Extension) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a single canonical user guide that teaches benchmark runs via API and WebUI/extension UI, with explicit current-state behavior and clearly labeled roadmap notes.

**Architecture:** Implement docs changes with test-first guardrails. Add one focused Docs test to enforce guide discoverability and key route references, then add the new guide, update index/navigation links, and add minimal cross-links from existing evaluation guides. Keep scope to shipped behavior and separate roadmap notes.

**Tech Stack:** Markdown docs in `Docs/`, pytest docs tests in `tldw_Server_API/tests/Docs/`, existing project test runner (`python -m pytest`).

---

### Task 1: Add Docs Regression Test For Benchmark Guide Discoverability

**Files:**
- Create: `tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py`
- Test: `tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py`

**Step 1: Write the failing test**

```python
from pathlib import Path


def test_benchmark_guide_exists_and_is_indexed() -> None:
    guide = Path("Docs/User_Guides/Server/Benchmark_Creation_API_WebUI_Extension_Guide.md")
    assert guide.exists()

    index_text = Path("Docs/User_Guides/index.md").read_text()
    assert "Benchmark_Creation_API_WebUI_Extension_Guide.md" in index_text


def test_benchmark_guide_mentions_api_and_webui_paths() -> None:
    text = Path(
        "Docs/User_Guides/Server/Benchmark_Creation_API_WebUI_Extension_Guide.md"
    ).read_text()
    assert "/api/v1/evaluations/benchmarks" in text
    assert "/api/v1/evaluations/benchmarks/{benchmark_name}/run" in text
    assert "benchmark-run" in text
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py -v`  
Expected: FAIL because guide and index link do not yet exist.

**Step 3: Write minimal implementation**

Create test file with the code above only.

**Step 4: Run test to verify it passes/fails as expected**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py -v`  
Expected: FAIL at assertions referencing not-yet-created docs (this is the intentional red state).

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py
git commit -m "test(docs): add benchmark guide discoverability guard"
```

### Task 2: Create Canonical Benchmark Guide (Operator-First)

**Files:**
- Create: `Docs/User_Guides/Server/Benchmark_Creation_API_WebUI_Extension_Guide.md`
- Modify: `Docs/User_Guides/Server/Benchmark_Creation_API_WebUI_Extension_Guide.md` (full content)
- Test: `tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py`

**Step 1: Write the failing test (confirm red)**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py -v`  
Expected: FAIL due missing guide content.

**Step 2: Run test to verify it fails**

Expected failure details:
- Missing file `Benchmark_Creation_API_WebUI_Extension_Guide.md`
- Missing required API/UI strings

**Step 3: Write minimal implementation**

Add guide with these required sections and exact strings:

```md
# Benchmark Creation and Runs (API + WebUI/Extension)

## Who this guide is for
...

## Current state (shipped)
- API routes:
  - `GET /api/v1/evaluations/benchmarks`
  - `GET /api/v1/evaluations/benchmarks/{benchmark_name}`
  - `POST /api/v1/evaluations/benchmarks/{benchmark_name}/run`
- WebUI/extension:
  - Evaluations -> Runs -> Ad-hoc evaluator -> `benchmark-run`

## WebUI/Extension quickstart
...

## API quickstart
...

## Troubleshooting
...

## Roadmap (Not yet shipped)
...

## Contributor appendix
...
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py -v`  
Expected: one test may still fail because index link is not added yet (acceptable until Task 3).

**Step 5: Commit**

```bash
git add Docs/User_Guides/Server/Benchmark_Creation_API_WebUI_Extension_Guide.md
git commit -m "docs(user-guide): add canonical benchmark api+webui/extension guide"
```

### Task 3: Wire Discoverability Links In User Guide Entry Points

**Files:**
- Modify: `Docs/User_Guides/index.md`
- Modify: `Docs/User_Guides/Server/Evaluations_User_Guide.md`
- Modify: `Docs/User_Guides/WebUI_Extension/User_Guide.md`
- Test: `tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py`

**Step 1: Write failing test (confirm index link missing)**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py -v`  
Expected: FAIL on missing index link assertion.

**Step 2: Run test to verify it fails**

Expected: failure in `test_benchmark_guide_exists_and_is_indexed`.

**Step 3: Write minimal implementation**

Add links:

- In `Docs/User_Guides/index.md`, add:
  - `[Benchmark Creation and Runs (API + WebUI/Extension)](Server/Benchmark_Creation_API_WebUI_Extension_Guide.md)`
- In server/webui guides, add a short “See also” line linking to the new guide.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add Docs/User_Guides/index.md Docs/User_Guides/Server/Evaluations_User_Guide.md Docs/User_Guides/WebUI_Extension/User_Guide.md
git commit -m "docs: link benchmark guide from user guide entry points"
```

### Task 4: Validate Broader Docs Safety And Route Accuracy

**Files:**
- Modify: `Docs/User_Guides/Server/Benchmark_Creation_API_WebUI_Extension_Guide.md` (final edits if needed)
- Test: `tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py`
- Test: `tldw_Server_API/tests/Docs/test_speech_api_guide_map.py`
- Test: `tldw_Server_API/tests/Docs/test_stt_tts_link_hygiene.py`

**Step 1: Write failing test (if any regressions)**

Run:

```bash
source .venv/bin/activate && \
python -m pytest \
  tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py \
  tldw_Server_API/tests/Docs/test_speech_api_guide_map.py \
  tldw_Server_API/tests/Docs/test_stt_tts_link_hygiene.py \
  -v
```

**Step 2: Run test to verify status**

Expected: PASS. If FAIL, capture exact assertion and fix only touched-doc issues.

**Step 3: Write minimal implementation**

If needed, adjust link text/paths in modified guides only.

**Step 4: Run test to verify it passes**

Re-run the same command.  
Expected: PASS across all targeted docs tests.

**Step 5: Commit**

```bash
git add Docs/User_Guides/Server/Benchmark_Creation_API_WebUI_Extension_Guide.md Docs/User_Guides/index.md Docs/User_Guides/Server/Evaluations_User_Guide.md Docs/User_Guides/WebUI_Extension/User_Guide.md
git commit -m "docs: finalize benchmark guide accuracy and docs test validation"
```

### Task 5: Security Check On Touched Scope (Policy Requirement)

**Files:**
- Test/Report: `/tmp/bandit_benchmark_guide_docs.json`

**Step 1: Write failing test**

Not applicable for Bandit; this task is validation-only.

**Step 2: Run command**

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/tests/Docs -f json -o /tmp/bandit_benchmark_guide_docs.json
```

Expected: command completes and report file is written.

**Step 3: Write minimal implementation**

If Bandit flags new issues in touched files, apply minimal fixes.

**Step 4: Run validation again**

Re-run Bandit command above.  
Expected: no new unresolved findings in touched files.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Docs/test_benchmark_guide_discoverability.py Docs/User_Guides/Server/Benchmark_Creation_API_WebUI_Extension_Guide.md Docs/User_Guides/index.md Docs/User_Guides/Server/Evaluations_User_Guide.md Docs/User_Guides/WebUI_Extension/User_Guide.md
git commit -m "chore(docs): complete benchmark guide validations"
```

