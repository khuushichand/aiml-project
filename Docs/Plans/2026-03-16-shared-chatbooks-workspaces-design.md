# Shared Chatbooks & Workspaces — Design Document

**Date**: 2026-03-16
**Status**: Draft
**Author**: AI-assisted design

---

## Context

Users can currently export chatbooks (ZIP archives with media, conversations, notes, etc.) and create research workspaces (NotebookLM-style containers with sources, artifacts, chat). However, there is **no way to share** these within a team or organization. Users must manually export files and send them out-of-band.

The goal is to enable:
1. **Token-based chatbook distribution** — Share links with expiry, password protection, and download limits
2. **Intra-team/org workspace sharing** — Expose a workspace to team/org members with configurable access levels
3. **Per-user chat isolation** — Team members chat with shared workspaces, conversations saved to their own profiles
4. **Clone/fork** — Deep copy a shared workspace into a personal workspace, fully detached

This is analogous to sharing notebooks in NotebookLM, with the added complexity of multi-user deployments, org/team hierarchies, and cross-instance distribution.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Distribution mechanism | Token-based share links | Supports expiry, password, limits; extends existing HMAC pattern |
| Media model for shared workspaces | Reference-based (read from owner's DB) | No duplication; owner updates visible to all |
| Clone model | Deep copy into cloner's DB | Full independence; clean break from source |
| Access tiers | View+Chat / View+Chat+Add / Full Edit | Three-tier balances granularity vs simplicity |
| Sharing metadata storage | AuthNZ DB (central) | Single source of truth; content stays in owner's per-user DB |
| Sharing scopes (v1) | Team + Org | Leverages existing hierarchy; user-to-user deferred to v2 |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  AuthNZ DB (central)                                            │
│  ┌──────────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │ shared_workspaces │  │ share_tokens │  │ share_audit_log │   │
│  │ (who shared what  │  │ (external    │  │ (all sharing    │   │
│  │  with whom, what  │  │  link tokens │  │  events)        │   │
│  │  access level)    │  │  + expiry)   │  │                 │   │
│  └──────────────────┘  └──────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
   │ Owner's DBs  │  │ Member A DB  │  │ Member B DB  │
   │ ChaChaNotes  │  │ ChaChaNotes  │  │ ChaChaNotes  │
   │ Media_DB_v2  │  │ (own convos) │  │ (own convos) │
   │ (workspace   │  │              │  │              │
   │  + sources)  │  │              │  │              │
   └──────────────┘  └──────────────┘  └──────────────┘
         ▲                   │                │
         │  read via         │                │
         └──SharedWorkspaceDBResolver─────────┘
```

**Key principle**: Sharing metadata lives centrally in AuthNZ DB. Content stays in the owner's per-user databases. Each team member's conversations are isolated in their own DB.

---

## Database Schema

### Table: `shared_workspaces` (AuthNZ DB)

```sql
CREATE TABLE IF NOT EXISTS shared_workspaces (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id     TEXT NOT NULL,
    owner_user_id    INTEGER NOT NULL,
    share_scope_type TEXT NOT NULL DEFAULT 'team'
        CHECK (share_scope_type IN ('team', 'org')),
    share_scope_id   INTEGER NOT NULL,
    access_level     TEXT NOT NULL DEFAULT 'view_chat'
        CHECK (access_level IN ('view_chat', 'view_chat_add', 'full_edit')),
    allow_clone      INTEGER NOT NULL DEFAULT 1,
    created_by       INTEGER NOT NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at       TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES users(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    UNIQUE(workspace_id, owner_user_id, share_scope_type, share_scope_id)
);
CREATE INDEX IF NOT EXISTS idx_shared_ws_owner ON shared_workspaces(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_shared_ws_scope ON shared_workspaces(share_scope_type, share_scope_id);
```

### Table: `share_tokens` (AuthNZ DB)

```sql
CREATE TABLE IF NOT EXISTS share_tokens (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash      TEXT UNIQUE NOT NULL,
    token_prefix    TEXT NOT NULL,
    resource_type   TEXT NOT NULL
        CHECK (resource_type IN ('chatbook', 'workspace')),
    resource_id     TEXT NOT NULL,
    owner_user_id   INTEGER NOT NULL,
    access_level    TEXT NOT NULL DEFAULT 'view_chat',
    allow_clone     INTEGER NOT NULL DEFAULT 1,
    password_hash   TEXT,
    max_uses        INTEGER,
    use_count       INTEGER NOT NULL DEFAULT 0,
    expires_at      TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at      TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_share_tokens_prefix ON share_tokens(token_prefix);
CREATE INDEX IF NOT EXISTS idx_share_tokens_owner ON share_tokens(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_share_tokens_resource ON share_tokens(resource_type, resource_id);
```

### Table: `share_audit_log` (AuthNZ DB)

```sql
CREATE TABLE IF NOT EXISTS share_audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT NOT NULL,
    actor_user_id   INTEGER,
    resource_type   TEXT NOT NULL,
    resource_id     TEXT NOT NULL,
    owner_user_id   INTEGER NOT NULL,
    share_id        INTEGER,
    token_id        INTEGER,
    metadata_json   TEXT DEFAULT '{}',
    ip_address      TEXT,
    user_agent      TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_share_audit_created ON share_audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_share_audit_owner ON share_audit_log(owner_user_id);
```

### Table: `sharing_config` (AuthNZ DB)

```sql
CREATE TABLE IF NOT EXISTS sharing_config (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scope_type      TEXT NOT NULL DEFAULT 'global'
        CHECK (scope_type IN ('global', 'org', 'team')),
    scope_id        INTEGER,
    config_key      TEXT NOT NULL,
    config_value    TEXT NOT NULL,
    updated_by      INTEGER,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scope_type, scope_id, config_key)
);
```

Config keys: `default_access_level`, `allow_clone`, `max_shares_per_workspace`, `max_tokens_per_user`, `require_password_for_external`.

---

## API Endpoints

New router: `/api/v1/sharing/`

### Workspace Sharing (team/org)

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| `POST` | `/sharing/workspaces/{workspace_id}/share` | Share with team/org | `sharing.create` |
| `GET` | `/sharing/workspaces/{workspace_id}/shares` | List shares for a workspace | `sharing.read` + owner/admin |
| `PATCH` | `/sharing/shares/{share_id}` | Update access level / clone | `sharing.update` + owner/admin |
| `DELETE` | `/sharing/shares/{share_id}` | Revoke a share | `sharing.delete` + owner/admin |
| `GET` | `/sharing/shared-with-me` | List workspaces shared with me | `sharing.read` |
| `GET` | `/sharing/shared-with-me/{share_id}/workspace` | Read shared workspace metadata | `sharing.read` |
| `GET` | `/sharing/shared-with-me/{share_id}/sources` | List sources in shared workspace | `sharing.read` |
| `GET` | `/sharing/shared-with-me/{share_id}/media/{media_id}` | Read media from owner's DB | `sharing.read` |
| `POST` | `/sharing/shared-with-me/{share_id}/chat` | Chat with shared workspace | `sharing.read` |
| `POST` | `/sharing/shared-with-me/{share_id}/clone` | Clone/fork workspace | `sharing.clone` |

### Share Tokens (external links)

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| `POST` | `/sharing/tokens` | Create share link | `sharing.token.create` |
| `GET` | `/sharing/tokens` | List my tokens | `sharing.token.read` |
| `DELETE` | `/sharing/tokens/{token_id}` | Revoke a token | `sharing.token.delete` |
| `GET` | `/sharing/public/{token}` | Preview shared resource | public (rate limited) |
| `POST` | `/sharing/public/{token}/verify` | Verify password | public (rate limited) |
| `POST` | `/sharing/public/{token}/import` | Import from token | requires auth |

### Admin

| Method | Path | Purpose | Permission |
|--------|------|---------|------------|
| `GET` | `/sharing/admin/shares` | List all shares | `sharing.admin` |
| `PATCH` | `/sharing/admin/config` | Update sharing defaults | `sharing.admin` |
| `GET` | `/sharing/admin/audit` | Query audit log | `sharing.admin` |

---

## Cross-User Database Access

### SharedWorkspaceDBResolver

When a team member accesses a shared workspace, the backend needs a split DB context:

```
Source content (read):  owner's ChaChaNotes_DB + Media_DB_v2
Conversations (write):  accessor's ChaChaNotes_DB
Embeddings (read):      owner's ChromaDB namespace
```

**New service**: `SharedWorkspaceDBResolver` in `app/core/Sharing/`

1. Takes `share_id` + `accessor_user_id`
2. Validates the share record (not revoked, accessor is in scope team/org)
3. Returns a `SharedWorkspaceContext`:
   - `source_chacha_db`: owner's ChaChaNotes_DB (read-only or access-level gated)
   - `source_media_db`: owner's Media_DB_v2 (read-only)
   - `conversation_chacha_db`: accessor's ChaChaNotes_DB
   - `embedding_namespace`: owner's user_id (for ChromaDB vector search)
   - `access_level`: the effective access tier

**Safety constraints:**
- For `view_chat`: SQLite `PRAGMA query_only = ON` on owner's DBs
- For `view_chat_add`: Write proxy that only allows `add_workspace_source`
- For `full_edit`: Full access with optimistic locking (`version` column)
- All writes to owner's DB are audit-logged

### RAG Pipeline Integration

The `unified_rag_pipeline()` already accepts explicit `media_db_path`, `media_db`, `chacha_db`, and `user_id` parameters. For shared workspace chat:

1. Pass **owner's** `media_db` and `chacha_db` as source databases
2. Pass **owner's** `user_id` as `embedding_namespace` (new parameter, falls back to `user_id`)
3. Write conversation to **accessor's** ChaChaNotes_DB with `shared_workspace_ref = share_id`

**New parameter on `unified_rag_pipeline`**: `embedding_namespace_override: Optional[str]` — when set, uses this instead of `user_id` for vector store namespace resolution.

---

## Permission Model

### New Permission Codes (`privilege_catalog.yaml`)

```yaml
sharing.create:    Share workspaces (default: admin, lead, member)
sharing.read:      View shared workspaces (default: admin, lead, member, viewer)
sharing.update:    Modify share settings (default: admin, lead + owns_resource)
sharing.delete:    Revoke shares (default: admin, lead + owns_resource)
sharing.clone:     Clone shared workspaces (default: admin, lead, member)
sharing.token.create: Create external links (default: admin, lead)
sharing.token.read:   List own tokens (default: admin, lead, member)
sharing.token.delete: Revoke tokens (default: admin, lead + owns_resource)
sharing.admin:     Admin sharing management (default: admin)
```

### Access Tier Enforcement

The `access_level` on the share record is a **ceiling**:
- `view_chat`: Browse sources, read content, chat (own conversations). Cannot modify workspace.
- `view_chat_add`: Above + add new sources to workspace. Cannot edit/delete existing sources.
- `full_edit`: Above + edit/delete sources, modify workspace metadata, manage notes/artifacts.

Effective access = `min(share.access_level, user's RBAC capability)`.

---

## Share Token System

### Token Lifecycle

1. **Generate**: `secrets.token_urlsafe(32)` → raw token
2. **Store**: `SHA256(raw_token)` as `token_hash`, `raw_token[:8]` as `token_prefix`
3. **Return**: Raw token to user (shown once, never stored server-side)
4. **URL format**: `https://{host}/share/{token}`

### Token Validation Flow

1. Extract prefix for index lookup → find candidate rows
2. Compute `SHA256(incoming_token)` and constant-time compare against `token_hash`
3. Check: `revoked_at IS NULL`, `expires_at > NOW()`, `use_count < max_uses`
4. If password-protected: require `/verify` call first (returns short-lived session cookie)
5. Increment `use_count` atomically
6. Audit log the access

### Security Mitigations

- **Rate limiting**: 10 req/min per IP on public endpoints
- **Constant-time comparison** on token hash
- **Identical error responses** for not-found/expired/revoked (prevent enumeration)
- **Password**: bcrypt hash, separate verify step

---

## Clone/Fork Workflow

### Steps

1. **Pre-check**: Validate `allow_clone` + `sharing.clone` permission + user quota + verify user has embedding provider (warn if not)
2. **Create async job**: Reuse `ExportJob`/`ImportJob` pattern from ChatbookService
3. **Copy workspace metadata**: New UUID in cloner's ChaChaNotes_DB
4. **Deep copy media**: For each `workspace_sources` entry:
   - Copy full Media record + MediaChunks + Transcripts + Keywords from owner's Media_DB
   - Insert into cloner's Media_DB with new `media_id`
   - Update workspace_sources to point to new media_ids
5. **Copy workspace_notes and workspace_artifacts** (with new IDs)
6. **Queue re-embedding job** (don't copy ChromaDB vectors; regenerate in cloner's namespace)
7. **Audit log**: `share.cloned` event

The cloned workspace is fully independent. No link back to source.

---

## Stale Reference Handling

When the owner deletes a workspace:
1. The workspace deletion flow in ChaChaNotes_DB fires a hook
2. Hook calls `SharedWorkspaceRepo.revoke_shares_for_workspace(workspace_id, owner_user_id)`
3. Sets `revoked_at = NOW()` on all matching `shared_workspaces` records
4. `shared-with-me` endpoint returns clear "workspace no longer available" message (not 500)

---

## Frontend

### 1. Share Dialog (on WorkspacePlayground)

New "Share" button in workspace header → dialog with:
- **Team/Org picker**: Dropdown populated from `AuthPrincipal.team_ids`/`org_ids`
- **Access level**: Radio buttons (View+Chat / View+Chat+Add / Full Edit)
- **Allow clone toggle**
- **Create link tab**: Generates share token, shows copyable URL, expiry picker, password toggle
- **Active shares list**: Current shares with revoke buttons

### 2. "Shared With Me" Page

New route `/shared` in Next.js app:
- Card grid of shared workspaces
- Each card: workspace name, owner, share date, access level badge
- "Open" → opens WorkspacePlayground in restricted mode
- "Clone" → triggers clone workflow (if allowed)

### 3. Restricted Workspace Mode

Reuses `WorkspacePlayground` with access-level gating:
- `view_chat`: Sources pane read-only, chat fully functional, artifacts read-only
- `view_chat_add`: Sources pane allows adding, rest read-only
- `full_edit`: Full access
- Banner: "Shared by {owner} • {access_level}"

### 4. Public Share Landing Page

Route `/share/{token}`:
- Resource preview (name, description, content counts)
- Password field if required
- "Import to my account" button (requires login)

---

## Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| RAG pipeline reads wrong DB | High | `SharedWorkspaceDBResolver` validates share + returns explicit DB context |
| SQLite write contention with `full_edit` | Medium | Document Postgres recommendation for large teams; warn for >5 members |
| Stale shares after workspace deletion | Medium | Deletion hook revokes shares; endpoints handle missing workspace gracefully |
| Token enumeration on public endpoints | Medium | Rate limiting, constant-time compare, identical error responses |
| Clone without embedding provider | Low | Pre-check warns user; FTS5 text search still works |
| Storage amplification from mass cloning | Low | QuotaManager limits + optional clone count per share token |

---

## Critical Files to Modify

| File | Change |
|------|--------|
| `tldw_Server_API/app/core/AuthNZ/migrations.py` | New migration for 4 tables |
| `tldw_Server_API/Config_Files/privilege_catalog.yaml` | Add `sharing.*` permission codes |
| `tldw_Server_API/app/core/AuthNZ/repos/` | New `shared_workspace_repo.py` (follows `mcp_hub_repo.py` pattern) |
| `tldw_Server_API/app/core/Sharing/` | New module: `share_token_service.py`, `shared_workspace_resolver.py`, `clone_service.py` |
| `tldw_Server_API/app/api/v1/endpoints/sharing.py` | New router with all endpoints |
| `tldw_Server_API/app/api/v1/schemas/sharing_schemas.py` | Pydantic models for requests/responses |
| `tldw_Server_API/app/api/v1/API_Deps/ChaCha_Notes_DB_Deps.py` | `get_chacha_db_for_owner()` dependency |
| `tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py` | `get_media_db_for_owner()` dependency |
| `tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py` | Add `embedding_namespace_override` parameter |
| `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py` | Workspace deletion hook for share revocation |
| `apps/packages/ui/src/components/Option/WorkspacePlayground/` | Share dialog, restricted mode |
| `apps/tldw-frontend/` | New `/shared` page, `/share/{token}` page |

---

## Implementation Stages

### Stage 1: Schema & Core Services
- AuthNZ migration for 4 new tables
- `SharedWorkspaceRepo` in `app/core/AuthNZ/repos/`
- `ShareTokenService` in `app/core/Sharing/`
- `ShareAuditService` for logging
- Permission codes in `privilege_catalog.yaml`
- Unit tests for all services

### Stage 2: Cross-User DB Access & RAG Integration
- `SharedWorkspaceDBResolver` service
- `get_chacha_db_for_owner()` and `get_media_db_for_owner()` dependencies
- `SharedWorkspaceWriteProxy` with access-level enforcement
- `embedding_namespace_override` in unified_pipeline
- Integration tests for cross-user reads

### Stage 3: API Endpoints
- `sharing.py` router — workspace sharing CRUD
- Shared-with-me proxy endpoints
- Token CRUD endpoints
- Public token access endpoints (with rate limiting)
- Admin config/audit endpoints
- Pydantic schemas
- Endpoint tests

### Stage 4: Clone Workflow
- `CloneService` with async job pattern
- Deep media copy logic
- Embedding provider pre-check
- Quota integration
- Workspace deletion hook for share revocation
- Clone tests

### Stage 5: Frontend
- Share dialog component on WorkspacePlayground
- "Shared With Me" page (`/shared`)
- Restricted workspace mode (access-level gating)
- Public share landing page (`/share/{token}`)
- E2E tests

---

## Verification

### Backend Testing
```bash
# Unit tests for sharing services
python -m pytest tests/Sharing/ -v

# Integration tests for cross-user DB access
python -m pytest tests/Sharing/test_cross_user_access.py -v

# Full endpoint tests
python -m pytest tests/Sharing/test_sharing_endpoints.py -v
```

### Manual E2E Verification
1. Create workspace with 2-3 media sources
2. Share workspace with a team → verify team member sees it in "Shared With Me"
3. Team member opens shared workspace → verify sources are readable, chat works, conversation saved to their DB
4. Team member clones workspace → verify deep copy, independence from original
5. Owner deletes workspace → verify shares are revoked, team member sees clear message
6. Create share token → verify link works, password protection, expiry, download limits
7. Import chatbook via share token → verify content imported correctly

### Security Verification
- Attempt to access shared workspace without team membership → 403
- Attempt write operation with `view_chat` access → 403
- Attempt clone when `allow_clone = false` → 403
- Brute-force token endpoint → rate limit kicks in
- Access expired/revoked token → identical error to not-found
