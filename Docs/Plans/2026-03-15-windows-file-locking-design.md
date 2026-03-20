# Windows File Locking Design

## Context

The `full-suite-os` GitHub Actions job runs on `windows-latest` and imports `tldw_Server_API.app.core.Infrastructure.distributed_lock`. That module currently imports `fcntl` at module load time, which raises `ModuleNotFoundError` on Windows before the test suite can run.

## Goal

Keep the existing `FileLock` and `acquire_migration_lock()` APIs unchanged while making file-based locking importable and functional on both POSIX and Windows runners.

## Chosen Approach

Use a small platform adapter inside `distributed_lock.py`:

- Prefer `fcntl.flock()` when `fcntl` is available.
- Fall back to `msvcrt.locking()` when running on Windows.
- Keep lock ownership and PID file semantics inside `FileLock`.

This keeps the change local, avoids new dependencies, and matches patterns already used elsewhere in the repository.

## Testing Strategy

- Replace the POSIX-only test import of `fcntl` with module-level lock contention through `FileLock`.
- Add regression coverage for the Windows fallback path by monkeypatching the module-level lock backend and asserting the helper calls `msvcrt.locking()` with the expected non-blocking modes.
- Run the targeted infrastructure test file and Bandit on the touched scope.

## Non-Goals

- No changes to Redis locking.
- No changes to other modules that already guard `fcntl` unless verification exposes another import-time failure in this path.
