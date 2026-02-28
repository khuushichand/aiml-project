## Stage 1: Scope and Baseline
**Goal**: Define the modularization scope for Slack/Discord endpoint files without changing endpoint contracts.
**Success Criteria**: Existing route paths and function names in `slack.py`/`discord.py` remain stable; plan documented.
**Tests**: N/A
**Status**: Complete

## Stage 2: Slack OAuth/Admin Extraction
**Goal**: Move Slack OAuth + admin policy/install logic to a dedicated module and keep thin wrappers in `slack.py`.
**Success Criteria**: `slack.py` shrinks materially; OAuth/admin endpoints behave the same; monkeypatch-based tests remain compatible.
**Tests**: `python -m pytest -q tldw_Server_API/tests/Slack/test_slack_oauth_lifecycle.py tldw_Server_API/tests/Slack/test_slack_policy_hardening.py`
**Status**: Complete

## Stage 3: Discord OAuth/Admin Extraction
**Goal**: Move Discord OAuth + admin policy/install logic to a dedicated module and keep thin wrappers in `discord.py`.
**Success Criteria**: `discord.py` shrinks materially; OAuth/admin endpoints behave the same; monkeypatch-based tests remain compatible.
**Tests**: `python -m pytest -q tldw_Server_API/tests/Discord/test_discord_oauth_lifecycle.py tldw_Server_API/tests/Discord/test_discord_policy_hardening.py`
**Status**: Complete

## Stage 4: Verification and Closeout
**Goal**: Run targeted test suite and capture outcomes in this plan.
**Success Criteria**: All targeted tests pass; plan statuses updated to complete.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/Slack/test_slack_oauth_lifecycle.py tldw_Server_API/tests/Slack/test_slack_policy_hardening.py`
- `python -m pytest -q tldw_Server_API/tests/Discord/test_discord_oauth_lifecycle.py tldw_Server_API/tests/Discord/test_discord_policy_hardening.py`
**Status**: Complete

## Verification Notes
- 2026-02-28: `python -m pytest -q tldw_Server_API/tests/Slack/test_slack_oauth_lifecycle.py tldw_Server_API/tests/Slack/test_slack_policy_hardening.py` -> `11 passed`.
- 2026-02-28: `python -m pytest -q tldw_Server_API/tests/Discord/test_discord_oauth_lifecycle.py tldw_Server_API/tests/Discord/test_discord_policy_hardening.py` -> `11 passed`.
- 2026-02-28: `python -m pytest -q tldw_Server_API/tests/Slack/test_slack_command_routing.py tldw_Server_API/tests/Slack/test_slack_webhook_foundation.py` -> `9 passed`.
- 2026-02-28: `python -m pytest -q tldw_Server_API/tests/Discord/test_discord_command_routing.py tldw_Server_API/tests/Discord/test_discord_interaction_foundation.py` -> `8 passed`.
