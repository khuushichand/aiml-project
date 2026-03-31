# FTUE Comprehensive Audit & Improvement Design

**Date:** 2026-03-30
**Status:** In Progress (v2 — Sprint 1 and 2 complete, Sprint 3 partial)
**Scope:** First-time user experience across server, WebUI, extension, and documentation
**Personas:** Non-technical self-hoster (Persona A) and Technical developer (Persona B)

---

## Context

tldw_server has a mature backend with setup endpoints, configuration management, Docker entrypoints, and a Next.js WebUI with onboarding flows. However, a first-time user faces multiple competing entry points, silent failures, and missing guidance that extends time-to-first-success from the ideal 5-10 minutes to 25-60 minutes depending on the deployment path.

This audit catalogs 33 FTUE issues across 5 categories and proposes 13 prioritized improvements.

**Key architectural detail:** The default Docker quickstart uses a Next.js same-origin proxy (`next.config.mjs` rewrites `/api/*` → `http://app:8000/api/*`). In this mode, the WebUI works without the user ever entering an API key. This means issues around "API key not displayed" only affect non-WebUI access (curl, extension, advanced mode).

---

## Prioritization Framework

| Priority | Definition | Target |
|----------|-----------|--------|
| **P0** | Blocks first success or creates security risk | Immediate |
| **P1** | Causes 30+ min friction or missing critical guidance | 1-2 sprints |
| **P2** | Suboptimal but user can succeed with effort | 1-2 months |
| **P3** | Polish | Backlog |

---

## Issue Catalog

### Category A: Configuration & Environment Files

| ID | P | Title | Impact |
|----|---|-------|--------|
| CFG-001 | P1 | Setup UI deliberately disabled by default — `config.txt` ships with `enable_first_time_setup=false` and `setup_completed=true`; the guided setup flow (`setup.py`, 722 lines) is opt-in but undocumented | Both |
| CFG-002 | P1 | `.env.example` has 5 `CHANGE_ME` placeholders with no required/optional distinction | Both |
| CFG-003 | P1 | `config.txt` is 1,490 lines / 30+ sections with no "essential vs optional" guidance | Persona A |
| CFG-004 | P1 | `NEXT_PUBLIC_X_API_KEY` vs `SINGLE_USER_API_KEY` confusion between frontend/backend `.env` files | Both |
| CFG-005 | P2 | Config precedence (`.env` vs `config.txt` vs env vars) undocumented | Persona B |
| CFG-006 | P1 | MCP secrets in `.env.example` as `CHANGE_ME` but Docker entrypoint doesn't auto-generate them (only `AuthNZ.initialize` does) | Both |
| CFG-007 | P1 | Any change to `config.txt` defaults (e.g., enabling setup UI) risks re-triggering setup for existing users who use the shipped config; needs runtime first-run detection | Both |

**Key files:**
- `tldw_Server_API/Config_Files/config.txt` (lines 1-9: Setup section)
- `tldw_Server_API/Config_Files/.env.example`
- `apps/tldw-frontend/.env.local.example`

### Category B: Documentation & Guides

| ID | P | Title | Impact |
|----|---|-------|--------|
| DOC-001 | P0 | README has three redundant sections presenting the same decision tree in different formats ("New here?", "Start Here", "Quickstart At-a-Glance") with slightly different emphasis | Both |
| DOC-002 | P1 | "quickstart" overloaded across 7+ contexts (make targets, endpoint, docs sections) | Both |
| DOC-003 | P1 | Profile guides have no "What to Do Next" after setup succeeds — user has running server and no next step | Both |
| DOC-004 | P1 | Docker multi-user profile missing Postgres prerequisites and compose file guidance | Both |
| DOC-005 | P1 | Audio guides contradict on default STT: CPU guide says `parakeet-onnx`, GPU guide says `faster-whisper` | Both |
| DOC-006 | P2 | `New-User-Guide.md` deprecated but still referenced and more detailed than replacement profiles | Persona A |
| DOC-007 | P2 | No `make help` target — 10+ user-facing targets with zero discoverability | Both |
| DOC-008 | P1 | Docker profile's manual `.env` edit step is redundant with Docker auto-generation but not explained | Persona A |
| DOC-009 | P2 | Profile guides have no Windows/WSL2 coverage; `make` not available on Windows natively | Both |
| DOC-010 | P1 | Same-origin proxy behavior in Docker quickstart is undocumented — users don't understand why API key "isn't needed" in WebUI or why port 8000 isn't used directly | Both |

