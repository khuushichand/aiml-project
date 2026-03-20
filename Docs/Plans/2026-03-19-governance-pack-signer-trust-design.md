# Governance Pack Signer Trust And Verification UX Design

Date: 2026-03-19
Status: Approved
Scope: repo-bound trusted signer policy, structured Git verification results, signer provenance, and operator-facing verification diagnostics for governance-pack Git sources

## 1. Summary

Extend the deployment-wide governance-pack trust store so it governs both:

- source trust
- trusted signer policy

The current distribution layer already supports trusted Git sources, optional Git signature verification, prepared candidates, provenance, and source-backed upgrades. The next slice makes signer trust explicit and operator-manageable by adding repo-bound trusted signer bindings, structured verification results, signer provenance on prepared candidates and installed packs, and clear diagnostics in MCP Hub APIs and UI.

The design remains intentionally conservative:

- Git/local verification tooling remains the backend
- `tldw` stores signer fingerprints and policy, not public keys
- signer trust is bound to canonical repo identities or simple repo-pattern rules
- the server must distinguish source allow, signature validity, and signer trust
- signature verification stays fail-closed when required
- v1 signer extraction is limited to the currently supported Git/GPG verification path rather than promising multi-backend signer support

## 2. User-Approved Decisions

Validated during brainstorming:

1. Trusted-key management in v1 should be a fingerprint registry, not a managed public-key store and not a pure “trust whatever local Git trusts” model.
2. Trusted signer fingerprints should be bindable to specific repos or repo patterns, not globally valid for every allowed repo.
3. If a later candidate is signed by a different still-trusted signer for the same repo, the system should warn but allow.
4. V1 should include CRUD plus verification diagnostics, not only a basic signer registry.
5. Signer trust should live inside the same deployment-wide governance-pack trust store as source policy.

## 3. Review-Driven Revisions

Pressure-testing the approved direction against the merged distribution/trust implementation produced these corrections:

1. The current trust store is still a flat policy document with `trusted_git_key_fingerprints`, so the next slice must provide an explicit schema migration and normalization path into structured signer bindings.
2. The current verification path in `mcp_hub_governance_pack_distribution_service.py` only returns a boolean and parses `VALIDSIG` fingerprints from raw Git output, which is insufficient for diagnostics-heavy UX. V1 needs a structured verification result object.
3. Provenance must distinguish what Git object was verified. A verified tag and a verified commit are not the same thing, so v1 needs `verified_object_type`.
4. The current fingerprint extraction path is effectively GPG/OpenPGP-specific. To keep diagnostics reliable, v1 should explicitly scope structured signer extraction to the currently supported Git/GPG flow and classify other backends as unsupported rather than pretending parity.
5. Repo-bound signer matching should reuse the canonical repo identity model already used for source trust. V1 should allow exact repo ids and simple prefix patterns only, not regex.
6. Existing provenance and UI fields such as `source_verified` and `source_verification_mode` must remain as backward-compatible summaries while richer verification fields are added alongside them.
7. Older installed packs may not have signer provenance, so update checks need an `unknown_previous_signer` warning state in addition to normal signer-rotation warnings.
8. Once signer bindings live in the deployment-wide trust store, trust-policy updates need a version or fingerprint guard to avoid silent admin overwrite races.

## 4. Current State In The Repo

The merged governance-pack distribution/trust slice already provides:

- deployment-wide trust policy storage
- local-path allowlist enforcement
- canonical Git repo normalization
- Git source resolution by repo, ref, and subpath
- optional Git signature verification enforcement
- prepared candidate persistence
- per-install source provenance fields
- MCP Hub UI for trust policy and source-backed installs

Important current limitations:

- trust policy stores only a flat `trusted_git_key_fingerprints` list
- `evaluate_git_source()` can only report source allow/deny plus whether verification is required
- `_verify_git_revision_sync()` returns only `True` or `False`
- prepared candidates and installed packs only persist `source_verified` and `source_verification_mode`
- MCP Hub UI can only display a coarse verified/unverified tag

This means the next slice must extend the existing trust store, provenance fields, and API/UI surfaces rather than introduce a parallel signer-verification subsystem.

## 5. Goals And Non-Goals

### 5.1 Goals

