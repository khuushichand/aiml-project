# ACP Workspace Entity: Design Document

## Overview

The ACP Workspace entity provides persistent binding between orchestration projects and filesystem directories. It enables automatic CWD resolution during task dispatch, workspace discovery, health monitoring, and workspace-level MCP server configuration.

## Architecture

### Data Model

```
ACPWorkspace (acp_workspaces table)
├── id, name, root_path (absolute host path)
├── workspace_type: manual | discovered | monorepo_child
├── parent_workspace_id (FK self-ref, ON DELETE SET NULL)
├── env_vars (JSON), metadata (JSON)
├── git_*: remote_url, default_branch, current_branch, is_dirty
├── health_status: healthy | degraded | missing
└── last_health_check (ISO timestamp)

AgentProject.workspace_id → acp_workspaces.id (ON DELETE SET NULL)
```

### Storage

- All workspace data lives in per-user `orchestration.db` (schema v2)
- Schema migration v1→v2 is automatic on first access
- Unique constraints: `(user_id, name)` and `(user_id, root_path)`

### CWD Resolution Chain

```
dispatch_run(cwd=".")
  → explicit cwd (if != ".")
  → project.workspace.root_path
  → "." (fallback)
```

### MCP Integration

- Workspace MCP servers are injected into `create_session(mcp_servers=...)` during dispatch
- `McpHubWorkspaceRootResolver` has an `acp_workspace` fallback source for path resolution

## API Endpoints

All under `/api/v1/agent-orchestration/`:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/workspaces` | Create workspace |
| GET | `/workspaces` | List workspaces (filter by type, health) |
| GET | `/workspaces/{id}` | Get workspace + children + MCP servers |
| PUT | `/workspaces/{id}` | Update workspace |
| DELETE | `/workspaces/{id}` | Delete workspace (SET NULL on projects) |
| GET | `/workspaces/{id}/health` | On-demand health check |
| POST | `/workspaces/health/refresh-all` | Batch health refresh |
| GET | `/workspaces/{id}/mcp-servers` | List MCP servers |
| POST | `/workspaces/{id}/mcp-servers` | Add MCP server |
| DELETE | `/workspaces/{id}/mcp-servers/{sid}` | Remove MCP server |
| POST | `/workspaces/discover` | Scan directory for candidates |

## Configuration

Add to `config.txt` under `[ACP-WORKSPACE]`:

```ini
[ACP-WORKSPACE]
# Required for workspace create, update, discovery, and dispatch path entry points.
# Comma-separated absolute paths.
allowed_base_paths = /home,/projects,/workspaces

# Discovery defaults (used by POST /workspaces/discover)
discovery_max_depth = 3
discovery_patterns = .git,package.json,pyproject.toml,Cargo.toml,go.mod
```

## Docker Guidance

When running in Docker, bind-mount host project directories and restrict workspace creation:

```yaml
# docker-compose.yml
services:
  tldw-server:
    volumes:
      - ~/projects:/workspaces:rw
    environment:
      - ACP_WORKSPACE_ALLOWED_BASE_PATHS=/workspaces
```

The `allowed_base_paths` config (or `ACP_WORKSPACE_ALLOWED_BASE_PATHS` env var) is required for ACP workspace path entry points and prevents workspaces from being created outside the mounted volume.

## Security Notes

- `root_path` must stay under a configured allowlist before it can be stored or used as a session CWD
- `env_vars` are stored as plaintext JSON in the per-user SQLite DB
- Path validation uses `Path.is_relative_to()` for allowed_base_paths enforcement
- Discovery service uses `followlinks=False` to prevent symlink loop attacks

## Files

| File | Purpose |
|------|---------|
| `app/core/Agent_Orchestration/models.py` | `ACPWorkspace` dataclass, `AgentProject.workspace_id` |
| `app/core/DB_Management/Orchestration_DB.py` | Schema v2, workspace CRUD, MCP server CRUD |
| `app/api/v1/endpoints/agent_orchestration.py` | REST endpoints, CWD resolution in dispatch |
| `app/services/workspace_discovery_service.py` | Directory scanning, git metadata extraction |
| `app/services/workspace_health_service.py` | Health checks, batch refresh |
| `app/services/mcp_hub_workspace_root_resolver.py` | ACP workspace fallback source |
