## Stage 1: Validate Parked Findings
**Goal**: Confirm which previously parked issues are still real and which are already fixed or harness-only.
**Success Criteria**: The remaining work list contains only reproducible unresolved issues.
**Tests**: Focused existing tests for the media trash/undo and bulk-action paths.
**Status**: Complete

## Stage 2: Remove Misleading Runtime Probe Debt
**Goal**: Clean up the built-extension runtime spec so it stops running raw `chrome.runtime` ping probes that are known to be harness-only noise.
**Success Criteria**: The packaged runtime spec still validates seeded config and real app surfaces without raw callback/promise/port ping diagnostics.
**Tests**: Focused Playwright runtime spec run or targeted source/guard verification.
**Status**: Complete

## Stage 3: Verify and Record Outcome
**Goal**: Run targeted verification and document what was fixed versus what was already resolved.
**Success Criteria**: Relevant tests pass, Bandit is clean on the touched scope, and the audit log reflects the cleanup.
**Tests**: Targeted Vitest/Playwright runs plus Bandit on touched files.
**Status**: Complete

## Outcome
- The previously parked media trash/undo issue was already fixed in the product code. Focused media permalink and bulk-action tests stayed green, so no further product patch was needed in this cleanup pass.
- `apps/extension/tests/e2e/built-extension-runtime.spec.ts` no longer runs raw callback/promise/port ping diagnostics or fake `e2e:test-listener` probes. It now validates seeded config, service worker presence, and the real packaged options plus sidepanel `/chat` surfaces only.
- `apps/extension/tests/e2e/utils/extension.ts` no longer injects a synthetic runtime listener or logs timeout noise on every unpacked extension launch.
- `apps/extension/tests/e2e/context-menu-actions.spec.ts` no longer relies on the synthetic listener. It now checks real `action.onClicked` and `contextMenus.onClicked` listener registration in the background worker.
- Verification:
  - `apps/extension/tests/e2e/built-extension-runtime.spec.ts`: `1/1` passed outside the sandbox
  - `apps/extension/tests/e2e/background-proxy-api.spec.ts` + `apps/extension/tests/e2e/context-menu-actions.spec.ts`: `4 passed`, `1 skipped` outside the sandbox
  - `python -m bandit -r ... -f json -o /tmp/bandit_extension_runtime_harness_cleanup.json`: `0` findings
