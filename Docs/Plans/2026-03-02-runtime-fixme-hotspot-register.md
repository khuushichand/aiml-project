# Runtime FIXME Hotspot Register (2026-03-02)

This register tracks runtime-path `FIXME/TODO` hotspots called out by the remediation plan.

| Hotspot | Path | Runtime Risk | Contract Test | Status | Owner |
| --- | --- | --- | --- | --- | --- |
| CORS wildcard policy in production | `tldw_Server_API/app/main.py` | Broad cross-origin exposure in prod deployments | `tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py` | Completed in this batch | Maintainer + codex/stability-core-cleanup |
| Runtime TTS placeholder defaults | `tldw_Server_API/app/core/config.py` | Placeholder literals leaking into live runtime config | `tldw_Server_API/tests/Config/test_config_precedence_contract.py` | Completed in this batch | Maintainer + codex/stability-core-cleanup |
| Sync write path logs `FTS Disabled` and bypasses FTS refresh | `tldw_Server_API/app/api/v1/endpoints/sync.py` | Sync writes may not surface in FTS-backed search | `tldw_Server_API/tests/Security/test_runtime_fixme_hotspots.py` (scaffold), planned dedicated sync/search test in Task 4 | Deferred to Task 4 | Maintainer + codex/stability-core-cleanup |
| Prompt config placeholders | `tldw_Server_API/app/core/config.py` | Low (non-critical runtime path) | N/A in this batch | Backlog | Maintainer |

## Exit Criteria For This Plan

- Task 1: Register exists and baseline hotspot contract tests are runnable.
- Task 2: Production-mode wildcard CORS is blocked by startup validation, with regression tests.
- Task 3: Runtime config contract ensures no placeholder literals are emitted in runtime settings.
- Task 4: Sync write path updates/maintains FTS integrity with regression coverage.
