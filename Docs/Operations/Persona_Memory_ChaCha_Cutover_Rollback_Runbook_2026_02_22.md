# Persona Memory ChaCha Cutover + Rollback Runbook (2026-02-22)

## Purpose
Cut over persona memory reads/writes from legacy `PersonalizationDB` to `ChaChaNotesDB` with an idempotent backfill and a reversible rollout path.

## Safety Invariants
- Personalization opt-in remains the write/read gate for persona memory behavior.
- Use `dual_write` during rollout to keep rollback lossless.
- Keep `chacha_first_fallback_legacy` until backfill and parity checks are complete.

## Runtime Flags
Set via env vars or `[persona]` config keys:
- `PERSONA_MEMORY_READ_MODE` / `persona_memory_read_mode`
- `PERSONA_MEMORY_WRITE_MODE` / `persona_memory_write_mode`

Allowed values:
- Read: `legacy_only`, `chacha_only`, `chacha_first_fallback_legacy`
- Write: `legacy_only`, `chacha_only`, `dual_write`

## Rollout Phases
1. Baseline
- Read: `legacy_only`
- Write: `legacy_only`

2. Safe cutover (recommended)
- Read: `chacha_first_fallback_legacy`
- Write: `dual_write`
- Outcome: new writes land in both stores; reads prefer ChaCha and fall back to legacy.

3. Final cutover
- Read: `chacha_only`
- Write: `chacha_only`
- Do this only after parity checks are stable.

## Backfill (Idempotent + Resumable)
Run from repo root:

```bash
source .venv/bin/activate
python - <<'PY'
from tldw_Server_API.app.core.Persona.memory_integration import backfill_persona_memory_from_legacy

user_id = "1"
persona_id = "research_assistant"
checkpoint = None

while True:
    result = backfill_persona_memory_from_legacy(
        user_id=user_id,
        persona_id=persona_id,
        batch_size=200,
        checkpoint=checkpoint,
        include_usage_events=True,
    )
    print(result)
    if result.completed:
        break
    checkpoint = result.next_checkpoint
PY
```

Notes:
- Re-running is safe; deterministic IDs skip duplicates.
- Persist `next_checkpoint` if you need to resume after interruption.

## Validation
Run Stage 0 regression checks:

```bash
source .venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/Persona/test_persona_memory_integration.py \
  tldw_Server_API/tests/Persona/test_persona_ws.py \
  tldw_Server_API/tests/Persona/test_ws_metrics_persona.py \
  tldw_Server_API/tests/Persona/test_persona_policy_evaluator.py \
  tldw_Server_API/tests/Persona/test_persona_profiles_api.py \
  tldw_Server_API/tests/Persona/test_persona_sessions.py -q
```

## Rollback
Immediate rollback:
1. Set read/write to legacy:
   - `PERSONA_MEMORY_READ_MODE=legacy_only`
   - `PERSONA_MEMORY_WRITE_MODE=legacy_only`
2. Restart API workers.
3. Re-run the Stage 0 regression checks above.

Lossless rollback guarantee:
- Guaranteed while rollout uses `dual_write`.
- If you run `chacha_only` writes for a period, reverting to legacy-only can exclude those writes unless reverse backfill is performed.
