# Watchlists Help Release Checklist (2026-02-18)

## Scope

Use this checklist for releases that touch `/watchlists` UX, terminology, onboarding, or docs links.

## Automated Checks

- [ ] `bunx vitest run src/components/Option/Watchlists/shared/__tests__/help-docs.test.ts`
- [ ] `bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx`
- [ ] Watchlists guided-tour tests pass in the Watchlists targeted suite.

## Manual UI Checks

- [ ] Header shows persistent `Watchlists docs` link.
- [ ] Header shows contextual `Learn more: <tab>` link for the active tab.
- [ ] Beta banner includes docs + issue-report links.
- [ ] Beta banner remains dismissible and stays dismissed after reload.

## Guided Tour Checks

- [ ] `Start guided tour` opens Sources -> Jobs -> Runs -> Items -> Outputs sequence.
- [ ] `Skip` persists dismissed state.
- [ ] In-progress tour shows `Resume guided tour` after reload.
- [ ] Finishing tour shows completion notice and Activity/Articles quick actions.

## Copy/Terminology Drift Checks

- [ ] Tab names in UI match guide/help labels.
- [ ] Error remediation copy still matches run/source/job behaviors.
- [ ] Help links resolve to valid https targets and relevant docs sections.

## Sign-off

- [ ] Frontend owner sign-off
- [ ] Docs owner sign-off
- [ ] QA sign-off
