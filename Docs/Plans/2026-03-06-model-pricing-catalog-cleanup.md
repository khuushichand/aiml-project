# Model Pricing Catalog Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove outdated model IDs from the pricing catalog while preserving only clear rename-based compatibility aliases.

**Architecture:** Prune stale model entries directly from `model_pricing.json`, add a small top-level `model_aliases` block for safe migrations, and verify both pricing enumeration and alias resolution through existing catalog/chat helpers. The cleanup should change advertised provider model lists without changing how current documented models are priced.

**Tech Stack:** JSON config, Python pytest, pricing catalog loader, chat alias loader

---

### Task 1: Add failing coverage for cleanup behavior

**Files:**
- Modify: `tldw_Server_API/tests/Usage/test_pricing_catalog.py`

**Step 1: Write the failing test**

Add assertions that stale models are absent from `list_provider_models()` and that alias-backed legacy IDs are mapped via the catalog alias loader.

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Usage/test_pricing_catalog.py -v`
Expected: FAIL because stale models are still present and aliases are not yet defined.

**Step 3: Write minimal implementation**

Update the catalog to remove stale entries and define only the needed aliases.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Usage/test_pricing_catalog.py -v`
Expected: PASS.

### Task 2: Prune catalog and add compatibility aliases

**Files:**
- Modify: `tldw_Server_API/Config_Files/model_pricing.json`

**Step 1: Remove stale provider entries**

Delete outdated or unavailable model IDs from the provider blocks identified by the approved design.

**Step 2: Add alias block**

Add a top-level `model_aliases` mapping for only clear rename paths, keyed by provider.

**Step 3: Validate JSON**

Run: `source .venv/bin/activate && python -m json.tool tldw_Server_API/Config_Files/model_pricing.json >/tmp/model_pricing_cleanup_pretty.json`
Expected: command succeeds with no parse errors.

### Task 3: Verify touched scope and security check

**Files:**
- Modify: `docs/plans/2026-03-06-model-pricing-catalog-cleanup.md`

**Step 1: Run focused verification**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Usage/test_pricing_catalog.py -v`
Expected: PASS.

**Step 2: Run Bandit on touched Python scope**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/tests/Usage/test_pricing_catalog.py -f json -o /tmp/bandit_model_pricing_cleanup.json`
Expected: command succeeds; only expected test-file `assert` findings, no new actionable issues.
