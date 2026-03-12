# Model Pricing Refresh Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refresh `model_pricing.json` with current provider-backed pricing for the most actively used hosted model families and cover the refresh with a catalog regression test.

**Architecture:** Update the static pricing override catalog in place, keeping the existing provider/model schema and per-1K token units. Verify the refreshed entries through `PricingCatalog`, which lowercases and merges the JSON overrides at runtime.

**Tech Stack:** JSON config, Python pytest, FastAPI backend pricing catalog loader

---

### Task 1: Refresh pricing catalog entries

**Files:**
- Modify: `tldw_Server_API/Config_Files/model_pricing.json`

**Step 1: Write the refreshed provider entries**

Update the `openai`, `anthropic`, `moonshot`, and `zai` sections with current model names and per-1K token prices derived from the official provider pricing pages.

**Step 2: Preserve schema compatibility**

Keep the existing `prompt` and `completion` fields, and only use extra metadata when the current file already does so.

**Step 3: Validate JSON formatting**

Run: `python -m json.tool tldw_Server_API/Config_Files/model_pricing.json >/tmp/model_pricing_pretty.json`
Expected: command succeeds with no JSON parse errors.

### Task 2: Add regression coverage

**Files:**
- Modify: `tldw_Server_API/tests/Usage/test_pricing_catalog.py`

**Step 1: Add exact-rate assertions**

Add a test that instantiates `PricingCatalog` and verifies exact, non-estimated lookups for representative refreshed entries.

**Step 2: Cover free and formerly-placeholder models**

Assert that a free model can resolve as an exact catalog entry and that a formerly-placeholder OpenAI model now returns concrete prices.

**Step 3: Run the focused test file**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Usage/test_pricing_catalog.py -v`
Expected: PASS.

### Task 3: Verify and security-check touched scope

**Files:**
- Modify: `docs/plans/2026-03-06-model-pricing-refresh-implementation-plan.md`

**Step 1: Run targeted verification**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Usage/test_pricing_catalog.py -v`
Expected: PASS.

**Step 2: Run Bandit on touched Python scope**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/tests/Usage/test_pricing_catalog.py -f json -o /tmp/bandit_model_pricing_refresh.json`
Expected: command succeeds; no new actionable findings in touched code.
