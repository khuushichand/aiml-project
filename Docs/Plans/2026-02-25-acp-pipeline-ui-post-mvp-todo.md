# ACP Pipeline UI Post-MVP Todo (2026-02-25)

Scope: deferred frontend work for ACP-centric workflow pipelines after backend completion.

## Core UX Backlog

- [ ] Add ACP pipeline run timeline view (stage-by-stage progression across `req/plan/impl/test`).
- [ ] Add `wait_for_approval` decision controls in run details (`approve`/`reject`, comment capture).
- [ ] Add ACP session inspector panel (`session_id`, `workspace_id`, `workspace_group_id`, stage metadata).
- [ ] Add governance/error visualization for normalized ACP outcomes (`acp_governance_blocked`, `acp_timeout`, `acp_prompt_error`, `review_loop_exceeded`).
- [ ] Add artifact/event drill-down links from each ACP stage output block.

## Template UX Backlog

- [ ] Add template picker cards for `pipeline_l1_acp`, `pipeline_l2_acp`, and `pipeline_l3_acp`.
- [ ] Add domain-only scope badge and explanatory copy in template details.
- [ ] Add required input hints for reviewer and workspace fields (`reviewer_user_id`, `workspace_id`, `workspace_group_id`).

## Integration Follow-On (ACP + Sandbox)

- [ ] Add workspace/instance launch panel when sandbox module integration lands.
- [ ] Add per-run workspace lifecycle status indicator (provisioning, ready, teardown).
- [ ] Add stage-level links to ACP/sandbox diagnostics when available.
