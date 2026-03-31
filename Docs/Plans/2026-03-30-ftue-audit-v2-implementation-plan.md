# FTUE Audit v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 13 residual FTUE issues found in the second audit pass, covering Docker hardening, frontend UX, and documentation polish.

**Architecture:** All changes are isolated edits to existing files. No new modules, no migrations, no architectural changes. Backend fixes harden the Docker entrypoint and startup preflight. Frontend fixes improve CompanionHomeShell and onboarding text. Documentation fixes add troubleshooting guidance.

**Tech Stack:** Shell (entrypoint), Python (preflight), TypeScript/React (frontend), Markdown (docs)

---

### Task 1: Docker entrypoint — fail on init error (P0)

**Files:**
- Modify: `Dockerfiles/entrypoints/tldw-app-first-run.sh:126-134`

**Step 1: Add error check after initialize command**

Replace lines 126-134:

```sh
if [ "$AUTH_MODE" = "single_user" ] && [ "$RUN_AUTH_INIT_ON_START" != "0" ] && [ "$should_run_auth_init" = "1" ]; then
  mkdir -p "$AUTH_MARKER_DIR"
  if [ ! -f "$AUTH_MARKER_FILE" ]; then
    echo "[entrypoint] Running first-use auth initialization..."
    if ! python -m tldw_Server_API.app.core.AuthNZ.initialize --non-interactive; then
      echo "[entrypoint] ERROR: Auth initialization failed. Fix configuration and restart." >&2
      exit 1
    fi
    touch "$AUTH_MARKER_FILE"
    echo "[entrypoint] Auth initialization complete."
  fi
fi
```

**Step 2: Verify by reading the file**

Confirm `if !` wraps the python command and `exit 1` follows the error message.

**Step 3: Commit**

```
fix: fail Docker entrypoint on auth init failure
```

---

### Task 2: Docker compose — document placeholder pattern (P1)

**Files:**
- Modify: `Dockerfiles/docker-compose.yml:16-17`

**Step 1: Add comment explaining placeholder detection**

Change line 16-17 from:
```yaml
      # Provide a secure API key in single_user mode
      - SINGLE_USER_API_KEY=${SINGLE_USER_API_KEY:-change-me}
```
To:
```yaml
      # Provide a secure API key in single_user mode.
      # Placeholder values (change-me, CHANGE_ME*, etc.) are auto-replaced
      # by the entrypoint with a secure random key on first run.
      - SINGLE_USER_API_KEY=${SINGLE_USER_API_KEY:-change-me}
```

**Step 2: Add UVICORN_WORKERS guidance (issue 13)**

Change line 26 from:
```yaml
      - UVICORN_WORKERS=${UVICORN_WORKERS:-4}
```
To:
```yaml
      # Worker count. Default 4. Set to 1-2 for machines with <4GB RAM.
      - UVICORN_WORKERS=${UVICORN_WORKERS:-4}
```

**Step 3: Commit**

```
docs: clarify Docker compose placeholder and worker defaults
```

---

### Task 3: Multi-user profile — actionable JWT_SECRET_KEY (P1)

**Files:**
- Modify: `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md:21-27`

**Step 1: Make JWT generation an explicit step**

Replace the .env configuration block (lines 21-27) with:

```markdown
Configure multi-user mode in `.env`:

```bash
AUTH_MODE=multi_user
```

Generate and set the required secrets:

```bash
# Run each command, then paste the output into .env as the value
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste as: JWT_SECRET_KEY=<output>

python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste as: MCP_JWT_SECRET=<output>

python -c "import secrets; print(secrets.token_urlsafe(32))"
# Paste as: MCP_API_KEY_SALT=<output>
```

Set the Postgres connection URL (see Postgres Options below):

```bash
DATABASE_URL=postgresql://tldw_user:your_password@postgres:5432/tldw_users
```
```

**Step 2: Commit**

```
docs: make JWT_SECRET_KEY generation actionable in multi-user profile
```

---

### Task 4: Startup preflight — DATABASE_URL connectivity check (P1)

**Files:**
- Modify: `tldw_Server_API/app/core/startup_preflight.py`

**Step 1: Add check_database_connectivity function**

