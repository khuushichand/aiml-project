## Stage 1: Scope & Baseline
**Goal**: Confirm where EchoTTS CUDA integration tests live and which fixtures/guards to reuse.
**Success Criteria**:
- Existing integration test module identified with model/cache/CUDA guards.
**Tests**:
- N/A
**Status**: Complete

## Stage 2: Add Regression Integration Test
**Goal**: Add an integration test that verifies WAV voice references do not require `inference.load_audio`.
**Success Criteria**:
- New test patches `inference.load_audio` to fail if called.
- Generation still succeeds for WAV reference when CUDA + cached models + module checkout are present.
**Tests**:
- `pytest` for the new test path.
**Status**: Complete

## Stage 3: Verify & Security Scan
**Goal**: Run targeted test command(s) and Bandit on touched source/test paths.
**Success Criteria**:
- Test command exits successfully (pass or skip due environment guards).
- Bandit run completed and findings reported.
**Tests**:
- `python -m pytest -v ...test_echo_tts_cuda_integration.py -k wav`
- `python -m bandit -r ... -f json`
**Status**: Complete
