# PR 898 Review Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Resolve the validated review findings on PR #898 without widening the scope into unrelated architectural refactors.

**Architecture:** Keep the existing module structure intact and patch the concrete defects in-place. Use test-first changes in each affected area so the fixes stay attributable and regressions remain localized.

**Tech Stack:** Python, FastAPI, pytest, aiosqlite, SQLite/PostgreSQL compatibility paths, Bandit

---

### Task 1: Baseline The Impacted Review Area

**Files:**
- Modify: `docs/plans/2026-03-17-pr-898-review-fixes.md`
- Test: `tldw_Server_API/tests/AuthNZ/test_consent_endpoints.py`
- Test: `tldw_Server_API/tests/AuthNZ/test_audit_chain_integration.py`
- Test: `tldw_Server_API/tests/Billing/test_overage_enforcement_integration.py`
- Test: `tldw_Server_API/tests/Jobs/test_fair_share_integration.py`
- Test: `tldw_Server_API/tests/test_stripe_metering.py`

**Step 1: Run the impacted tests before any code changes**

Run:
```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/AuthNZ/test_consent_endpoints.py \
  tldw_Server_API/tests/AuthNZ/test_audit_chain_integration.py \
  tldw_Server_API/tests/Billing/test_overage_enforcement_integration.py \
  tldw_Server_API/tests/Jobs/test_fair_share_integration.py \
  tldw_Server_API/tests/test_stripe_metering.py -v
```

Expected:
- Existing tests pass or reveal current branch failures that match the review findings.

**Step 2: Record the baseline result in the working notes**

Update this plan if unexpected failures appear that are unrelated to the review scope.

### Task 2: Fix Consent Router Wiring And Endpoint Cleanup

**Files:**
- Modify: `tldw_Server_API/app/main.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/consent.py`
- Test: `tldw_Server_API/tests/AuthNZ/test_consent_endpoints.py`

**Step 1: Write the failing tests**

Add tests that verify:
- The production import/include path in `main.py` exposes the consent router.
- `grant_consent()` reads `request.client.host` and `request.headers.get("user-agent")` without swallowing broad exceptions.

**Step 2: Run the consent tests to verify the new assertions fail**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/AuthNZ/test_consent_endpoints.py -v
```

Expected:
- Failure showing the consent router is not available in the normal app path and/or the new endpoint expectation is unmet.

**Step 3: Write the minimal implementation**

Implement:
- Production import/include of `consent_router` in `tldw_Server_API/app/main.py`
- Direct `request.client.host if request.client else None`
- Direct `request.headers.get("user-agent")`

**Step 4: Run the consent tests to verify they pass**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/AuthNZ/test_consent_endpoints.py -v
```

Expected:
- PASS

### Task 3: Preserve Audit Chain Continuity Across Restarts

**Files:**
- Modify: `tldw_Server_API/app/core/Audit/unified_audit_service.py`
- Test: `tldw_Server_API/tests/AuthNZ/test_audit_chain_integration.py`

**Step 1: Write the failing restart-continuity test**

Add a test that:
- Flushes an initial batch to a DB
- Stops the service
- Creates a second service instance against the same DB
- Flushes another batch
- Verifies `verify_audit_chain()` succeeds across all rows

**Step 2: Run the audit tests to verify the new test fails**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/AuthNZ/test_audit_chain_integration.py -v
```

Expected:
- Failure showing the chain breaks after service recreation.

**Step 3: Write the minimal implementation**

Implement:
- A helper to load the last persisted `chain_hash`
- Initialization logic that hydrates `self._last_chain_hash` after schema setup
- Deterministic ordering compatible with persisted insertion order

**Step 4: Run the audit tests to verify they pass**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/AuthNZ/test_audit_chain_integration.py -v
```

Expected:
- PASS

### Task 4: Correct Billing Enforcement Policy Handling

**Files:**
- Modify: `tldw_Server_API/app/core/Billing/enforcement.py`
- Test: `tldw_Server_API/tests/Billing/test_overage_enforcement_integration.py`

**Step 1: Write the failing tests**

