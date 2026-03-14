# OPA Governance Packs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add schema-first, file-based governance packs that compile to deterministic OPA artifacts, dry-run against local MCP Hub adapter rules, and import into immutable MCP Hub base objects with provenance.

**Architecture:** Introduce a new governance-pack domain that validates pack source into a normalized IR, emits generated OPA artifacts for portability, computes a local dry-run compatibility report, and then materializes immutable base records plus provenance links into existing MCP Hub policy objects. Keep live runtime enforcement in the current MCP Hub + protocol path, and expose pack preview/import status through MCP Hub management APIs and UI.

**Tech Stack:** FastAPI, Pydantic, SQLite/PostgreSQL AuthNZ migrations, MCP Hub services/repo, React, Vitest, pytest, Bandit, YAML/JSON serialization

---

## Status

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Not Started
- Task 5: Not Started
- Task 6: Not Started

### Task 1: Add governance-pack schema, fixtures, and failing validation tests

**Files:**
- Create: `tldw_Server_API/app/core/MCP_unified/governance_packs/__init__.py`
- Create: `tldw_Server_API/app/core/MCP_unified/governance_packs/models.py`
- Create: `tldw_Server_API/app/core/MCP_unified/governance_packs/validation.py`
- Create: `tldw_Server_API/app/core/MCP_unified/governance_packs/fixtures.py`
- Create: `tldw_Server_API/tests/MCP_unified/test_governance_pack_validation.py`
- Create: `tldw_Server_API/tests/MCP_unified/fixtures/governance_packs/minimal_researcher_pack/manifest.yaml`
- Create: `tldw_Server_API/tests/MCP_unified/fixtures/governance_packs/minimal_researcher_pack/profiles/researcher.yaml`
- Create: `tldw_Server_API/tests/MCP_unified/fixtures/governance_packs/minimal_researcher_pack/personas/researcher.yaml`
- Create: `tldw_Server_API/tests/MCP_unified/fixtures/governance_packs/minimal_researcher_pack/approvals/ask.yaml`
- Create: `tldw_Server_API/tests/MCP_unified/fixtures/governance_packs/minimal_researcher_pack/assignments/default.yaml`

**Step 1: Write the failing validation tests**

Add tests that expect:

- a minimal valid pack loads and validates
- missing referenced profile ids fail validation
- duplicate stable ids fail validation
- unsupported `capability_taxonomy_version` fails validation
- persona templates containing runtime-only fields like memory/session data fail validation

Example test shape:

```python
def test_validate_minimal_pack(tmp_path):
    pack = load_governance_pack_fixture("minimal_researcher_pack")
    result = validate_governance_pack(pack)
    assert result.errors == []
    assert result.manifest.pack_id == "researcher-pack"
```

**Step 2: Run the focused tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_governance_pack_validation.py -v
```

Expected: FAIL because the governance-pack module does not exist yet.

**Step 3: Write the minimal schema/validation implementation**

Add:

- Pydantic models for manifest, profiles, approvals, persona templates, and assignment templates
- reference-integrity validation
- stable-id uniqueness checks
- runtime-only field rejection for persona templates

Example model shape:

```python
class GovernancePackManifest(BaseModel):
    pack_id: str
    pack_version: str
    pack_schema_version: int
    capability_taxonomy_version: int
    adapter_contract_version: int
```

**Step 4: Re-run the validation tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_governance_pack_validation.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/MCP_unified/governance_packs/__init__.py \
  tldw_Server_API/app/core/MCP_unified/governance_packs/models.py \
  tldw_Server_API/app/core/MCP_unified/governance_packs/validation.py \
  tldw_Server_API/app/core/MCP_unified/governance_packs/fixtures.py \
  tldw_Server_API/tests/MCP_unified/test_governance_pack_validation.py \
  tldw_Server_API/tests/MCP_unified/fixtures/governance_packs/minimal_researcher_pack
git commit -m "feat: add governance pack schema validation"
```

### Task 2: Add normalized IR generation and deterministic OPA artifact output