Add after `check_python_dependencies()` (after line 125):

```python
def check_database_connectivity() -> dict[str, Any]:
    """Attempt a basic connection test for Postgres DATABASE_URLs."""
    name = "database_connectivity"
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url.startswith("postgresql"):
        return {"name": name, "status": "ok", "message": "SQLite (no remote check needed)"}
    try:
        import socket
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
        return {"name": name, "status": "ok", "message": f"Postgres reachable at {host}:{port}"}
    except OSError as exc:
        return {
            "name": name,
            "status": "fail",
            "message": f"Cannot reach Postgres at DATABASE_URL: {exc}. Check host, port, and network.",
        }
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "status": "warn", "message": f"Could not parse DATABASE_URL: {exc}"}
```

**Step 2: Register check in run_preflight_checks**

Add `check_database_connectivity` to the tuple in `run_preflight_checks()` (line 144-149):

```python
    for check_fn in (
        check_ffmpeg_available,
        check_disk_space,
        check_database_directories,
        check_python_dependencies,
        check_database_connectivity,
    ):
```

**Step 3: Commit**

```
feat: add DATABASE_URL connectivity check to startup preflight
```

---

### Task 5: Extension intro — demo mode limitations text (P1)

**Files:**
- Modify: `apps/tldw-frontend/extension/routes/option-index.tsx:36-41`

**Step 1: Add limitation subtitle to demo button**

Change the demo button from:
```tsx
      <button
        onClick={onDemo}
        className="w-full rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-text-subtle transition-colors hover:bg-surface-hover"
      >
        Try demo mode (no server needed)
      </button>
```
To:
```tsx
      <button
        onClick={onDemo}
        className="w-full rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-text-subtle transition-colors hover:bg-surface-hover"
      >
        <span>Try demo mode (no server needed)</span>
        <span className="block mt-1 text-xs opacity-70">
          Explore with sample data. Chat and search use demo content only.
        </span>
      </button>
```

**Step 2: Commit**

```
fix: explain demo mode limitations in extension intro
```

---

### Task 6: CompanionHomeShell — demo exit, language, badge (P1-P2)

This task addresses issues 6, 7, and 8 together since they all modify the same file.

**Files:**
- Modify: `apps/packages/ui/src/components/Option/CompanionHome/CompanionHomeShell.tsx`

**Step 1: Add demo mode import and exit banner, fix language, remove badge**

Replace the entire file content with:

