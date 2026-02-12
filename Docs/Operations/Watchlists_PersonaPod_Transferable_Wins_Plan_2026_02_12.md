# PersonaPod -> tldw_server2: Transferable Wins Plan (Adjusted)

Date: 2026-02-12
Status: Draft (review-adjusted)

## Context

PersonaPod is a single-purpose AI podcast generator (RSS -> LLM summarization -> persona-driven TTS -> background music mixing -> cloud upload -> RSS feed).

`tldw_server2` already covers most primitives (LLM providers, TTS providers, workflows, watchlists), but there are targeted quality and delivery improvements worth porting as patterns.

This plan keeps the original 6-win structure, with architecture-safe adjustments based on current `tldw_server2` workflow and artifact behavior.

## Cross-Cutting Guardrails

1. Spoken-text fixes must run where text is actually consumed by TTS.
2. Any post-TTS workflow step must account for current early-exit behavior.
3. Final audio endpoint selection must prefer final/mixed artifacts, not earliest intermediate artifacts.
4. New adapters are incomplete until registry + aggregate exports + step-type validation paths are wired.
5. RSS publish must be race-safe and must not default to arbitrary remote URL fetch.
6. `map` fan-out summarization must define an explicit merge contract back to `[{title, summary, url}]`.

---

## Win 1: Strip Reasoning Model `<think>` Blocks (Quick Win)

### Problem
Reasoning model output may include `<think>...</think>`-style blocks that can be spoken aloud.

### Current Gap
`text_clean` can be extended, but current `clean_script` output is not what multi-voice/fallback TTS actually speaks in the briefing workflow.

### Adjusted Implementation
1. Add reasoning-block stripping in one (or both) real consumption points:
   - `audio_briefing_compose` output normalization before section parsing, and/or
   - `multi_voice_tts` section `clean_text` preprocessing.
2. Keep optional `text_clean` operation support for non-spoken cleanup, but do not rely on it for spoken correctness.
3. Patterns to strip (DOTALL): `<think>`, `<thinking>`, `<reasoning>`.

### Files
- `tldw_Server_API/app/core/Workflows/adapters/content/audio_briefing.py`
- `tldw_Server_API/app/core/Workflows/adapters/audio/multi_voice_tts.py`
- Optional: `tldw_Server_API/app/core/Workflows/adapters/text/transform.py`

---

## Win 2: TTS-Safe LLM Prompt Rules (Quick Win)

### Problem
Current briefing prompt says “NO markdown” but misses common audible artifacts (emoji, character counts, stylized labels, signatures, etc.).

### Adjusted Implementation
1. Strengthen `_build_system_prompt()` with explicit anti-pattern bans.
2. Add configurable language control instead of hard-coded English-only:
   - `audio_language` in workflow inputs / output prefs (default `en`).
   - Prompt rule becomes conditional (“respond in `<audio_language>` only”).
3. Optional shared prompt suffix constant for reuse by other LLM->TTS paths.

### Files
- `tldw_Server_API/app/core/Workflows/adapters/content/audio_briefing.py`
- `tldw_Server_API/app/core/Watchlists/audio_briefing_workflow.py`
- Optional: `tldw_Server_API/app/core/TTS/audio_utils.py`
- Optional schema path(s) for `output_prefs` docs/validation

---

## Win 3: TTS Text Preprocessing (Quick Win)

### Problem
Characters like `+`, `&`, and dash variants can produce low-quality speech.

### Current Gap
Hooking only `split_text_into_chunks()` is insufficient for briefing path, because briefing TTS currently streams and often bypasses service-level chunking logic.

### Adjusted Implementation
1. Add `clean_text_for_tts()` utility (newline collapse, symbol replacements, whitespace normalization).
2. Call it in actual briefing speech paths:
   - `multi_voice_tts` per-section before synth call.
   - Optional fallback single-voice TTS preprocessing in workflow adapter path.
3. Optional `text_clean` operation (`tts_normalize`) for non-briefing usage, but not primary path for this win.

### Files
- `tldw_Server_API/app/core/Workflows/adapters/audio/multi_voice_tts.py`
- `tldw_Server_API/app/core/Workflows/adapters/audio/tts.py` (if applied in adapter path)
- Optional utility location: `tldw_Server_API/app/core/TTS/audio_utils.py`
- Optional: `tldw_Server_API/app/core/Workflows/adapters/text/transform.py`

---

## Win 4: Background Track Mixing for Audio Briefings (Feature Win)

### Problem
Current mix adapter is a basic `amix` path; briefing workflow has no podcast-style background mix stage.