**Key files:**
- `README.md` (lines 82-96, 197-350)
- `Docs/Getting_Started/Profile_Local_Single_User.md` (56 lines)
- `Docs/Getting_Started/Profile_Docker_Single_User.md`
- `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md`
- `New-User-Guide.md`
- `Makefile`

### Category C: Server-Side Setup Flow

| ID | P | Title | Impact |
|----|---|-------|--------|
| SRV-001 | P1 | No documented way to retrieve the auto-generated API key after Docker quickstart (needed for curl, extension, advanced mode) | Both |
| SRV-002 | P1 | Setup endpoints reject LAN/remote browsers with no explanation (local-only `require_local_setup_access`) | Persona A |
| SRV-003 | P1 | `--non-interactive` AuthNZ init silently uses defaults; misconfig errors only surface at request time | Both |
| SRV-004 | P2 | No "create first admin" endpoint in multi-user setup flow | Both |

**Key files:**
- `tldw_Server_API/app/api/v1/endpoints/setup.py`
- `tldw_Server_API/app/core/AuthNZ/initialize.py`
- `Dockerfiles/entrypoints/tldw-app-first-run.sh` (line ~100)

### Category D: Frontend/WebUI Onboarding

| ID | P | Title | Impact |
|----|---|-------|--------|
| FE-001 | P2 | Deprecated OnboardingWizard (1,400 lines) still in codebase; feature-flagged but imported unconditionally by `option-setup.tsx` and extension | Persona B |
| FE-002 | P1 | Onboarding form asks for API key with no hint about where Docker users find it, and no note that quickstart proxy mode doesn't require it | Persona A |
| FE-003 | P2 | No "essential first config" guidance after onboarding — 26 settings pages with no priority order | Both |
| FE-004 | P2 | Tutorial system has 11 page tutorials but no sequenced "Getting Started" tutorial | Persona A |
| FE-005 | P1 | Demo mode doesn't indicate which features work offline vs. require a server connection | Both |
| FE-006 | P2 | Extension onboarding reuses web wizard with no extension-specific guidance (what is a tldw_server? where do I get one?) | Persona A |
| FE-007 | P3 | Admin UI has separate `.env` and onboarding not covered by this audit | Both |

### Category E: Silent Failures & Error Recovery

| ID | P | Title | Impact |
|----|---|-------|--------|
| ERR-001 | P2 | No-Make Docker path uses `.env.example` directly — entrypoint catches placeholders but behavior is invisible to user | Persona A |
| ERR-002 | P1 | Missing `ffmpeg` is a warning, not an error — audio/video silently fails on first use | Both |
| ERR-003 | P1 | Wrong `DATABASE_URL` in multi-user mode: server starts but all auth requests return 500 | Both |
| ERR-004 | P2 | Frontend error messages lack "how to fix" guidance (7 error types, 0 remediation steps) | Persona A |
| ERR-005 | P2 | Config precedence undefined — conflicting `.env` + `config.txt` = unpredictable behavior | Persona B |

**Key files:**
- `apps/packages/ui/src/components/Option/Onboarding/validation.ts`
- `tldw_Server_API/app/core/AuthNZ/initialize.py`
- `Dockerfiles/entrypoints/tldw-app-first-run.sh`
- `apps/tldw-frontend/next.config.mjs` (lines 29-40: same-origin proxy)

---

## Top 13 Improvements (Prioritized)

### Sprint 1 — P0 + Critical P1 Fixes

#### 1. Unify the README entry point
**Problem:** Three redundant sections ("New here?", "Start Here", "Quickstart At-a-Glance") present the same decision tree differently.
**Solution:** Single "Start Here" section: (1) check prereqs, (2) pick profile, (3) run one command. Consolidate into one flow. Add prominent deprecation to `New-User-Guide.md`.
**Files:** `README.md`, `New-User-Guide.md`, `Docs/Getting_Started/README.md`
**Effort:** Small (docs only)
**Must bundle with:** Improvement 5 (profile guide next-steps) to avoid dead-end profile guides.

