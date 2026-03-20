# Governance Pack Signer Trust And Verification UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend governance-pack Git-source trust with a repo-bound trusted signer registry, structured verification results, signer provenance, and operator-facing diagnostics while preserving backward-compatible summary verification fields.

**Architecture:** Evolve the existing deployment-wide governance-pack trust store into a single source of truth for both source rules and signer bindings. Replace the current boolean-only Git verification path with a structured result object, persist signer provenance on prepared candidates and installed packs, and surface those diagnostics through MCP Hub API and UI flows without changing MCP Hub’s runtime-authority model.

**Tech Stack:** FastAPI, Pydantic, SQLite/PostgreSQL AuthNZ repo layer, local Git CLI verification, MCP Hub services, React/TypeScript MCP Hub UI, pytest, vitest

---

### Task 1: Add Structured Signer Bindings To The Trust Store

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_trust_service.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py`

**Step 1: Write the failing test**

Add tests that expect the trust-policy API and trust service to support:
- `trusted_signers` entries with fingerprint, display name, repo bindings, and status
- legacy `trusted_git_key_fingerprints` input to normalize into structured signer bindings
- simple repo-binding semantics using exact canonical repo ids and prefix rules

Example assertions:

```python
policy = await trust_service.update_policy(
    {
        "allow_git_sources": True,
        "allowed_git_hosts": ["github.com"],
        "allowed_git_repositories": ["github.com/example/packs"],
        "allowed_git_ref_kinds": ["tag"],
        "require_git_signature_verification": True,
        "trusted_signers": [
            {
                "fingerprint": "ABC123",
                "display_name": "Release Bot",
                "repo_bindings": ["github.com/example/packs"],
                "status": "active",
            }
        ],
    },
    actor_id=1,
)
assert policy["trusted_signers"][0]["fingerprint"] == "ABC123"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py -q
```

Expected: FAIL because the trust store only supports `trusted_git_key_fingerprints`.

**Step 3: Write minimal implementation**

Implement:
- structured signer-binding schema models
- trust-service normalization for `trusted_signers`
- legacy fingerprint upconversion into active signer bindings
- exact and prefix repo-binding normalization

Keep the existing flat fingerprint list as a compatibility input only.

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_trust_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py
git commit -m "feat: add governance pack signer bindings"
```

### Task 2: Add Trust-Policy Version Guard And Signer Evaluation Semantics

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_trust_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py`

**Step 1: Write the failing test**

Add tests that expect:
- trust-policy `GET` to return a version or fingerprint
- trust-policy `PUT` to reject stale writes
- signer evaluation to classify:
  - signer trusted for repo
  - signer not allowed for repo
  - signer revoked

Example assertions:

```python
policy = client.get("/api/v1/mcp-hub/governance-pack-trust-policy").json()
response = client.put(
    "/api/v1/mcp-hub/governance-pack-trust-policy",
    json={**updated_policy, "policy_fingerprint": "stale"},
)
assert response.status_code == 409
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py -q
```

Expected: FAIL because trust-policy writes are currently unconditional and signer trust is not classified separately.

**Step 3: Write minimal implementation**

Implement:
- trust-policy fingerprint/version generation
- optimistic-concurrency validation on updates
- trust-service signer evaluation helpers returning explicit result codes

Keep this deployment-wide; do not add per-scope trust writes.

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_trust_service.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py
git commit -m "feat: guard governance pack trust policy updates"
```

### Task 3: Replace Boolean Git Verification With A Structured Result

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_trust_service.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py`

**Step 1: Write the failing test**

Add tests that expect Git verification to return a structured result with:
- `verified`
- `verification_mode`
- `verified_object_type`
- `signer_fingerprint`
- `signer_identity`
- `result_code`
- `warning_code`

Include cases for:
- valid signed commit
- valid signed tag
- invalid signature
- missing signer fingerprint under strict signer policy
- unsupported signature backend

Example assertions:

```python
result = await distribution_service._verify_git_revision(...)
assert result["verified"] is True
assert result["verified_object_type"] == "tag"
assert result["signer_fingerprint"] == "ABC123"
assert result["result_code"] == "verified_and_trusted"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py -q
```

Expected: FAIL because verification currently returns only `True` or `False`.

**Step 3: Write minimal implementation**

Implement:
- a structured verification result object
- Git/GPG `VALIDSIG` parsing into signer fingerprint fields
- explicit result codes and warning codes
- backward-compatible derivation of `source_verified` and `source_verification_mode`

Keep v1 scoped to the explicitly implemented Git/GPG extraction path.

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_trust_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py
git commit -m "feat: add structured governance pack verification results"
```

