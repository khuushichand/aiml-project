## tldw-frontend Audit

This document is a working log for assessing and improving the `tldw-frontend` application. Use it to capture what you find, decisions made, and follow-up tasks.

> Tip: Keep entries terse and dated. Treat this as an engineering notebook rather than polished docs.

---

## 0. Scope & Goals

- **Date / Reviewer(s)**:
- **Backend version / branch**:
- **Frontend version / branch**:
- **Primary goals for this audit** (for example: “make it production-safe for single_user”, “align with v0.1.0 API”, “remove critical UX blockers”):
- **Out of scope for now**:

---

## 1. Environment & Tooling

- **Node/npm version used**:
- **Install status** (`npm install` / `npm ci`):
- **Core scripts** (`npm run dev`, `build`, `start`, `smoke`) – working? Notes:
- **Lint / typecheck scripts present?** If yes, status and typical warnings:
- **Dev server URL / port used**:

Notes / issues:

- …

Follow-ups:

- [ ] …

---

## 2. High-Level Architecture

- **Routing** (pages router, notable routes: `/`, `/login`, `/media`, `/chat`, `/audio`, `/search`, `/evaluations`, `/admin/*`, etc.):
- **State management** (React Query, React context, local state, others):
- **Key shared modules** (for example `lib/api.ts`, `lib/auth.ts`, `hooks/useAuth.ts`, UI layout components):
- **Main layout/navigation components**:

Observations:

- …

Risks / questions:

- …

---

## 3. API & Backend Alignment

- **API base configuration** (env vars: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_API_VERSION`, `NEXT_PUBLIC_X_API_KEY`, `NEXT_PUBLIC_API_BEARER`, etc.):
- **AuthNZ modes supported** (single_user X-API-KEY, multi_user JWT):
- **Key backend endpoints used** and notes (for each, confirm path, method, payload, and response shape match backend docs):
  - Media (ingest/search):
  - Chat / RAG:
  - Audio (STT/TTS):
  - Evaluations:
  - MCP:
  - Admin / Auth:
  - Other:

Drift from backend (missing endpoints, outdated payloads, assumptions that no longer hold):

- …

Follow-ups:

- [ ] …

---

## 4. Auth, Roles & Security

- **Auth flow overview**:
  - Where login happens (page/components).
  - How tokens / API keys are stored and refreshed.
  - How logout is handled.
- **Auth-related modules** reviewed (`lib/auth.ts`, `lib/authz.ts`, `hooks/useAuth.ts`, `hooks/useIsAdmin.ts`, login pages, admin pages):
- **Supported auth modes**:
  - Single-user (X-API-KEY from env):
  - Multi-user (JWT / sessions):
- **Role / privilege handling** (admin vs. regular user, per-page protection):

Findings:

- …

Security concerns / gaps:

- …

Refactor ideas (short bullets; detailed plan can live elsewhere):

- …

---

## 5. UX & Flows

Key user journeys (note status: ✅ works, ⚠ rough, ❌ broken):

- [ ] Landing / navigation:
- [ ] Login / logout:
- [ ] Media upload, processing, and browsing:
- [ ] Search (FTS / RAG):
- [ ] Chat / character chat:
- [ ] Audio transcription / TTS:
- [ ] Evaluations:
- [ ] Admin (privileges, users, connectors, watchlists):
- [ ] Reading / notebook / notes:

UX notes (loading states, error messages, responsiveness, accessibility, clarity of labels):

- …

Top UX issues to address first:

- [ ] …

---

## 6. State Management & Data Fetching

- **React Query usage** (where, patterns, cache keys):
- **Custom hooks for data** (for example `useAuth`, `useVlmBackends`, `useConnectorBackend`):
- **Patterns for loading / error / empty states**:

Good patterns:

- …

Inconsistent or problematic patterns:

- …

Follow-ups:

- [ ] …

---

## 7. Error Handling & Resilience

- **Global error surface** (toasts, banners, error boundary?):
- **How API errors are surfaced** (per-page vs. central):
- **Behavior on network failures / timeouts / 401 / 403 / 500**:

Findings:

- …

Quick wins:

- [ ] …

---

## 8. Performance & Bundling

- **Next.js build output** (any large bundles, warnings):
- **Usage of heavy libraries** (Monaco, charts, etc.) and whether they are code-split/lazy-loaded:
- **Client-side caching / memoization**:

Notes:

- …

Potential optimizations:

- [ ] …

---

## 9. Dependencies & Technical Debt

- **Key dependencies and versions** (Next, React, React Query, Tailwind, etc.):
- **Known outdated / beta / misaligned dependencies**:
- **Unused or suspicious dependencies**:

Tech debt list (short, actionable bullets):

- [ ] …

Priorities (P0/P1/P2):

- P0:
- P1:
- P2:

---

## 10. Testing & Automation

- **Existing tests** (unit, integration, E2E – if any):
- **Smoke tests** (for example `npm run smoke`) – coverage and reliability:
- **CI integration** (if present):

Gaps:

- …

First test targets:

- [ ] …

---

## 11. Build, Deployment & Integration

- **Build status** (`npm run build`):
- **Production runtime assumptions** (reverse proxy paths, CORS, `NEXT_PUBLIC_API_BASE_URL` usage):
- **How this frontend is deployed** (Vercel, Docker, static export, other):
- **Integration with backend release process**:

Notes:

- …

Follow-ups:

- [ ] …

---

## 12. Summary & Next Steps

- **Overall health** (subjective: green / yellow / red) and why:
- **Top 3 risks**:
  1. …
  2. …
  3. …
- **Top 3 short-term improvements** (1–2 weeks):
  1. …
  2. …
  3. …
- **Longer-term refactors / improvements**:
  - …

