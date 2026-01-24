# Shared UI Monorepo Notes

This repo hosts the browser extension and web UI in a bun workspace with a shared UI base.

> **See also:** [DEVELOPMENT.md](./DEVELOPMENT.md) for comprehensive development workflows, feature parity checklists, and platform adaptation patterns.

## Quick Start

```bash
cd apps
bun install

# Extension development
bun run --cwd extension dev

# Web development
bun run --cwd tldw-frontend dev
```

## Layout

| Directory | Purpose |
|-----------|---------|
| `extension/` | WXT extension build config & manifests |
| `packages/ui/src/` | **Shared UI** (routes, components, hooks, services) |
| `tldw-frontend/` | Next.js web app consuming shared UI |

## Import Aliases

| Alias | Resolves To | Usage |
|-------|-------------|-------|
| `@/`, `~/`, `@tldw/ui/*` | `packages/ui/src/` | Shared code (both platforms) |
| `@web/*` | `tldw-frontend/` | Web-only modules |

## Key Rules

1. **Shared code** → `packages/ui/src/` (components, hooks, services, routes)
2. **Extension entries** → `packages/ui/src/entries/` (background, sidepanel, content scripts)
3. **Web-only code** → `tldw-frontend/` (auth, Next.js pages, browser shims)
4. **Always use `{ ssr: false }`** when importing shared routes in Next.js pages

## More Information

- [DEVELOPMENT.md](./DEVELOPMENT.md) — Full development guide with workflows and patterns
- [extension/AGENTS.md](./extension/AGENTS.md) — Extension-specific guide
- [tldw-frontend/README.md](./tldw-frontend/README.md) — Web UI documentation
