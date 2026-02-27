# Admin UI Improvement Review Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Produce a prioritized, evidence-backed improvement backlog for `admin-ui` across easy (1-2 days), medium, and large effort tiers covering code quality, UX/product polish, and release/process improvements.

**Architecture:** Execute a hybrid review pipeline: broad sweep first, then targeted deep dives on highest-impact hotspots. Store all findings in a single normalized backlog document with per-item action cards and a 30/60/90 sequence.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS, Vitest, ESLint, Bun, Markdown planning artifacts.

---

### Task 1: Create Review Artifact and Baseline Evidence

**Files:**
- Create: `Docs/Plans/2026-02-27-admin-ui-review-findings.md`
- Modify: `Docs/Plans/2026-02-27-admin-ui-review-implementation-plan.md`

**Step 1: Create findings document skeleton**

Add headings:
- Executive Summary
- Easy Wins (1-2 days)
- Medium Effort
- Large Effort
- Action Cards
- 30/60/90 Plan
- Evidence Log

**Step 2: Run lint baseline**

Run: `bun run --cwd admin-ui lint`
Expected: Command exits `0` and prints eslint execution.

**Step 3: Run full test baseline**

Run: `bun run --cwd admin-ui test`
Expected: All tests pass and counts are captured in findings Evidence Log.

**Step 4: Record baseline snapshot in findings file**

Document exact command results (pass/fail, counts, notable warnings).

**Step 5: Commit baseline artifact**

```bash
git add Docs/Plans/2026-02-27-admin-ui-review-findings.md Docs/Plans/2026-02-27-admin-ui-review-implementation-plan.md
git commit -m "docs: add admin-ui review baseline artifact"
```

### Task 2: Easy-Win Sweep (Breadth Pass)

**Files:**
- Modify: `Docs/Plans/2026-02-27-admin-ui-review-findings.md`
- Inspect: `admin-ui/app/**/*.tsx`
- Inspect: `admin-ui/components/**/*.tsx`
- Inspect: `admin-ui/lib/**/*.ts`

**Step 1: Identify low-risk consistency wins**

Run targeted scans:

```bash
rg -n "TODO|FIXME|console\\.|any\\b|as unknown as|@ts-ignore" admin-ui/app admin-ui/components admin-ui/lib
```

Expected: Candidate cleanup items with file/line references.

**Step 2: Review UX consistency primitives**

Inspect shared building blocks (`empty-state`, `table`, `pagination`, `confirm-dialog`, `status-indicator`) and list mismatch patterns across pages.

**Step 3: Review error/loading/empty states across pages**

Sample at least: `users`, `monitoring`, `incidents`, `jobs`, `data-ops`, `api-keys`.
Record missing or inconsistent patterns as easy wins.

**Step 4: Add easy wins to findings file**

For each item include:
- Problem
- Why it matters
- Tier = Easy
- First PR slice

**Step 5: Commit easy-win backlog slice**

```bash
git add Docs/Plans/2026-02-27-admin-ui-review-findings.md
git commit -m "docs: add admin-ui easy-win review findings"
```

### Task 3: Medium-Effort Deep Dive (Hotspots)

**Files:**
- Modify: `Docs/Plans/2026-02-27-admin-ui-review-findings.md`
- Inspect: `admin-ui/lib/api-client.ts`
- Inspect: `admin-ui/lib/http.ts`
- Inspect: `admin-ui/lib/use-paged-resource.ts`
- Inspect: `admin-ui/app/monitoring/page.tsx`
- Inspect: `admin-ui/app/users/page.tsx`
- Inspect: `admin-ui/app/*/__tests__/*.test.tsx`

**Step 1: Analyze data-fetching and state-management patterns**

Identify repeated fetch/error/refresh logic and opportunities for shared hooks/utilities.

**Step 2: Analyze test maintainability patterns**

Find test duplication, brittle selector use, and missing high-value integration seams.

**Step 3: Analyze release workflow friction**

