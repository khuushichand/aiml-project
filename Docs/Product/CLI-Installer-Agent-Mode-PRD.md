# PRD: CLI Installer Agent Mode (V2)

### Overview
  - Goal: Add an agent-driven setup path that can plan and optionally apply repo-safe changes to accelerate advanced setup tasks.
  - Style: Offline-first, explicit approval gates, tool allowlist, deterministic outputs with clear diffs.
  - Outcomes: Faster multi-step setup, fewer manual edits, safer automation with machine-readable plans.

### Objectives
  - Provide a guided agent mode for complex setup tasks (e.g., client integration, env alignment, repo config).
  - Ensure every agent action is explainable, previewable, and reversible.
  - Preserve security and privacy: no network calls without explicit opt-in.

### Non-Goals
  - Fully autonomous modifications without user approval.
  - Remote hosting provisioning or infrastructure changes.
  - Automatic edits outside the repo or explicit allowlisted paths.

### Personas
  - Power User: Wants the CLI to propose and apply multi-step setup changes.
  - Team Developer: Needs repeatable steps to align server and client config.
  - Maintainer: Wants consistent, auditable changes with tight safety rails.

### Success Metrics
  - ≥80% of agent-mode runs complete without manual edits outside approvals.
  - ≥90% of generated plans contain valid actionable steps.
  - 0 high-severity incidents from unintended file changes (guard rails hold).

### Scope
  - MVP
      - Agent mode command or flag that produces a structured plan and optionally applies it.
      - Tool allowlist limited to repo-safe operations (read, diff, wizard steps, formatting).
      - Explicit approval flow per action (or `--yes` for scripted runs).
      - JSON output with stable schema for plan + action results.
  - Future
      - Optional remote model selection with strong network gating.
      - Agent-assisted integrations for external clients (Cursor/VS Code/Claude) beyond MCP config.

### CLI UX
  - Entry points
      - `tldw-setup agent --goal "configure ui + env" [options]`
      - `tldw-setup init --agent [options]` (agent used for selected steps)
  - Key options
      - `--goal` (freeform intent), `--plan-only`, `--apply`, `--dry-run`, `--json`
      - `--yes/--no-input` (assume approval), `--allow-network` (explicit opt-in)
      - `--model` (optional model override), `--tools` (optional tool allowlist)
  - Output
      - Human-readable plan and diff previews.
      - JSON payload with `plan`, `actions`, `status`, and `notes`.

### Functional Requirements
  - Planning
      - Collect local context (detected config, repo layout, wizard facts).
      - Generate a plan with ordered actions, each with expected effects and affected files.
  - Execution
      - Support `--plan-only` to emit plan without changes.
      - Require explicit confirmation for each action unless `--yes` is provided.
      - Apply changes using existing wizard utilities (env, gitignore, providers, mcp, format).
      - Always generate diffs for file edits and capture before/after snapshots for undo.
  - Guard Rails
      - Tool allowlist enforced at runtime; default is repo-only actions.
      - No network calls unless `--allow-network` or explicit step gating.
      - Path allowlist restricts writes to repo and known config locations.
  - JSON Schema
      - Include top-level `status`, `command`, `facts`, `actions`, `notes`.
      - Agent-specific action shape:
          - `agent_plan`: { "summary", "steps", "approval_required": true }
          - `agent_action`: { "id", "status", "description", "changes": [...] }
  - Error Handling
      - On failure, emit actionable errors and stop further actions unless `--continue-on-error`.
      - Always include a rollback hint (e.g., backup path, revert instructions).

### Non-Functional Requirements
  - Security/Privacy
      - Secrets redacted in logs and JSON output.
      - No telemetry; no remote calls unless explicitly enabled.
  - Reliability
      - Atomic writes and backups for every file change.
      - Idempotent actions; repeated runs should not cause drift.
  - Performance
      - Plan generation under 10s on typical dev machines (offline mode).

### Architecture
  - CLI orchestrates agent mode using MCP Unified tool execution endpoints.
  - Agent prompt built from wizard facts, config summary, and explicit user goal.
  - Tools exposed to agent:
      - Read-only: repo scan, file read, config summary.
      - Write: env updates, gitignore updates, format on changed files.
  - All tool calls mediated by the CLI to enforce allowlists and approvals.

### User Flows
  - Plan-only flow
      - `tldw-setup agent --goal "configure ui env" --plan-only --json`
      - Output plan, list of actions, and recommended next steps.
  - Apply flow (interactive)
      - CLI presents each action with diff; user approves or skips.
      - Summary includes applied actions and rollback hints.
  - Non-interactive flow (CI)
      - `tldw-setup agent --goal "sync env" --apply --yes --json --no-format`
      - Exits non-zero on any action failure.

### Testing Plan
  - Unit
      - Plan assembly, tool allowlist enforcement, diff generation, JSON schema.
  - Integration
      - Agent plan-only run in tmpdir with fixtures; verify no writes.
      - Apply flow with `--yes` for env/gitignore actions; validate backups.
  - Mocked MCP
      - Use a stubbed MCP Unified client to simulate agent plan outputs.

### Risks
  - Overreach of agent actions: mitigate with strict allowlists and confirmations.
  - Model variability: mitigate with deterministic plan schema validation.
  - Accidental network calls: default to offline and require explicit opt-in.

### Acceptance Criteria
  - Agent mode emits a structured plan and does not modify files in plan-only mode.
  - Approved actions apply via existing wizard utilities with backups and diffs.
  - `--json` output matches the stable envelope schema and includes agent actions.
  - Agent mode honors tool allowlists and fails closed on disallowed operations.
