## Stage 1: Runtime Gating & Error Semantics
**Goal**: Make Firecracker availability and error mapping match the PRD.
**Success Criteria**:
- Requests for Firecracker when disabled/unavailable return 503 `runtime_unavailable` with `details.runtime="firecracker"` and `suggested=["docker"]`.
- Invalid kernel/rootfs paths map to 400 with clear field errors.
- Discovery only advertises Firecracker when real mode is enabled and preflight passes.
**Tests**:
- Unit: preflight gating (OS/KVM/binaries) and 503 mapping.
- Unit: invalid kernel/rootfs maps to 400.
**Status**: Complete

## Stage 2: Workspace Mount & Exit/Log Semantics
**Goal**: Align workspace, log format, and exit schema with the PRD.
**Success Criteria**:
- Workspace supports virtiofs and a fallback (ext4 block device) or explicit documented hard requirement.
- `run.log` uses ISO8601 prefix per line and fsync/flush behavior.
- `.sandbox_status.json` includes required schema (with optional `signal`) and is validated on read.
**Tests**:
- Unit: exit JSON schema validation; log format; artifact capture via glob.
- Unit: virtiofs present vs fallback drive behavior (or hard failure if no fallback).
**Status**: Not Started

## Stage 3: Lifecycle Robustness (Timeout/Cancel/Cleanup)
**Goal**: Ensure reliable termination and cleanup behavior.
**Success Criteria**:
- Timeout/cancel follows SIGTERM -> SIGKILL escalation.
- End frame is emitted exactly once on all paths.
- Firecracker + virtiofsd cleanup is deterministic; per-run dirs removed.
**Tests**:
- Unit: timeout transition -> timed_out.
- Unit: cancel transition -> killed.
**Status**: Not Started

## Stage 4: Tests + Documentation Completion
**Goal**: Add targeted tests and finish docs for Firecracker MVP.
**Success Criteria**:
- Firecracker unit tests cover gating, log/exit semantics, workspace, and error mapping.
- Optional Linux integration test gated by env.
- Docs include kernel/rootfs prep details and limitations.
**Tests**:
- Integration (Linux only, opt-in): boot minimal VM, run `echo`, verify log streaming and artifacts.
**Status**: Not Started
