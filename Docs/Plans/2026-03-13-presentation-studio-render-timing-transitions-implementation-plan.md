# Presentation Studio Render Timing And Transitions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Presentation Studio video exports honor manual slide timing and supported transition presets in the backend renderer.

**Architecture:** Extend the Slides renderer with explicit timing-resolution helpers, keep a cut-only concat path for simple decks, and add a filtered final video assembly path for eligible visual transitions. Audio remains sequential and non-overlapping; manual timing only pads narration with silence and never trims it.

**Tech Stack:** Python, ffmpeg/ffprobe, pytest, FastAPI Slides render pipeline

---

### Task 1: Add failing tests for timing resolution helpers

**Files:**
- Modify: `tldw_Server_API/tests/Slides/test_presentation_rendering.py`
- Modify: `tldw_Server_API/app/core/Slides/presentation_rendering.py`

**Step 1: Write the failing test**

Add tests that expect helper behavior for:
- audio duration from metadata
- audio duration from probed asset when metadata is missing
- effective duration using `max(audio_duration, manual_duration)`
- transition mapping from slide metadata to ffmpeg filter selection

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_presentation_rendering.py -k "timing or transition" -v`

Expected: FAIL because the helpers do not exist yet.

**Step 3: Write minimal implementation**

Add small helpers in `presentation_rendering.py` for:
- studio metadata normalization
- audio-duration resolution
- effective-duration resolution
- transition filter mapping
- transition eligibility resolution

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Slides/test_presentation_rendering.py tldw_Server_API/app/core/Slides/presentation_rendering.py
git commit -m "test: add presentation render timing resolution coverage"
```

### Task 2: Add failing tests for narrated slide padding in cut-only renders

**Files:**
- Modify: `tldw_Server_API/tests/Slides/test_presentation_rendering.py`
- Modify: `tldw_Server_API/app/core/Slides/presentation_rendering.py`

**Step 1: Write the failing test**

Add a render test expecting narrated slides with longer manual timing to emit a segment command that pads audio and uses explicit effective duration instead of ending at narration length.

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_presentation_rendering.py -k "padding or cut_only" -v`

Expected: FAIL because segment commands still rely on `-shortest`.

**Step 3: Write minimal implementation**

Adjust segment command generation so:
- silent slides keep the existing synthetic-audio path
- narrated slides can use `apad` and `-t <effective_duration>`
- cut-only decks remain concat-based

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Slides/test_presentation_rendering.py tldw_Server_API/app/core/Slides/presentation_rendering.py
git commit -m "feat: pad narrated presentation slides for manual timing"
```

### Task 3: Add failing tests for transitioned deck assembly

**Files:**
- Modify: `tldw_Server_API/tests/Slides/test_presentation_rendering.py`
- Modify: `tldw_Server_API/app/core/Slides/presentation_rendering.py`

**Step 1: Write the failing test**

Add a render test expecting:
- `cut`-only decks to keep concat final assembly
- decks with `wipe` or `zoom` boundaries to use filtered final video assembly instead of concat-copy
- transitioned decks to preserve total authored runtime by using an outgoing visual hold buffer

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_presentation_rendering.py -k "transitioned or filter_complex" -v`

Expected: FAIL because final assembly still always uses concat-copy.

**Step 3: Write minimal implementation**

Add:
- a filtered final video assembly command builder
- sequential audio assembly for transitioned decks
- path selection logic choosing concat vs filtered assembly

**Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Slides/test_presentation_rendering.py tldw_Server_API/app/core/Slides/presentation_rendering.py
git commit -m "feat: add presentation render transition assembly"
```

### Task 4: Verify Slides render endpoints and job flow stay green

**Files:**
- Test: `tldw_Server_API/tests/Slides/test_presentation_rendering.py`
- Test: `tldw_Server_API/tests/Slides/test_presentation_render_jobs.py`

**Step 1: Run targeted backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides/test_presentation_rendering.py tldw_Server_API/tests/Slides/test_presentation_render_jobs.py -v
```

Expected: PASS for all affected Slides render tests.

**Step 2: Run broader Slides regression**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Slides -v
```

Expected: PASS with no render regressions.

**Step 3: Run Bandit on touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Slides/presentation_rendering.py tldw_Server_API/tests/Slides/test_presentation_rendering.py -f json -o /tmp/bandit_presentation_render_timing_transitions.json
```

Expected: `0` findings in touched code.

**Step 4: Commit**

```bash
git add tldw_Server_API/app/core/Slides/presentation_rendering.py tldw_Server_API/tests/Slides/test_presentation_rendering.py Docs/Plans/2026-03-13-presentation-studio-render-timing-transitions-design.md Docs/Plans/2026-03-13-presentation-studio-render-timing-transitions-implementation-plan.md
git commit -m "feat: wire presentation render timing and transitions"
```
