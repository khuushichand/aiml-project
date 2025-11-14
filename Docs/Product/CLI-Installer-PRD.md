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
- 
  - Solo Developer: Wants local, single-user API key mode working quickly.
  - Team Developer: Sets up multi-user (JWT) with PostgreSQL for shared use.
  - Power User: Wants MCP clients configured to talk to tldw_server’s MCP Unified module.

### Success Metrics
- 
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

  - Entrypoint: python -m Helper_Scripts.wizard.cli [command] [options]
  - Commands
      - init – full guided setup. Options: --default, --install-dir, --non-interactive, --debug
      - auth – set AUTH_MODE, provision defaults. Options: --mode=single_user|multi_user
      - db – init and validate databases. Options: --postgres-url, --sqlite-paths
      - providers – collect and store provider/api keys. Options: --openai-key, --...
      - mcp – install/remove MCP server in supported clients. Options: add|remove, --local
      - verify – run checks: ffmpeg, CUDA, key presence, server endpoints reachable
      - format – run Black/Ruff only on changed files if in git repo
      - doctor – detect issues and propose/apply fixes
  - Common flags
      - --debug (verbose logging), --default (skip prompts with safe defaults), --install-dir (default: CWD), --force (overwrite with backup), --non-interactive (env-driven)

### Functional Requirements

  - Detection
      - Detect .env or .env.local, .git, presence of ffmpeg/CUDA, and active ports.
      - Detect DB mode via DATABASE_URL or default SQLite layouts described in AGENTS.md.
  - Env management
      - Create/update .env and .gitignore safely; append keys only if missing; update values if changed.
      - Never log secrets. Mask on screen except when explicitly revealed to user.
  - Auth modes
      - single_user: set AUTH_MODE=single_user, ensure SINGLE_USER_API_KEY exists or generate.
      - multi_user: set AUTH_MODE=multi_user, validate DATABASE_URL, offer to run AuthNZ initializer.
  - DB initialization
      - SQLite: ensure on-disk structure exists per per-user conventions. Confirm writeability.
      - PostgreSQL: validate connection and permissions; print migration helper instructions (no implicit destructive ops).
  - Providers
      - Prompt for LLM/STT/TTS keys (OpenAI, Anthropic, local); write to .env or Config_Files/config.txt.
      - Optionally run a no-op test call if available in offline/mocked mode; otherwise, lint format and file placement.
  - MCP clients
      - Detect supported clients (cursor/claude/vscode/zed) and add MCP server entries pointing to tldw_server MCP Unified endpoints.
      - Back up any modified client config and avoid duplicates.
  - Verify
      - Check: ffmpeg present; CUDA visible if requested; Python deps; ports; server endpoints GET /api/v1/mcp/status, GET /docs reachable if started.
      - If server not running, optionally spin uvicorn in background for checks and stop after.
  - Formatting
      - If in a git repo, run black/ruff only on changed/untracked files.
  - Idempotency and backups
      - Skip re-writes if unchanged; create .bak with timestamp on first write to existing files.
  - Error handling
      - Clear, meaningful messages with hints; safe fallbacks; never crash mid-step without a summary.

### Non‑Functional Requirements

  - Security/Privacy
      - No telemetry. No external network calls outside explicit “verify provider” toggles.
      - Redact keys in logs; keep .env entries minimal and consistent.
  - Performance
      - Init completes in ≤30s on typical dev machines (excluding optional server verification).
  - Compatibility
      - Python 3.10+; macOS/Linux/Windows (WSL); supports repo layout described in AGENTS.md.
  - Quality
      - PEP8, type hints, docstrings; use Loguru for logging; async I/O where applicable.
  - Reliability
      - Atomic writes; consistent rollbacks on failure; detailed error context.

