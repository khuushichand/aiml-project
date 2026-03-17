# Default Production Onboarding Design

Date: 2026-03-15
Owner: Codex
Status: Approved

## Problem

The current first-run onboarding is split between newer profile-based docs and an older top-level quickstart that still defaults to local Python and WebUI dev flows.

That mismatch creates two concrete problems:
- first-time users are still funneled toward local/dev commands like `make quickstart-install` and `bun run dev`,
- the repository's default `make quickstart` behavior still launches a loopback-only local server instead of the safer Docker single-user deployment.

This makes the most visible onboarding path more fragile than it needs to be and increases the chance that users hit development-only issues such as Turbopack crashes, hot-reload instability, and local dependency drift.

## Goals

- Make the first recommended setup path a production-style deployment.
- Make `Docker single-user` the default onboarding profile for private/self-hosted users.
- Keep `Docker multi-user + Postgres` prominently visible as the recommended path for teams and public deployments.
- Relegate local Python and local WebUI flows to developer-only documentation.
- Change the default `make quickstart` contract so it aligns with the production-first docs.
- Add regression tests so onboarding entrypoints do not drift back toward dev-first behavior.

## Non-Goals

- Do not redesign the deployment stack itself.
- Do not change the Docker Compose architecture beyond onboarding/default-target behavior.
- Do not migrate the frontend to a different Next.js router or major version as part of this work.
- Do not remove local development workflows; they remain supported, but no longer lead the onboarding story.

## Chosen Direction

The chosen approach is:
- production-first docs,
- Docker single-user as the default quickstart,
- multi-user + Postgres called out as the next step for public/team deployments,
- local development moved into dedicated development documentation,
- Makefile default quickstart updated to match the docs.

This is intentionally broader than a README edit. The onboarding contract spans:
- the top-level `README.md`,
- the Getting Started index and profile pages,
- the public website quickstart surface,
- the `Makefile`,
- docs metadata and tests that protect the entrypoints.

## Default User Journey

The new default user journey should be:

1. Clone the repository.
2. Run `make quickstart` or `make quickstart-docker`.
3. Get a Docker single-user deployment with first-use auth bootstrapping.
4. Optionally add the WebUI with Docker if desired.
5. See a clearly labeled callout that `Docker multi-user + Postgres` is the right path for teams or internet-facing deployments.

The developer journey should be separate:

1. Read the development guide.
2. Use local Python, local Bun/Next.js dev servers, and dev-specific troubleshooting.

## Documentation Changes

### Top-level README

`README.md` becomes production-first:
- the first quickstart command is `make quickstart`,
- that command maps to Docker single-user,
- `make quickstart-docker-webui` is presented as an optional add-on,
- local Python and local `bun run dev` instructions move out of the main onboarding section and into a dedicated development section with links.

### Getting Started Index

`Docs/Getting_Started/README.md` should explicitly describe the ordering:
- `Docker single-user` is the default recommended profile,
- `Docker multi-user + Postgres` is the public/team deployment path,
- `Local single-user` is for local development and debugging.

### Public Website Quick Start

`Docs/Website/index.html` currently surfaces manual no-Docker and local WebUI development as peer quickstart options.

That page should be re-ordered so the first and strongest call to action is Docker single-user, followed by:
- Docker API + WebUI,
- Docker multi-user + Postgres callout,
- developer-only local/manual setup in a clearly labeled secondary section.

### Developer Docs

`apps/DEVELOPMENT.md` should absorb or link to:
- local API startup,
- local WebUI startup,
- Turbopack caveats,
- the `dev:webpack` fallback,
- the distinction between developer workflows and production/self-hosting flows.

`Docs/Getting_Started/Profile_Local_Single_User.md` should be reframed as a development-oriented profile rather than a first recommendation.

## Makefile Changes

The `Makefile` should reflect the same story as the docs.

Recommended target layout:
- `quickstart` becomes the default Docker single-user entrypoint,
- `quickstart-docker` remains the explicit Docker single-user target,
- the current local Python targets are renamed to clear dev-only names such as:
  - `quickstart-local-dev-prereqs`
  - `quickstart-local-dev-install`
  - `quickstart-local-dev`
- `quickstart-install` becomes a compatibility shim or deprecation bridge that points users toward the new local-dev target name rather than remaining a first-class onboarding command.

This preserves local workflows without letting them define the default contract.

## Test Strategy

This change needs automated regression coverage because onboarding drift has already happened once.

Coverage should include:
- README entrypoint tests that assert the production-first default wording and ordering,
- manifest tests that encode which profile is the default,
- Makefile tests that assert `quickstart` delegates to Docker single-user,
- existing hardening tests for the Docker targets,
- published-doc parity checks for any touched Getting Started pages.

## Risks And Mitigations

### Risk: Breaking existing user muscle memory

Some users may still expect `make quickstart-install` to start a local server.

Mitigation:
- keep a compatibility target,
- print a clear message,
- preserve the local workflow under an explicit dev-focused name.

### Risk: Incomplete docs migration

If only the README changes, users can still hit stale quickstart surfaces in the website or mirrored docs.

Mitigation:
- update all onboarding entrypoints in the same change,
- include tests and published mirror updates in the implementation plan.

### Risk: Overstating Docker single-user as fully public-production ready

Docker single-user is the right default for private self-hosting, but not the best path for public/team deployment.

Mitigation:
- add a prominent callout to `Docker multi-user + Postgres`,
- keep production hardening docs linked from the default flow.

## Next.js 17 Migration Assessment

There is no stable official Next.js 17 upgrade guide available yet. The current official upgrade path goes through Next.js 16, and unreleased behavior appears under canary channels rather than a supported major-version migration guide.

That means a "migrate to Next.js 17" estimate is inherently uncertain today.

For this repository, the risk factors are:
- the frontend is heavily invested in the Pages Router under `apps/tldw-frontend/pages/`,
- several modules depend on `next/router`,
- `apps/tldw-frontend/next.config.mjs` contains custom webpack and Turbopack aliasing for the shared UI and extension shims,
- the build currently relies on `typescript.ignoreBuildErrors`,
- the web app and extension share abstractions that already need custom compatibility shims.

Assessment:
- staying current within Next.js 16.x is low-to-medium effort,
- preparing for a future Next.js 17 major is medium-to-high uncertainty,
- an eventual upgrade should be treated as a separate focused project after the onboarding cleanup lands.

## Success Criteria

This design is successful when:
- a first-time reader of `README.md` is steered to Docker single-user by default,
- `make quickstart` provisions the Docker single-user path instead of a local reload server,
- developer-only setup is clearly separated from user/self-hosting setup,
- multi-user + Postgres remains visible as the recommended public/team deployment path,
- automated tests lock in the new default.
