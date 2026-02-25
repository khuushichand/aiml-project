# Governance Operations (MCP + ACP)

This guide documents governance rollout controls, compatibility guarantees, and
operational checks for the unified governance plane used by MCP and ACP paths.

## Rollout Modes

Supported rollout values:
- `off`
- `shadow`
- `enforce`

Resolution order:
1. Explicit runtime value (if supplied by caller)
2. `GOVERNANCE_ROLLOUT_MODE` environment variable
3. `config.txt` `[Governance] rollout_mode`
4. Default `off`

Invalid values fall back to `off`.

## MCP Wire Compatibility

Compatibility contract:
- Existing JSON-RPC error code behavior is unchanged.
- Governance denial details are additive and appear in `error.data.governance`.
- `governance.*` tool calls bypass governance preflight to prevent recursion.
- Requests with `context.metadata.governance_bypass=true` bypass preflight.

This preserves existing MCP client parsing logic while exposing richer policy
decision context for upgraded clients.

## ACP Governance Contract

ACP uses a unified coordinator contract:
- Prompt validation and permission validation both pass through a shared
  governance coordinator.
- Permission outcomes are normalized to `approve`, `deny`, or `prompt`.
- Governance `require_approval` feeds the same approval prompt path used by ACP
  tier approvals, avoiding duplicate prompts.

Migration direction:
- Keep MCP wire compatibility stable.
- Move ACP behavior toward the unified governance contract and deprecate legacy
  split approval behavior.

## Metrics and Audit Trace Fields

Governance checks emit low-cardinality metrics:
- Prometheus: `mcp_governance_checks_total{surface,category,status,rollout_mode}`
- Internal metrics key: `governance_check`

Normalized label behavior:
- Unknown `surface` or `category` values normalize to `other`.
- Unknown `status` values normalize to `unknown`.
- Unknown `rollout_mode` values normalize to `off`.

Governance trace payloads include:
- `policy_revision_ref`
- `rule_revision_ref`
- `rollout_mode`
- Optional `fallback_reason`
- Optional `matched_rules`

## Recommended Rollout Procedure

1. Start with `off` in production while validating configuration and dashboards.
2. Move to `shadow` and observe governance check volumes, denied actions, and
   trace payload quality.
3. Move to `enforce` only after validating expected deny/approval behavior in
   staging and shadow production telemetry.
4. If unexpected deny behavior appears, revert to `shadow` or `off` and inspect
   governance traces before re-enabling enforcement.

## Verification Commands

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Governance \
  tldw_Server_API/app/core/MCP_unified/tests/test_governance_module.py \
  tldw_Server_API/app/core/MCP_unified/tests/test_protocol_governance_preflight.py \
  tldw_Server_API/tests/Agent_Client_Protocol/test_acp_governance_coordinator.py -v
```

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/Governance \
  tldw_Server_API/app/core/MCP_unified \
  tldw_Server_API/app/core/Agent_Client_Protocol \
  tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py \
  -f json -o /tmp/bandit_governance.json
```
