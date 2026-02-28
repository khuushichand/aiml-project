# Last 25 Open Issues Closeout Packet (Local-Only)

Generated: 2026-02-25 23:35:50 PST
Branch: `codex/batch1-open-issues-20260226`
Execution mode: Grouped batch execution (local only, no GitHub issue comments posted)

## Commit Groups

| Group | Commit | Scope |
|---|---|---|
| Integrations batch | `c138c8c69` | Slack/Discord/ACP implementation and tests for issues `#739-#750` and `#774-#781` |
| Issue #752 | `b29ece1ab` | Image prompt refinement (`off/auto/basic`) with docs and tests |
| Issue #758 | `470f89bcb` | Reading import normalization and quality improvements with docs/tests |
| Issue #757 | `34b879f83` | Workflows node-pack scope/matrix and runtime registry coverage guard |

## Consolidated Verification Evidence

- Impacted suite pass: `python -m pytest -q tldw_Server_API/tests/Slack tldw_Server_API/tests/Discord tldw_Server_API/tests/Agent_Client_Protocol tldw_Server_API/tests/Image_Generation/test_prompt_refinement.py tldw_Server_API/tests/Files/test_image_adapter_prompt_refinement_unit.py tldw_Server_API/tests/Collections/test_reading_import_normalization.py tldw_Server_API/tests/Collections/test_reading_service.py tldw_Server_API/tests/Workflows/adapters/test_content_adapters.py tldw_Server_API/tests/Workflows/test_step_registry_runtime_coverage.py`
- Result: `219 passed`
- Consolidated Bandit report: `/tmp/bandit_last25_grouped_closure.json` (0 findings)
- Additional batch/issue Bandit evidence:
  - `/tmp/bandit_batch4_hardening.json`
  - `/tmp/bandit_issue_752_prompt_refinement.json`
  - `/tmp/bandit_issue_758_reading_import_quality.json`
  - `/tmp/bandit_issue_757_workflows_nodes.json`

## Per-Issue Closure Matrix
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

## Closure Notes

- Epics `#772` and `#773` are closure-ready locally based on completed child issue sets documented above.
- Batch 0 pre-flight/DoD gates are marked complete in the checklist.
- This packet is intended for local closeout tracking and manual issue closure steps when desired.
