## Stage 1: Audit Non-Threaded PR Feedback
**Goal**: Verify the remaining top-level PR #911 review summaries and outside-diff comments against the current branch.
**Success Criteria**: Each non-threaded review item is classified as `fix now`, `already fixed`, or `not taking with rationale`.
**Tests**: None
**Status**: Complete

## Stage 2: Implement Confirmed Fixes
**Goal**: Land any still-valid correctness or low-risk maintenance fixes from the non-threaded PR feedback.
**Success Criteria**: Confirmed issues are fixed with targeted regression coverage where warranted.
**Tests**: Focused pytest for touched modules; Bandit on touched Python scope.
**Status**: Complete

## Stage 3: Close PR Discussion Loop
**Goal**: Reply on the PR with the disposition of the remaining non-threaded review comments and push the follow-up branch state.
**Success Criteria**: PR has an explicit response for the remaining top-level review items and the worktree is clean.
**Tests**: `git status --short` clean after push
**Status**: In Progress

## Notes
- Fixed now:
  - removed dead code in `web_scraping_service.py`
  - stopped sending caller-owned DB handles through `asyncio.to_thread()` in `claims_review_metrics_scheduler.py`
  - kept `database_retrievers.py` adapters in sync after media DB attach and now propagate factory/configuration failures instead of silently swallowing them
  - added missing `@pytest.mark.unit` to `test_media_transcripts_upsert.py`
- Not taking in this slice:
  - the `process_code.py` unused dependency naming/type-cleanup suggestion was reverted after it proved low-value and introduced ambiguous endpoint-verification churn; this batch keeps the route on the known-good signature