#### 2. Add `make show-api-key` and `make help` targets
**Problem:** (a) Auto-generated API key is inaccessible to users for curl/extension use. (b) 10+ make targets with zero discoverability.
**Solution:** (a) `make show-api-key` reads from `.env` on host filesystem — does NOT log secrets. (b) `make help` as default target with descriptions.
**Security:** Never log the key to stdout/container logs. Read from `.env` file only.
**Files:** `Makefile`
**Effort:** Small

#### 3. Document the setup UI and how to enable it
**Problem:** `config.txt` ships with setup UI disabled by design. Users don't know the guided wizard exists.
**Solution:** Do NOT flip defaults in committed config.txt (breaks existing users on upgrade). Instead: (a) document in profile guides how to enable it, (b) have Docker first-run entrypoint enable it on genuine first-run via marker file detection (following existing `.authnz_initialized_single_user` pattern).
**Files:** Profile guides, `Dockerfiles/entrypoints/tldw-app-first-run.sh`, `tldw_Server_API/Config_Files/config.txt` (documentation only, not value change)
**Effort:** Small

#### 4. Document same-origin proxy behavior
**Problem:** Default Docker quickstart uses Next.js rewrite proxy — users don't understand why API key "isn't needed" in WebUI and get confused about port 8000.
**Solution:** Add a "How It Works" note to the Docker profile guide and the WebUI onboarding form explaining the proxy.
**Files:** `Docs/Getting_Started/Profile_Docker_Single_User.md`, possibly `OnboardingConnectForm.tsx`
**Effort:** Small

### Sprint 2 — P1 Fixes

#### 5. Add "What to Do Next" to all profile guides
**Problem:** Profile guides end at "Troubleshoot" with no next steps.
**Solution:** Add section with: open API docs, configure LLM provider, try first API call, connect WebUI/extension.
**Files:** All three `Docs/Getting_Started/Profile_*.md` files
**Effort:** Small
**Dependency:** Must ship with Improvement 1.

#### 6. Restructure `.env.example` with required/optional markers
**Problem:** 222 lines, unclear what must be changed.
**Solution:** Split into `REQUIRED` and `OPTIONAL` sections with inline key generation commands. Clarify `NEXT_PUBLIC_X_API_KEY` vs `SINGLE_USER_API_KEY` relationship.
**Files:** `tldw_Server_API/Config_Files/.env.example`, `apps/tldw-frontend/.env.local.example`
**Effort:** Small

#### 7. Document multi-user Postgres prerequisites
**Problem:** Profile says `DATABASE_URL=postgresql://...` without explaining where Postgres comes from.
**Solution:** Add Postgres setup subsection (docker-compose option vs external, which compose file to use, example URLs).
**Files:** `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md`
**Effort:** Small

#### 8. Resolve audio guide contradictions
**Problem:** CPU and GPU guides recommend different default STT engines.
**Solution:** Align both guides with the actual shipped default (`parakeet-onnx`). Note GPU-specific alternatives clearly.
**Files:** `Docs/Getting_Started/First_Time_Audio_Setup_CPU.md`, `First_Time_Audio_Setup_GPU_Accelerated.md`
**Effort:** Small

#### 9. Quick-fix bundle for remaining P1 issues
**Problem:** Multiple P1 issues with < 30 min fixes each.
**Solution:** Address as a batch:
- **ERR-002:** Add startup health check that logs prominent banner if ffmpeg is missing
- **ERR-003:** Validate `DATABASE_URL` connectivity at startup in multi-user mode; log actionable error if unreachable
- **CFG-006:** Auto-generate MCP secrets in Docker entrypoint (same pattern as `SINGLE_USER_API_KEY`)
- **DOC-008:** Add note to Docker profile explaining auto-generation and when manual edit is needed
- **FE-002:** Add hint text in onboarding form about where to find the key, and note that quickstart mode doesn't require it
**Files:** Various (see issue catalog for file references)
**Effort:** Medium (batch of small fixes)

### Sprint 3 — P1/P2

#### 10. Improve frontend error messages with remediation steps
**Problem:** 7 error types categorized but messages lack fix guidance.
**Solution:** Add per-error-kind remediation text (e.g., CORS → "Add origin to ALLOWED_ORIGINS", refused → "Check server is running"). Requires i18n locale file updates.
**Files:** `apps/packages/ui/src/components/Option/Onboarding/validation.ts`, i18n locale files
**Effort:** Medium (includes i18n work)

