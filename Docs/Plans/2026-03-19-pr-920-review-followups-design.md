# PR 920 Review Follow-Ups Design

**Goal:** Close the remaining open PR review threads for `#920` without widening the refactor beyond verified issues.

## Verified Open Items

1. `Helper_Scripts/docs/check_public_private_boundary.py` is still missing function docstrings.
2. `tldw_Server_API/tests/test_public_private_boundary.py` is still missing a module docstring.
3. The boundary checker only scans a narrow set of suffixes, so it skips relevant text assets such as `.example` env templates, `Dockerfile.*`, and `Caddyfile*` files under the configured scan targets.
4. The boundary checker uses raw substring matching, which is looser than necessary and can report false positives for denylist tokens embedded inside longer identifiers.
5. The currently open `usePlaygroundAttachments` review thread is stale from a code perspective: the branch already clears the native file input in a `finally` block. The extra work for option 2 is a regression test that locks that behavior in.

## Non-Goals

- No broad Playground behavior changes outside the already-landed file-input reset.
- No expansion of the OSS/private boundary policy beyond the existing denylist and scan targets.
- No unrelated cleanup in the large Playground refactor.

## Approach

### Boundary Checker

Keep the helper script small and explicit:

- Add docstrings to each helper and to `main()`.
- Introduce a single helper that decides whether a candidate file is scannable text.
- Treat the existing text suffixes as the baseline, then explicitly include:
  - `.example` files
  - files whose names start with `Dockerfile`
  - files whose names start with `Caddyfile`
- Replace raw `token in line` checks with regex-based token matching that:
  - still catches import/path-prefix references such as `@web/components/hosted/...`
  - avoids matching denylist entries when they are embedded inside larger identifiers or suffixed filenames

### Tests

Extend `tldw_Server_API/tests/test_public_private_boundary.py` instead of adding another boundary-check test module:

- Add a module docstring.
- Add focused unit tests that load the checker module directly and verify:
  - `_iter_candidate_files()` includes `.example`, `Dockerfile.*`, and `Caddyfile*` files
  - `_find_violations()` matches real denylist references while ignoring obvious larger-token false positives

### Playground Regression Coverage

Add a small hook-level test for `usePlaygroundAttachments` that verifies repeated selection of the same file still triggers the handler because the native input value is cleared after each change event.

## Verification

- `pytest` for the public/private boundary test module
- `vitest` for the new `usePlaygroundAttachments` regression test
- `bandit` on the touched Python paths
- Resolve or reply to the remaining GitHub review threads with exact status
