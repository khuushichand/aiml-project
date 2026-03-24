# tldw Homepage Setup Copy Refresh Design

**Date:** 2026-03-21

## Summary

This phase updates the live-style `tldwproject.com` homepage using the old homepage structure that is currently deployed, not the newer redesign. The scope is intentionally narrow: refresh versioning, setup instructions, and the most important onboarding copy to match the current repository truth.

## Goals

- Keep the old live homepage structure and styling.
- Update the displayed project version to the current release (`0.1.26`).
- Replace stale setup instructions with the current recommended quickstart paths.
- Point team/public deployments to the canonical multi-user + Postgres guide.
- Keep `VademHQ` out of scope for this pass.

## Non-Goals

- No redesign of the homepage layout or visual treatment.
- No broader messaging rewrite yet.
- No edits to `Docs/Website/vademhq/index.html`.

## Approved Scope

Update only these areas of the old homepage:

- hero version/status pill
- structured data version number
- quickstart/setup copy and commands
- setup-related docs links

## Copy Direction

- Default recommendation: `make quickstart`
- API-only Docker alternative: `make quickstart-docker`
- Local development/no-Docker path: `make quickstart-install`
- Preflight check mention: `make quickstart-prereqs`
- Team/shared deployment pointer: `Docs/Getting_Started/Profile_Docker_Multi_User_Postgres.md`

## Verification

Add or update regression tests so the homepage asserts:

- old live section structure remains intact
- version is `v0.1.26`
- quickstart includes `make quickstart`, `make quickstart-docker`, `make quickstart-install`, and `make quickstart-prereqs`
- stale `pip install tldw_server` and bare `docker compose up` homepage instructions are removed
