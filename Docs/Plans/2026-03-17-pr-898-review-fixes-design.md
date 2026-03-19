# PR 898 Review Fixes Design

**Context**

PR #898 introduces integration work for consent endpoints, audit hash chaining, billing enforcement, fair-share job scheduling, and Stripe metering. The open review comments mix concrete correctness issues with broad refactor suggestions. This fix pass targets defects that are real in the current branch and defers architectural rewrites that are disproportionate to the PR scope.

**Validated Review Scope**

1. Mount the consent router in the normal FastAPI startup path so `/api/v1/consent/*` exists outside minimal test mode.
2. Resume the audit hash chain from the last persisted event during service initialization so tamper verification survives restarts.
3. Correct fair-share priority mapping so higher fair-share urgency yields a smaller numeric job priority, matching queue ordering semantics.
4. Make Stripe metering robust to partially migrated `usage_daily` schemas that do not yet have `bytes_in_total`.
5. Add the documented subscription lookup fallback for organization owners.
6. Cache overage policy parsing on `BillingEnforcer` and raise skipped-policy/fair-share failures to `warning`.
7. Tighten the consent endpoint implementation where the review feedback is low-risk and directly improves clarity.

**Deferred Comments**

1. Rewriting the jobs and Stripe metering modules to route all DB access through new DB_Management abstractions.
2. Replacing the synchronous consent manager with a new async persistence layer.
3. Converting the new consent endpoints to a broader schema refactor beyond what is required to resolve the PR defects.

These items may be worthwhile follow-up work, but they are larger architectural changes than this PR’s review-fix pass should absorb.

**Approach**

Use targeted tests first for each defect, then apply the minimum code change to make each test pass. Keep the fix set localized to the touched modules and add only the tests needed to prove the reported issues are resolved.

**Verification**

1. Run the impacted pytest files before editing to establish current failures and behavior.
2. Add or adjust tests for each defect before implementation.
3. Run the impacted pytest files after the changes.
4. Run Bandit on the touched backend paths before closing out.
