## Stage 1: Baseline & Scope Mapping
**Goal**: Identify the exact behavior changes from `jordandare/echo-tts` PR #4 and map them to tldw_server integration points.
**Success Criteria**:
- PR #4 diff is reviewed and summarized.
- Local files that must change are identified.
**Tests**:
- N/A (analysis stage).
**Status**: Complete

## Stage 2: Implement EchoTTS WAV Loading Fallback
**Goal**: Port PR #4 behavior by preferring `torchaudio.load` for WAV reference audio and falling back to the upstream loader for non-WAV/exception paths.
**Success Criteria**:
- Echo adapter no longer depends on `inference.load_audio` for normal WAV references.
- Fallback behavior remains intact for non-WAV or torchaudio-unavailable cases.
**Tests**:
- Add/extend unit tests covering WAV preferred path and fallback path.
**Status**: Complete

## Stage 3: Dependency Alignment
**Goal**: Mirror PR #4 dependency update by ensuring `soundfile` is included for EchoTTS install paths.
**Success Criteria**:
- EchoTTS optional dependency sets include `soundfile`.
**Tests**:
- Static verification via file diff + targeted test run.
**Status**: Complete

## Stage 4: Verification & Security Checks
**Goal**: Validate behavior with focused tests and run Bandit on touched scope.
**Success Criteria**:
- Updated EchoTTS unit tests pass.
- Bandit JSON report generated with no new findings in touched code.
**Tests**:
- `python -m pytest` on touched EchoTTS tests.
- `python -m bandit -r` on touched source/test paths.
**Status**: Complete