### Current Risks
- `generate_audio` currently exits workflow early on success.
- If mix runs but artifact selection is unchanged, endpoint may still return pre-mix audio.

### Adjusted Implementation
1. Implement mix safely via one path:
   - Preferred: integrate optional background mix into `multi_voice_tts` before final artifact registration.
   - Alternative: add explicit mix step and remove/adjust early `_end` exit.
2. Add background mix controls (volume, delay, fade duration).
3. Ensure `/watchlists/runs/{run_id}/audio` returns final/mixed artifact by precedence rule (latest/final-tagged).

### Files
- `tldw_Server_API/app/core/Workflows/adapters/audio/multi_voice_tts.py` (preferred)
- Or `tldw_Server_API/app/core/Workflows/adapters/audio/processing.py`
- `tldw_Server_API/app/core/Watchlists/audio_briefing_workflow.py`
- `tldw_Server_API/app/api/v1/endpoints/watchlists.py`

---

## Win 5: Podcast RSS Feed Generation (Feature Win)

### Problem
Audio briefing generation exists, but feed publication/subscription flow is missing.

### Adjusted Implementation
1. Add `podcast_rss_publish` adapter under integration.
2. Input sources:
   - Default: local file / S3 object reference.
   - Remote URL fetch only when explicitly enabled.
3. Merge semantics:
   - Deduplicate by GUID,
   - deterministic ordering,
   - retain required podcast metadata fields.
4. Concurrency:
   - optimistic concurrency (etag/version compare) to avoid lost updates.
5. Storage contract alignment:
   - normalize with existing S3 upload expectations (`file_uri` vs legacy aliases).

### Files
- New: `tldw_Server_API/app/core/Workflows/adapters/integration/podcast_rss.py`
- `tldw_Server_API/app/core/Workflows/adapters/integration/_config.py`
- `tldw_Server_API/app/core/Workflows/adapters/integration/storage.py` (contract alignment)
- `tldw_Server_API/app/core/Watchlists/audio_briefing_workflow.py` (optional publish step)

---

## Win 6: Per-Story Persona Summarization (Pattern Win)

### Problem
Single-pass script composition limits per-story persona shaping.

### Adjusted Implementation
1. Add optional per-item pre-summarization mode (`persona_summarize=true`).
2. Use `map` over items with summarize/persona adapter.
3. Add explicit merge step that reconstructs compose input contract exactly:
   - `[{title, summary, url}]`.
4. Add output prefs inputs:
   - `persona_summarize` (bool)
   - `persona_id` (or equivalent persona selector)
   - optional provider/model overrides for pre-summarization.

### Files
- `tldw_Server_API/app/core/Watchlists/audio_briefing_workflow.py`
- Optional new adapter under content/ for persona-aware per-item summarization

---

## Required Wiring Checklist (Applies to Wins 4-6)

- Register adapter with `@registry.register(...)`.
- Import/export in category `__init__.py`.
- Expose in aggregate adapters package exports.
- Ensure workflow step type is recognized in step-type registry/API validation paths.
- Add config model and adapter registration tests.

---

## What NOT to Adopt

- PersonaPod Docker container cycling for VRAM.
- PersonaPod sync-first orchestration style.
- PersonaPod global `globals()` config patterns.
- Direct code transplant from PersonaPod.

---

## Verification Plan

1. Wins 1-3:
   - Unit tests for reasoning-strip and TTS preprocessing in spoken path.
   - Integration run of audio briefing with reasoning-capable model output fixture.
2. Win 4:
   - Test workflow control flow (post-TTS mix stage executes).
   - Assert endpoint returns final mixed artifact.
   - Validate duration/output file generation from ffmpeg path.
3. Win 5:
   - Unit tests for RSS XML generation + namespace fields.
   - Dedup test by GUID.
   - Concurrency conflict test (etag/version mismatch).
4. Win 6:
   - Map fan-out count equals item count.
   - Merge output shape validation.
   - Compose step consumes merged items without contract break.
5. Wiring:
   - Step type accepted by workflow API validation.
   - Adapter listed/registered in registry catalog.

---

## Implementation Order (Adjusted)

1. Win 1 - Strip reasoning blocks in actual spoken path
2. Win 2 - TTS-safe prompt hardening + configurable language
3. Win 3 - Spoken-path TTS preprocessing
4. Win 4 - Background mixing + artifact selection precedence
5. Win 6 - Per-story persona summarization with explicit merge contract
6. Win 5 - Podcast RSS publish adapter (highest integration complexity)