Add tests that verify:
- `OveragePolicy.from_env()` is not called on every `check_limit()` invocation
- Overage-policy evaluation failures are logged at warning level

**Step 2: Run the billing tests to verify the new assertions fail**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Billing/test_overage_enforcement_integration.py -v
```

Expected:
- Failure showing repeated env parsing or insufficient logging.

**Step 3: Write the minimal implementation**

Implement:
- Cached policy initialization in `BillingEnforcer.__init__`
- `warning` level logging when policy evaluation is skipped

**Step 4: Run the billing tests to verify they pass**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Billing/test_overage_enforcement_integration.py -v
```

Expected:
- PASS

### Task 5: Correct Fair-Share Priority Semantics

**Files:**
- Modify: `tldw_Server_API/app/core/Jobs/manager.py`
- Test: `tldw_Server_API/tests/Jobs/test_fair_share_integration.py`

**Step 1: Write the failing priority-direction test**

Add a test that verifies a user with lower active job count gets a smaller numeric stored priority than a neutral explicit value when fair-share boosts urgency.

**Step 2: Run the jobs tests to verify the new assertion fails**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Jobs/test_fair_share_integration.py -v
```

Expected:
- Failure showing fair-share currently pushes the numeric priority in the wrong direction.

**Step 3: Write the minimal implementation**

Implement:
- Fair-share score to DB priority mapping where larger score becomes smaller numeric priority
- `min(priority, mapped_fair_priority)`
- `warning` level logging when fair-share checks are skipped

**Step 4: Run the jobs tests to verify they pass**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Jobs/test_fair_share_integration.py -v
```

Expected:
- PASS

### Task 6: Harden Stripe Metering Compatibility

**Files:**
- Modify: `tldw_Server_API/app/services/stripe_metering_service.py`
- Test: `tldw_Server_API/tests/test_stripe_metering.py`

**Step 1: Write the failing tests**

Add tests that verify:
- `_query_usage_for_date()` falls back cleanly when `bytes_in_total` is unavailable
- `_query_user_subscription()` can find an active org subscription through `organizations.owner_user_id`

**Step 2: Run the Stripe metering tests to verify the new assertions fail**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_stripe_metering.py -v
```

Expected:
- Failure showing the schema fallback and owner lookup are missing.

**Step 3: Write the minimal implementation**

Implement:
- Legacy-schema fallback in `_query_usage_for_date()`
- Owner fallback query in `_query_user_subscription()`

**Step 4: Run the Stripe metering tests to verify they pass**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/test_stripe_metering.py -v
```

Expected:
- PASS

### Task 7: Final Verification

**Files:**
- Modify: `docs/plans/2026-03-17-pr-898-review-fixes.md`
- Test: `tldw_Server_API/tests/AuthNZ/test_consent_endpoints.py`
- Test: `tldw_Server_API/tests/AuthNZ/test_audit_chain_integration.py`
- Test: `tldw_Server_API/tests/Billing/test_overage_enforcement_integration.py`
- Test: `tldw_Server_API/tests/Jobs/test_fair_share_integration.py`
- Test: `tldw_Server_API/tests/test_stripe_metering.py`

**Step 1: Run the full impacted test subset**

Run:
```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/AuthNZ/test_consent_endpoints.py \
  tldw_Server_API/tests/AuthNZ/test_audit_chain_integration.py \
  tldw_Server_API/tests/Billing/test_overage_enforcement_integration.py \
  tldw_Server_API/tests/Jobs/test_fair_share_integration.py \
  tldw_Server_API/tests/test_stripe_metering.py -v
```

Expected:
- PASS

**Step 2: Run Bandit on the touched paths**

Run:
```bash
source .venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/consent.py \
  tldw_Server_API/app/core/Audit/unified_audit_service.py \
  tldw_Server_API/app/core/Billing/enforcement.py \
  tldw_Server_API/app/core/Jobs/manager.py \
  tldw_Server_API/app/services/stripe_metering_service.py \
  -f json -o /tmp/bandit_pr898_review_fixes.json
```

Expected:
- No new security findings in touched code