**Files:**
- Create: `tldw_Server_API/app/core/MCP_unified/governance_packs/normalize.py`
- Create: `tldw_Server_API/app/core/MCP_unified/governance_packs/opa_bundle.py`
- Create: `tldw_Server_API/tests/MCP_unified/test_governance_pack_opa_bundle.py`
- Create: `tldw_Server_API/tests/MCP_unified/snapshots/governance_pack_minimal_bundle.json`
- Modify: `tldw_Server_API/app/core/MCP_unified/governance_packs/__init__.py`

**Step 1: Write the failing artifact-generation tests**

Add tests that expect:

- the same pack produces the same normalized IR and bundle digest on repeated runs
- changing one capability changes the bundle digest
- the generated bundle contains only normalized fields and never includes runtime secrets

Example test shape:

```python
def test_bundle_generation_is_deterministic():
    pack = load_governance_pack_fixture("minimal_researcher_pack")
    first = build_opa_bundle(pack)
    second = build_opa_bundle(pack)
    assert first.digest == second.digest
    assert first.bundle_json == second.bundle_json
```

**Step 2: Run the focused tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_governance_pack_opa_bundle.py -v
```

Expected: FAIL because normalization and bundle generation do not exist yet.

**Step 3: Write minimal normalization and bundle generation**

Implement:

- deterministic sort order for all pack objects
- canonical IR output
- generated `dist/opa` payload structure represented as JSON for now
- digest calculation over canonical serialized IR

Example code shape:

```python
def build_opa_bundle(pack: GovernancePack) -> GeneratedBundle:
    ir = normalize_governance_pack(pack)
    bundle_json = {"manifest": ir.manifest, "data": ir.data}
    digest = sha256(canonical_json(bundle_json).encode("utf-8")).hexdigest()
    return GeneratedBundle(ir=ir, bundle_json=bundle_json, digest=digest)
```

**Step 4: Re-run the focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_governance_pack_opa_bundle.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/MCP_unified/governance_packs/normalize.py \
  tldw_Server_API/app/core/MCP_unified/governance_packs/opa_bundle.py \
  tldw_Server_API/tests/MCP_unified/test_governance_pack_opa_bundle.py \
  tldw_Server_API/tests/MCP_unified/snapshots/governance_pack_minimal_bundle.json
git commit -m "feat: generate governance pack OPA artifacts"
```

### Task 3: Add pack provenance storage and immutable import materialization

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Create: `tldw_Server_API/app/services/mcp_hub_governance_pack_service.py`
- Create: `tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_governance_pack_migrations.py`
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py`
- Modify: `tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py`

**Step 1: Write the failing migration and import tests**

Add tests that expect:

- new tables exist for pack manifests and imported object provenance
- imported pack objects are recorded with stable source ids
- imported base objects are flagged immutable
- local overlays remain editable after import

Recommended new tables:

- `mcp_governance_packs`
- `mcp_governance_pack_objects`

Example test shape:

```python
def test_imported_profile_has_pack_provenance(sqlite_repo):
    result = import_governance_pack(sqlite_repo, fixture_pack)
    profile = sqlite_repo.get_permission_profile(result.profile_ids[0])
    assert profile["is_immutable"] == 1
    link = sqlite_repo.get_governance_pack_object("permission_profile", profile["id"])
    assert link["source_object_id"] == "researcher.profile"
```

**Step 2: Run the focused tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_governance_pack_migrations.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py -v
```

Expected: FAIL because the new tables, repo methods, and import service do not exist yet.

**Step 3: Add the minimal storage and import implementation**

Implement:

- SQLite and Postgres migration coverage for pack metadata and provenance tables
- repo methods to create/list packs and source-object links
- import service that materializes immutable permission profiles, approval policies, and assignment templates into existing MCP Hub tables

Example service shape:

```python
class GovernancePackImportResult(BaseModel):
    pack_id: int
    imported_object_counts: dict[str, int]
    blocked_objects: list[str]
```

