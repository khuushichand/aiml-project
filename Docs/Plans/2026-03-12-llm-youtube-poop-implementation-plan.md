# `LLM` YouTube Poop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Generate a short original "YouTube poop" style video about the experience of being an LLM using Python-rendered visuals and `ffmpeg`.

**Architecture:** Add a small helper-script module that builds a deterministic storyboard, synthesizes a procedural soundtrack, renders frame images, and shells out to `ffmpeg` for the final mux. Keep the logic decomposed into testable pure helpers so the end-to-end render step is thin orchestration instead of unstructured script code.

**Tech Stack:** Python, Pillow, `numpy`, `wave`, `pathlib`, `subprocess`, `ffmpeg`, pytest

---

### Task 1: Create The Storyboard And Timing Helpers

**Files:**
- Create: `Helper_Scripts/Creative/__init__.py`
- Create: `Helper_Scripts/Creative/generate_llm_youtube_poop.py`
- Create: `tldw_Server_API/tests/Helper_Scripts/test_generate_llm_youtube_poop.py`

**Step 1: Write the failing tests**

Add tests that prove:

- the storyboard contains multiple scenes
- every scene has non-empty text
- the total duration stays within the target short-form window
- the output plan resolves expected artifact paths under `tmp_dir/generated/llm_youtube_poop/`

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Helper_Scripts/test_generate_llm_youtube_poop.py`

Expected: FAIL because the creative helper module does not exist yet.

**Step 3: Write minimal implementation**

Implement dataclasses and helpers for:

- scene definitions
- storyboard construction
- output path planning

Keep the first pass pure and deterministic.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Helper_Scripts/test_generate_llm_youtube_poop.py`

Expected: PASS for the storyboard and path planning assertions.

**Step 5: Commit**

```bash
git add Helper_Scripts/Creative/__init__.py Helper_Scripts/Creative/generate_llm_youtube_poop.py tldw_Server_API/tests/Helper_Scripts/test_generate_llm_youtube_poop.py
git commit -m "feat(helper): add llm youtube poop storyboard generator"
```

### Task 2: Add Audio Synthesis And Frame Rendering Primitives

**Files:**
- Modify: `Helper_Scripts/Creative/generate_llm_youtube_poop.py`
- Modify: `tldw_Server_API/tests/Helper_Scripts/test_generate_llm_youtube_poop.py`

**Step 1: Write the failing tests**

Extend the test file to prove:

- audio synthesis returns the expected sample count and PCM-safe range
- text event planning emits enough overlay beats for visible motion
- one rendered frame has the requested dimensions and writes successfully

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Helper_Scripts/test_generate_llm_youtube_poop.py`

Expected: FAIL because the audio and frame helpers are not implemented yet.

**Step 3: Write minimal implementation**

Add helpers for:

- procedural tone/noise mixing
- sample normalization to 16-bit PCM
- a single-frame renderer using Pillow with glitch overlays and text jitter

Avoid the full render loop in this task.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Helper_Scripts/test_generate_llm_youtube_poop.py`

Expected: PASS, with the new helper coverage green.

**Step 5: Commit**

```bash
git add Helper_Scripts/Creative/generate_llm_youtube_poop.py tldw_Server_API/tests/Helper_Scripts/test_generate_llm_youtube_poop.py
git commit -m "feat(helper): add llm youtube poop audio and frame primitives"
```

### Task 3: Wire The CLI Render Flow And Produce The Artifact

**Files:**
- Modify: `Helper_Scripts/Creative/generate_llm_youtube_poop.py`
- Verify: `tmp_dir/generated/llm_youtube_poop/`

**Step 1: Write the failing test**

Add a focused orchestration test that proves the CLI planning layer names:

- `frames/`
- `llm_youtube_poop.wav`
- `llm_youtube_poop.mp4`

without invoking `ffmpeg`.

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Helper_Scripts/test_generate_llm_youtube_poop.py`

Expected: FAIL because the orchestration helper is incomplete.

**Step 3: Write minimal implementation**

Implement:

- output directory creation
- frame loop rendering
- WAV writing
- `ffmpeg` invocation
- CLI entrypoint with optional `--output-dir`

Then render the final artifact locally.

**Step 4: Run test and render verification**

Run:

- `source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/Helper_Scripts/test_generate_llm_youtube_poop.py`
- `source .venv/bin/activate && python Helper_Scripts/Creative/generate_llm_youtube_poop.py`

Expected:

- pytest PASS
- generated MP4 present at `tmp_dir/generated/llm_youtube_poop/llm_youtube_poop.mp4`

**Step 5: Commit**

```bash
git add Helper_Scripts/Creative/generate_llm_youtube_poop.py tldw_Server_API/tests/Helper_Scripts/test_generate_llm_youtube_poop.py
git commit -m "feat(helper): render original llm youtube poop video"
```

### Task 4: Security And Completion Checks

**Files:**
- Verify: `Helper_Scripts/Creative/generate_llm_youtube_poop.py`
- Verify: `tldw_Server_API/tests/Helper_Scripts/test_generate_llm_youtube_poop.py`
- Verify: `tmp_dir/generated/llm_youtube_poop/llm_youtube_poop.mp4`

**Step 1: Run Bandit on the touched scope**

Run: `source .venv/bin/activate && python -m bandit -r Helper_Scripts/Creative -f json -o /tmp/bandit_llm_youtube_po.json`

Expected: no new actionable findings in the touched helper script.

**Step 2: Inspect the artifact**

Confirm:

- the video file exists
- duration is short-form
- audio and video streams are present

Suggested command:

```bash
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height -of json tmp_dir/generated/llm_youtube_poop/llm_youtube_poop.mp4
```

**Step 3: Inspect the working tree**

Run: `git diff -- Helper_Scripts/Creative tldw_Server_API/tests/Helper_Scripts/test_generate_llm_youtube_poop.py docs/plans/2026-03-12-llm-youtube-poop-design.md docs/plans/2026-03-12-llm-youtube-poop-implementation-plan.md`

Expected: only the planned creative helper, its tests, and the plan docs.

**Step 4: Completion note**

Report the artifact path, the verification commands run, and any residual quality limits such as fallback font choice or render length.
