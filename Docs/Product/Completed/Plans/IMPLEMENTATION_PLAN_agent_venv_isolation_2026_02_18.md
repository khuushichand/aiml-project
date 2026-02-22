## Stage 1: Confirm Current Agent Environment Path
**Goal**: Identify where Codex agents source and install Python dependencies in this repo.
**Success Criteria**: Confirmed current setup and install commands that touch `.venv`.
**Tests**: Inspect `.codex/environments/environment.toml` and `.gitignore`.
**Status**: Complete

## Stage 2: Isolate Agent Environment to `.venv-agent`
**Goal**: Ensure agent setup and install actions use `.venv-agent` instead of `.venv`.
**Success Criteria**: `.codex/environments/environment.toml` sources `.venv-agent` and installs through `.venv-agent/bin/python`.
**Tests**: File-level validation via `nl -ba` output after patch.
**Status**: In Progress

## Stage 3: Bootstrap and Verify Isolation
**Goal**: Create `.venv-agent` and verify commands resolve to that environment.
**Success Criteria**: `.venv-agent` exists and `python`/`pip` path checks resolve inside `.venv-agent`.
**Tests**: Run `python -m venv .venv-agent` and path/version probes.
**Status**: Not Started
