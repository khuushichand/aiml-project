# Governance Pack Distribution And Trust Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add trusted governance-pack distribution from local allowlisted paths and Git sources, persist per-install provenance, support prepared candidate pinning, and let Git-backed installs check for updates and feed candidates into the existing dry-run/import and upgrade flows.

**Architecture:** Extend the existing governance-pack system with a deployment-wide trust store, source provenance persistence, a source-resolution/distribution service, prepared source candidates pinned by commit and pack digest, and MCP Hub API/UI surfaces for source install and update checks. Reuse the current governance-pack import and upgrade planner/executor instead of building a second policy-install path.

**Tech Stack:** FastAPI, Pydantic, SQLite/PostgreSQL AuthNZ repo layer, local Git CLI integration, MCP Hub services, React/TypeScript MCP Hub UI, pytest, vitest

---

### Task 1: Add Governance-Pack Source Provenance And Prepared Candidate Storage

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py`

**Step 1: Write the failing test**

Add repo and API tests that expect:
- governance-pack detail/list responses to expose source provenance fields
- a prepared candidate record to persist `source_type`, `source_location`, `source_ref_requested`, `source_subpath`, `source_commit_resolved`, and `pack_content_digest`
- superseded governance-pack rows to retain their original provenance

Example assertions:

```python
detail = await repo.get_governance_pack(governance_pack_id)
assert detail["source_type"] == "git"
assert detail["source_commit_resolved"] == commit_sha

candidate = await repo.create_governance_pack_source_candidate(...)
assert candidate["pack_content_digest"]
assert candidate["source_subpath"] == "packs/researcher"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py -q
```

Expected: FAIL because provenance fields and prepared candidate storage do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- migration updates for governance-pack source provenance persistence
- prepared candidate storage table or equivalent repo-backed persistence
- repo create/get/list helpers for provenance and candidates
- schema updates for provenance-bearing governance-pack responses

Keep provenance attached to each governance-pack install row, not only the active install.

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py
git commit -m "feat: add governance pack source provenance storage"
```

### Task 2: Add Deployment-Wide Governance-Pack Trust Policy

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Add: `tldw_Server_API/app/services/mcp_hub_governance_pack_trust_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py`

**Step 1: Write the failing test**

Add trust-policy tests that expect:
- local-path installs to be blocked outside allowlisted roots
- denied Git hosts/repos to be rejected
- branch/tag/commit policy to be enforced
- optional verification-required mode to be exposed via the trust-policy API

Example assertions:

```python
decision = await trust_service.evaluate_git_source(...)
assert decision["allowed"] is False
assert "repo_not_trusted" in decision["reason"]

policy = await repo.get_governance_pack_trust_policy()
assert policy["allowed_local_roots"] == ["/srv/packs"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py -q
```

Expected: FAIL because the trust store and service do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- deployment-wide trust-policy persistence
- trust-service read/validate helpers
- schema/API support for trust-policy read/update
- normalization-ready policy fields for:
  - local allowlist roots
  - allowed Git hosts/repos
  - allowed ref modes
  - verification mode and key references

Keep trust policy deployment-wide only in v1.

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_trust_service.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py
git commit -m "feat: add governance pack trust policy"
```

### Task 3: Build Local Path And Git Source Resolution

**Files:**
- Add: `tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/governance_packs/models.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/governance_packs/fixtures.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_service.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py`

**Step 1: Write the failing test**

Add source-resolution tests that expect:
- repo URLs to canonicalize before trust matching
- source URLs with embedded credentials to be rejected or sanitized
- local paths outside allowlisted roots to fail
- Git `repo + ref + subpath` resolution to return an exact commit and pack digest
- symlink or `..` subpath escapes to be rejected
- optional local signature verification mode to gate Git candidates

Example assertions:

```python
resolved = await distribution_service.resolve_git_source(...)
assert resolved.source_commit_resolved == commit_sha
assert resolved.source_subpath == "packs/researcher"
assert resolved.pack_content_digest

with pytest.raises(ValueError, match="subpath"):
    await distribution_service.resolve_git_source(..., subpath="../escape")
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py -q
```

Expected: FAIL because source resolution and canonicalization do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- source-resolution service for local path and Git sources
- canonical repo normalization
- credential sanitization/rejection
- local-path allowlist enforcement
- Git fetch/checkout/commit-resolution helpers
- subpath normalization and escape rejection
- normalized pack digest generation
- optional local `git verify-commit` / `git verify-tag` enforcement
- governance-pack model support for richer source metadata beyond `source_path`

Do not execute pack-provided code.

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py \
  tldw_Server_API/app/core/MCP_unified/governance_packs/models.py \
  tldw_Server_API/app/core/MCP_unified/governance_packs/fixtures.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py
git commit -m "feat: add governance pack source resolution"
```

