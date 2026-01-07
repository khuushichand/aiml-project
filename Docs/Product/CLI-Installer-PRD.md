# PRD: tldw_server CLI Installer (Setup Wizard)

### Overview
  - Goal: Provide a deterministic, idempotent CLI installer to bootstrap and configure tldw_server for local and production-like use.
  - Style: Deterministic steps first, optional “agent mode” later. Local-first, privacy-preserving, no telemetry.
  - Outcomes: Fast, safe setup for single-user and multi-user AuthNZ; correct DB initialization; provider keys; MCP client integration; verification and clear next steps.

### Objectives
  - Reduce time-to-first-successful-run to under 5 minutes for single-user mode.
  - Eliminate common misconfigurations (env, DB paths, ffmpeg/CUDA).
  - Make changes safe (backups, only write when needed, git-aware formatting).
  - Provide repeatable “doctor/verify” commands.

### Non‑Goals
  - No new external analytics or telemetry.
  - No GUI/TUI beyond helpful CLI prompts and spinners.
  - No cloud-hosting provisioning in MVP (offer export guidance only).

### Personas
  - Solo Developer: Wants local, single-user API key mode working quickly.
  - Team Developer: Sets up multi-user (JWT) with PostgreSQL for shared use.
  - Power User: Wants MCP clients configured to talk to tldw_server’s MCP Unified module.

### Success Metrics
  - ≥90% users complete single-user init without manual file editing.
  - Verified server start via uvicorn on first run ≥80% of attempts.
  - “Doctor” resolves ≥70% of common issues automatically or with actionable guidance.

### Scope
 - MVP
      - init (interactive defaults): env + DB + providers + verify + summary
      - auth (single_user|multi_user) and .env management
      - db (SQLite default; optional PostgreSQL validation)
      - providers (LLM/STT/TTS keys; write .env or Config_Files/config.txt)
      - mcp (configure MCP clients: Claude, Cursor, VS Code, Zed)
      - verify (API health check, ffmpeg check, CUDA check)
      - format (git-aware Black/Ruff on changed files)
      - doctor (auto-fix or print actionable steps)
  - V2 (Future)
      - Agent mode: delegate edits to MCP Unified agent for frontend/client integration
      - Host provider env upload helpers (optional, offline-first stance)

### CLI UX

  - Console entrypoint: `tldw-setup [command] [options]`
  - Module fallback (repo/local): `python -m tldw_Server_API.cli.wizard.cli [command] [options]`
  - Commands
      - init – full guided setup. Options: --default, --install-dir, --non-interactive, --debug, --dry-run, --json
      - auth – set AUTH_MODE, provision defaults. Options: --mode=single_user|multi_user
      - db – init and validate databases. Options: --postgres-url, --sqlite-paths
      - providers – collect and store provider/api keys. Options: --openai-key, --..., --check-provider
      - mcp – install/remove MCP server in supported clients. Options: add|remove, --local
      - verify – run checks: ffmpeg, CUDA, key presence, server endpoints reachable (/api/v1/health, /healthz, /mcp/status)
      - format – run Black/Ruff only on changed files if in git repo
      - doctor – detect issues and propose/apply fixes
  - Common flags
      - --debug (verbose logging), --default (skip prompts with safe defaults), --install-dir (default: CWD), --force (overwrite with backup), --non-interactive (env-driven), --dry-run (preview changes), --json (machine-readable output), --yes/--no-input (assume yes), --no-format (skip format), --no-color, --quiet
  - Non-interactive env mapping (consumed when `--non-interactive` or `--yes/--no-input`):
      - AUTH_MODE, SINGLE_USER_API_KEY, DATABASE_URL
      - OPENAI_API_KEY, ANTHROPIC_API_KEY, and other provider-specific keys
      - TLDW_CHECK_PROVIDER (1/0) to enable provider verification
      - TLDW_SERVER_PORT (port selection for ephemeral verification spin-up)

