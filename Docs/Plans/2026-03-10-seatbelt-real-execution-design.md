# Real Seatbelt Execution Design

## Goal

Replace the fake `seatbelt` runner with a real macOS host-execution path for
`trusted` workflows, while keeping `untrusted` on VM runtimes and preserving the
existing sandbox API, policy admission rules, artifact flow, and diagnostics
surfaces.

## Validated Decisions

- Execution starts in the Python service, not a new native launcher.
- Scope includes:
  - generated per-run seatbelt policy
  - per-run workspace staging
  - isolated `HOME` and temp directories
  - stdout/stderr capture
  - artifact capture/export
  - best-effort network deny through seatbelt policy only
- `trusted` stays supported
- `standard` remains gated by `TLDW_SANDBOX_SEATBELT_STANDARD_ENABLED=1`
- `untrusted` remains rejected

## Reviewed Adjustments

The original design direction is still sound, but four corrections are required
before implementation:

1. `sandbox-exec` is available on the current macOS host, but the local man page
   marks it as deprecated. The first implementation must treat it as a
   compatibility-gated launcher, not as the long-term macOS isolation platform.
2. Seatbelt-based network deny must not be described as strict VM-grade
   `deny_all`. Runtime discovery and diagnostics need to present it as
   best-effort host-local deny.
3. Generated policy files and any wrapper or launcher shim must live in a
   runner-managed control directory outside the writable workspace, otherwise a
   run can tamper with its own enforcement scaffolding.
4. The real path must use curated subprocess environments and process-group
   cleanup. Inheriting the server environment or leaving cancellation as a stub
   would make the runtime unsafe and operationally brittle.

## Architecture

The implementation stays inside `SeatbeltRunner` plus a small policy-rendering
helper. The runtime continues to participate in the existing capability-driven
admission path, but it stops advertising fake-only execution once the host can
launch a real seatbelt-constrained subprocess.

The runtime has three storage areas per run:

- session workspace: the existing writable sandbox workspace used for inline
  files and artifact matching
- runner-managed control dir: a temporary directory outside the workspace that
  holds the generated seatbelt profile and any launcher shim
- isolated temp env dirs: per-run `HOME`, `TMPDIR`, and related temp/cache roots

The session workspace remains the user-visible file surface. The control dir is
owned by the runner and should never be writable by the executed command.

## Execution Flow

1. Admission selects `seatbelt` only for `trusted`, or `standard` when the
   existing opt-in flag is enabled.
2. `SeatbeltRunner.preflight()` verifies:
   - macOS host
   - current seatbelt runtime enablement
   - `sandbox-exec` presence
   - requested trust level support
   - requested network policy support
3. `SeatbeltRunner.start_run()` resolves the command as an argv launch, not an
   implicit shell string.
4. The runner stages:
   - inline files into the session workspace
   - a runner-owned control dir
   - isolated `HOME` and temp directories
5. The runner renders a per-run seatbelt profile with only the paths needed for:
   - command execution
   - reads and writes inside the workspace
   - reads and writes inside the isolated temp dirs
   - best-effort network deny directives
6. The runner launches the subprocess under `sandbox-exec -f <profile> -- ...`
   using `subprocess.Popen`.
7. The runner captures stdout/stderr, updates run status, and collects artifacts
   using the existing `capture_patterns` flow.
8. On normal exit, timeout, or cancellation, the runner tears down the process
   group, removes the control dir, and removes isolated temp dirs in `finally`.

## Runtime Contract

The first real `seatbelt` slice is explicitly a trusted-workflow convenience
path, not a VM-equivalent boundary.

What it will guarantee:

- host-local process launch under a generated seatbelt profile
- writable access limited to the sandbox workspace and runner-created temp dirs
- curated environment variables
- artifact capture through the existing sandbox artifact mechanism
- best-effort local network deny through seatbelt policy

What it will not claim:

- VM-grade filesystem isolation
- strict or verifiable network isolation equivalent to `vz_linux` or `vz_macos`
- allowlist networking
- `untrusted` safety

## Discovery And Diagnostics Semantics

This slice must keep `/api/v1/sandbox/runtimes` and
`/api/v1/sandbox/admin/macos-diagnostics` truthful.

Implications:

- `seatbelt` may be `available=true` for real execution even while
  `strict_deny_all_supported=false`
- `strict_allowlist_supported` remains `false`
- discovery `notes` should explain that seatbelt network deny is best-effort
- admin diagnostics should report `execution_mode=real` only when the runner can
  actually launch through `sandbox-exec`
- preflight errors should use concrete reasons such as:
  - `macos_required`
  - `apple_silicon_required` while the runtime family stays Apple-silicon-only
  - `seatbelt_unavailable`
  - `sandbox_exec_missing`
  - `seatbelt_standard_disabled`
  - `strict_allowlist_not_supported`

## Environment And Process Safety

The subprocess environment must be built explicitly instead of inheriting the
server process environment wholesale.

Required behavior:

- start from a minimal env
- set `HOME`, `TMPDIR`, `TMP`, and `TEMP` to runner-created dirs
- set `PWD` to the workspace
- use a controlled `PATH`
- merge only the non-secret `spec.env` entries already accepted by the sandbox
  API
- reject implicit shell expansion; the command is executed as argv

Cancellation and timeout handling must track the child PID and kill the process
group, not just the direct child, so shell-free subprocess trees do not leak.

## Testing Strategy

Unit tests:

- preflight reports real readiness reasons instead of
  `seatbelt_real_execution_not_implemented`
- policy rendering includes only expected workspace and temp paths
- subprocess env building does not inherit unexpected host env values
- `standard` and `untrusted` policy admission behavior remains unchanged

Integration tests:

- trusted seatbelt run executes a simple command successfully
- inline files are visible in the workspace
- artifact capture via `capture_patterns` still works
- attempted write outside the workspace fails
- timeout and cancellation clean up the subprocess and temp dirs

Host-gated macOS smoke tests:

- verify `sandbox-exec` exists on the host
- verify a simple real seatbelt command runs
- verify control-dir and temp-dir cleanup

## Rollout

1. Add policy-rendering and env-building helpers with unit tests.
2. Implement real `SeatbeltRunner.start_run()` behind an explicit execution flag.
3. Add subprocess tracking, timeout, and cancellation cleanup.
4. Update discovery and diagnostics semantics.
5. Add macOS host-gated smoke coverage and operator documentation.

## Recommendation

Proceed with real `seatbelt` execution as a scoped trusted-workflow backend, but
keep the contract deliberately narrow:

- compatibility-gated `sandbox-exec`
- runner-owned control files outside the workspace
- curated env and process-group cleanup
- best-effort network deny called out explicitly as best-effort

That ships a useful macOS host-exec path without blurring the boundary between
seatbelt and the VM runtimes.
