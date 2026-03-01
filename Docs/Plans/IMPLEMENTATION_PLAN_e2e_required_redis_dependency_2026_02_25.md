## Stage 1: Capture Contract Gap
**Goal**: Add a CI contract test that fails when `e2e-required` lacks Redis service/environment wiring.
**Success Criteria**: New test fails against current workflow and clearly identifies missing Redis contract.
**Tests**: `python -m pytest -q tldw_Server_API/tests/CI/test_e2e_required_redis_contract.py`
**Status**: Complete

## Stage 2: Implement Workflow Fix
**Goal**: Update `.github/workflows/e2e-required.yml` to include Redis service and deterministic Redis env values for e2e execution.
**Success Criteria**: New contract test passes and existing required workflow contract tests remain green.
**Tests**: `python -m pytest -q tldw_Server_API/tests/CI`
**Status**: Complete

## Stage 3: Validate and Ship
**Goal**: Verify touched-scope security gate and publish branch updates.
**Success Criteria**: Bandit on touched scope has no new findings in changed lines; branch is committed/pushed.
**Tests**: `python -m bandit -r .github/workflows tldw_Server_API/tests/CI -f json -o /tmp/bandit_e2e_required_redis.json`
**Status**: In Progress
