# tldw Admin UI

Admin and operations dashboard for `tldw_server`. This UI is intended for sysadmin/ops workflows and is separate from the end-user Next.js WebUI (`apps/tldw-frontend`).

## Features

- **System Ops**: system logs, feature flags, maintenance mode, incidents
- **Admin Core**: users, orgs, teams, roles, API keys
- **Operational Views**: audit logs, usage, budgets, jobs, monitoring, data ops
- **RBAC-aware UI**: routes filtered by role/permission

## Tech Stack

- **Next.js 15** (App Router)
- **React 19**
- **TypeScript**
- **Tailwind CSS**
- **Lucide React**

## Getting Started

### Prerequisites

- Bun 1.3+
- `tldw_server` API running (default: `http://localhost:8000`)

### Install

```bash
bun install
```

### Environment Variables

Create `.env.local` with the API base URL (and optional defaults):

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_DEFAULT_AUTH_MODE=password
```

`NEXT_PUBLIC_DEFAULT_AUTH_MODE` supports `password` (JWT) or `apikey` (single-user).
`NEXT_PUBLIC_ALLOW_ADMIN_API_KEY_LOGIN=true` is required before the UI will expose the API-key login
tab, and `ADMIN_UI_ALLOW_API_KEY_LOGIN=true` is required before the server-side route will accept it.
The server-side API-key login route also requires `AUTH_MODE=single_user`; it is rejected in
multi-user deployments even if the UI toggle is enabled.
Leave both disabled for enterprise/live-customer admin use.

Optional JWT local verification (middleware) reads `JWT_SECRET_KEY`, `JWT_SECONDARY_SECRET`,
and `JWT_ALGORITHM` (HS256/384/512). If missing or invalid, the middleware falls back
to backend verification.

### Run Dev Server

```bash
bun run dev
```

Open `http://localhost:3001`.

## Quality Gate

Run the production gate from `admin-ui/` before cutting a release or merging risky admin changes:

```bash
bun run lint
bun run typecheck
bun run test
bun run test:a11y
bun run build
bun run test:smoke
```

`test:smoke` starts a local Next server by default, stubs the critical `/api/auth/*` and `/api/proxy/*`
calls in-browser, and verifies the hardened password+MFA login path plus privileged user actions.
It does not require a live backend. To point the smoke suite at an already running server, set
`TLDW_ADMIN_UI_AUTOSTART=false` and `TLDW_ADMIN_UI_URL=http://127.0.0.1:3001`.

## Authentication

- **Single-user mode**: API key login remains supported, but the validated key is moved into an
  `httpOnly` session cookie after login instead of being persisted in web storage. This path is
  disabled by default and should only be re-enabled for local/single-user deployments.
- **Multi-user mode**: username/password login is exchanged through Next route handlers that set
  `httpOnly` session cookies. Browser JavaScript never stores or reads admin bearer tokens.
- **Authenticated API calls**: the UI sends privileged requests through `/api/proxy/*` on the same
  origin, and the proxy attaches the server-managed credential to backend requests.

## System Ops Endpoints Used

- `GET /api/v1/admin/system/logs`
- `GET /api/v1/admin/maintenance`, `PUT /api/v1/admin/maintenance`
- `GET /api/v1/admin/feature-flags`, `PUT/DELETE /api/v1/admin/feature-flags/{flag_key}`
- `GET /api/v1/admin/incidents`, `POST/PATCH/DELETE /api/v1/admin/incidents`

## Project Structure

```
admin-ui/
├── app/                 # Next.js App Router pages
├── components/          # Shared UI components
├── lib/                 # API client + auth helpers
├── types/               # TypeScript models
└── public/              # Static assets
```
