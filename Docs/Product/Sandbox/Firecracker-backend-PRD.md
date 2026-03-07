# Firecracker Backend (MVP) — Implementation Plan

## Objective

Deliver a real Firecracker backend with net=off, microVM lifecycle, host-shared workspace, artifact capture, exit-code/logging via workspace files, and image digest reporting. Keep the existing scaffold as the default and gate real execution behind feature flags.

## Current Status (as of 2026-01-24)

Stage-level progress against this PRD:

- Stage 0 (Feature flags & gating): **Done**
  - Real execution is gated by `SANDBOX_FIRECRACKER_ENABLE_REAL`.
  - Preflight checks exist (Linux, `/dev/kvm`, `firecracker`, `virtiofsd` when enabled).
  - When disabled/unavailable, Firecracker requests return 503 `runtime_unavailable` with `suggested=["docker"]`.
- Stage 1 (Kernel/rootfs + digest): **Mostly done**
  - Kernel/rootfs paths are resolved from env and/or `spec.base_image` path.
  - Rootfs SHA‑256 digest is computed and returned as `image_digest`.
  - Invalid kernel/rootfs paths map to 400 with field-level details.
  - **Gap**: Kernel digest not captured.
- Stage 2 (Workspace & devices): **Partial**
  - Per‑run workdir and host workspace are created.
  - Inline files and `.env` are written to workspace; `entry.sh` is created.
  - **Gap**: No ext4 workspace fallback; virtiofs is required and disabling it currently fails.
- Stage 3 (MicroVM boot, net=off): **Done**
  - Firecracker API socket, machine config, boot source, rootfs drive, and virtiofs config are set.
  - No network devices are configured (net=off).
- Stage 4 (Command execution & exit): **Partial**
  - `entry.sh` executes the command and writes `run.log` + `.sandbox_status.json`.
  - **Gaps**:
    - `run.log` does not prepend timestamps or fsync per line.
    - `.sandbox_status.json` lacks the optional `signal` field and is not schema‑validated.
    - No rc.local/systemd fallback if `init=/workspace/entry.sh` cannot run.
- Stage 5 (Log streaming & metrics): **Partial**
  - `run.log` is tailed via virtiofs for stdout streaming.
  - **Gaps**: No non‑virtiofs fallback, no cgroup metrics, no FIFO/metrics parsing.
- Stage 6 (Timeouts, cancel, cleanup): **Partial**
  - Timeout enforcement exists; Firecracker and virtiofsd are terminated; run dir cleaned up.
  - **Gaps**: No SIGTERM→SIGKILL escalation sequence, no explicit cancel path, end‑frame “exactly once” guarantees not enforced.
- Stage 7 (Service wiring & discovery): **Done**
  - `runtime_version` is populated; service wiring calls the runner in foreground/background.
  - 503 `runtime_unavailable` behavior is enforced when Firecracker is disabled/unavailable.
- Stage 8 (Tests & fake mode): **Partial**
  - Fake mode exists; Firecracker‑specific tests have not been added.
- Stage 9 (Docs & examples): **Partial**
  - Firecracker host checklist added and linked; API doc now references it.
  - **Gap**: remaining docs updates (kernel/rootfs prep details, limitations) not fully written.

## Scope

- Files:
  - `tldw_Server_API/app/core/Sandbox/runners/firecracker_runner.py`
  - `tldw_Server_API/app/core/Sandbox/service.py`
- Non-goals: full guest agent, cross‑platform support, rich egress controls, VM snapshots.

## Preconditions & Config

- Flags/env:
  - `SANDBOX_FIRECRACKER_ENABLE_REAL=0|1` (default 0)
  - `SANDBOX_FC_BIN` (path to `firecracker`)
  - `SANDBOX_FC_JAILER` (optional; for later hardening)
  - `SANDBOX_FC_KERNEL_PATH` (path to kernel, e.g., vmlinux)
  - `SANDBOX_FC_ROOTFS_PATH` (path to rootfs image; or use `spec.base_image` when provided)
  - `SANDBOX_FC_USE_VIRTIOFS=true`
  - `SANDBOX_FC_BOOT_ARGS="console=ttyS0 reboot=k panic=1 pci=off"`
  - `SANDBOX_FC_LOG_DIR` (optional)
  - `TLDW_SANDBOX_FIRECRACKER_FAKE_EXEC=1` (tests)
