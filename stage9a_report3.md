# Stage 9A RG Parity Report (Staging/Dev)

- Before: `stage9a_before3.prom` (2025-12-14 17:00:28 UTC)
- After: `stage9a_after3.prom` (2025-12-14 17:01:10 UTC)
- RG policy: version=1 store=file policies=20

## Shadow mismatches
- `rg_shadow_decision_mismatch_total` increase: **0**

## Coverage (policy_id)
Observed policy_ids (decisions increase > 0):
- `media.default`

Missing expected policy_ids:
- `chat.default`
- `character_chat.default`
- `embeddings.default`
- `audio.default`
- `authnz.default`
- `evals.default`
- `workflows.default`
- `rag.default`

## Decisions
- `media.default`: 1
- `evals.default`: 0
- `mcp.ingestion`: 0
- `workflows.default`: 0
- `embeddings.default`: 0
- `chat.default`: 0
- `audio.default`: 0

## Denials (top)
- `media.default` reason=`insufficient_capacity`: 0

## Result
- FAIL
- Reasons: `missing_policy_ids=8`