**Step 4: Re-run the focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_governance_pack_migrations.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_governance_pack_migrations.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py
git commit -m "feat: import immutable governance packs into MCP Hub"
```

### Task 4: Expose dry-run preview and import APIs through MCP Hub management

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_service.py`
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py`

**Step 1: Write the failing API tests**

Add tests that expect:

- `POST /api/v1/mcp/hub/governance-packs/dry-run` returns manifest summary, digest, resolved capabilities, unresolved capabilities, warnings, and import verdict
- `POST /api/v1/mcp/hub/governance-packs/import` persists the pack after a successful dry-run
- immutable imported objects cannot be edited directly through normal update routes
- list/detail endpoints include pack provenance

Example response shape:

```python
assert response.json()["report"]["resolved_capabilities"] == [
    "tool.invoke.research",
    "filesystem.read",
]
```

**Step 2: Run the focused API tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py -v
```

Expected: FAIL because the routes and schemas do not exist yet.

**Step 3: Implement the minimal API surface**

Add:

- dry-run request/response schemas
- import request/response schemas
- list/detail read endpoints
- immutability guards in existing MCP Hub update/delete flows for pack-managed base objects

Example endpoint shape:

```python
@router.post("/mcp/hub/governance-packs/dry-run")
async def dry_run_governance_pack(...):
    return await service.dry_run(payload)
```

**Step 4: Re-run the focused API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py
git commit -m "feat: add MCP Hub governance pack APIs"
```

### Task 5: Add MCP Hub UI for pack preview, import, and provenance

**Files:**
- Create: `apps/packages/ui/src/components/Option/MCPHub/GovernancePacksTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/index.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx`

**Step 1: Write the failing UI tests**

Add tests that expect:

- a Governance Packs tab renders pack inventory
- a user can upload or paste a pack payload for dry-run preview
- the dry-run report displays resolved capabilities, unresolved capabilities, warnings, and verdict
- imported policy summaries show pack provenance badges or labels

Example test shape:

```tsx
it("renders dry-run compatibility findings before import", async () => {
  render(<GovernancePacksTab />)
  expect(await screen.findByText("Resolved capabilities")).toBeTruthy()
  expect(screen.getByText("tool.invoke.research")).toBeTruthy()
})
```

**Step 2: Run the focused UI tests to confirm they fail**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx \
  src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx
```

Expected: FAIL because the tab and provenance UI do not exist yet.

**Step 3: Implement the minimal UI**

Add:

- new MCP Hub tab for governance packs
- dry-run preview table/summary
- import action wired to the new APIs
- provenance display on persona policy summaries when imported pack metadata exists

Example component shape:

```tsx
<Descriptions column={1}>
  <Descriptions.Item label="Pack">{pack.title}</Descriptions.Item>
  <Descriptions.Item label="Resolved capabilities">{resolved.join(", ")}</Descriptions.Item>
  <Descriptions.Item label="Warnings">{warnings.join(", ") || "None"}</Descriptions.Item>
</Descriptions>
```

**Step 4: Re-run the focused UI tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx \
  src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/MCPHub/GovernancePacksTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx \
  apps/packages/ui/src/components/Option/MCPHub/index.tsx \
  apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx
git commit -m "feat: add MCP Hub governance pack UI"
```

### Task 6: Final verification, Bandit, and documentation touch-up

**Files:**
- Modify: `docs/plans/2026-03-13-opa-governance-packs-design.md` if implementation details drift
- Modify: touched API or UI docs if endpoint names or UX copy changes

**Step 1: Run the final focused backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_governance_pack_validation.py \
  tldw_Server_API/tests/MCP_unified/test_governance_pack_opa_bundle.py \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_governance_pack_migrations.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py -v
```

Expected: PASS.

**Step 2: Run the final focused UI verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx \
  src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx
```

Expected: PASS.

**Step 3: Run Bandit on the touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/MCP_unified/governance_packs \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  -f json -o /tmp/bandit_governance_packs.json
```

Expected:

- Bandit reports no new findings in touched code

**Step 4: Commit**

```bash
git add \
  docs/plans/2026-03-13-opa-governance-packs-design.md \
  docs/plans/2026-03-13-opa-governance-packs-implementation-plan.md
git commit -m "docs: finalize governance pack implementation plan"
```