### Functional Requirements

  - Detection
      - Detect .env or .env.local, .git, presence of ffmpeg/CUDA, and active ports.
      - Detect DB mode via DATABASE_URL or default SQLite layouts described in AGENTS.md.
      - Prefer local checks; avoid external network calls unless explicitly requested.
  - Env management
      - Create/update .env and .gitignore safely; append keys only if missing; update values if changed.
      - Write `.env` with restrictive permissions (0600) and ensure `.env`/`.env.local` are gitignored.
      - Never log secrets. Mask on screen except when explicitly revealed to user.
  - Auth modes
      - single_user: set AUTH_MODE=single_user, ensure SINGLE_USER_API_KEY exists or generate.
      - multi_user: set AUTH_MODE=multi_user, validate DATABASE_URL, offer to run AuthNZ initializer (`python -m tldw_Server_API.app.core.AuthNZ.initialize`).
  - DB initialization
      - SQLite: ensure on-disk structure exists per-user conventions. Confirm writeability. Canonical defaults:
          - Content (Media DB v2): `<USER_DB_BASE_DIR>/<user_id>/Media_DB_v2.db`
          - Notes/Chats: `<USER_DB_BASE_DIR>/<user_id>/ChaChaNotes.db`
          - Evaluations: `Databases/evaluations.db`
          - AuthNZ users (if SQLite): `Databases/users.db` (PostgreSQL recommended for multi-user)
      - PostgreSQL: validate connection and permissions; print migration helper instructions (no implicit destructive ops). For tests, reuse the AuthNZ Postgres fixture rather than rolling your own.
  - Providers
      - Prompt for LLM/STT/TTS keys (OpenAI, Anthropic, local); prefer `.env` as the source of truth. Generate/update `Config_Files/config.txt` only when missing or explicitly requested.
      - Optionally run a no-op test call (offline/mocked) gated behind `--check-provider` or `TLDW_CHECK_PROVIDER=1`; otherwise, lint format and file placement without network calls.
  - MCP clients
      - Detect supported clients (cursor/claude/vscode/zed) and add MCP server entries pointing to tldw_server MCP Unified endpoints.
      - Back up any modified client config and avoid duplicates. Provide a dry-run with human-readable diffs; maintain a compatibility table of known paths per OS and client.
  - Verify
      - Check: ffmpeg present; CUDA visible if requested; Python deps; ports; server endpoints (`GET /api/v1/health`, `GET /api/v1/healthz`, `GET /api/v1/mcp/status`) and docs reachable if started.
      - If server not running, optionally spin uvicorn in background for checks on an ephemeral or specified port (respect `TLDW_SERVER_PORT`); detect conflicts and ensure clean shutdown with timeout.
  - Formatting
      - If in a git repo, run black/ruff only on changed/untracked files. Detect tool availability and skip gracefully if not installed. Provide `--no-format` to opt out.
  - Idempotency and backups
      - Skip re-writes if unchanged; create .bak with timestamp on first write to existing files. Prefer atomic writes and roll back on failure.
  - Error handling
      - Clear, meaningful messages with hints; safe fallbacks; never crash mid-step without a summary.

### Non‑Functional Requirements

  - Security/Privacy
      - No telemetry. No external network calls outside explicit “verify provider” toggles.
      - Redact keys in logs; keep .env entries minimal and consistent. If local logging is enabled, write to `wizard.log` (rotated/truncated) with secrets redacted and ensure it is gitignored.
  - Performance
      - Init completes in ≤30s on typical dev machines (excluding optional server verification).
  - Compatibility
      - Python 3.10+; macOS/Linux/Windows (WSL); supports repo layout described in AGENTS.md. ffmpeg detection and install help should be platform-aware (brew/apt/choco). GPU detection should allow opting out; on Apple Silicon, avoid NVIDIA-only assumptions and optionally detect MLX if present.
  - Quality
      - PEP8, type hints, docstrings; use Loguru for logging; async I/O where applicable.
  - Reliability
      - Atomic writes; consistent rollbacks on failure; detailed error context.

