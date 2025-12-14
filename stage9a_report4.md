# Stage 9A RG Parity Report (Staging/Dev)

- Before: `stage9a_before4.prom` (2025-12-14 17:22:24 UTC)
- After: `stage9a_after4.prom` (2025-12-14 17:23:41 UTC)
- RG policy: version=1 store=file policies=20

## Shadow mismatches
- `rg_shadow_decision_mismatch_total` increase: **0**

## Coverage (policy_id)
Observed policy_ids (decisions increase > 0):
- `audio.default`
- `authnz.default`
- `character_chat.default`
- `chat.default`
- `embeddings.default`
- `evals.default`
- `media.default`
- `rag.default`

Missing expected policy_ids:
- `workflows.default`

## Decisions
- `embeddings.default`: 2
- `chat.default`: 2
- `media.default`: 1
- `authnz.default`: 1
- `rag.default`: 1
- `audio.default`: 1
- `character_chat.default`: 1
- `evals.default`: 1
- `workflows.default`: 0
- `mcp.ingestion`: 0

## Denials (top)
- `media.default` reason=`insufficient_capacity`: 0

## Result
- FAIL
- Reasons: `missing_policy_ids=1`
