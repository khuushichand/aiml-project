# Remove Public Hosted Docs Design

## Goal

Remove the remaining hosted SaaS deployment docs from the public `tldw_server` repo now that canonical copies exist in the private hosted repo, and tighten enforcement so those files cannot quietly return to the public published surface.

## Recommended Approach

Use a hard-removal extraction:

1. Delete the hosted deployment docs from `Docs/Published/Deployment`.
2. Remove the hosted-doc exceptions from the public/private boundary checker.
3. Extend the public boundary tests to assert those files do not exist in the curated public tree.
4. Re-run the boundary checker, boundary pytest, and strict MkDocs build.

This is the cleanest boundary. It avoids public stubs, redirect placeholders, or hidden hosted filenames lingering in the public docs tree.

## Scope

The change is intentionally narrow:

- `Docs/Published/Deployment`
- `Helper_Scripts/docs/check_public_private_boundary.py`
- `tldw_Server_API/tests/test_public_private_boundary.py`

It does not expand the public docs site, restore old docs, or change the private repo contents.

## Concrete Changes

### 1. Delete hosted deployment docs from the public repo

Remove:

- `Docs/Published/Deployment/Hosted_SaaS_Profile.md`
- `Docs/Published/Deployment/Hosted_Staging_Runbook.md`
- `Docs/Published/Deployment/Hosted_Production_Runbook.md`

The canonical copies already exist in the private repo:

- `/Users/macbook-dev/Documents/GitHub/tldw-hosted/docs/Hosted_SaaS_Profile.md`
- `/Users/macbook-dev/Documents/GitHub/tldw-hosted/docs/Hosted_Staging_Runbook.md`
- `/Users/macbook-dev/Documents/GitHub/tldw-hosted/docs/Hosted_Production_Runbook.md`

### 2. Tighten the boundary checker

Update `Helper_Scripts/docs/check_public_private_boundary.py` so it no longer skips those hosted public doc paths.

Important refinement:

- keep the checker scoped to public docs/runtime surfaces
- do not broaden it to scan planning/governance docs like `Docs/Plans` or the policy doc, because those legitimately mention the private filenames

### 3. Extend the public boundary tests

Add a test that explicitly asserts the hosted deployment docs are absent from `Docs/Published/Deployment`.

Keep the existing denylist expectations so references to those filenames in public publish surfaces still fail.

### 4. Verify the public docs build still passes

Because the nav is already trimmed away from these files, deleting them should not affect the now-green strict MkDocs build.

## Risks And Mitigations

### Risk: accidental reintroduction through public docs refresh

Mitigation:

- remove checker skip exceptions
- keep denylist scanning on public publish/runtime surfaces

### Risk: hidden references elsewhere in the public docs tree

Mitigation:

- verify with boundary checker
- verify with strict MkDocs build
- keep task narrow, with no nav expansion or unrelated docs edits

### Risk: weakening the boundary with public stubs

Mitigation:

- do not add redirect stubs or placeholder files
- perform a hard delete only

## Validation

Run:

- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -v`
- `source .venv/bin/activate && python Helper_Scripts/docs/check_public_private_boundary.py`
- `source .venv/bin/activate && mkdocs build --strict -f Docs/mkdocs.yml`

Success means:

- hosted deployment docs are absent from the public curated tree
- checker passes without hosted-doc skip exceptions
- strict MkDocs build still passes

## Non-Goals

- adding public redirect stubs
- reworking the docs nav
- modifying the private hosted docs
- broadening the checker to planning/policy docs
