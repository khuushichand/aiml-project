## Stage 1: Reproduce And Bound The Failure
**Goal**: Reproduce the grouped websocket stress failure deterministically and identify whether the missing `end` frame is caused by queue loss, subscription timing, or test harness behavior.
**Success Criteria**: One grouped pytest command reproduces the issue and the likely failure mode is documented from code/test evidence.
**Tests**: `python -m pytest -vv tldw_Server_API/tests/sandbox/test_store_sqlite_migrations.py tldw_Server_API/tests/sandbox/test_streams_hub_lifecycle.py tldw_Server_API/tests/sandbox/test_streams_hub_resume_and_ordering.py tldw_Server_API/tests/sandbox/test_ws_connection_quotas.py tldw_Server_API/tests/sandbox/test_ws_heartbeat_seq.py tldw_Server_API/tests/sandbox/test_ws_multi_subscribers.py tldw_Server_API/tests/sandbox/test_ws_multi_subscribers_stress.py tldw_Server_API/tests/sandbox/test_ws_queue_overflow_drops.py tldw_Server_API/tests/sandbox/test_ws_resume_edge_cases.py tldw_Server_API/tests/sandbox/test_ws_resume_from_seq.py tldw_Server_API/tests/sandbox/test_ws_resume_url_exposure.py tldw_Server_API/tests/sandbox/test_ws_seq.py`
**Status**: In Progress

## Stage 2: Restore A Clean Regression Surface
**Goal**: Remove unsuccessful experimental edits and replace them with a focused regression that captures the actual websocket failure mode.
**Success Criteria**: Only intentional test coverage remains and the failing behavior is asserted directly.
**Tests**: Focused websocket stress test(s)
**Status**: Not Started

## Stage 3: Implement And Verify The Minimal Fix
**Goal**: Fix the websocket failure without regressing the original sandbox bug fixes.
**Success Criteria**: Grouped websocket subset passes, original sandbox regression slice passes, and Bandit reports no findings in touched files.
**Tests**: Grouped websocket subset, original focused sandbox regression slice, Bandit on touched paths
**Status**: Not Started
