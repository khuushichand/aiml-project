# Governance Pack Distribution And Trust Design

Date: 2026-03-18
Status: Approved
Scope: file-based governance-pack distribution from local path and Git sources, with centralized trust policy, source provenance, prepared candidate pinning, and source-backed update discovery

## 1. Summary

Add a `Governance Pack Distribution Service` and a deployment-wide `Governance Pack Trust Store` so governance packs can be installed from local paths or trusted Git sources without changing MCP Hub's runtime-authority model.

Governance packs remain file-based artifacts. The new distribution layer governs how packs are acquired, validated, fingerprinted, verified, and recorded before the existing dry-run, import, and upgrade workflows execute. Source-backed installs persist provenance so operators can later check for updates, prepare a candidate from the same trusted source, and run the existing transactional upgrade/rebase flow against that exact pinned candidate.

The design is intentionally conservative:

- v1 sources are `local_path` and `git` only
- trust policy is deployment-wide, not per scope
- remote sources must pass trust checks before pack parsing
- Git-backed updates are manual `fetch + dry-run upgrade`, not auto-upgrade
- optional stronger verification uses local Git signature verification only
- local-path installs can be allowed, but only from configured allowlist roots

## 2. User-Approved Decisions

Validated during brainstorming:

1. Governance packs in v1 should be installable from `local path + Git ref`, not arbitrary URL archives.
2. Trust should default to `digest + trusted source policy`, with stronger `signature required` available as an optional mode.
3. Trust policy should live in a deployment-wide trust store.
4. A remotely sourced install should be identified by `pack_id + pack_version` plus source provenance, not by source provenance alone.
5. Source-backed update behavior should be `fetch + dry-run upgrade`, not notification-only or auto-upgrade.
6. Stronger verification in v1 should use Git commit/tag verification semantics, not a custom manifest-signing system.

## 3. Review-Driven Revisions

Pressure-testing the proposal against the current governance-pack code produced these corrections:

1. A Git source identity needs `repo + ref + subpath`, not just a repo URL, so a single repository can safely host multiple packs.
2. Source provenance must separate `source_commit_resolved` from `pack_content_digest`; commit identity and normalized pack content are related but not interchangeable.
3. Optional strong verification must mean local `git verify-commit` / `git verify-tag` against deployment-managed trusted keys. Host “verified” badges are not a portable trust contract.
4. Local-path installs need allowlisted base directories inside the deployment trust store or they become a general trust bypass.
5. Repo URLs must be canonicalized before trust matching so equivalent Git transport syntaxes do not bypass allowlists.
6. Prepared candidates must be durable enough to pin `repo + commit + subpath + pack digest` across dry-run and execute.
7. Source provenance must attach to each installed governance-pack row, including superseded versions, so upgrade lineage remains auditable.
8. Fetched pack traversal must reject symlink and path-escape cases that would walk outside the checkout or local allowlist root.
9. Source URLs containing embedded credentials must be rejected or sanitized before persistence and logs.
10. Update checks need a `source_drift` / `same_version_different_content` outcome distinct from “no update available.”

## 4. Current State In The Repo

The current governance-pack implementation already provides:

- file-based local pack loading from disk fixtures and directories
- normalized manifest/profile/approval/persona/assignment parsing
- dry-run compatibility reporting
- import into immutable MCP Hub base objects
- pack inventory and provenance for imported runtime objects
- transactional upgrade/rebase against active installed packs

Important current limitations:

- `GovernancePack` currently carries only `source_path`
- there is no first-class source provenance row for installs
- there is no deployment-wide governance-pack trust store
- there is no Git fetch/resolve path in the backend
- there is no prepared-candidate pinning for dry-run-to-execute
- update discovery does not exist for installed packs

This means the distribution/trust design must extend the existing governance-pack import and upgrade system rather than replace it.

## 5. Goals And Non-Goals

### 5.1 Goals

- Support governance-pack acquisition from local allowlisted paths and trusted Git sources.
- Enforce server-side trust policy before pack parsing, dry-run, import, or upgrade-from-source.
- Persist source provenance per governance-pack install row.
- Support prepared source candidates pinned by commit and normalized pack digest.
- Reuse the existing dry-run/import and upgrade/rebase workflows once a candidate has been resolved.
- Let operators check for updates on Git-backed installs and feed the fetched candidate into the existing upgrade planner.

### 5.2 Non-Goals

- Do not support arbitrary remote URL archives in v1.
- Do not implement OCI or registry publishing in v1.
- Do not rely on host-provider “verified” badges as a trust primitive.
- Do not provide auto-polling or auto-upgrade in v1.
- Do not add local-path update discovery in v1.
- Do not add pack-manifest custom signature formats in v1.

## 6. Proposed Architecture

### 6.1 Core Split

The architecture separates four concerns:

1. `pack content`
   - manifest
   - profiles
   - approvals
   - personas
   - assignments
   - generated OPA artifacts