- Preflight checks (refuse real execution if any fail):
  - Linux only, `/dev/kvm` present, `firecracker` executable available.
  - If virtiofs enabled, `virtiofsd` available.

## Architecture Overview

- Guest I/O: Do not rely on Firecracker FIFOs for guest logs. Use host-shared `/workspace` with:
  - `run.log` (log tail for WS streaming when virtiofs is available)
  - `.sandbox_status.json` (exit code + reason)
- Storage layout:
  - Mount rootfs read-only.
  - Attach a per‑run writable block device for `/workspace` (ext4 file).
  - Prefer virtiofs for live sharing; fall back to writable block device without live streaming.
- Net-off: Omit `network-interfaces` entirely (no NICs).
- Control plane: Configure microVM via the REST API socket (machine-config, boot-source, drives, virtiofs).
- Cleanup: Kill Firecracker and helpers, unmount/detach drives, delete per‑run directories and devices.

## Phased Stages

### Stage 0: Feature Flags & Gating

- Implement `enable_real` gate; refuse real Firecracker when preflight fails (503 `runtime_unavailable` with `details.runtime="firecracker"` and `suggested=["docker"]`).
- Discovery: advertise Firecracker available only when enabled and preflight passes; do not advertise `egress_allowlist_supported` yet.

### Stage 1: Kernel/Rootfs Resolution & Digest

- Resolve `kernel_path` and `rootfs_path` from env or `spec.base_image` (path).
- Compute `image_digest` (SHA‑256) for rootfs; optionally compute kernel digest for diagnostics.
- Errors: missing/invalid → 400 with clear field names and guidance.

### Stage 2: Per‑Run Workspace & Devices

- Create a per‑run workdir with unique sockets/FIFOs.
- Writable workspace:
  - Preferred: virtiofs mount of a host workspace dir.
  - Fallback: create ephemeral ext4 file (fallocate + mkfs), attach as writable drive for `/workspace`.
- Write `entry.sh` and `.env` under host workspace.

### Stage 3: MicroVM Boot (Net=Off)

- Start Firecracker process; create API socket.
- Configure machine: vCPU/mem from policy; boot‑source with kernel + boot args.
- CPU and memory limits for the Firecracker microVM are sourced from the `[Sandbox]` section of `tldw_Server_API/Config_Files/config.txt` (keys such as `max_cpu` and `max_mem_mb`) via `SANDBOX_MAX_CPU`/`SANDBOX_MAX_MEM_MB` in `tldw_Server_API/app/core/config.py` and `SandboxPolicyConfig` in `tldw_Server_API/app/core/Sandbox/policy.py`, surfaced as `max_cpu`/`max_mem_mb` defaults in `SandboxService.feature_discovery()` (`tldw_Server_API/app/core/Sandbox/service.py`), with per-run overrides coming from `RunSpec.cpu`/`RunSpec.memory_mb` in `tldw_Server_API/app/core/Sandbox/models.py` that take precedence over the policy defaults but are bounded by these configured maxima (precedence: spec → env → config → built-in defaults).
- Add drives: rootfs (read-only) and workspace (rw) and/or virtiofs share.
- Ensure no `network-interfaces` configured (net=off).

### Stage 4: Command Execution & Exit Code

- Entry strategy (MVP options):
  - Prefer: minimal initrd that runs `init=/workspace/entry.sh` to avoid rootfs customization.
  - Fallback: if rootfs supports rc.local/systemd, use that to run `/workspace/entry.sh`.
- `entry.sh` behavior:
  - Loads env, executes spec command, writes logs to `/workspace/run.log` (append + fsync per line), and writes exit JSON to `/workspace/.sandbox_status.json`.
  - Redirects both stdout and stderr from the user command into a single `/workspace/run.log` file (no separate stderr log), with lines from both streams interleaved in write order, each line prefixed with an ISO8601 timestamp and flushed/fsynced after append to match the log tailing implementation planned in `tldw_Server_API/app/core/Sandbox/runners/firecracker_runner.py`.
  - `.sandbox_status.json` MUST be a UTF‑8 JSON object with schema `{ "exit_code": integer, "reason": string, "duration_ms": integer, "timestamp": ISO8601 string, "signal": optional string }` (additional fields ignored), and this schema will be validated when `_read_exit_status()` in `tldw_Server_API/app/core/Sandbox/runners/firecracker_runner.py` deserializes the file and corresponding tests in `tldw_Server_API/tests/sandbox/` assert the mapping into `RunStatus`.