- Add a deployment-wide trusted signer registry inside the governance-pack trust store.
- Bind trusted signers to canonical repo identities or simple repo-pattern rules.
- Convert Git verification into a structured result with actionable diagnostics.
- Persist signer provenance on prepared candidates and installed governance-pack rows.
- Surface signer trust failures and warnings in prepare, check-for-updates, import, and upgrade flows.
- Preserve backward-compatible summary verification fields for existing API/UI consumers.
- Support signer rotation warnings when a new candidate is signed by a different still-trusted signer.

### 5.2 Non-Goals

- Do not manage public keys or keyrings in `tldw` in v1.
- Do not add manifest-signature formats.
- Do not implement expiry scheduling or staged signer-trust changes.
- Do not promise parity across all Git signature backends in v1.
- Do not add per-scope signer policy; signer trust remains deployment-wide.

## 6. Proposed Architecture

### 6.1 Trust Evaluation Layers

Governance-pack Git-source trust should become a three-layer decision:

1. `source allowed`
   - repo/ref source policy allows the candidate
2. `signature valid`
   - local Git verification succeeds for the verified object
3. `signer trusted for repo`
   - the extracted signer fingerprint is trusted for the canonical repo identity

Each layer must be reported separately. A valid signature from an untrusted signer is still a policy failure.

### 6.2 Integrated Trust Store

Keep a single deployment-wide governance-pack trust store. Extend it with:

- `trusted_signers`
  - structured signer bindings
- `policy_version` or equivalent optimistic-concurrency fingerprint

The existing source trust fields remain:

- `allow_local_path_sources`
- `allowed_local_roots`
- `allow_git_sources`
- `allowed_git_hosts`
- `allowed_git_repositories`
- `allowed_git_ref_kinds`
- `require_git_signature_verification`

The old `trusted_git_key_fingerprints` field should normalize into default signer bindings so existing policy documents remain valid.

### 6.3 Verification Backend Contract

Git/local verification remains the execution backend. `tldw` does not decide cryptographic validity itself.

The backend contract in v1 is:

- run local Git verification
- parse structured verification details from the currently supported Git/GPG output path
- evaluate the resulting signer fingerprint against the trust store

If the backend is unavailable, signature output is malformed, or the signature backend is unsupported, the result must classify that condition explicitly.

## 7. Signer Registry

### 7.1 Signer Binding Model

Each trusted signer binding should contain:

- `fingerprint`
- `display_name`
- `repo_bindings`
  - exact canonical repo ids and/or simple prefix patterns
- `status`
  - `active`
  - `revoked`
- optional metadata
  - `notes`
  - `created_at`
  - `created_by`

### 7.2 Matching Rules

Repo matching should reuse the canonical repo identity model from source trust.

V1 repo-binding grammar:

- exact canonical repo ids such as `github.com/example/research-packs`
- simple prefix patterns such as `github.com/example/`

V1 should not support regex or free-form matcher plugins.

### 7.3 Backward Compatibility

If an existing trust policy contains `trusted_git_key_fingerprints`, normalization should upconvert them into active signer bindings with global repo coverage inside the already-allowed source set.

This keeps current strict-verification deployments working while allowing administrators to tighten bindings later.

## 8. Structured Verification Result

### 8.1 Result Shape

The distribution layer should return a structured verification result object rather than only a boolean:

- `verified`
- `verification_mode`
- `verified_object_type`
  - `commit`
  - `tag`
- `signer_fingerprint`
- `signer_identity`
- `result_code`
- `warning_code`

### 8.2 Result Codes

Suggested result codes:

- `verification_not_required`
- `verified_and_trusted`
- `signature_required_but_missing`
- `signature_invalid`
- `signer_untrusted`
- `signer_not_allowed_for_repo`
- `verification_backend_unavailable`
- `unsupported_signature_backend`
- `signer_unknown`

Suggested warning codes:

- `signer_rotated_trusted`
- `unknown_previous_signer`
- `revoked_signer_on_historical_install`

### 8.3 Compatibility Summary Fields

Prepared candidates and installed packs should continue to expose:

- `source_verified`
- `source_verification_mode`

These fields remain coarse summaries derived from the structured result so current UI/API clients do not break.

## 9. Provenance

Prepared candidates and installed governance-pack rows should gain signer provenance fields:

- `signer_fingerprint`
- `signer_identity`
- `verified_object_type`
- `verification_result_code`
- `verification_warning_code`

Older installs may legitimately have:

