# CORS Self-Host Onboarding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent confusing first-run startup failures from explicit empty CORS origin configuration while keeping local browser-based onboarding working by default.

**Architecture:** Keep the existing CORS middleware-on-by-default model for local/self-hosted browser access, but move the empty-origin compatibility handling into origin resolution for non-production startup. Production validation remains strict and continues to reject empty or wildcard misconfiguration as appropriate.

**Tech Stack:** Python, FastAPI, Starlette CORSMiddleware, pytest

---

## Stage 1: Document The Decision
**Goal:** Capture the approved behavior change and its constraints.
**Success Criteria:** A task-specific design note exists under `Docs/Plans/` and reflects the approved approach.
**Tests:** None.
**Status:** Complete

## Stage 2: Add A Failing Regression Test
**Goal:** Prove that a non-production explicit empty origin configuration currently fails and should instead fall back to local defaults.
**Success Criteria:** A new or updated unit test fails for the target behavior before implementation.
**Tests:** `python -m pytest tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py -k cors -v`
**Status:** Not Started

## Stage 3: Implement Minimal Runtime Change
**Goal:** Resolve empty configured origins to the built-in localhost defaults in non-production only.
**Success Criteria:** Non-production startup succeeds with local fallback; production remains strict.
**Tests:** `python -m pytest tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py -k cors -v`
**Status:** Not Started

## Stage 4: Update Self-Host Docs
**Goal:** Make the local default behavior understandable without requiring CORS knowledge.
**Success Criteria:** Env/config docs explain that local browser access works by default and that `ALLOWED_ORIGINS` is only needed for custom origins.
**Tests:** Manual review of touched docs.
**Status:** Not Started

## Stage 5: Verify Security And Regression Coverage
**Goal:** Confirm the change passes targeted tests and introduces no new Bandit findings in touched code.
**Success Criteria:** Targeted pytest and Bandit runs succeed.
**Tests:** `python -m pytest tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py -k cors -v`; `python -m bandit -r tldw_Server_API/app/main.py tldw_Server_API/app/core/config.py tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py -f json -o /tmp/bandit_cors_selfhost_onboarding.json`
**Status:** Not Started

### Task 1: Add The Failing Test

**Files:**
- Modify: `tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py`

**Step 1: Write the failing test**

Add a unit test that sets:

- `ENV=development`
- `DISABLE_CORS=false`
- `CORS_ALLOW_CREDENTIALS=false`
- `ALLOWED_ORIGINS=[]`

and asserts that app startup resolves to the built-in local origins instead of raising.

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py -k cors -v`

Expected: the new test fails because startup currently treats the parsed empty list as fatal.

**Step 3: Commit**

```bash
git add tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py
git commit -m "test: cover empty local cors origin fallback"
```

### Task 2: Implement The Runtime Fallback

**Files:**
- Modify: `tldw_Server_API/app/main.py`
- Modify: `tldw_Server_API/app/core/config.py`

**Step 1: Write minimal implementation**

- Reuse the existing built-in localhost allowlist from config.
- When resolved origins are empty and the runtime is not production, fall back to the built-in local origins with a warning.
- Keep the current production error path for empty origins.

**Step 2: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py -k cors -v`

Expected: the new fallback test passes and the production tests remain green.

**Step 3: Commit**

```bash
git add tldw_Server_API/app/main.py tldw_Server_API/app/core/config.py
git commit -m "fix: fall back to local cors origins outside production"
```

### Task 3: Update Self-Host Documentation

**Files:**
- Modify: `tldw_Server_API/Config_Files/.env.example`
- Modify: `Docs/Operations/Env_Vars.md`
- Modify: `tldw_Server_API/Config_Files/README.md`

**Step 1: Update docs**

- Explain that local browser access works by default on localhost/loopback.
- Explain that `ALLOWED_ORIGINS` is only needed when using a different browser origin.
- Keep production guidance explicit.

**Step 2: Review docs**

Verify the wording avoids forcing first-time self-hosters to understand CORS terminology before first run.

**Step 3: Commit**

```bash
git add tldw_Server_API/Config_Files/.env.example Docs/Operations/Env_Vars.md tldw_Server_API/Config_Files/README.md
git commit -m "docs: clarify local cors defaults for self-hosting"
```

### Task 4: Final Verification

**Files:**
- Modify: none

**Step 1: Run targeted tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py -k cors -v`

**Step 2: Run Bandit on touched scope**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/main.py tldw_Server_API/app/core/config.py tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py -f json -o /tmp/bandit_cors_selfhost_onboarding.json`

**Step 3: Commit**

```bash
git add Docs/Plans/2026-03-19-cors-selfhost-onboarding-design.md Docs/Plans/2026-03-19-cors-selfhost-onboarding-implementation-plan.md
git commit -m "docs: capture cors self-host onboarding plan"
```
