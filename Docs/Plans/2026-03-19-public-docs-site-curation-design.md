# Public Docs Site Curation Design

## Goal

Make the public docs site build successfully with `mkdocs build --strict -f Docs/mkdocs.yml` without weakening the new OSS/private boundary.

## Recommended Approach

Use a curated-minimal nav cleanup:

1. Trim `Docs/mkdocs.yml` so the nav only points to files that actually exist under `Docs/Published`.
2. Fix broken links inside the retained public pages.
3. Fix the known anchor warning in the curated embeddings documentation.

This is the fastest, lowest-risk path to a green strict build. It also matches the repo's current published-docs model better than trying to restore a much larger legacy docs surface.

## Scope

The fix stays inside the public docs pipeline:

- `Docs/mkdocs.yml`
- curated docs under `Docs/Published`
- existing boundary enforcement

It does not try to recreate the old full docs tree or restore hosted/commercial material into the public site.

## Concrete Change Set

### 1. Trim the public nav

Update `Docs/mkdocs.yml` so every nav entry targets a file that exists in `Docs/Published`.

Keep top-level sections only where there is enough curated content to support them.

### 2. Fix broken links inside retained curated pages

The current strict-build failures show two primary hotspots:

- `Docs/Published/Getting_Started/README.md`
- `Docs/Published/Overview/Feature_Status.md`

For those pages:

- retarget links to existing curated pages where possible
- otherwise replace them with stable repo links or plain text where the target is intentionally outside the public curated site

### 3. Fix the bad anchor

Correct the `Monitoring & Operations` table-of-contents link in:

- `Docs/Published/Code_Documentation/Embeddings-Documentation.md`

so strict mode stops flagging that page.

## Keep vs Drop Rules

Keep:

- `Home`
- `Overview`
- `Getting Started`
- `Deployment`
- `Environment Variables`
- `Monitoring` only if its linked curated pages exist
- selected `API`, `Code`, and `User Guides` pages that are actually present in `Docs/Published`

Drop for now:

- nav groups whose index or most children are missing
- stale leaves that point outside the curated docs set
- anything that would require reconstructing large parts of the old docs tree

Rule:

- if the page exists and is public-safe, keep it
- if it is missing, stale, or outside the curated public surface, remove it from nav instead of inventing filler

## Validation

Use a tight verification loop:

- `python Helper_Scripts/docs/check_public_private_boundary.py`
- `mkdocs build --strict -f Docs/mkdocs.yml`

Success means:

- no missing nav targets
- no broken links in retained curated pages
- no anchor warnings in retained pages
- boundary checker still passes

## Non-Goals

- rebuilding the full historical docs site
- restoring missing legacy docs into `Docs/Published`
- changing the OSS/private boundary
