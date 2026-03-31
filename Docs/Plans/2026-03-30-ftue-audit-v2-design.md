# FTUE Audit v2 — Residual Issues Design

**Date:** 2026-03-30
**Status:** Draft
**Prerequisite:** PR #938 (FTUE audit v1) — addresses 33 issues
**Scope:** 13 residual/new issues found in fresh re-audit

---

## Context

After implementing the initial FTUE audit (PR #938), a fresh re-audit of the codebase identified 13 additional issues not covered by the first pass. These range from a critical Docker entrypoint error-handling gap to UI language polish.

---

## Issues (13 total)

### Sprint A: Backend/Docker Hardening

| # | P | Issue | File | Fix |
|---|---|-------|------|-----|
| 1 | P0 | Docker entrypoint continues after init failure | `Dockerfiles/entrypoints/tldw-app-first-run.sh:130` | Add error check after `initialize --non-interactive` |
| 2 | P1 | Docker compose uses `change-me` vs `.env.example` uses `CHANGE_ME_TO_SECURE_API_KEY` | `Dockerfiles/docker-compose.yml` | Add comment explaining entrypoint catches both patterns |
| 3 | P1 | Multi-user profile: JWT_SECRET_KEY generation is a comment, not actionable | `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md:25` | Add explicit "run this, paste output" instruction |
| 4 | P1 | No DATABASE_URL connectivity check at startup | `tldw_Server_API/app/core/startup_preflight.py` | Add `check_database_connectivity()` for Postgres URLs |

### Sprint B: Frontend UX

| # | P | Issue | File | Fix |
|---|---|-------|------|-----|
| 5 | P1 | Demo mode button doesn't explain what works/doesn't | `apps/tldw-frontend/extension/routes/option-index.tsx:40` | Add subtitle about demo limitations |
| 6 | P1 | No way to exit demo mode | `apps/packages/ui/src/components/Option/CompanionHome/CompanionHomeShell.tsx` | Add "Connect real server" banner when in demo mode |
| 7 | P2 | "Escape hatches" language confusing | `CompanionHomeShell.tsx:61` | Change to "Quick links to main features" |
| 8 | P2 | Surface badge ("options"/"sidepanel") meaningless | `CompanionHomeShell.tsx:64` | Remove the badge |
| 9 | P2 | API key help text doesn't cover local installs | `OnboardingConnectForm.tsx` | Add "For local installs, check your .env file" |

### Sprint C: Documentation/Polish

| # | P | Issue | File | Fix |
|---|---|-------|------|-----|
| 10 | P2 | Port conflict not in profile troubleshooting | All 3 profile guides | Add troubleshooting bullet |
| 11 | P2 | No .env vs config.txt guidance | `config.txt` header | Add note about when to use each |
| 12 | P3 | Feature flags have no JSDoc comments | `useFeatureFlags.ts` | Add one-line comment per flag |
| 13 | P3 | UVICORN_WORKERS=4 no sizing guidance | `docker-compose.yml` | Add comment about RAM requirements |

---

## Verification

- Docker: `make quickstart` with intentionally broken init → verify container fails to start (issue 1)
- Multi-user: Follow profile guide → verify JWT_SECRET_KEY instructions are actionable (issue 3)
- Extension: Install fresh → demo mode → verify limitations text (issue 5) and exit path (issue 6)
- Home page: Verify no "escape hatches" or surface badge (issues 7-8)
- Port conflict: Verify troubleshooting bullet in each profile (issue 10)
