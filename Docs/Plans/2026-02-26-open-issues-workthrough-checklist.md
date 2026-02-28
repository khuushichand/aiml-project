# Open Issues Workthrough Checklist (Local-Only)

**Intent:** Execute the latest 25 open issues in controlled batches or strict one-by-one order.

**Constraint:** Do not post planning comments to GitHub issues during execution.

---

## Operating Modes

### Mode A: Grouped Batches (recommended)

1. **Batch 0: Pre-flight**
- [x] Confirm Track 2 hardening prerequisites for ACP follow-on tracks.
- [x] Confirm Definition of Done for each issue:
  - tests green,
  - docs updated,
  - Bandit clean on touched scope,
  - issue acceptance criteria satisfied.

2. **Batch 1: Integration Foundations**
- [x] #739 Slack ingress/security foundation
- [x] #745 Discord ingress/security foundation
- [x] #774 ACP bootstrap provisioning contract
- [x] #778 ACP run-control contract

3. **Batch 2: Lifecycle + Routing**
- [x] #740 Slack OAuth/install lifecycle
- [x] #741 Slack parser/routing
- [x] #746 Discord app/install lifecycle
- [x] #747 Discord parser/routing
- [x] #775 ACP metadata propagation
- [x] #779 ACP status schema

4. **Batch 3: Async + Query Surfaces**
- [x] #742 Slack async jobs/replies
- [x] #748 Discord async jobs/replies
- [x] #780 ACP artifact/event queries

5. **Batch 4: Governance + Hardening**
- [x] #743 Slack tenant/policy controls
- [x] #744 Slack test/metrics/hardening
- [x] #749 Discord tenant/policy controls
- [x] #750 Discord test/metrics/hardening
- [x] #776 ACP teardown/reconciliation
- [x] #777 ACP diagnostic normalization
- [x] #781 ACP authz/rate-limit/audit hardening

6. **Batch 5: Standalone Enhancements**
- [x] #752 image generation prompt quality
- [x] #758 read-it-later improvements
- [x] #757 workflows more-nodes scope + first delivery pack

7. **Batch 6: Epic Closures**
- [x] #772 close after #774-#777 are done
- [x] #773 close after #778-#781 are done

### Mode B: Strict One-by-One Order

- [x] #739
- [x] #740
- [x] #741
- [x] #742
- [x] #743
- [x] #744
- [x] #745
- [x] #746
- [x] #747
- [x] #748
- [x] #749
- [x] #750
- [x] #774
- [x] #775
- [x] #776
- [x] #777
- [x] #778
- [x] #779
- [x] #780
- [x] #781
- [x] #752
- [x] #758
- [x] #757
- [x] #772
- [x] #773

---

## Per-Issue Execution Template

Use this checklist for each issue before marking it complete:

- [ ] Create branch: `codex/issue-<number>-<slug>`
- [ ] Write/update failing tests first
- [ ] Implement minimal passing change
- [ ] Run targeted tests
- [ ] Run broader impacted suite
- [ ] Run Bandit on touched paths
- [ ] Update docs/design notes
- [ ] Capture closure evidence in local notes

Suggested verification commands:

```bash
source .venv/bin/activate
python -m pytest -v <targeted_tests>
python -m bandit -r <touched_paths> -f json -o /tmp/bandit_issue_<number>.json
```

---

## Local Progress Tracker