Inspect:
- `admin-ui/package.json`
- `admin-ui/Release_Checklist.md`

Document medium-effort process improvements (test partitioning, smoke lanes, release gates).

**Step 4: Add medium-effort items to findings**

Each item must include dependencies and estimated regression risk.

**Step 5: Commit medium-effort slice**

```bash
git add Docs/Plans/2026-02-27-admin-ui-review-findings.md
git commit -m "docs: add admin-ui medium-effort review findings"
```

### Task 4: Large-Effort Strategic Initiatives

**Files:**
- Modify: `Docs/Plans/2026-02-27-admin-ui-review-findings.md`
- Inspect: `admin-ui/app/layout.tsx`
- Inspect: `admin-ui/components/Sidebar.tsx`
- Inspect: `admin-ui/lib/navigation.ts`
- Inspect: `admin-ui/lib/auth.ts`
- Inspect: `admin-ui/middleware.ts`

**Step 1: Map strategic architecture candidates**

Potential themes:
- Frontend domain modularization by admin capability
- Unified data layer/query conventions
- Session/auth hardening and cross-route guard model
- Scalable design-system consistency program

**Step 2: Define phased rollout for each large item**

For each initiative include:
- Phase 0: validation/pilot
- Phase 1: core migration
- Phase 2: cleanup and deprecation

**Step 3: Add large-effort cards with milestone checkpoints**

Include expected lead time and suggested owner profile.

**Step 4: Commit large-effort slice**

```bash
git add Docs/Plans/2026-02-27-admin-ui-review-findings.md
git commit -m "docs: add admin-ui large-effort strategy findings"
```

### Task 5: Final Prioritization and 30/60/90 Roadmap

**Files:**
- Modify: `Docs/Plans/2026-02-27-admin-ui-review-findings.md`

**Step 1: Score all backlog items**

Apply scoring fields per item:
- Impact (1-5)
- Confidence (1-5)
- Effort (Easy/Medium/Large)
- Risk (Low/Med/High)

**Step 2: Build ordered “Do First” list**

Select top 5 items with highest impact-to-effort ratio.

**Step 3: Build 30/60/90 timeline**

- 30: easy wins and stabilization
- 60: medium refactors/process improvements
- 90: strategic large initiatives (phase 0/1 kickoff)

**Step 4: Run final verification pass**

Run:

```bash
bun run --cwd admin-ui lint
bun run --cwd admin-ui test
```

Expected: both commands pass; evidence updated in file.

**Step 5: Final commit**

```bash
git add Docs/Plans/2026-02-27-admin-ui-review-findings.md
git commit -m "docs: finalize admin-ui tiered improvement review and roadmap"
```

### Task 6: Quality Gate and Handoff

**Files:**
- Modify: `Docs/Plans/2026-02-27-admin-ui-review-findings.md`

**Step 1: Self-review against design constraints**

Verify the final artifact contains:
- Easy/Medium/Large tiers
- Action cards for each recommendation
- 30/60/90 roadmap
- Evidence references

**Step 2: Verify no scope drift**

Confirm recommendations stay within:
- code quality/maintainability
- UX/product polish
- release/process quality

**Step 3: Add explicit implementation-ready next actions**

For top 3 items, include exact first PR boundary and success criteria.

**Step 4: Handoff for execution mode selection**

Prompt user to choose:
- Subagent-driven execution in current session (`@superpowers:subagent-driven-development`)
- Parallel session execution (`@superpowers:executing-plans`)

**Step 5: Commit handoff-ready artifact**

```bash
git add Docs/Plans/2026-02-27-admin-ui-review-findings.md
git commit -m "docs: prepare admin-ui improvement review handoff"
```

## Notes
- Keep recommendations DRY and avoid duplicate items across tiers.
- Prefer YAGNI framing: do not recommend abstractions without concrete payoff.
- Before any “done” claim, use `@superpowers:verification-before-completion` and capture command evidence in the findings document.