### Architecture

  - Language/Libs
      - Python, Typer for CLI, Rich for UX, python-dotenv for env file handling, Loguru for logging.
  - Directory Layout
      - tldw_Server_API/cli/wizard/cli.py (Typer main; packaged)
      - tldw_Server_API/cli/wizard/steps/*.py (prereqs, auth, db, providers, mcp, verify, format, summary)
      - tldw_Server_API/cli/wizard/utils/{env.py,files.py,git.py,format.py,detect.py,validation.py}
      - Helper_Scripts/wizard/ (optional thin wrappers for repo-only usage)
      - tldw_Server_API/tests/wizard/ (unit + integration tests)
  - Patterns
      - Step registry with clear inputs/outputs; shared context object with install dir, decisions, detected facts.
      - File ops via utils that ensure idempotency and backups (atomic writes).
      - Config precedence: env vars > .env > Config_Files/config.txt (enforced consistently to avoid drift).
  - MCP Client Config
      - Implement per-client writers that know default config paths; check install; add server entry; back up file; avoid duplicates. Provide dry-run and diff previews before write.

### User Flows

  - Quick Start
      - `tldw-setup init` (or `python -m tldw_Server_API.cli.wizard.cli init`)
      - Wizard asks for mode (default single_user), writes `.env` (0600), initializes DBs, asks for provider keys, offers MCP client config, runs verify (health/mcp status), formats changes, prints summary (including paths and next steps).
  - Multi‑User Flow
      - `tldw-setup auth --mode=multi_user`
      - Prompt for `DATABASE_URL` (Postgres), optionally run AuthNZ initializer (`python -m tldw_Server_API.app.core.AuthNZ.initialize`), set `AUTH_MODE=multi_user`, verify connections.
  - MCP Install
      - `tldw-setup mcp add`
      - Detect clients, show selection, preview diffs, write client config entries with backups, print next steps.
  - Non‑interactive Flow (CI / scripted)
      - Provide required env vars (see mapping above) and run `tldw-setup init --non-interactive --yes --json --no-format`.
      - Exits non-zero on failure; prints machine-readable summary.

### Files and Keys Managed

  - .env
      - AUTH_MODE, SINGLE_USER_API_KEY (generated when needed), DATABASE_URL, provider keys, OPENAI_API_KEY, etc. Written with mode 0600.
  - .gitignore
      - Ensure `.env`, `.env.local`, and `wizard.log` entries exist.
  - MCP Client Configs
      - Known paths for Cursor, Claude, VS Code, Zed. Maintain backups and non-duplication.
  - Logs
      - Optional `wizard.log` (rotated/truncated, redacted) for local troubleshooting; never includes raw secrets.

### Acceptance Criteria

  - init creates or updates .env with correct keys; prints paths; no duplicate lines.
  - auth sets correct AUTH_MODE and supports both single/multi; multi-user validates DB connection or prints clear guidance.
  - db creates SQLite files in expected locations and ensures writeability.
  - providers stores keys in `.env` by default; never logs them; re-run updates values without duplicates; `config.txt` generated only on explicit request.
  - mcp detects supported clients and installs entries with backups; preview diffs; re-run offers reinstall; removal works and is confirmed.
  - verify detects missing ffmpeg/CUDA/keys and provides actionable steps; confirms health endpoints and MCP status reachable (when server is started/spun-up).
  - format runs only on changed/untracked files when in git repo; no-op otherwise; skips gracefully if tools unavailable.
  - Every step is idempotent and atomic; repeated runs do not corrupt configs; failures roll back partial writes.
  - `.env` file permissions are 0600; `.gitignore` updated; `wizard.log` (if present) is redacted and ignored by git.
  - `--json` output mode emits a stable machine-readable schema; `--dry-run` produces an accurate preview without writes.

### Testing Plan

  - Unit
      - Env manipulations, git detection, file write idempotency, path handling, key masking, mcp client config writers.
  - Integration
      - Run init in a temporary directory (with and without git), assert files created, env updated (0600), backups created on second run, atomicity under induced failures.
      - Multi-user path that reuses the project’s AuthNZ PostgreSQL fixture for connectivity (no ad-hoc DB setup).
      - Server verification spins uvicorn on a free ephemeral port and shuts down cleanly within a timeout.
  - E2E (optional)
      - Smoke-run server verification in CI with SQLite; skip CUDA tests.
  - Coverage
      - ≥80% for wizard code.

### Risks

  - OS-specific client config paths vary: maintain well-tested per-client adapters, a compatibility table of paths/schemas, dry-run/diff previews, and back up before writing.
  - Users with non-standard repo layouts: prefer prompts with detection hints and clear fallback paths.
  - Provider verification causing network calls: gate behind an explicit --check-provider flag and mock in tests.

### Rollout

  - Phase 1: MVP without agent mode; single_user first; SQLite only.
  - Phase 2: Multi-user with Postgres validation; MCP client install.
  - Phase 3: Optional agent mode; host-provider env export helpers.

### Milestones

  - Week 1–2: CLI skeleton (Typer), env + prereqs + format + tests, console script entry (`tldw-setup`).
  - Week 3: Auth modes + DB init + verify + tests.
  - Week 4: Providers + MCP clients + doctor + docs; stabilization.

### Decisions (formerly Open Questions)

  - Auto-run AuthNZ initializer during init for multi-user: Yes, prompt first; support `--non-interactive` consent via `--yes`.
  - MCP client config locations: Maintain a compatibility table per OS/client; probe known paths and allow manual override.
  - Local troubleshooting log: Provide optional `wizard.log` with redaction, rotation, and `.gitignore` entry.

### Deliverables

  - Packaged CLI under `tldw_Server_API/cli/wizard/` with PEP8, types, docstrings.
  - Console entrypoint `tldw-setup` added to `project.scripts`.
  - Tests under `tldw_Server_API/tests/wizard/` with fixtures (reusing AuthNZ Postgres fixture where applicable).
  - `Docs/Development/Wizard.md` with usage, flags, non-interactive mapping, and troubleshooting.
  - `IMPLEMENTATION_PLAN.md` maintained per AGENTS.md process and linked from the PRD.

### Implementation Plan

## Stage 1: Scaffold + Packaging
**Goal**: Ship a packaged CLI skeleton with core commands, safe file ops, and JSON output.
**Success Criteria**:
- Console script `tldw-setup` available after install; module fallback works.
- Commands `init`, `auth`, `db`, `providers`, `mcp`, `verify`, `format`, `doctor` exist with `--dry-run` and `--json` modes.
- `.env` is created with mode 0600 when missing; `.gitignore` contains `.env`, `.env.local`, `wizard.log`.
- Formatting runs on changed files (when available) and skips gracefully otherwise.
**Tests**:
- CLI smoke tests for `init --dry-run --json`, `auth --mode single_user --json`, `verify --json`.
- `.env` creation and permissions verified in tmpdir.
**Status**: Complete

## Stage 2: Env Management + Auth Modes
**Goal**: Implement robust `.env` merge/update with masking and key generation; support single/multi-user flows.
**Success Criteria**:
- Key-by-key merge without duplicates; backups on first modification; atomic writes.
- Generate `SINGLE_USER_API_KEY` if missing (single_user); set `AUTH_MODE` reliably.
- Multi-user: prompt or non-interactive consent to run `python -m tldw_Server_API.app.core.AuthNZ.initialize` after validating `DATABASE_URL`.
- No secrets logged; masks in console and logs.
**Tests**:
- Unit tests for merge logic (idempotency, dedupe, updates, backup on first change).
- Integration tests: single_user first run and re-run; multi_user path with valid/invalid `DATABASE_URL`.
**Status**: Not Started

## Stage 3: Database Initialization + Verification
**Goal**: Create per-user SQLite structure and validate Postgres connectivity.
**Success Criteria**:
- Create and verify canonical SQLite paths (Media DB v2, Notes/Chats, Evaluations) with writeability checks.
- Postgres: validate connectivity/permissions (no destructive ops). Provide clear migration guidance.
- For tests, reuse AuthNZ Postgres fixture; no ad-hoc DB setup.
**Tests**:
- Integration tests using tmpdir for SQLite creation; permissions and write probes.
- Fixture-backed connectivity test for Postgres (skippable when fixture unavailable).
**Status**: Not Started

## Stage 4: Verification Endpoints + Ephemeral Server
**Goal**: Verify `/api/v1/health`, `/api/v1/healthz`, and `/api/v1/mcp/status`; support ephemeral uvicorn start/stop.
**Success Criteria**:
- Respect `TLDW_SERVER_PORT` or auto-pick a free port; detect conflicts.
- Start server in background, perform health checks, and shut down cleanly with timeout.
- Clear diagnostics on failures with actionable next steps.
**Tests**:
- Ephemeral server spin-up/down on a free port; retries; timeout handling.
- Health endpoint shape and status code expectations.
**Status**: Not Started

## Stage 5: Providers + MCP Client Configuration
**Goal**: Manage provider keys (.env-first) and add MCP entries with dry-run diffs and backups.
**Success Criteria**:
- Provider keys written to `.env`; `config.txt` generated only on explicit request.
- Optional offline/mock provider checks gated by `--check-provider` or env.
- MCP writers for Cursor/Claude/VS Code/Zed: detect install, path per OS, dry-run diff preview, timestamped backups, duplicate avoidance, and removal confirmation.
**Tests**:
- Unit tests for provider key write/update (idempotency, masking).
- MCP path detection per OS (mocked); diff generation and backup logic.
**Status**: Not Started

## Stage 6: Doctor (Auto-Fix Heuristics)
**Goal**: Implement remediation for common issues with preview and confirmation.
**Success Criteria**:
- Detect and optionally fix missing `.env` keys, `.gitignore` entries, ffmpeg absence (print install hints), invalid `DATABASE_URL`, and conflicting ports.
- `--dry-run` shows planned fixes; `--json` returns structured recommendations.
**Tests**:
- Unit tests for each heuristic; integration tests for end-to-end doctor runs in tmpdir.
**Status**: Not Started

## Stage 7: CI/DX Polish + Docs
**Goal**: Finalize docs, improve DX, and strengthen CI coverage.
**Success Criteria**:
- `Docs/Development/Wizard.md` complete; README links to wizard quickstart.
- Coverage ≥80% for wizard code; stable JSON schemas documented.
- Pre-commit hooks include formatting on wizard code; all tests passing in CI.
**Tests**:
- CI job for wizard tests; coverage thresholds enforced.
**Status**: Not Started
