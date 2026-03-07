# External_Sources

## 1. Descriptive of Current Feature Set

- Purpose: Connect external providers (Google Drive, Notion) to import/sync content into user collections.
- Capabilities:
  - OAuth linking, account listing/removal
  - Browsing remote sources (Drive folders, Notion pages/databases)
  - Creating sources with per-org policy enforcement; queuing import jobs
  - Source-level sync cursors, webhook state, and legacy-import rescan markers
  - Canonical remote-to-media bindings and append-only item sync events
  - Org policy admin: allowed providers, paths, domains, quotas
- Inputs/Outputs:
  - Inputs: OAuth code/state, provider selection, source path/IDs, policy documents
  - Outputs: accounts, sources, import job descriptors; ingested content in Collections DB
- Related Endpoints:
  - Connectors API: `tldw_Server_API/app/api/v1/endpoints/connectors.py:46` (providers/catalog, authorize/callback, accounts, sources, jobs, policy)
- Related Schemas:
  - `tldw_Server_API/app/api/v1/schemas/connectors.py:1`

## 2. Technical Details of Features

- Architecture & Data Flow:
  - Provider connectors implement a small interface; service functions write to AuthNZ DB tables via async pool
  - OAuth state is generated on authorize, stored in AuthNZ DB, and consumed once during callback
  - Endpoints enforce org-level policy in multi-user mode; single-user mode bypasses org checks
- Key Classes/Functions:
  - Connectors service: `core/External_Sources/connectors_service.py` (DDL ensure, policy upsert/get, accounts/sources CRUD)
  - Providers: `google_drive.py`, `notion.py`; registry: `get_connector_by_name`
- Dependencies:
  - Internal: AuthNZ DB pool, policy helpers, Logging context
  - External: Google/Notion APIs (networked); tokens stored via DB
- Data Models & DB:
  - AuthNZ DB tables: `external_accounts`, `external_sources`, `external_items`, `external_source_sync_state`, `external_item_events`, `org_connector_policy`, `external_oauth_state` (SQLite/PG variants)
  - `external_items` is the canonical remote binding row; legacy rows without `media_id` are marked for full rescan during migration
- Configuration:
  - `CONNECTOR_REDIRECT_BASE_URL` for OAuth callbacks (fallback to request host/connector redirect base); provider keys via env/config
  - `CONNECTOR_OAUTH_STATE_TTL_MINUTES` to control OAuth state validity (default: 10)
- Concurrency & Performance:
  - Import jobs queued with daily quotas by role; pagination support
- Error Handling:
  - Consistent HTTP 4xx/5xx; policy evaluation yields 403 with reason; token refresh envelope helpers covered by tests
- Security:
  - RBAC by role; email/workspace validations; path/domain allow/deny lists; token handling in AuthNZ DB

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure:
  - `External_Sources/` (provider adapters, policy), service helpers, endpoints under `/api/v1/endpoints/connectors.py`
- Extension Points:
  - Add a provider module and wire into `get_connector_by_name`; implement browse, list, and token exchange as needed
- Coding Patterns:
  - Async DB via pool; structured logs; keep endpoints thin (service owns DDL and logic)
- Tests:
  - `tldw_Server_API/tests/External_Sources/test_policy_and_connectors.py:1`
  - `tldw_Server_API/tests/External_Sources/test_token_refresh_envelope.py:1`
- Local Dev Tips:
  - Use TEST_MODE and mock provider modules in tests; set callback base URL via env for manual flows
- Pitfalls & Gotchas:
  - Quotas per role; pagination cursors; workspace and domain constraints
- Roadmap/TODOs:
  - Additional providers; shared sync coordinator, delta polling, and webhook reconciliation