#### 11. Add "Getting Started" tutorial to WebUI
**Problem:** Tutorial system exists but no sequenced first-run tutorial.
**Solution:** Add tutorial that auto-triggers after onboarding: configure provider → try chat → ingest document.
**Files:** Tutorial store, locale files, CompanionHomeShell
**Effort:** Large (multi-day: tutorial content, i18n, trigger logic, testing across web + extension)

#### 12. Add extension-specific onboarding path
**Problem:** Extension imports web wizard with no context about what tldw_server is or where to get it.
**Solution:** Add extension-specific intro screen before the connection form: "What is tldw_server?", link to setup guide, prominent demo mode.
**Files:** Extension entry points, shared onboarding components
**Effort:** Medium

#### 13. Remove deprecated OnboardingWizard (after verification gate)
**Problem:** 1,400 lines of legacy wizard behind feature flag, but imported unconditionally by `option-setup.tsx` and extension.
**Solution:** Delete legacy wizard, remove feature flag, update all import sites (`option-setup.tsx`, extension `option-index.tsx`).
**Gate:** Only proceed after confirming: (a) OnboardingConnectForm handles all 7 error types with remediation, (b) extension builds successfully with new form, (c) no users have `ff_newOnboarding=false` in production.
**Files:** `OnboardingWizard.tsx`, feature flag config, `option-setup.tsx`, extension entry points
**Effort:** Large (extension + route changes + verification)

---

## P2/P3 Backlog (not in sprint plan)

| ID | Title | Quick fix? |
|----|-------|-----------|
| CFG-003 | config.txt needs "essential vs optional" section headers | Yes — add comments |
| CFG-005 | Document config precedence | Yes — add to README |
| DOC-006 | Remove deprecated New-User-Guide.md body content | Yes |
| DOC-007 | Covered by Improvement 2 | N/A |
| DOC-009 | Add Windows/WSL2 notes to profiles | Small |
| FE-001 | Covered by Improvement 13 | N/A |
| FE-003 | Add "configure first" guidance to settings | Small |
| FE-004 | Covered by Improvement 11 | N/A |
| FE-006 | Covered by Improvement 12 | N/A |
| FE-007 | Admin UI FTUE audit | Defer |
| SRV-004 | Multi-user first-admin endpoint | Needs design |
| ERR-001 | Document Docker entrypoint placeholder catching | Yes |
| ERR-004 | Covered by Improvement 10 | N/A |
| ERR-005 | Covered by CFG-005 | N/A |

---

## Verification Plan

### Per-Improvement Verification

1. **README + Profile guides (1, 5):** Read modified docs as each persona end-to-end. Verify: single clear path from README to profile to running server to first API call. No dead ends.
2. **`make show-api-key` + `make help` (2):** Run `make` with no args → verify help output. Run `make quickstart` → `make show-api-key` → verify key shown. Verify key NOT in container logs.
3. **Setup UI docs (3):** Follow documented steps to enable setup UI. Verify wizard loads at `/setup`. Verify existing user upgrade does NOT re-trigger setup.
4. **Proxy docs (4):** Read Docker profile guide. Verify proxy explanation is present and clear.
5. **Audio guide fix (8):** Read both guides. Verify no contradictions on default STT.
6. **Quick-fix batch (9):** Start server without ffmpeg → verify banner warning. Set bad DATABASE_URL → verify startup error message. Verify MCP secrets auto-generated in Docker.
7. **Error messages (10):** Trigger each of 7 error types in onboarding → verify remediation text appears.
8. **Tutorial (11):** Complete onboarding → verify tutorial triggers → complete steps. Test in both web and extension.
9. **Extension onboarding (12):** Install extension fresh → verify intro screen appears before connection form.
10. **Legacy wizard removal (13):** Verify no imports remain. Verify extension builds. Verify `/setup` route works with new form.

### Cross-Cutting Verification

- **Upgrade regression:** Existing user pulls latest code with default `config.txt` → server starts normally, no unexpected setup wizard.
- **Extension rebuild:** All frontend changes must pass extension build (`pnpm build:extension` or equivalent).
- **Both proxy paths:** Verify Docker quickstart works (same-origin, no key needed in browser) AND advanced mode works (direct API access, key required).
- **Security:** No API keys in container logs. No secrets exposed in error messages.