- `source_verified`
- `source_verification_mode`
- no signer provenance

The UI and update-check logic must treat those as historical unknowns, not as proof that the signer did not change.

## 10. Update And Upgrade Semantics

### 10.1 Update Checks

When checking for updates on a Git-backed install:

- a new signer that is trusted for the same repo should not block the candidate
- the system should emit `signer_rotated_trusted`
- if the previous install lacks signer provenance, emit `unknown_previous_signer`

### 10.2 Revocation

If a signer becomes revoked after an install:

- existing installed pack history remains intact
- future prepare, import, and upgrade attempts signed by that signer block
- installed-pack detail should surface a historical warning rather than mutating the original provenance

### 10.3 Verified Object Type

Because the current source flow may verify a tag or a commit, provenance must persist what object type was actually verified. Otherwise, “verified by signer X” becomes ambiguous and misleading.

## 11. API And UI

### 11.1 API Changes

Extend trust policy request/response schemas to include:

- `trusted_signers`
- `policy_version` or `policy_fingerprint`

Extend source-prepare, update-check, prepared-candidate, and governance-pack detail responses to include:

- structured verification summary
- signer summary
- failure result code
- warning code when applicable

### 11.2 UI Changes

The MCP Hub trust-policy UI should gain a `Trusted Signers` section with:

- list signers
- add signer binding
- edit signer display name, repo bindings, and notes
- revoke signer

Source prepare and update flows should show:

- signer fingerprint
- signer identity
- verified object type
- exact failure reason when blocked
- trusted rotation warning when allowed

Installed-pack detail should show:

- current stored signer provenance
- verification result summary
- historical revoked-signer warning if applicable

Summary should remain compact by default, with detail expandable.

## 12. Failure Modes And Security Boundaries

Fail-closed when verification is required.

Failure modes:

- source allowed but signature missing
- signature present but invalid
- signature valid but signer fingerprint not extracted
- signature valid but signer untrusted
- signature valid but signer not allowed for repo
- verification backend unavailable
- unsupported signature backend under strict policy

Security boundaries:

- trust evaluation is server-side only
- free-form Git output must be parsed into structured fields
- host “verified” badges are not authoritative
- source URLs with embedded credentials remain forbidden
- signer trust is additive to source trust, not a replacement

## 13. Migration Strategy

Backward compatibility requirements:

- existing trust policy documents remain valid
- existing `trusted_git_key_fingerprints` normalize into structured signer bindings
- existing API clients keep working via summary verification fields
- historical installs without signer provenance are supported and rendered as `unknown`

Administrative safety:

- trust-policy updates should require a version or fingerprint match
- rejected writes must ask the client to re-read the latest policy

## 14. Testing Strategy

### 14.1 Trust Policy Evaluation

Test:

- active signer allowed for exact repo
- active signer denied for other repo
- prefix-bound signer allowed only within prefix
- revoked signer blocks
- legacy fingerprint list normalizes into signer bindings

### 14.2 Verification Parsing

Test:

- valid GPG-signed commit returns structured signer result
- valid GPG-signed tag returns `verified_object_type=tag`
- invalid signature returns `signature_invalid`
- missing `VALIDSIG` fingerprint under required signer trust returns `signer_unknown`
- unsupported backend returns `unsupported_signature_backend`

### 14.3 Source Workflows

Test:

- prepare candidate returns signer diagnostics
- install persists signer provenance
- update check emits `signer_rotated_trusted`
- update check emits `unknown_previous_signer` for historical installs without signer fields
- revoked signer blocks prepare/import/upgrade

### 14.4 UI/API

Test:

- trust-policy CRUD with signer bindings
- concurrency guard on trust-policy updates
- candidate and installed-pack views render signer diagnostics correctly
- historical installs without signer fields render safely

## 15. Refined V1 Boundary

Include:

- structured signer bindings inside the deployment-wide trust store
- repo-bound signer allow rules
- normalization from legacy fingerprint lists
- structured Git/GPG verification result parsing
- signer provenance on prepared candidates and installed packs
- signer-rotation and revoked-signer warnings
- trust-policy version/fingerprint guard
- MCP Hub UI/API updates for signer diagnostics

Exclude:

- public-key storage or keyring management
- expiry scheduling
- staged trust changes
- manifest signatures
- arbitrary regex repo bindings
- multi-backend signer support beyond the explicitly implemented Git/GPG path
