## Stage 1: Confirm Remaining Qodo Threads
**Goal**: Identify unresolved Qodo review comments and map each to exact files/functions.
**Success Criteria**: List of unresolved threads with actionable changes and no ambiguity.
**Tests**: GitHub API query for PR #763 reviewThreads and local source inspection.
**Status**: Complete

## Stage 2: Add Required Docstrings and Return Types
**Goal**: Add missing docstrings and explicit return annotations in watchlists, MLX endpoints, telemetry metrics, and Watchlists DB functions flagged by Qodo.
**Success Criteria**: All flagged functions include project-compliant docstrings and explicit return types where required.
**Tests**: Targeted pytest smoke on touched modules’ related tests.
**Status**: Complete

## Stage 3: Fix CI Argument Parsing Regression
**Goal**: Ensure CI helper scripts consume real CLI flags when `main()` is invoked without explicit argv.
**Success Criteria**: `main(None)` path respects `sys.argv[1:]`; existing behavior with explicit argv remains intact.
**Tests**: Add/execute regression tests in `tldw_Server_API/tests/scripts/` for both scripts.
**Status**: Complete

## Stage 4: Verify and Report
**Goal**: Run targeted tests and Bandit for touched scope; summarize what remains.
**Success Criteria**: Fresh evidence for test/bandit runs and clear status report tied to each Qodo comment.
**Tests**:
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/scripts/test_watchlists_rc_gate.py tldw_Server_API/tests/scripts/test_watchlists_telemetry_rc_report.py`
- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/watchlists.py tldw_Server_API/app/api/v1/endpoints/mlx.py tldw_Server_API/app/core/Watchlists/watchlists_telemetry_metrics.py tldw_Server_API/app/core/DB_Management/Watchlists_DB.py Helper_Scripts/ci/watchlists_rc_gate.py Helper_Scripts/ci/watchlists_telemetry_rc_report.py -f json -o /tmp/bandit_pr763_qodo.json`
**Status**: Complete