| Issue | Batch | Status | Branch | Tests | Bandit | Docs | Ready to Close |
|---|---|---|---|---|---|---|---|
| #739 | 1 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tests/Slack + tests/Workflows` | `/tmp/bandit_batch1_739_745.json` clean | Checklist updated | Yes |
| #740 | 2 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tests/Slack/test_slack_oauth_lifecycle.py` + Slack foundation suite | `/tmp/bandit_batch1_batch2_slack_discord.json` clean | Checklist updated | Yes |
| #741 | 2 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tests/Slack/test_slack_command_routing.py` + Slack suites | `/tmp/bandit_batch1_batch2_slack_discord.json` clean | Checklist updated | Yes |
| #742 | 3 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tests/Slack/test_slack_command_routing.py` + Slack suites | `/tmp/bandit_batch1_batch3_slack_discord.json` clean | Checklist updated | Yes |
| #743 | 4 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tldw_Server_API/tests/Slack/test_slack_policy_hardening.py` + Slack/Discord/ACP impacted suite (`99 passed`) | `/tmp/bandit_batch4_hardening.json` clean | Checklist updated | Yes |
| #744 | 4 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tldw_Server_API/tests/Slack tldw_Server_API/tests/Discord tldw_Server_API/tests/Agent_Client_Protocol` | `/tmp/bandit_batch4_hardening.json` clean | Checklist updated | Yes |
| #745 | 1 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tests/Discord + tests/Slack + tests/Workflows` | `/tmp/bandit_batch1_739_745.json` clean | Checklist updated | Yes |
| #746 | 2 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tests/Discord/test_discord_oauth_lifecycle.py` + Discord foundation suite | `/tmp/bandit_batch1_batch2_slack_discord.json` clean | Checklist updated | Yes |
| #747 | 2 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tests/Discord/test_discord_command_routing.py` + Discord suites | `/tmp/bandit_batch1_batch2_slack_discord.json` clean | Checklist updated | Yes |
| #748 | 3 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tests/Discord/test_discord_command_routing.py` + Discord suites | `/tmp/bandit_batch1_batch3_slack_discord.json` clean | Checklist updated | Yes |
| #749 | 4 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tldw_Server_API/tests/Discord/test_discord_policy_hardening.py` + Slack/Discord/ACP impacted suite (`99 passed`) | `/tmp/bandit_batch4_hardening.json` clean | Checklist updated | Yes |
| #750 | 4 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tldw_Server_API/tests/Slack tldw_Server_API/tests/Discord tldw_Server_API/tests/Agent_Client_Protocol` | `/tmp/bandit_batch4_hardening.json` clean | Checklist updated | Yes |
| #752 | 5 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tldw_Server_API/tests/Image_Generation/test_prompt_refinement.py tldw_Server_API/tests/Files/test_image_adapter_prompt_refinement_unit.py tldw_Server_API/tests/Workflows/adapters/test_content_adapters.py -k "prompt_refinement"` | `/tmp/bandit_issue_752_prompt_refinement.json` clean | Image generation docs updated | Yes |
| #757 | 5 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tldw_Server_API/tests/Workflows/test_step_registry_runtime_coverage.py` | `/tmp/bandit_issue_757_workflows_nodes.json` clean | Node pack matrix + plan updated | Yes |
| #758 | 5 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tldw_Server_API/tests/Collections/test_reading_import_normalization.py tldw_Server_API/tests/Collections/test_reading_service.py -k "normalize_domain_and_read_at or normalize_import_items"` | `/tmp/bandit_issue_758_reading_import_quality.json` clean | Reading API docs updated | Yes |
| #772 | 6 | Closure-ready locally (children complete) | `codex/batch1-open-issues-20260226` | Child issues `#774/#775/#776/#777` verified in checklist | N/A (epic closure) | Checklist updated | Yes |
| #773 | 6 | Closure-ready locally (children complete) | `codex/batch1-open-issues-20260226` | Child issues `#778/#779/#780/#781` verified in checklist | N/A (epic closure) | Checklist updated | Yes |
| #774 | 1 | Validated in existing implementation | `codex/batch1-open-issues-20260226` | `pytest -q tests/Agent_Client_Protocol/test_acp_endpoints.py::test_acp_session_new_forwards_tenancy_fields` + sandbox runner suite | N/A (no code change) | Checklist updated | Yes |
| #775 | 2 | Implemented/validated locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tests/Agent_Client_Protocol/test_acp_endpoints.py tests/Agent_Client_Protocol/test_acp_status_schema.py` | N/A (tests-only for ACP scope) | Checklist updated | Yes |
| #776 | 4 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tldw_Server_API/tests/Agent_Client_Protocol/test_acp_hardening_controls.py` + ACP impacted suite | `/tmp/bandit_batch4_hardening.json` clean | Checklist updated | Yes |
| #777 | 4 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tldw_Server_API/tests/Agent_Client_Protocol/test_acp_hardening_controls.py` + ACP impacted suite | `/tmp/bandit_batch4_hardening.json` clean | Checklist updated | Yes |
| #778 | 1 | Validated in existing implementation | `codex/batch1-open-issues-20260226` | `pytest -q tests/Agent_Client_Protocol/test_acp_endpoints.py::test_acp_session_cancel_and_close` + endpoint suite | N/A (no code change) | Checklist updated | Yes |
| #779 | 2 | Implemented/validated locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tests/Agent_Client_Protocol/test_acp_status_schema.py` | N/A (tests-only for ACP scope) | Checklist updated | Yes |
| #780 | 3 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tests/Agent_Client_Protocol/test_acp_status_schema.py` + ACP suite | `/tmp/bandit_batch1_batch3_all.json` clean | Checklist updated | Yes |
| #781 | 4 | Implemented locally (pending merge) | `codex/batch1-open-issues-20260226` | `pytest -q tldw_Server_API/tests/Agent_Client_Protocol/test_acp_hardening_controls.py` + Slack/Discord/ACP impacted suite (`99 passed`) | `/tmp/bandit_batch4_hardening.json` clean | Checklist updated | Yes |

