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

- Node.js 18+
- `tldw_server` API running (default: `http://localhost:8000`)

### Install

```bash
npm install
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
npm run dev
```

Open `http://localhost:3000`.

## Authentication

- **Single-user mode**: API key login (X-API-KEY); key stored in memory for the session.
- **Multi-user mode**: username/password login via `/auth/login` and JWT stored in localStorage.

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