### Task 4: Add Source-Backed Dry-Run And Import APIs

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py`

**Step 1: Write the failing test**

Add API and service tests that expect:
- dry-run import from a prepared local-path or Git source candidate
- execute import from a prepared candidate
- trust validation to happen before pack parsing/import
- installed governance-pack rows to store the candidate provenance used for import

Example assertions:

```python
response = client.post("/api/v1/mcp-hub/governance-packs/source/dry-run", json={...})
assert response.status_code == 200
assert response.json()["report"]["manifest"]["pack_id"] == "researcher_pack"

installed = await repo.get_governance_pack(governance_pack_id)
assert installed["source_location"] == canonical_repo
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py -q
```

Expected: FAIL because source-based dry-run/import endpoints do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- source-aware dry-run/import request/response schemas
- endpoint wiring for:
  - resolve/prepare source candidate
  - dry-run import from candidate
  - import from candidate
- service integration so existing dry-run/import logic consumes the prepared candidate's pinned pack content
- provenance persistence on successful import

Keep the existing document-based import path working.

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py
git commit -m "feat: add governance pack source import APIs"
```

### Task 5: Add Update Discovery And Prepared-Candidate Upgrade Integration

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py`

**Step 1: Write the failing test**

Add tests that expect:
- Git-backed installs to report `newer_version_available`
- same-version different-content checks to report `source_drift_same_version`
- mismatched `pack_id` candidates to be rejected
- prepared upgrade candidates to pin commit/digest across dry-run upgrade and execute-upgrade
- stale or drifted candidates to be rejected before execution

Example assertions:

```python
check = await distribution_service.check_for_updates(governance_pack_id)
assert check["status"] == "newer_version_available"

plan = await service.dry_run_upgrade_from_candidate(...)
assert plan["plan"]["planner_input_fingerprint"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py -q
```

Expected: FAIL because source-backed update checks and candidate-pinned upgrades do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- Git-backed update-check service flow
- update result classification including `source_drift_same_version`
- prepare-candidate record reuse for dry-run upgrade and execute-upgrade
- stale candidate rejection using stored commit/digest identity
- API endpoints for:
  - check updates
  - prepare upgrade candidate
  - dry-run upgrade from candidate
  - execute upgrade from candidate

Reuse the existing transactional upgrade planner/executor once candidate validation passes.

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py
git commit -m "feat: add governance pack source updates"
```

### Task 6: Extend The MCP Hub UI For Source Install, Provenance, And Update Checks

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/GovernancePacksTab.tsx`
- Test: `apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx`

**Step 1: Write the failing test**

Add UI tests that expect:
- local-path and Git source install forms
- provenance summary and trust/verification badges in governance-pack detail
- check-for-updates action on Git-backed installs only
- rendering of `newer_version_available`, `no_update`, and `source_drift_same_version`
- prepared candidate source details in upgrade modals

Example assertions:

```tsx
expect(screen.getByText(/Git Source/i)).toBeInTheDocument();
expect(screen.getByText(/Verified Commit/i)).toBeInTheDocument();
expect(screen.getByRole("button", { name: /Check For Updates/i })).toBeEnabled();
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx
```

Expected: FAIL because source install/update UI does not exist yet.

**Step 3: Write minimal implementation**

Implement:
- client types and API methods for trust policy, source install, provenance, and update checks
- UI affordances for:
  - install from local path
  - install from Git repo/ref/subpath
  - provenance display
  - trust/verification badges
  - check-for-updates and prepared-candidate upgrade flow

Keep summary-first UX, with expandable raw provenance detail.

**Step 4: Run test to verify it passes**

Run the same vitest command and confirm PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/mcp-hub.ts \
  apps/packages/ui/src/components/Option/MCPHub/GovernancePacksTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx
git commit -m "feat: add governance pack source distribution UI"
```

### Task 7: Final Verification And Hardening

**Files:**
- Verify touched backend and frontend files from Tasks 1-6

**Step 1: Run targeted backend tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_distribution.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py -q
```

Expected: PASS.

**Step 2: Run targeted frontend tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx
```

Expected: PASS.

**Step 3: Run Bandit on the touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/services/mcp_hub_governance_pack_distribution_service.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_trust_service.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py
```

Expected: no new findings in changed code.

**Step 4: Run diff sanity checks**

Run:

```bash
git diff --check
```

Expected: clean.

**Step 5: Commit verification fixes if needed**

If any verification changes are required:

```bash
git add <touched files>
git commit -m "test: finalize governance pack distribution verification"
```

If no further changes are required, do not create an extra commit.
