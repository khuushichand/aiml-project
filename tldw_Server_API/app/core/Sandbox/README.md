# Sandbox

## Current Feature Set

- Purpose: isolated execution with sessions, queued runs, idempotency, artifact streaming, and capability-driven runtime admission.
- Core runtimes:
  - `docker`
  - `firecracker`
  - `lima`
  - `vz_linux`
  - `vz_macos`
  - `seatbelt`
- Capabilities:
  - Create and destroy sessions
  - Queue runs with TTL and capacity limits
  - Stream run events over WebSocket
  - Serve guarded artifact download URLs
  - Expose runtime discovery with preflight reasons, host facts, and supported trust levels

## Runtime Model

- `docker`: general-purpose default runtime with existing interactive support.
- `firecracker`: VM-oriented Linux isolation path.
- `lima`: strict macOS-host VM path with explicit deny-all readiness checks.
- `vz_linux`: Apple `Virtualization.framework` Linux guest scaffold on Apple silicon macOS hosts.
- `vz_macos`: Apple `Virtualization.framework` macOS guest scaffold on Apple silicon macOS hosts.
- `seatbelt`: host-local process isolation runtime for conservative trusted macOS workflows, compatibility-gated by deprecated `sandbox-exec`.

Trust-level rules:

- `untrusted` requires a VM runtime.
- `seatbelt` is rejected for `untrusted`.
- `seatbelt` defaults to `trusted` only; `standard` requires `TLDW_SANDBOX_SEATBELT_STANDARD_ENABLED=1`.
- `vz_linux` and `vz_macos` advertise `trusted`, `standard`, and `untrusted`.

## Technical Notes

- `SandboxOrchestrator` owns session/run lifecycle, queueing, idempotency, and artifact storage.
- `SandboxService` is the integration point for policy admission, runtime preflights, execution dispatch, and runtime discovery.
- Runtime capability snapshots are collected in `runtime_capabilities.py`.
- macOS scaffolding currently includes:
  - fake-backed helper contract in `macos_virtualization/`
  - manifest/image-store contract in `image_store.py`
  - fake-backed runners for `vz_linux` and `vz_macos`
  - a real trusted-only `seatbelt` runner that stages a run-local workspace and launches through `sandbox-exec`

Current limitations:

- Real `Virtualization.framework` execution is not implemented yet.
- `vz_linux` and `vz_macos` require helper/template readiness plus `*_FAKE_EXEC=1`; otherwise discovery reports `real_execution_not_implemented`.
- Strict allowlist networking is not implemented for `vz_linux`, `vz_macos`, or `seatbelt`.
- `seatbelt` discovery may be `available=True` while `strict_deny_all_supported=False`; deny-all is a best-effort host policy claim, not a VM-grade guarantee.
- `seatbelt` control files and isolated `HOME`/temp dirs live outside the writable workspace and are removed after each run.
- `seatbelt` real execution still depends on deprecated `sandbox-exec` and may be blocked by an enclosing sandbox even on macOS hosts.
- Warm session VM reuse is not implemented yet.
- `seatbelt` is intentionally conservative and should not be treated as equivalent to a VM boundary.

## Operations And Development

- Main API surface: `tldw_Server_API/app/api/v1/endpoints/sandbox.py`
- Main schemas: `tldw_Server_API/app/api/v1/schemas/sandbox_schemas.py`
- ACP integration: `tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py`
- Recommended validation endpoints:
  - `/api/v1/sandbox/health`
  - `/api/v1/sandbox/runtimes`
  - `/api/v1/sandbox/admin/macos-diagnostics`
  - `/api/v1/sandbox/runs`

`/api/v1/sandbox/runtimes` is the summarized discovery surface used by clients and ACP.
`/api/v1/sandbox/admin/macos-diagnostics` is an admin-only diagnostics surface for
operator troubleshooting and exposes helper/template readiness details that are not
included in the public discovery payload.

Selected configuration knobs:

- Queue and idempotency:
  - `SANDBOX_QUEUE_MAX_LENGTH`
  - `SANDBOX_QUEUE_TTL_SEC`
  - `SANDBOX_IDEMPOTENCY_TTL_SEC`
- macOS scaffolding:
  - `TLDW_SANDBOX_MACOS_HELPER_READY`
  - `TLDW_SANDBOX_MACOS_HELPER_PATH`
  - `TLDW_SANDBOX_VZ_LINUX_AVAILABLE`
  - `TLDW_SANDBOX_VZ_LINUX_FAKE_EXEC`
  - `TLDW_SANDBOX_VZ_LINUX_TEMPLATE_READY`
  - `TLDW_SANDBOX_VZ_LINUX_TEMPLATE_SOURCE`
  - `TLDW_SANDBOX_VZ_MACOS_AVAILABLE`
  - `TLDW_SANDBOX_VZ_MACOS_FAKE_EXEC`
  - `TLDW_SANDBOX_VZ_MACOS_TEMPLATE_READY`
  - `TLDW_SANDBOX_VZ_MACOS_TEMPLATE_SOURCE`
  - `TLDW_SANDBOX_SEATBELT_AVAILABLE`
  - `TLDW_SANDBOX_SEATBELT_FAKE_EXEC`
  - `TLDW_SANDBOX_SEATBELT_STANDARD_ENABLED`
