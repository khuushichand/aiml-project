# Stage 9A RG Parity Report (Staging/Dev)

- Before: `stage9a_before.prom` (2025-12-14 06:29:45 UTC)
- After: `stage9a_after.prom` (2025-12-14 07:43:26 UTC)
- RG policy: version=1 store=file policies=20

## Shadow mismatches
- `rg_shadow_decision_mismatch_total` increase: **0**

## Coverage (policy_id)
Observed policy_ids (decisions increase > 0):
- `audio.default`
- `chat.default`
- `embeddings.default`
- `evals.default`
- `mcp.ingestion`
- `workflows.default`

Missing expected policy_ids:
- `authnz.default`
- `character_chat.default`
- `web_scraping.default`

## Decisions
- `chat.default`: 2
- `workflows.default`: 1
- `embeddings.default`: 1
- `audio.default`: 1
- `evals.default`: 1
- `mcp.ingestion`: 1

## Result
- FAIL
- Reasons: `missing_policy_ids=3`
