# Stage 9A RG Parity Report (Staging/Dev)

- Before: `stage9a_before2.prom` (2025-12-14 16:30:49 UTC)
- After: `stage9a_after2.prom` (2025-12-14 16:31:08 UTC)
- RG policy: version=1 store=file policies=20

## Shadow mismatches
- `rg_shadow_decision_mismatch_total` increase: **0**

## Coverage (policy_id)
Observed policy_ids (decisions increase > 0):
- `media.default`

Missing expected policy_ids:
- `chat.default`
- `embeddings.default`
- `mcp.ingestion`
- `audio.default`
- `authnz.default`
- `evals.default`
- `character_chat.default`
- `web_scraping.default`
- `workflows.default`

## Decisions
- `media.default`: 1
- `chat.default`: 0
- `embeddings.default`: 0
- `mcp.ingestion`: 0
- `workflows.default`: 0
- `audio.default`: 0
- `evals.default`: 0

## Result
- FAIL
- Reasons: `missing_policy_ids=9`