### Stage 5: Log Streaming & Metrics

- If virtiofs is available: tail `/workspace/run.log` and publish stdout frames in near‑real‑time.
- Otherwise: buffer and flush logs on shutdown from the workspace.
- Resource usage: wall time + cgroup CPU/memory from Firecracker process; count log/artifact bytes. Optionally parse metrics FIFO as supplemental data.

### Stage 6: Timeouts, Cancel, Cleanup

- Enforce startup and run timeouts.
- On timeout/cancel: send SIGTERM → SIGKILL to FC process; stop `virtiofsd`; stop tailer threads; publish end frame with `timed_out` or `killed`.
- Cleanup per‑run dirs, sockets, and temporary drives; ensure end frame emitted exactly once.

### Stage 7: Service Wiring & Discovery

- `service.py`: branch to real Firecracker runner when enabled and requested; otherwise use scaffold or return 503 with suggestions.
- Set `runtime_version` from `firecracker --version`.
- Keep `interactive_supported=false` for Firecracker until a guest agent exists.

### Stage 8: Tests & Fake Mode

- Fake mode (`TLDW_SANDBOX_FIRECRACKER_FAKE_EXEC=1`): skip spawning, emit deterministic frames/status/usage shape.
- Unit tests:
  - Preflight gating (OS, KVM, binaries), digest computation, “no NICs” config.
  - Workspace: virtiofs present vs fallback drive; artifact capture via glob.
  - Timeout/cancel transitions; exit JSON parsing; error mapping (missing image, boot failure).
- Integration (skipped unless enabled, Linux):
  - Boot minimal VM, run `echo`, verify log streaming (virtiofs) and artifacts.

### Stage 9: Docs & Examples

- `Docs/API-related/Sandbox_API.md`: prerequisites, flags, rootfs/kernel prep, example run, log/exit file semantics, limitations.
- `Docs/Deployment/Operations/Firecracker_Host_Checklist.md`: host prerequisites, boot flow, and smoke-test checklist.
- `Docs/Product/Sandbox/Firecracker-backend-PRD.md`: update status, constraints, discovery flags.

## Implementation Notes

- Helpers in `firecracker_runner.py`:
  - `_check_env()`, `_build_run_dir()`, `_start_fc()`, `_configure_vm()`, `_start_virtiofsd()`, `_tail_run_log()`, `_read_exit_status()`, `_collect_artifacts()`, `_kill_and_cleanup()`.
- `service.py` wiring:
  - Resolve runtime; call Firecracker runner under gate; propagate `runtime_version`, `image_digest`, `resource_usage`.

## Error Semantics

- 503 `runtime_unavailable` with `details.runtime="firecracker"` (use exception field if present) and `suggested=["docker"]` when disabled, missing prerequisites, or unsupported host.
- 400 for invalid paths (kernel/rootfs), sizes, or malformed spec.

## Security & Isolation

- Real execution typically requires root/capabilities; refuse if `/dev/kvm` or permissions are missing.
- Leave hooks for `jailer` adoption (chroot + UID/GID drop). Emit clear warnings when not using jailer.

## Cleanup Guarantees

- Always stop tailers, Firecracker, and virtiofsd; detach/unmount drives; remove temp files/dirs.
- Ensure a single end frame is sent on all code paths.

## Acceptance Criteria

- With real mode disabled, requesting Firecracker yields 503 `runtime_unavailable` with `suggested=["docker"]`.
- With real mode enabled and prerequisites satisfied:
  - Run executes the command inside a microVM with no NICs.
  - Logs stream via virtiofs (when available) and are flushed on completion otherwise.
  - Exit code and status derived from `.sandbox_status.json`.
  - Artifacts produced under `/workspace` are captured and downloadable.
  - `runtime_version` and `image_digest` included in run details/admin views.
- All unit tests pass; integration tests pass on supported Linux hosts.

## Risks & Mitigations

- Rootfs/init complexity → Prefer initrd `init=/workspace/entry.sh`; document fallback strategies.
- Virtiofs unavailability → Fallback writable drive, no live streaming; document behavior.
- Privilege/safety → Gate behind flags + preflight; plan early migration to `jailer`.
- Flaky log streaming → Make `entry.sh` fsync and flush lines; add WS timeouts in tests.