## Execution Notes

- 2026-02-26: Completed local foundation implementation and verification for `#739` and `#745` in grouped Batch 1 mode without posting to GitHub issues.
- 2026-02-26: Verified `#774` (session bootstrap provisioning contract) and `#778` (run-control contract) are already covered by ACP endpoint/sandbox tests and current codepaths.
- 2026-02-26: Completed `#740` locally with OAuth start/callback, encrypted installation persistence, and admin list/toggle/delete endpoints; verified with dedicated Slack OAuth tests.
- 2026-02-26: Completed `#746` locally with Discord OAuth start/callback, encrypted installation persistence, and admin list/toggle/delete endpoints; verified with dedicated Discord OAuth tests.
- 2026-02-26: Completed `#741` and `#747` locally with command parser/routing for `help|ask|rag|summarize|status`, mention/default-ask behavior, and usage guidance for unknown commands.
- 2026-02-26: Completed `#775` and `#779` locally by adding ACP session status-schema/tenancy propagation tests (`list/detail/usage`) and revalidating existing ACP endpoint contracts.
- 2026-02-26: Completed `#742` and `#748` locally by wiring async command handoff to Jobs (`domain=slack|discord`, `queue=default`) with job-id/status query surfaces.
- 2026-02-26: Completed `#780` locally by adding ACP session `events` and `artifacts` query endpoints and contract tests.
- 2026-02-26: Completed Batch 4 local hardening set `#743/#744/#749/#750/#776/#777/#781` with Slack+Discord tenant policy controls, ACP teardown/diagnostics/audit/rate-limit surfaces, targeted tests, impacted suite (`99 passed`), and clean Bandit report at `/tmp/bandit_batch4_hardening.json`.
- 2026-02-26: Completed `#752` locally by adding deterministic image prompt refinement (`off|auto|basic`) with request-level opt-in/opt-out in Files + Workflows image entrypoints, unit coverage, and docs updates; verified with targeted tests and clean Bandit report at `/tmp/bandit_issue_752_prompt_refinement.json`.
- 2026-02-26: Completed `#758` locally by improving read-it-later import quality: canonical URL normalization + duplicate merge semantics + status/read_at enrichment + domain/title backfill, with targeted tests and clean Bandit report at `/tmp/bandit_issue_758_reading_import_quality.json`.
- 2026-02-26: Completed `#757` locally by shipping a workflows node-pack closure pack: runtime coverage guard test for registry-vs-handler alignment and node-pack scope matrix documenting full catalog coverage (adapter-registered + engine-native wait nodes).
- 2026-02-26: Marked epics `#772` and `#773` closure-ready locally after dependent child issue sets (`#774-#777` and `#778-#781`) were fully implemented and verified.
- 2026-02-26: Completed grouped closure verification for the full last-25 touched scope with consolidated impacted-suite execution (`219 passed`) and clean Bandit report at `/tmp/bandit_last25_grouped_closure.json`, satisfying Batch 0 DoD gates locally.