### Task 4: Persist Signer Provenance On Candidates And Installed Packs

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py`

**Step 1: Write the failing test**

Add tests that expect prepared candidates and installed packs to persist:
- `signer_fingerprint`
- `signer_identity`
- `verified_object_type`
- `verification_result_code`
- `verification_warning_code`

Also assert that the older summary fields remain populated.

Example assertions:

```python
candidate = await repo.get_governance_pack_source_candidate(candidate_id)
assert candidate["signer_fingerprint"] == "ABC123"
assert candidate["verification_result_code"] == "verified_and_trusted"
assert candidate["source_verified"] is True
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py -q
```

Expected: FAIL because signer provenance fields are not stored yet.

**Step 3: Write minimal implementation**

Implement:
- migration changes for candidate/install signer fields
- repo read/write support
- candidate persistence from structured verification results
- install/import persistence for signer provenance
- backward-compatible schema exposure

Historical rows without signer data must still load cleanly.

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py
git commit -m "feat: persist governance pack signer provenance"
```

### Task 5: Add Signer Diagnostics To Update And Upgrade Flows

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py`

**Step 1: Write the failing test**

Add tests that expect:
- `signer_rotated_trusted` warning when a newer candidate is signed by a different trusted signer
- `unknown_previous_signer` warning for historical installs without signer provenance
- revoked signer to block prepare/import/upgrade

Example assertions:

```python
update = await distribution_service.check_for_updates(governance_pack_id)
assert update["verification_warning_code"] == "signer_rotated_trusted"

with pytest.raises(ValueError, match="signer"):
    await distribution_service.prepare_upgrade_candidate(...)
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py -q
```

Expected: FAIL because update flows only report coarse verification state today.

**Step 3: Write minimal implementation**

Implement:
- signer-rotation comparison using installed signer provenance
- `unknown_previous_signer` fallback when historical rows lack signer fields
- revoked-signer blocking in prepare/import/upgrade flows
- warning/result propagation through update and upgrade preparation responses

Do not mutate historical install provenance when signer trust changes later.

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py
git commit -m "feat: add governance pack signer diagnostics"
```

### Task 6: Expose Trusted Signers And Verification UX In MCP Hub UI

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/GovernancePacksTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx`
- Test: `apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts`

**Step 1: Write the failing test**

Add UI/service tests that expect:
- trust policy payloads to include signer bindings
- candidate and installed-pack data to expose signer diagnostics
- Governance Packs UI to show signer fingerprint, result code, and rotation/revocation warnings

Example assertions:

```ts
expect(screen.getByText("Trusted Signers")).toBeInTheDocument()
expect(screen.getByText("ABC123")).toBeInTheDocument()
expect(screen.getByText("Signer rotated")).toBeInTheDocument()
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/services/tldw/__tests__/mcp-hub.test.ts \
  src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx
```

Expected: FAIL because the client and UI only understand coarse verification fields.

**Step 3: Write minimal implementation**

Implement:
- client types for signer bindings and verification result fields
- trust-policy UI support for trusted signer CRUD payloads
- candidate/install detail rendering for signer diagnostics and warnings
- safe rendering for historical installs without signer provenance

Keep default presentation compact with expandable detail.

**Step 4: Run test to verify it passes**

Run the same vitest command and confirm PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/mcp-hub.ts \
  apps/packages/ui/src/components/Option/MCPHub/GovernancePacksTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx \
  apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts
git commit -m "feat: add governance pack signer trust UI"
```

### Task 7: Run Focused Verification And Finalize

**Files:**
- Modify: `Docs/Plans/2026-03-19-governance-pack-signer-trust-implementation-plan.md`

**Step 1: Run backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py -q
```

Expected: PASS.

**Step 2: Run UI verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/services/tldw/__tests__/mcp-hub.test.ts \
  src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx
```

Expected: PASS.

**Step 3: Run security and diff checks**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/services/mcp_hub_governance_pack_trust_service.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py
git diff --check
```

Expected: no new Bandit findings in touched code and a clean diff check.

**Step 4: Update the plan status**

Mark every task complete in this plan file and record any deviations from the original design scope.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-19-governance-pack-signer-trust-implementation-plan.md
git commit -m "docs: finalize governance pack signer trust plan"
```

## Final Status

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete
- Task 6: Complete
- Task 7: Complete

## Verification Summary

- Backend focused governance-pack suite: `84 passed`
- UI signer-trust vitest slice: `17 passed`
- Bandit on touched backend governance-pack scope: `0 findings`
- `git diff --check`: clean

## Deviations

- Task 5 expanded the MCP Hub update-check response shape to carry signer diagnostics at the top level, not only inside prepared candidates. This was necessary so Task 6 could surface signer rotation and unknown-previous-signer warnings directly in the update banner without making an extra fetch.