2. `source resolution`
   - local path or Git acquisition
   - repo/ref/subpath normalization
   - content digest generation
   - optional signature verification

3. `trust enforcement`
   - deployment-wide allow/deny policy for local paths and Git sources
   - server-side validation before parsing or install

4. `install/upgrade authority`
   - existing MCP Hub dry-run/import/upgrade planner/executor
   - unchanged runtime authority model

### 6.2 New Services

Add:

- `McpHubGovernancePackDistributionService`
  - resolves local-path and Git-backed governance-pack sources
  - applies trust policy
  - computes source provenance and pack digests
  - prepares candidate records for later dry-run/execute

- `McpHubGovernancePackTrustService`
  - reads and validates the deployment-wide trust store
  - canonicalizes repo URLs and local paths for evaluation
  - evaluates source requests against allowlists and verification requirements

The existing `McpHubGovernancePackService` remains the authority for:

- pack schema validation
- dry-run compatibility
- import
- upgrade planning
- upgrade execution

### 6.3 Source Types

V1 supported source types:

- `local_path`
- `git`

Local-path installs remain explicit operator actions. Git-backed installs add fetch, provenance, and update discovery.

## 7. Trust Store

### 7.1 Deployment-Wide Trust Policy

The trust store should be a single deployment-wide config object containing:

- whether local-path installs are allowed
- allowed local-path root directories
- whether Git source installs are allowed
- allowed Git hosts
- allowed repo URLs or repo patterns
- allowed ref policies
  - commit-only
  - tags-only
  - branches allowed or denied
- whether local Git signature verification is required
- trusted key fingerprints or trust-root references for signature verification

### 7.2 Canonicalization Rules

Before trust matching:

- Git repo URLs are canonicalized to a normalized host/owner/repo identity
- embedded credentials are stripped or rejected
- local paths are resolved against the filesystem and checked against allowlisted roots
- Git subpaths are normalized and rejected if they escape the checkout root

Trust policy must be enforced server-side. UI hints are informative only.

## 8. Source Resolution

### 8.1 Local Path Resolution

Resolution flow:

1. normalize the requested local path
2. ensure it is inside an allowlisted root
3. load the pack from the target directory or subpath
4. compute the normalized pack digest
5. return a resolved source object and provenance summary

Local-path installs may store provenance, but they do not support update discovery in v1.

### 8.2 Git Resolution

Git resolution flow:

1. admin provides canonicalizable repo URL plus ref and optional subpath
2. trust service validates source type, repo, and ref policy
3. distribution service fetches the repo into an isolated checkout/cache
4. the requested ref resolves to an exact commit SHA
5. the requested subpath is validated to remain within the checkout
6. the governance pack is loaded from that subpath
7. the normalized pack digest is computed from pack content
8. if required, local Git verification is run for the resolved commit or tag
9. a resolved-source object is returned for dry-run/import/update planning

Fetched repos are read-only inputs. Pack-provided code is never executed.

## 9. Source Provenance

Each governance-pack install row should carry source provenance fields or a linked per-install provenance record containing:

- `source_type`
- `source_location`
- `source_ref_requested`
- `source_subpath`
- `source_commit_resolved`
- `pack_content_digest`
- `source_verified`
- `source_verification_mode`
- `source_fetched_at`
- `fetched_by`

Important distinctions:

- `source_commit_resolved` identifies the Git revision that was fetched
- `pack_content_digest` identifies the normalized pack content actually installed

This allows the system to answer:

- where did this pack come from?
- exactly which commit produced it?
- which subpath within the repo was used?
- was stronger verification required and satisfied?
- does the current fetched candidate match the originally installed content?

## 10. Prepared Candidates

Prepared candidates are needed so dry-run and execute can refer to the exact same fetched content.

Prepared candidate identity should include:

- source type
- canonical source location
- requested ref
- resolved commit
- source subpath
- pack content digest

Prepared candidates should be stored durably enough to survive the normal admin flow from:

1. fetch candidate
2. dry-run import or dry-run upgrade
3. execute import or execute upgrade

Execution must reject candidates if the prepared commit/digest pair no longer matches the referenced plan inputs.

## 11. Source-Backed Install And Update Flow

### 11.1 Install From Source

Install flow:

1. resolve local-path or Git source
2. enforce trust policy
3. parse and validate the governance pack
4. compute or retrieve prepared candidate identity
5. run existing dry-run compatibility reporting
6. if approved, run existing import logic
7. persist source provenance with the installed governance-pack row

### 11.2 Update Discovery

Git-backed installs gain manual update discovery:

1. operator triggers `check for updates`
2. distribution service re-resolves the stored Git source under current trust policy
3. candidate manifest and provenance are compared to the installed pack
4. result is classified as one of:
   - `newer_version_available`
   - `no_update`
   - `source_drift_same_version`
   - `pack_id_mismatch`
   - `trust_failure`
   - `fetch_failure`