### Architecture

  - Language/Libs
      - Python, Typer for CLI, Rich for UX, python-dotenv for env file handling, Loguru for logging.
  - Directory Layout
      - Helper_Scripts/wizard/cli.py (Typer main)
      - Helper_Scripts/wizard/steps/*.py (prereqs, auth, db, providers, mcp, verify, format, summary)
      - Helper_Scripts/wizard/utils/{env.py,files.py,git.py,format.py,detect.py,validation.py}
      - tldw_Server_API/tests/wizard/ (unit + integration tests)
  - Patterns
      - Step registry with clear inputs/outputs; shared context object with install dir, decisions, detected facts.
      - File ops via utils that ensure idempotency and backups.
      - Config precedence: env vars > .env > Config_Files/config.txt.
  - MCP Client Config
      - Implement per-client writers that know default config paths; check install; add server entry; back up file; avoid duplicates.

### User Flows

  - Quick Start
      - python -m Helper_Scripts.wizard.cli init
      - Wizard asks for mode (default single_user), writes .env, initializes DBs, asks for provider keys, offers MCP client config, runs verify, formats changes, prints summary.
  - Multi‑User Flow
      - python -m Helper_Scripts.wizard.cli auth --mode=multi_user
      - Prompt for DATABASE_URL (Postgres), run AuthNZ initializer if desired, set AUTH_MODE=multi_user, verify connections.
  - MCP Install
      - python -m Helper_Scripts.wizard.cli mcp add
      - Detect clients, show selection, write client config entries, print next steps.

### Files and Keys Managed

  - .env
      - AUTH_MODE, SINGLE_USER_API_KEY (generated when needed), DATABASE_URL, provider keys, OPENAI_API_KEY, etc.
  - .gitignore
      - Ensure .env, .env.local entries exist.
  - MCP Client Configs
      - Known paths for Cursor, Claude, VS Code, Zed. Maintain backups and non-duplication.

### Acceptance Criteria

  - init creates or updates .env with correct keys; prints paths; no duplicate lines.
  - auth sets correct AUTH_MODE and supports both single/multi; multi-user validates DB connection or prints clear guidance.
  - db creates SQLite files in expected locations and ensures writeability.
  - providers stores keys; never logs them; re-run updates values without duplicates.
  - mcp detects supported clients and installs entries; re-run offers reinstall; removal works.
  - verify detects missing ffmpeg/CUDA/keys and provides actionable steps; optionally confirms API endpoints reachable.
  - format runs only on changed/untracked files when in git repo; no-op otherwise.
  - Every step is idempotent; repeated runs do not corrupt configs.

### Testing Plan

  - Unit
      - Env manipulations, git detection, file write idempotency, path handling, key masking, mcp client config writers.
  - Integration
      - Run init in a temporary directory (with and without git), assert files created, env updated, backups created on second run.
      - Multi-user path with fake DATABASE_URL success/failure.
  - E2E (optional)
      - Smoke-run server verification in CI with SQLite; skip CUDA tests.
  - Coverage
      - ≥80% for wizard code.

### Risks

  - OS-specific client config paths vary: maintain well-tested per-client adapters and back up before writing.
  - Users with non-standard repo layouts: prefer prompts with detection hints and clear fallback paths.
  - Provider verification causing network calls: gate behind an explicit --check-provider flag and mock in tests.

### Rollout

  - Phase 1: MVP without agent mode; single_user first; SQLite only.
  - Phase 2: Multi-user with Postgres validation; MCP client install.
  - Phase 3: Optional agent mode; host-provider env export helpers.

### Milestones

  - Week 1–2: CLI skeleton, env + prereqs + format + tests.
  - Week 3: Auth modes + DB init + verify + tests.
  - Week 4: Providers + MCP clients + doctor + docs; stabilization.

### Open Questions

  - Do we want to auto-run AuthNZ initializer during init for multi-user?
  - Which MCP client config locations are most commonly installed per OS in our user base?
  - Should we create a wizard.log for local troubleshooting?

### Deliverables

  - CLI code under Helper_Scripts/wizard/ with PEP8, types, docstrings.
  - Tests under tldw_Server_API/tests/wizard/ with fixtures.
  - Docs/Development/Wizard.md with usage examples and troubleshooting.
  - IMPLEMENTATION_PLAN.md maintained per AGENTS.md process.