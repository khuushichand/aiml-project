# Resource Governor PRD Closeout Tracker (Stage 5 Follow-Through)

## Context

This tracker is the closeout plan for the remaining work to fully complete:

- `Docs/Product/Completed/AuthNZ-Refactor/Resource_Governor_PRD.md`
- `Docs/Plans/IMPLEMENTATION_PLAN_authnz_refactor_remaining_items.md` (Stage 5)
- `Docs/Product/Completed/AuthNZ-PRDs_POST_V0_1_TRACKER.md` (Stage 9A/9B/9C operational tracker)

As of 2026-02-10, Stage 4 is complete and Stage 5 is in progress. The primary blocker for full PRD closure is release-window evidence for near-zero RG shadow mismatch on representative traffic.

---

## Current Remaining Work (Blocking vs Follow-Up)

### Blocking (must complete before PRD closeout)

1. Release-window evidence gate (representative traffic)
   - Collect a full, stable validation window and produce a formal report.
   - Demonstrate near-zero drift in `rg_shadow_decision_mismatch_total`.
   - Demonstrate expected policy coverage for governed surfaces.

### Post-gate follow-through (after release-window pass)

1. Remove/retire remaining compatibility-only limiter shims where safe
   - Complete planned demotion/removal after one stable release window.
   - Ensure no route double-enforces and no regressions in headers/429 semantics.
2. Final docs/env hardening pass
   - Ensure operator docs reference RG policies/envs as source of truth.
   - Keep any intentionally retained module-specific knobs explicitly scoped (for example MCP/Character Chat where applicable).
3. Closeout bookkeeping
   - Mark Stage 5 complete in the active AuthNZ refactor plan.
   - Add a final closure note in PRD tracker docs with artifact links.

---

## Stage A: Release-Window Evidence (Blocker)

**Goal**: Satisfy the Stage 5 release-window success criterion with auditable evidence.

**Success Criteria**:
- Window duration is at least 168 hours (or approved alternate window).
- `rg_shadow_decision_mismatch_total` drift is near-zero for the full window.
- Mismatch rate stays within agreed threshold (default target: <= 1%).
- Expected policy IDs are observed in `rg_decisions_total`.
- No counter-reset/data-quality issues invalidate the window.

**Required Artifacts**:
- Snapshot set: `stage9a_window/*.prom` (or equivalent metrics captures).
- Generated report (markdown): `stage9a_release_window.md`.
- Short decision summary with pass/fail and rationale.

**Runbook**:
```bash
source .venv/bin/activate

# During the window, capture periodic snapshots (example cadence handled by operator tooling)
python Helper_Scripts/rg_stage9a_parity_window.py snapshot --out stage9a_window/snap_$(date +%Y%m%d_%H%M%S).prom

# End-of-window analysis/report
python Helper_Scripts/rg_stage9a_parity_window.py release-window-report \
  --snapshots-glob "stage9a_window/*.prom" \
  --min-window-hours 168 \
  --mismatch-rate-threshold 0.01 \
  --out-md stage9a_release_window.md
```

**Status**: In Progress (external traffic evidence pending)

---

## Stage B: Post-Window Hard Removal

**Goal**: Finalize retirement/removal after release-window gate passes.

**Success Criteria**:
- Diagnostics-only compatibility shims that are no longer needed are removed or explicitly deferred with rationale.
- No double-enforcement in RG-enabled paths.
- Header/429 parity remains stable for memory and Redis backends.

**Validation Bundle**:
```bash
source .venv/bin/activate
pytest -q \
  tldw_Server_API/tests/Resource_Governance \
  tldw_Server_API/tests/AuthNZ/unit/test_rate_limiter_bootstrap.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_auth_deps_hardening.py \
  tldw_Server_API/tests/AuthNZ/unit/test_require_admin_callsite_guardrail.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_auth_deps_legacy_admin_shim_removed.py
```

**Status**: Pending Stage A pass

---

## Stage C: PRD Closure & Documentation Sign-Off

**Goal**: Close the PRD with traceable evidence and status updates.

**Success Criteria**:
- Stage 5 marked complete in `Docs/Plans/IMPLEMENTATION_PLAN_authnz_refactor_remaining_items.md`.
- PRD/tracker docs include closure date, evidence links, and final verification command output summary.
- Any intentional deferred items are documented with owner and rationale.

**Status**: Pending Stage A/B completion

---

## Decision Log

- 2026-02-10: Created this closeout tracker to isolate remaining Stage 5 work from completed Stage 4/early Stage 5 migrations and cleanups.
- 2026-02-10: Confirmed primary blocker is representative release-window evidence; tooling debt is closed via `rg_stage9a_parity_window.py release-window-report`.

