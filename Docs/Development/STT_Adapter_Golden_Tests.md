# STT Adapter Golden Tests (Local/GPU Profile)

This document describes the optional “golden” test profile for validating STT
adapters (faster‑whisper, Parakeet, Canary) against real audio clips and
known‑good reference transcripts. It is designed to run **only** on developer
machines or internal GPU runners, not GitHub Actions.

## Overview

Goals:
- Exercise the real STT adapters with actual audio.
- Compare adapter output to curated reference transcripts using a simple
  token‑level error rate (WER‑like).
- Keep tests completely opt‑in, guarded by environment variables and markers.

Non‑goals:
- No attempt to run on CI systems without GPUs.
- No requirement to check in large audio assets; paths are driven by
  environment variables.

## Test Harness Location

- Test file: `tldw_Server_API/tests/Audio/test_stt_adapters_golden.py`
- Markers:
  - `@pytest.mark.stt_golden` — used to select the golden profile.
- Environment gates:
  - `TLDW_STT_GOLDEN_ENABLE` — must be truthy for tests to run.
  - `TLDW_STT_GOLDEN_AUDIO_DIR` — base directory for audio + golden JSON files.

If either variable is missing or invalid, all tests in this file `skip` with a
clear message.

## Golden File Schema

Golden configuration files are JSON and live under
`$TLDW_STT_GOLDEN_AUDIO_DIR`. Tests look for the following filename patterns:

- Whisper: `whisper_*.golden.json`
- Parakeet: `parakeet_*.golden.json`
- Canary: `canary_*.golden.json`

Each JSON file uses this schema:

```json
{
  "audio": "audio/whisper/en/clip1.wav",
  "model": "large-v3",
  "language": "en",
  "expected_text": "This is the reference transcript for clip one.",
  "max_token_error_rate": 0.12,
  "min_segments": 2
}
```

Fields:
- `audio` (str, required)
  - Path to the audio file **relative** to `$TLDW_STT_GOLDEN_AUDIO_DIR`.
  - The tests resolve it via `Path(base_dir) / audio`.
- `model` (str, required)
  - Adapter‑specific model name (e.g. `"large-v3"`, `"parakeet-standard"`,
    `"nemo-canary-1b"`).
- `language` (str or null, optional)
  - Optional language hint (e.g. `"en"`); passed directly to the adapter.
- `expected_text` (str, required)
  - Reference transcript text used for scoring.
- `max_token_error_rate` (float, optional)
  - Upper bound on token‑level error rate (edit distance / reference tokens).
  - Defaults to `0.20` when omitted (conservative).
- `min_segments` (int, optional)
  - Minimum expected number of segments in `artifact["segments"]`.
  - Defaults to `1`.

## How the Tests Work

Common helpers in `test_stt_adapters_golden.py`:

- `_require_golden_env()`
  - Validates `TLDW_STT_GOLDEN_ENABLE` and `TLDW_STT_GOLDEN_AUDIO_DIR`.
  - Skips tests if env is not configured.
- `_normalize_text(text: str) -> list[str]`
  - Lowercases, strips punctuation, splits on whitespace to produce tokens.
- `_levenshtein(a: list[str], b: list[str]) -> int`
  - Token‑level Levenshtein edit distance.
- `_token_error_rate(ref: str, hyp: str) -> float`
  - Computes `distance / len(ref_tokens)`; analogous to WER.
- `_load_golden_cases(base: Path, pattern: str) -> list[GoldenCase]`
  - Discovers JSON files matching the pattern.
  - Validates each JSON and resolves `audio` to a real file.

For each adapter, a test:

1. Loads all matching golden cases under `TLDW_STT_GOLDEN_AUDIO_DIR`.
2. Instantiates the adapter (`FasterWhisperAdapter`, `ParakeetAdapter`,
   `CanaryAdapter`).
3. Calls `adapter.transcribe_batch(...)` with:
   - `audio_path` from the golden case.
   - `model` and `language` from the golden case.
   - `task="transcribe"`.
4. Compares:
   - `artifact["text"]` vs `expected_text` via `_token_error_rate(...)`.
   - Asserts `TER <= max_token_error_rate`.
   - Asserts `segments` is a list and `len(segments) >= min_segments`.

Additional gating:
- Parakeet and Canary tests call `is_nemo_available()` and skip when Nemo is
  not importable, so CPU‑only environments are not forced to install Nemo.

## Minimal Golden Setup (Recommended Starting Point)

On your GPU machine (or internal GPU runner):

1. Choose a base dir for goldens, e.g.:

```bash
mkdir -p /srv/tldw_stt_golden/audio/whisper/en
mkdir -p /srv/tldw_stt_golden/audio/parakeet/en
mkdir -p /srv/tldw_stt_golden/audio/canary/en
```

2. Place a short, clean English WAV in each directory; you can reuse the same
file if you want all adapters to see identical audio:

```bash
cp /path/to/your_clip.wav /srv/tldw_stt_golden/audio/whisper/en/clip1.wav
cp /path/to/your_clip.wav /srv/tldw_stt_golden/audio/parakeet/en/clip1.wav
cp /path/to/your_clip.wav /srv/tldw_stt_golden/audio/canary/en/clip1.wav
```

3. Generate initial golden JSONs using the helper script (see next section) or
by hand. Example for Whisper:

```json
{
  "audio": "audio/whisper/en/clip1.wav",
  "model": "large-v3",
  "language": "en",
  "expected_text": "This is the reference transcript for clip one.",
  "max_token_error_rate": 0.12,
  "min_segments": 2
}
```

4. Run the golden profile:

```bash
export TLDW_STT_GOLDEN_ENABLE=1
export TLDW_STT_GOLDEN_AUDIO_DIR=/srv/tldw_stt_golden
pytest -m "stt_golden" -v
```

or via the Makefile target:

```bash
make stt-golden STT_GOLDEN_AUDIO_DIR=/srv/tldw_stt_golden
```

## Helper Script: Generate Goldens from Current Adapters

You can add a small helper script (suggested path):

- `Helper_Scripts/Audio/generate_stt_golden.py`

Script responsibilities:

- Accept CLI arguments:
  - `--provider` (`faster-whisper`, `parakeet`, `canary`)
  - `--audio` (absolute or relative path to audio file)
  - `--model`
  - `--language`
  - `--base-dir` (your `$TLDW_STT_GOLDEN_AUDIO_DIR`)
  - `--output` (golden JSON path)
  - `--max-ter` (optional)
  - `--min-segments` (optional)
- Run the real adapter on the given audio.
- Write a golden JSON using the adapter’s output text as `expected_text`.

Example usage (Whisper):

```bash
export PYTHONPATH=.
BASE=/srv/tldw_stt_golden

python Helper_Scripts/Audio/generate_stt_golden.py \
  --provider faster-whisper \
  --audio "$BASE/audio/whisper/en/clip1.wav" \
  --model large-v3 \
  --language en \
  --base-dir "$BASE" \
  --output "$BASE/whisper_clip1.golden.json" \
  --max-ter 0.12 \
  --min-segments 2
```

Parakeet and Canary examples:

```bash
python Helper_Scripts/Audio/generate_stt_golden.py \
  --provider parakeet \
  --audio "$BASE/audio/parakeet/en/clip1.wav" \
  --model parakeet-standard \
  --language en \
  --base-dir "$BASE" \
  --output "$BASE/parakeet_clip1.golden.json"

python Helper_Scripts/Audio/generate_stt_golden.py \
  --provider canary \
  --audio "$BASE/audio/canary/en/clip1.wav" \
  --model nemo-canary-1b \
  --language en \
  --base-dir "$BASE" \
  --output "$BASE/canary_clip1.golden.json"
```

This gives you a reproducible baseline: the golden JSONs reflect the current
adapter behavior. Over time, you can:

- Tighten `max_token_error_rate` as you improve models or filters.
- Add more clips and languages (e.g. noisy English, another language, longer
  utterances).

## Makefile Integration

The repository includes a convenience target for running the golden tests:

- File: `Makefile`
- Target:

```make
.PHONY: stt-golden

STT_GOLDEN_AUDIO_DIR ?= ./test_models/stt_golden

stt-golden:
	@echo "[stt-golden] Running STT golden adapter tests against $(STT_GOLDEN_AUDIO_DIR)"
	TLDW_STT_GOLDEN_ENABLE=1 \
	TLDW_STT_GOLDEN_AUDIO_DIR="$(STT_GOLDEN_AUDIO_DIR)" \
	python -m pytest tldw_Server_API/tests/Audio/test_stt_adapters_golden.py -m "stt_golden" -v
```

Example invocation:

```bash
make stt-golden STT_GOLDEN_AUDIO_DIR=/srv/tldw_stt_golden
```

## When to Run This Profile

Recommended scenarios:
- Before tagging a release that changes STT adapters, models, or config.
- After upgrading heavy dependencies (faster‑whisper, Nemo, CUDA drivers) on
  your GPU machines.
- Before/after adjusting STT‑related VAD, pre‑processing, or normalization
  logic that could affect transcripts.

Because these tests are opt‑in and gated by env, they are safe to leave in the
repo without impacting normal CI runs. You decide when and where to exercise
them. 