```tsx
import { Link } from "react-router-dom"

import { useDemoMode } from "@/context/demo-mode"
import { CompanionHomePage } from "./CompanionHomePage"

type CompanionHomeShellProps = {
  surface: "options" | "sidepanel"
  onPersonalizationEnabled?: () => void
}

export function CompanionHomeShell({
  surface,
  onPersonalizationEnabled
}: CompanionHomeShellProps) {
  const { demoEnabled, setDemoEnabled } = useDemoMode()

  const actions =
    surface === "sidepanel"
      ? [
          {
            href: "/?view=chat",
            label: "Open Chat",
            description: "Jump back into the sidepanel chat workspace."
          },
          {
            href: "/settings",
            label: "Open Settings",
            description: "Adjust connection and sidepanel behavior."
          }
        ]
      : [
          {
            href: "/chat",
            label: "Open Chat",
            description: "Continue active work in the main chat workspace."
          },
          {
            href: "/knowledge",
            label: "Open Knowledge",
            description: "Review sources, notes, and captured knowledge from the main workspace."
          },
          {
            href: "/media-multi",
            label: "Open Analysis",
            description: "Review and compare media from the main workspace."
          }
        ]

  return (
    <section
      className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8"
      data-testid="companion-home-shell"
    >
      {demoEnabled && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-text">
                You are in demo mode
              </p>
              <p className="mt-1 text-xs text-text-muted">
                Chat and search use sample data only. Connect a server for full functionality.
              </p>
            </div>
            <Link
              to="/setup"
              onClick={() => setDemoEnabled(false)}
              className="shrink-0 rounded-lg border border-border bg-bg px-3 py-1.5 text-xs font-medium text-text transition-colors hover:bg-surface-hover"
            >
              Connect a server
            </Link>
          </div>
        </div>
      )}

      <CompanionHomePage
        onPersonalizationEnabled={onPersonalizationEnabled}
        surface={surface}
      />

      <div className="rounded-3xl border border-border/80 bg-surface/90 p-5 shadow-sm backdrop-blur-sm">
        <div>
          <h2 className="text-lg font-semibold text-text">Quick actions</h2>
          <p className="mt-1 text-sm text-text-muted">
            Jump to the main features.
          </p>
        </div>
        <div className="grid gap-3 pt-4 sm:grid-cols-2 xl:grid-cols-3" data-testid="companion-home-quick-actions">
          {actions.map((action) => (
            <Link
              key={action.href}
              to={action.href}
              data-testid={`companion-home-action-${action.href.replace(/\//g, "-").replace(/^-/, "")}`}
              className="rounded-2xl border border-border bg-bg/60 px-4 py-4 transition-colors hover:border-primary/40 hover:bg-primary/5"
            >
              <div className="text-sm font-semibold text-text">{action.label}</div>
              <p className="mt-2 text-sm leading-6 text-text-muted">{action.description}</p>
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}
```

Changes from current:
- Added `useDemoMode` import and hook call
- Added amber demo-mode banner with "Connect a server" link that clears demo and navigates to `/setup`
- Changed "Keep the old escape hatches close..." to "Jump to the main features."
- Removed the surface badge (`<span>options</span>`)
- Removed `justify-between` on the header div (no badge to space against)

**Step 2: Commit**

```
fix: add demo exit banner, fix language, remove surface badge on home page
```

---

### Task 7: API key help text — cover local installs (P2)

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Onboarding/OnboardingConnectForm.tsx`

**Step 1: Update API key help text**

Find the help text (search for `settings:onboarding.apiKeyHelp`) and change from:
```tsx
                  "Using Docker quickstart? The WebUI connects automatically \u2014 no key needed. For API or extension access, run: make show-api-key"
```
To:
```tsx
                  "Docker quickstart? The WebUI connects automatically. For API/extension access, run: make show-api-key. Local install? Check your .env file for SINGLE_USER_API_KEY."
```

**Step 2: Commit**

```
fix: API key help text covers both Docker and local installs
```

---

### Task 8: Profile guides — port conflict troubleshooting (P2)

**Files:**
- Modify: `Docs/Getting_Started/Profile_Local_Single_User.md`
- Modify: `Docs/Getting_Started/Profile_Docker_Single_User.md`
- Modify: `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md`

**Step 1: Add port conflict bullet to Local profile troubleshooting**

After the existing "If port `8000` is in use..." bullet, it already exists! Verify and skip if present.

**Step 2: Add port conflict bullet to Docker profile troubleshooting**

Add to the Troubleshoot section:
```markdown
- If port 8000 or 8080 is in use, stop the conflicting process or change the host port mapping in docker-compose (e.g., `"9000:8000"`).
```

**Step 3: Add port conflict bullet to Multi-user profile troubleshooting**

Add to the Troubleshoot section:
```markdown
- If port 8000 is in use, stop the conflicting process or change the host port in docker-compose.
```

**Step 4: Commit**

```
docs: add port conflict troubleshooting to Docker profile guides
```

---

### Task 9: config.txt — .env vs config.txt guidance (P2)

**Files:**
- Modify: `tldw_Server_API/Config_Files/config.txt` (header comments, lines 1-7)

**Step 1: Expand the header guidance**

Replace the current header (lines 1-7):
```ini
# -----------------------------------------------------------------------
# Essential sections for first-time setup: [Setup], [Server]
# Everything else can be left at defaults until you need the feature.
#
# Configuration precedence: Environment variables > .env file > config.txt
# -----------------------------------------------------------------------
```
With:
```ini
# -----------------------------------------------------------------------
# Essential sections for first-time setup: [Setup], [Server]
# Everything else can be left at defaults until you need the feature.
#
# Configuration precedence: Environment variables > .env file > config.txt
#
# When to use which:
#   .env        — secrets (API keys, passwords, JWT tokens)
#   config.txt  — runtime tuning (chunking, RAG, TTS, provider URLs)
#   env vars    — CI/Docker overrides that should not be persisted
# -----------------------------------------------------------------------
```

**Step 2: Commit**

```
docs: add .env vs config.txt usage guidance
```

---

### Task 10: Feature flags — add JSDoc comments (P3)

**Files:**
- Modify: `apps/packages/ui/src/hooks/useFeatureFlags.ts:16-35`

**Step 1: Add comments to FEATURE_FLAGS**

Replace the flag keys block with:
```typescript
// Flag keys
export const FEATURE_FLAGS = {
  /** Redesigned chat interface with sidebar and streaming */
  NEW_CHAT: "ff_newChat",
  /** Redesigned settings pages layout */
  NEW_SETTINGS: "ff_newSettings",
  /** Cmd+K command palette for quick navigation */
  COMMAND_PALETTE: "ff_commandPalette",
  /** Compact message bubbles in chat */
  COMPACT_MESSAGES: "ff_compactMessages",
  /** Collapsible sidebar in chat view */
  CHAT_SIDEBAR: "ff_chatSidebar",
  /** Side-by-side model comparison in chat */
  COMPARE_MODE: "ff_compareMode",
  /** Streaming responses in knowledge QA */
  KNOWLEDGE_QA_STREAMING: "ff_knowledgeQaStreaming",
  /** Side-by-side comparison in knowledge QA */
  KNOWLEDGE_QA_COMPARISON: "ff_knowledgeQaComparison",
  /** Branching conversation trees in knowledge QA */
  KNOWLEDGE_QA_BRANCHING: "ff_knowledgeQaBranching",
  /** Navigation panel in media viewer */
  MEDIA_NAVIGATION_PANEL: "ff_mediaNavigationPanel",
  /** Rich content rendering in media viewer */
  MEDIA_RICH_RENDERING: "ff_mediaRichRendering",
  /** Display mode selector in media analysis */
  MEDIA_ANALYSIS_DISPLAY_MODE_SELECTOR: "ff_mediaAnalysisDisplayModeSelector",
  /** Use generated fallback as default in media navigation */
  MEDIA_NAVIGATION_GENERATED_FALLBACK_DEFAULT:
    "ff_mediaNavigationGeneratedFallbackDefault",
  /** Provenance tracking in Research Studio */
  RESEARCH_STUDIO_PROVENANCE_V1: "research_studio_provenance_v1",
  /** Status guardrails in Research Studio */
  RESEARCH_STUDIO_STATUS_GUARDRAILS_V1:
    "research_studio_status_guardrails_v1"
} as const
```

**Step 2: Commit**

```
docs: add JSDoc comments to feature flags
```

---

### Task 11: Final commit and PR

**Step 1: Create worktree and branch**

```bash
git branch ftue/audit-v2-fixes dev
git worktree add /tmp/ftue-v2 ftue/audit-v2-fixes
```

**Step 2: Copy all modified files to worktree**

Copy each modified file from the main working tree to `/tmp/ftue-v2/`.

**Step 3: Stage, commit, push**

```bash
cd /tmp/ftue-v2
git add -A
git commit -m "fix: FTUE audit v2 — 13 residual issues

Addresses residual FTUE issues found in second audit pass:

Backend:
- Docker entrypoint now fails on auth init error instead of continuing
- Added DATABASE_URL connectivity check to startup preflight
- Documented placeholder key patterns in docker-compose.yml
- Added UVICORN_WORKERS sizing guidance

Frontend:
- Added demo mode exit banner on home page
- Replaced confusing 'escape hatches' language
- Removed meaningless surface badge
- Demo mode button now explains limitations
- API key help text covers both Docker and local installs

Documentation:
- Multi-user profile: JWT_SECRET_KEY generation is now actionable
- Port conflict troubleshooting in all Docker profiles
- .env vs config.txt usage guidance in config header
- JSDoc comments on all feature flags

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"

git push -u origin ftue/audit-v2-fixes
```

**Step 4: Create PR**

```bash
gh pr create --base dev --title "fix: FTUE audit v2 — 13 residual issues" --body "..."
```

**Step 5: Clean up worktree**

```bash
git worktree remove /tmp/ftue-v2
```
