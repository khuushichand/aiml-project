## Stage 1: Audit table adapters and define shared contract
**Goal**: Identify shared normalize/validate logic and error handling differences.
**Success Criteria**: Clear plan for base class/mixin and exception behavior.
**Tests**: N/A (analysis).
**Status**: Complete

## Stage 2: Implement shared base and update adapters
**Goal**: Add a table adapter base and refactor HTML/data/markdown adapters to inherit.
**Success Criteria**: No duplicated normalize/validate logic; behavior unchanged.
**Tests**: Existing unit tests for file artifacts.
**Status**: Complete

## Stage 3: Sanity check updates
**Goal**: Review imports/types and ensure refactor keeps adapter behavior intact.
**Success Criteria**: Files load cleanly; no accidental behavior changes.
**Tests**: Optional `python -m pytest -m unit` targeted runs.
**Status**: Complete
