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

Optional JWT local verification (middleware) reads `JWT_SECRET_KEY`, `JWT_SECONDARY_SECRET`,
and `JWT_ALGORITHM` (HS256/384/512). If missing or invalid, the middleware falls back
to backend verification.

### Run Dev Server

```bash
bun run dev
```

Open `http://localhost:3001`.

## Authentication

- **Single-user mode**: API key login remains supported, but the validated key is moved into an
  `httpOnly` session cookie after login instead of being persisted in web storage.
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
