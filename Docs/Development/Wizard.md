# tldw_setup Wizard — Developer Guide

This document describes the setup wizard CLI skeleton, usage patterns, and troubleshooting tips.

## Overview

- Console entrypoint: `tldw-setup [command] [options]`
- Module fallback (repo/local): `python -m tldw_Server_API.cli.wizard.cli [command] [options]`
- Current state: scaffold implementation with safe, idempotent file operations and JSON output mode for automation.

## Commands

- `init` — full guided setup (scaffold)
  - Options: `--default`, `--install-dir PATH`, `--non-interactive`, `--debug`, `--dry-run`, `--json`, `--yes/--no-input`, `--no-format`, `--no-color`, `--quiet`
  - Behavior (scaffold): detects environment, plans `.env` creation and `.gitignore` updates. In non-dry-run mode creates `.env` (0600) with basic defaults and ensures `.gitignore` entries. When `AUTH_MODE=multi_user` and a valid Postgres `DATABASE_URL` is present, `--yes` auto-runs the AuthNZ initializer; otherwise the wizard prompts in interactive shells.

- `auth` — configure authentication mode
  - Options: `--mode [single_user|multi_user]`, `--json`, `--dry-run`, `--yes/--no-input`
  - Behavior: updates `.env` with `AUTH_MODE`, generates `SINGLE_USER_API_KEY` when needed, validates `DATABASE_URL` for multi-user, and prompts to run the AuthNZ initializer when appropriate. Creates a timestamped backup on first modification.

- `db` — initialize/validate databases
  - Behavior: creates per-user SQLite files for Media/ChaChaNotes/Evaluations, ensures a shared evaluations DB under `Databases/`, and validates Postgres connectivity when `DATABASE_URL` uses a Postgres scheme.

- `providers` — collect/store provider keys (scaffold)
  - Options: `--json`, `--dry-run`, `--check-provider`
  - Behavior: prefers `.env` as the source of truth; `config.txt` generation only on explicit request (future step). Optional provider checks are offline/mock in the scaffold.

- `mcp [add|remove]` — manage MCP client configs (scaffold)
  - Options: `--json`, `--dry-run`
  - Behavior: reports which clients would be configured (Cursor, Claude, VS Code, Zed); full implementation will support dry-run diffs, backups, and removal confirmation.

- `verify` — run verification checks (scaffold)
  - Options: `--json`, `--check-provider`
  - Behavior: detects `ffmpeg` and CUDA presence. Full implementation will probe `/api/v1/health`, `/api/v1/healthz`, and `/api/v1/mcp/status`, optionally spinning up the server on a free port.

- `format` — format changed files with Black/Ruff when available
  - Behavior: if in a Git repo, formats changed/untracked files. Skips gracefully if tools missing.

- `doctor` — detect issues and propose fixes (scaffold)
  - Behavior: checks for `.env` and `.gitignore` basics and `ffmpeg` presence; full implementation will add specific remediation steps.

## Non-Interactive Usage

When running with `--non-interactive` or `--yes`, the wizard consumes environment variables instead of prompting. Common variables:

- `AUTH_MODE`, `SINGLE_USER_API_KEY`, `DATABASE_URL`
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (and other providers)
- `TLDW_CHECK_PROVIDER=1` to enable provider verification
- `TLDW_SERVER_PORT` to control the port used by ephemeral server verification

Example (CI):

```bash
AUTH_MODE=single_user \
OPENAI_API_KEY=sk-... \
tldw-setup init --non-interactive --yes --json --no-format
```

## Output Modes

- Human-readable (default) — concise status, actions, and notes.
- JSON (`--json`) — machine-readable, stable schema per command (`command`, `status`, `facts`, `actions`, `paths`, etc.).

## Files Managed

- `.env`: created with mode 0600; idempotent merge updates with de-duplication and timestamped backups.
- `.gitignore`: ensures `.env`, `.env.local`, and `wizard.log` entries.
- `wizard.log`: optional local troubleshooting log (future step); must be redacted and gitignored.

## Troubleshooting

- `ffmpeg` not detected
  - Install via package manager: `brew install ffmpeg` (macOS), `apt-get install -y ffmpeg` (Debian/Ubuntu), `choco install ffmpeg` or `scoop install ffmpeg` (Windows).

- CUDA check noisy on Apple Silicon or CPU-only systems
  - Pass `--non-interactive` without GPU flags; the wizard only performs passive detection in scaffold.

- Formatting didn’t run
  - Ensure you’re in a Git repo and Black/Ruff are installed (`pip install black ruff`). Use `--no-format` to skip explicitly.

- Multi-user AuthNZ initializer
  - The full implementation will offer to run: `python -m tldw_Server_API.app.core.AuthNZ.initialize`.

## Roadmap Notes

- Implement `.env` merge/update semantics with masking and backups.
- Add health endpoint probing and ephemeral server spawn with safe shutdown.
- MCP client installers: dry-run diffs, per-OS path table, timestamped backups, removal confirmation.
- Provider verification with offline/mocked checks gated by `--check-provider`.
