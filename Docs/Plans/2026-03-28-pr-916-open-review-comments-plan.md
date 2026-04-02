# PR 916 Open Review Comments Plan

## Stage 1: Validate Outstanding Review Scope
**Goal**: Confirm which PR #916 comments are still actionable against the current branch head.
**Success Criteria**: Live GitHub review threads and summary comments are checked against local files; outdated-only findings are excluded from implementation scope unless still reproducible.
**Tests**: `gh api graphql` review-thread query; targeted file inspection with `sed`/`rg`
**Status**: Complete

## Stage 2: Apply Infra and Workflow Fixes
**Goal**: Fix the still-valid workflow and Docker review findings in the PR branch.
**Success Criteria**: Review feedback is revalidated before implementation; `frontend-required.yml` is only changed if the family-guardrails gate is not already covered; `Dockerfile.webui` uses Bun consistently, keeps the API base URL wiring intact, and provides runtime env defaults; `docker-compose.host-storage.yml` uses healthy-service dependencies without regressing the existing Postgres image choice.
**Tests**: `python - <<'PY' ... yaml.safe_load(...)`; `docker compose -f Dockerfiles/docker-compose.host-storage.yml config`; `docker compose -f Dockerfiles/docker-compose.webui.yml config`
**Status**: Complete

## Stage 3: Clean Up Broken Documentation Links
**Goal**: Replace machine-local absolute Markdown links introduced in the audio setup guides.
**Success Criteria**: No `/Users/macbook-dev/Documents/GitHub/tldw_server2` links remain in the touched docs; all replacement links are repo-relative from the current files.
**Tests**: `rg -n '/Users/macbook-dev/Documents/GitHub/tldw_server2' Docs/Getting_Started/First_Time_Audio_Setup_CPU.md Docs/Getting_Started/First_Time_Audio_Setup_GPU_Accelerated.md`
**Status**: Complete

## Stage 4: Verify Touched Scope and Security
**Goal**: Run targeted verification and the required Bandit scan before reporting completion.
**Success Criteria**: File-level checks pass, the worktree diff contains only the PR #916 follow-up fixes plus plan/test artifacts, and Bandit passes on the touched Python production scope.
**Tests**: Targeted workflow/compose checks; `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r <touched_paths> -f json -o /tmp/bandit_pr916_open_review_comments.json`
**Status**: Complete

## Stage 5: Resolve Remaining PR Threads
**Goal**: Close the remaining unresolved PR #916 review threads with either code fixes or factual replies.
**Success Criteria**: Live unresolved threads are reduced to zero; stale findings are resolved with code references, and incorrect findings are resolved with supporting evidence.
**Tests**: `gh api graphql` unresolved-thread query; targeted local test evidence linked in replies
**Status**: In Progress
