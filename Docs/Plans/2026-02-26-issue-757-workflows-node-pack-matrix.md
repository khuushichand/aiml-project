# Workflows Node Pack Matrix (Issue #757)

## Scope Snapshot (2026-02-26)
- Registry step types: `126`
- Adapter-registered step types: `124`
- Engine-native step types (handled directly in workflow engine): `wait_for_human`, `wait_for_approval`
- Uncovered step types: `0`

## Delivery Pack 1 (Shipped Locally)
1. Runtime coverage guard test:
   - Added `tldw_Server_API/tests/Workflows/test_step_registry_runtime_coverage.py`
   - Enforces that every step in `StepTypeRegistry` is either:
     - registered in adapter registry, or
     - explicitly handled by engine-native control flow.
2. Coverage semantics locked:
   - Adding a new step type now requires runtime support to keep tests green.
   - Prevents silent drift between workflow catalog and executable runtime.

## Practical Closure Criteria
- “More nodes” scope is no longer open-ended: catalog/runtime alignment is test-enforced.
- First delivery pack is concrete and executable: new quality gate + matrix snapshot.
