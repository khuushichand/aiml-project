# Enterprise AuthNZ and MCP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add enterprise OIDC federation, safe local-user provisioning, generic MCP credential brokering, and a local secret-backend abstraction without introducing a separate control plane.

**Architecture:** Extend `AuthNZ` as the source of truth for enterprise identity, local-user provisioning, secret backend resolution, and brokered execution credentials. Keep `MCP Hub` as the source of truth for profile/assignment/slot policy and approval rules, and keep `MCP Unified` as a runtime consumer of resolved principal and ephemeral credential context only.

**Tech Stack:** FastAPI, Pydantic, PostgreSQL-first AuthNZ repos, existing JWT/session stack, MCP Hub repo/services, pytest, Bandit

---

### Task 1: Enterprise Feature Flags and Deployment Guardrails

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/settings.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/README.md`
- Create: `tldw_Server_API/tests/AuthNZ_Federation/test_enterprise_flags.py`

**Step 1: Write the failing test**

```python
def test_enterprise_federation_requires_multi_user_mode(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("AUTH_FEDERATION_ENABLED", "true")
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()
    assert settings.AUTH_FEDERATION_ENABLED is True
    assert settings.enterprise_federation_supported is False
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation/test_enterprise_flags.py -v
```

Expected: FAIL because the enterprise support guard/helper does not exist yet.

**Step 3: Write minimal implementation**

- Add:
  - `AUTH_FEDERATION_ENABLED`
  - `MCP_CREDENTIAL_BROKER_ENABLED`
  - `SECRET_BACKENDS_ENABLED`
  - `enterprise_federation_supported` derived helper
- Fail closed for unsupported deployment profiles in enterprise mode.
- Document the support matrix in the AuthNZ README.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation/test_enterprise_flags.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/settings.py tldw_Server_API/app/core/AuthNZ/README.md tldw_Server_API/tests/AuthNZ_Federation/test_enterprise_flags.py
git commit -m "feat: add enterprise federation feature flags and guardrails"
```

### Task 2: Identity Provider and Federated Identity Storage

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Create: `tldw_Server_API/app/core/AuthNZ/repos/identity_provider_repo.py`
- Create: `tldw_Server_API/app/core/AuthNZ/repos/federated_identity_repo.py`
- Create: `tldw_Server_API/tests/AuthNZ_Federation/test_identity_provider_repo.py`

**Step 1: Write the failing test**

```python
async def test_create_and_fetch_identity_provider(tmp_path, monkeypatch):
    from tldw_Server_API.app.core.AuthNZ.repos.identity_provider_repo import IdentityProviderRepo

    repo = IdentityProviderRepo(...)
    created = await repo.create_provider(
        slug="corp",
        provider_type="oidc",
        owner_scope_type="global",
        owner_scope_id=None,
        enabled=False,
        issuer="https://issuer.example.com",
        claim_mapping={"email": "email"},
        provisioning_policy={"mode": "jit_grant_only"},
    )
    fetched = await repo.get_provider(created["id"])
    assert fetched["slug"] == "corp"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation/test_identity_provider_repo.py -v
```

Expected: FAIL because the repo and tables do not exist.

**Step 3: Write minimal implementation**

- Add PostgreSQL and SQLite table creation for:
  - `identity_providers`
  - `federated_identities`
- Create repos with CRUD and list methods.
- Restrict provider scope to `global` and `org` in v1.
- Keep local `users` rows as the target of all federated identities.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation/test_identity_provider_repo.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py tldw_Server_API/app/core/AuthNZ/repos/identity_provider_repo.py tldw_Server_API/app/core/AuthNZ/repos/federated_identity_repo.py tldw_Server_API/tests/AuthNZ_Federation/test_identity_provider_repo.py
git commit -m "feat: add identity provider and federated identity storage"
```

### Task 3: OIDC Admin Configuration and Mapping Preview APIs

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/identity_provider_schemas.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/admin/admin_identity_providers.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/__init__.py`
- Create: `tldw_Server_API/app/core/AuthNZ/federation/claim_mapping.py`
- Create: `tldw_Server_API/tests/AuthNZ_Federation/test_identity_provider_admin_api.py`

**Step 1: Write the failing test**

```python
def test_identity_provider_mapping_preview_returns_derived_memberships(client, admin_headers):
    payload = {
        "provider_id": 1,
        "claims": {
            "sub": "abc-123",
            "email": "alice@example.com",
            "groups": ["eng-admins"],
        },
    }
    response = client.post("/api/v1/admin/identity/providers/1/mappings/preview", json=payload, headers=admin_headers)
    assert response.status_code == 200
    assert "derived_roles" in response.json()
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation/test_identity_provider_admin_api.py -v
```

Expected: FAIL because the admin endpoint and claim-mapping service do not exist.

**Step 3: Write minimal implementation**

- Add admin CRUD endpoints for identity providers.
- Add mapping preview endpoint that:
  - validates provider config
  - applies claim mapping
  - returns derived roles/orgs/teams without mutating state
- Require enterprise feature flags plus admin permission.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation/test_identity_provider_admin_api.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/identity_provider_schemas.py tldw_Server_API/app/api/v1/endpoints/admin/admin_identity_providers.py tldw_Server_API/app/api/v1/endpoints/admin/__init__.py tldw_Server_API/app/core/AuthNZ/federation/claim_mapping.py tldw_Server_API/tests/AuthNZ_Federation/test_identity_provider_admin_api.py
git commit -m "feat: add OIDC provider admin and mapping preview APIs"
```

### Task 4: OIDC Runtime Login, Callback, Linking, and JIT Provisioning

**Files:**
- Create: `tldw_Server_API/app/core/AuthNZ/federation/oidc_service.py`
- Create: `tldw_Server_API/app/core/AuthNZ/federation/provisioning_service.py`
- Create: `tldw_Server_API/app/core/AuthNZ/repos/federation_state_repo.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/auth.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/auth_principal_resolver.py`
- Create: `tldw_Server_API/tests/AuthNZ_Federation/test_oidc_login_flow.py`

**Step 1: Write the failing test**

```python
def test_oidc_callback_creates_local_user_and_links_subject(client, monkeypatch):
    monkeypatch.setenv("AUTH_FEDERATION_ENABLED", "true")
    response = client.get("/api/v1/auth/federation/callback/corp?code=fake&state=fake")
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["auth_method"] == "federated_oidc"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation/test_oidc_login_flow.py -v
```

Expected: FAIL because the federation routes and provisioning logic do not exist.

**Step 3: Write minimal implementation**

- Add login and callback routes under `/api/v1/auth/federation`.
- Validate state, issuer, audience, and mapped claims.
- Enforce local-user requirement:
  - resolve by provider subject
  - optionally link existing local account only when policy allows
  - otherwise create/update a local user and memberships
- Emit the existing access/refresh token contract.
- Do not create external-only session principals.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation/test_oidc_login_flow.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/federation/oidc_service.py tldw_Server_API/app/core/AuthNZ/federation/provisioning_service.py tldw_Server_API/app/core/AuthNZ/repos/federation_state_repo.py tldw_Server_API/app/api/v1/endpoints/auth.py tldw_Server_API/app/core/AuthNZ/auth_principal_resolver.py tldw_Server_API/tests/AuthNZ_Federation/test_oidc_login_flow.py
git commit -m "feat: add OIDC runtime login and JIT provisioning"
```

### Task 5: Secret Backend Interface and Local Encrypted Backend

**Files:**
- Create: `tldw_Server_API/app/core/AuthNZ/secret_backends/base.py`
- Create: `tldw_Server_API/app/core/AuthNZ/secret_backends/local_encrypted.py`
- Create: `tldw_Server_API/app/core/AuthNZ/secret_backends/registry.py`
- Create: `tldw_Server_API/app/core/AuthNZ/repos/managed_secret_refs_repo.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/user_provider_secrets.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Create: `tldw_Server_API/tests/AuthNZ_Federation/test_local_secret_backend.py`

**Step 1: Write the failing test**

```python
async def test_local_secret_backend_resolve_for_use_returns_ephemeral_material():
    from tldw_Server_API.app.core.AuthNZ.secret_backends.local_encrypted import LocalEncryptedSecretBackend

    backend = LocalEncryptedSecretBackend(...)
    ref = await backend.store_ref(owner_scope_type="user", owner_scope_id=1, provider_key="openai", payload={"api_key": "sk-test"})
    resolved = await backend.resolve_for_use(ref["id"])
    assert resolved["material"]
    assert resolved["expires_at"] is not None
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation/test_local_secret_backend.py -v
```

Expected: FAIL because the backend abstraction and secret refs do not exist.

**Step 3: Write minimal implementation**

- Introduce capability-oriented secret backend interface:
  - `store_ref`
  - `resolve_for_use`
  - `rotate_if_supported`
  - `describe_status`
  - `delete_ref`
- Wrap the current BYOK encryption path as `local_encrypted_v1`.
- Add `secret_backends` and `managed_secret_refs` tables.
- Keep remote backends out of scope for now.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation/test_local_secret_backend.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/secret_backends/base.py tldw_Server_API/app/core/AuthNZ/secret_backends/local_encrypted.py tldw_Server_API/app/core/AuthNZ/secret_backends/registry.py tldw_Server_API/app/core/AuthNZ/repos/managed_secret_refs_repo.py tldw_Server_API/app/core/AuthNZ/user_provider_secrets.py tldw_Server_API/app/core/AuthNZ/migrations.py tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py tldw_Server_API/tests/AuthNZ_Federation/test_local_secret_backend.py
git commit -m "feat: add local encrypted secret backend and managed secret refs"
```

### Task 6: MCP Hub Logical Secret References and Slot Status

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Create: `tldw_Server_API/app/services/mcp_credential_broker_service.py`
- Create: `tldw_Server_API/tests/MCP_Hub/test_mcp_slot_status.py`

**Step 1: Write the failing test**

```python
async def test_assignment_binding_reports_reauth_required_when_secret_ref_expired():
    from tldw_Server_API.app.services.mcp_credential_broker_service import McpCredentialBrokerService

    service = McpCredentialBrokerService(...)
    status = await service.get_slot_status(server_id="github", slot_name="bearer_token", assignment_id=7)
    assert status["state"] == "reauth_required"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_Hub/test_mcp_slot_status.py -v
```

Expected: FAIL because generic slot-state resolution does not exist.

**Step 3: Write minimal implementation**

- Extend MCP Hub binding model to reference logical secret refs instead of raw provider-specific assumptions.
- Add slot states:
  - `ready`
  - `missing`
  - `expired`
  - `reauth_required`
  - `approval_required`
  - `backend_unavailable`
- Expose status endpoints and bind/unbind APIs.
- Keep approval policy and path/workspace scope in MCP Hub.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_Hub/test_mcp_slot_status.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py tldw_Server_API/app/services/mcp_credential_broker_service.py tldw_Server_API/tests/MCP_Hub/test_mcp_slot_status.py
git commit -m "feat: add MCP slot status and logical secret reference bindings"
```

### Task 7: Brokered Runtime Credential Injection for External MCP Calls

**Files:**
- Modify: `tldw_Server_API/app/core/MCP_unified/external_servers/manager.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/external_servers/transports/base.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/external_servers/transports/stdio_adapter.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/external_servers/transports/websocket_adapter.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/modules/implementations/external_federation_module.py`
- Create: `tldw_Server_API/app/core/MCP_unified/tests/test_external_credential_broker_runtime.py`

**Step 1: Write the failing test**

```python
async def test_external_tool_call_uses_ephemeral_brokered_credential(monkeypatch):
    from tldw_Server_API.app.core.MCP_unified.external_servers.manager import ExternalServerManager

    manager = ExternalServerManager(...)
    result = await manager.execute_virtual_tool("ext.github.search", {"query": "repo:test"}, context={"request_id": "r1"})
    assert result["metadata"]["credential_mode"] == "brokered_ephemeral"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/app/core/MCP_unified/tests/test_external_credential_broker_runtime.py -v
```

Expected: FAIL because the runtime does not request brokered credential material yet.

**Step 3: Write minimal implementation**

- Add a broker call path from external-server execution to `AuthNZ`.
- Inject ephemeral execution material per call.
- Ensure adapters:
  - do not persist durable secret values
  - do not log injected values
  - redact brokered credentials from telemetry and errors

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/app/core/MCP_unified/tests/test_external_credential_broker_runtime.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/external_servers/manager.py tldw_Server_API/app/core/MCP_unified/external_servers/transports/base.py tldw_Server_API/app/core/MCP_unified/external_servers/transports/stdio_adapter.py tldw_Server_API/app/core/MCP_unified/external_servers/transports/websocket_adapter.py tldw_Server_API/app/core/MCP_unified/modules/implementations/external_federation_module.py tldw_Server_API/app/core/MCP_unified/tests/test_external_credential_broker_runtime.py
git commit -m "feat: broker ephemeral credentials into external MCP execution"
```

### Task 8: Federated Admin Reauthentication and Step-Up

**Files:**
- Modify: `tldw_Server_API/app/services/admin_guardrails_service.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/jwt_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/auth.py`
- Create: `tldw_Server_API/tests/AuthNZ_Federation/test_federated_admin_reauth.py`

**Step 1: Write the failing test**

```python
async def test_federated_admin_reauth_does_not_require_local_password(monkeypatch):
    from tldw_Server_API.app.services.admin_guardrails_service import verify_privileged_action

    principal = ...
    reason = await verify_privileged_action(
        principal,
        db=...,
        password_service=...,
        reason="rotate provider trust config",
        admin_password=None,
    )
    assert reason == "rotate provider trust config"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation/test_federated_admin_reauth.py -v
```

Expected: FAIL because admin reauth currently assumes a local password-backed admin.

**Step 3: Write minimal implementation**

- Split privileged reauth into:
  - local-password reauth
  - federated step-up reauth or short-lived signed step-up token flow
- Keep the human-readable reason requirement.
- Reuse existing JWT/session machinery where possible.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation/test_federated_admin_reauth.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_guardrails_service.py tldw_Server_API/app/core/AuthNZ/jwt_service.py tldw_Server_API/app/api/v1/endpoints/auth.py tldw_Server_API/tests/AuthNZ_Federation/test_federated_admin_reauth.py
git commit -m "feat: add federated admin reauthentication flow"
```

### Task 9: Verification, Security Review, and Documentation

**Files:**
- Modify: `Docs/` and module READMEs as needed
- Modify: `tldw_Server_API/app/core/AuthNZ/API_INTEGRATION_GUIDE.md`
- Modify: `tldw_Server_API/app/core/MCP_unified/README.md`

**Step 1: Run focused test suites**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation -v
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_Hub/test_mcp_slot_status.py -v
source .venv/bin/activate && python -m pytest tldw_Server_API/app/core/MCP_unified/tests/test_external_credential_broker_runtime.py -v
```

Expected: PASS

**Step 2: Run touched-scope Bandit**

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/AuthNZ/federation tldw_Server_API/app/core/AuthNZ/secret_backends tldw_Server_API/app/api/v1/endpoints/admin/admin_identity_providers.py tldw_Server_API/app/api/v1/endpoints/auth.py tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py tldw_Server_API/app/core/MCP_unified/external_servers -f json -o /tmp/bandit_enterprise_authnz_mcp.json
```

Expected: no new findings in changed code

**Step 3: Update docs**

- Document:
  - enterprise support matrix
  - OIDC-only phase 1
  - local-user invariant
  - brokered credential runtime rule
  - no raw secret persistence in adapters

**Step 4: Final verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Federation tldw_Server_API/tests/MCP_Hub/test_mcp_slot_status.py tldw_Server_API/app/core/MCP_unified/tests/test_external_credential_broker_runtime.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add Docs tldw_Server_API/app/core/AuthNZ/API_INTEGRATION_GUIDE.md tldw_Server_API/app/core/MCP_unified/README.md
git commit -m "docs: document enterprise federation and MCP credential broker"
```
