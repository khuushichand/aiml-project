# Flashcards And Quizzes PR 878 Local Hardening Design

Date: 2026-03-13  
Status: Approved

## Summary

This design defines a local hardening pass for PR `#878`, which already completes the planned flashcards/quizzes roadmap. The purpose of this pass is not to add new feature scope. It is to raise confidence that the merged roadmap slices do not regress baseline flashcards and quizzes behavior.

The hardening pass should favor broad regression coverage over speculative refactors:

- baseline backend contract verification
- baseline frontend regression verification
- docs and help-link hygiene checks
- slower UI verification using existing Playwright coverage where practical and manual walkthroughs where necessary
- immediate in-branch fixes for real regressions

## Current Context

PR `#878` now spans multiple connected flashcards/quizzes slices:

- structured Q&A preview import
- whole-deck document mode and bulk editing
- first-class image support with APKG image round-trip
- image occlusion authoring
- scheduler/next-card upgrade
- card-level study assistant and quiz remediation

This makes local hardening necessary because the risk is no longer isolated to one surface. The likely failure mode is interaction regressions between old and new paths rather than a single obvious broken feature.

## Product Framing

This pass should be treated as release hardening, not roadmap expansion.

Explicit non-scope:

- new flashcards/quizzes features
- broad repo-wide CI/workflow changes
- speculative architecture cleanup with no observed regression signal
- new E2E frameworks or heavy new test infrastructure

The only acceptable code changes are:

- regression fixes found during verification
- small test improvements required to capture the verified behavior
- doc/help-link corrections if verification shows drift

## Recommended Approach

Use a risk-based verification matrix that starts with backend and frontend contract tests, then moves into slower UI verification for the highest-risk journeys introduced or touched by the PR.

Recommended approach:

1. Run broad baseline backend coverage first.
2. Run broad baseline frontend coverage second.
3. Run docs and link-hygiene verification third.
4. Run slower UI verification fourth.
5. Fix real regressions immediately and rerun the smallest proving slice before continuing.

This is preferable to either:

- running every test in the repo without prioritization
- only smoke-testing the new features

The first is too noisy and inefficient. The second misses exactly the baseline regressions this pass is supposed to catch.

## Verification Scope

The hardening pass should cover four layers.

### 1. Backend Baseline Regression

The backend tier should verify both legacy and new flashcards/quizzes behavior:

- flashcards CRUD/list/manage/review/import/export routes
- quizzes CRUD/generate/attempt/results routes
- scheduler state and next-card selection
- structured import parsing
- study assistant persistence and context
- APKG import/export round-trip behavior
- image asset storage/reference behavior
- quiz source resolution for remediation and flashcards-driven quiz generation

### 2. Frontend Baseline Regression

The frontend tier should cover the main shipped surfaces:

- flashcards `Review`
- flashcards `Manage`
- flashcards `Import/Export/Transfer`
- image insert/edit/render flows
- image occlusion authoring
- flashcard assistant panel
- quiz `Manage`
- quiz `Take`
- quiz `Generate`
- quiz `Results`
- quiz remediation handoff to flashcards
- service/handoff/cache utilities that sit underneath those routes

The frontend command set should run from the UI package itself, or explicitly point Vitest at the UI package config. It should also include the shipped quiz baseline suites for `Create`, `Generate`, `Manage`, `Take`, and `Results`, rather than only remediation-oriented result tests.

### 3. Docs And Link Hygiene

The docs tier should confirm:

- flashcards help links still point to the correct guide
- the guide content reflects current shipped behavior
- a flashcards-specific guide discoverability guard passes

This is small, but it matters because several roadmap slices added new user-facing flows without a separate docs release track. The hardening pass should prefer targeted flashcards guide checks over the entire docs test directory so unrelated guide failures do not drown out the signal.

### 4. Slower UI Verification

This tier should use existing Playwright surfaces where practical and manual walkthroughs where coverage does not already exist.

Priority flows:

- structured Q&A preview and approval
- whole-deck document mode editing and save behavior
- image-backed card create/edit/review
- image occlusion authoring happy path
- scheduler-backed review next-card loop
- review assistant interactions
- quiz results remediation flow
- quiz-to-flashcards and flashcards-to-quiz handoffs

The slow tier should be explicit about which harness owns which check:

- the Next.js smoke gate should be used for the shared `/flashcards` route when the local web harness is available
- the extension quiz UX spec should be used for quiz workspace coverage when real-server config and host permissions are available
- remaining gaps should fall back to documented manual walkthroughs rather than ad hoc partial automation

Each automated command should list its local prerequisites up front. If a prerequisite is missing, record the skip reason and switch only that path to manual verification instead of silently dropping the coverage.

This is bounded to happy-path regression plus one or two critical error checks per surface. It is not a mandate to author a large new end-to-end matrix.

## Slower UI Verification Rules

The slower verification tier should be auditable.

Each manually or Playwright-verified flow should record:

- route or surface under test
- starting setup/data state
- action taken
- expected result
- actual result
- whether code changed because of the check

That record can stay in the execution notes or final summary; it does not require a new permanent artifact unless the findings justify one.

## Fix Policy

When the pass finds a real regression:

1. Fix it immediately in the branch.
2. Rerun the smallest failing test or proving flow first.
3. Rerun the containing verification tier.
4. Continue only when that tier is green.

This keeps the hardening pass disciplined and prevents hidden regressions from accumulating under a large verification umbrella.

## Known Boundary On CI

At the time of approval, GitHub did not report a failing GitHub Actions run for PR `#878`. The visible PR status only showed a passing `CodeRabbit` check. Because of that, this hardening pass focuses on local verification depth and local fixes, not CI workflow remediation.

If a later GitHub Actions failure appears, it should be handled as a separate follow-up using the CI debugging workflow.

## Success Criteria

This hardening pass is successful if it:

- exercises baseline flashcards/quizzes regression coverage across backend and frontend
- verifies the major new `#878` flows beyond unit-level assertions
- catches and fixes real regressions immediately
- leaves the branch with a clean verification summary and no known unfixed high-signal issues in the flashcards/quizzes surfaces