### 11.3 Upgrade From Prepared Candidate

When a newer trusted candidate exists:

1. prepare candidate
2. pass candidate content into the existing governance-pack dry-run upgrade planner
3. show the normal upgrade conflicts/warnings plus source/trust/provenance changes
4. if approved, execute the existing transactional upgrade/rebase against that exact prepared candidate

Distribution is therefore a fetch-and-pin layer. Upgrade safety remains the responsibility of the existing planner/executor.

## 12. Failure Modes And Security Boundaries

Fail closed on:

- untrusted source type
- Git repo or ref not allowed by trust policy
- local path outside allowed roots
- source URL with embedded credentials that cannot be sanitized safely
- Git verification required but not satisfied
- invalid governance-pack content
- requested subpath escaping the checkout or local path root
- candidate `pack_id` mismatch
- execute using a stale or drifted prepared candidate

Security boundaries:

- trust evaluation happens on the server
- fetched repos are never executed
- generated OPA artifacts continue to be regenerated locally from schema
- local Git verification depends on deployment-managed trust roots
- provenance is persisted without secrets

## 13. Data Model

### 13.1 Install Provenance

The repo needs first-class source provenance per governance-pack install row. This can be implemented as either:

- additional columns on `mcp_governance_packs`, or
- a linked `mcp_governance_pack_sources` table keyed one-to-one or one-to-many by governance-pack row

Either way, provenance must attach to every installed pack row, including superseded versions.

### 13.2 Trust Store

The trust store should be persisted as a deployment-wide config document or dedicated table. It needs to support:

- local-path allowlist roots
- allowed Git hosts/repos/ref policies
- verification mode
- trusted key fingerprints or references

### 13.3 Prepared Candidates

Prepared candidates should be persisted in a lightweight record keyed by:

- source identity
- resolved commit
- subpath
- pack content digest

The stored record should also capture creation time, creator, and expiry or invalidation metadata if desired.

## 14. API And UI

### 14.1 API Additions

Add source-aware governance-pack endpoints for:

- trust policy read/update
- resolve and dry-run source install
- execute source install from a prepared candidate
- check updates for a Git-backed install
- prepare a Git-backed upgrade candidate

The existing dry-run/import and upgrade endpoints should remain reusable once given a prepared candidate or resolved pack document.

### 14.2 MCP Hub UI

Extend the existing Governance Packs UI to add:

- install from local path
- install from Git repo/ref/subpath
- provenance summary on installed pack detail
- trust status and verification status badges
- last update check timestamp
- check-for-updates action for Git-backed installs
- prepared candidate and source drift summaries in dry-run/upgrade modals

Default presentation should stay summary-first, with raw provenance expandable.

## 15. Testing Strategy

Test layers:

1. `trust policy`
   - allowed Git repo accepted
   - denied repo rejected
   - local path allowlist enforced
   - ref policy enforced
   - verification-required mode enforced

2. `source resolution`
   - repo normalization
   - credential sanitization
   - subpath validation
   - path/symlink escape rejection
   - deterministic pack digest generation

3. `install provenance`
   - source-backed import stores provenance
   - local-path import stores provenance
   - superseded rows retain their original provenance

4. `update flow`
   - newer trusted candidate discovered
   - equal/older version rejected as update
   - same-version different-content surfaced as source drift
   - trust failure blocks before upgrade planning

5. `upgrade integration`
   - prepared candidate pins commit/digest across dry-run and execute
   - source-backed upgrade reuses existing planner/executor
   - stale candidate execute is rejected

6. `UI/API`
   - source install request/response rendering
   - provenance visibility
   - update-check results
   - trust status display

## 16. V1 Scope

### 16.1 Included

- deployment-wide trust store
- local-path allowlist
- Git source resolution using `repo + ref + subpath`
- canonical repo normalization
- source URL credential sanitization
- per-install source provenance
- prepared candidate pinning by commit and pack digest
- manual update checks for Git-backed installs
- optional local Git signature verification mode
- MCP Hub API/UI support for source install, provenance, and update checks

### 16.2 Excluded

- arbitrary remote archive URLs
- OCI or registry publishing
- manifest-level custom signatures
- host-badge-based signature trust
- auto-polling or auto-upgrade
- local-path update discovery
- per-scope trust stores

## 17. Recommendation

Implement governance-pack distribution as a Git-friendly, file-based acquisition layer with centralized trust enforcement and durable source provenance, then route all install and update operations back through the existing governance-pack dry-run/import and upgrade/rebase workflows.

This preserves the architecture already established in MCP Hub:

- source trust controls what may be fetched
- governance-pack validation controls what may be imported
- MCP Hub remains the runtime authority

That is the smallest design that materially advances the original goal of deployment-agnostic, easy-to-share governance packs without turning v1 into a registry platform.
