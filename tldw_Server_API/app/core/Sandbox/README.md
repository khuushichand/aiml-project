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
- `seatbelt`: host-local process isolation scaffold for conservative macOS trusted workflows.

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
  - fake-backed runners for `vz_linux`, `vz_macos`, and `seatbelt`

Current limitations:

- Real `Virtualization.framework` execution is not implemented yet.
- `vz_linux` and `vz_macos` require helper and template readiness env wiring to pass preflight.
- Strict allowlist networking is not implemented for `vz_linux`, `vz_macos`, or `seatbelt`.
- Warm session VM reuse is not implemented yet.
- `seatbelt` is intentionally conservative and should not be treated as equivalent to a VM boundary.

## Operations And Development

- Main API surface: `tldw_Server_API/app/api/v1/endpoints/sandbox.py`
- Main schemas: `tldw_Server_API/app/api/v1/schemas/sandbox_schemas.py`
- ACP integration: `tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_runner_client.py`
- Recommended validation endpoints:
  - `/api/v1/sandbox/health`
  - `/api/v1/sandbox/runtimes`
  - `/api/v1/sandbox/runs`

Selected configuration knobs:

- Queue and idempotency:
  - `SANDBOX_QUEUE_MAX_LENGTH`
  - `SANDBOX_QUEUE_TTL_SEC`
  - `SANDBOX_IDEMPOTENCY_TTL_SEC`
- macOS scaffolding:
  - `TLDW_SANDBOX_MACOS_HELPER_READY`
  - `TLDW_SANDBOX_VZ_LINUX_AVAILABLE`
  - `TLDW_SANDBOX_VZ_LINUX_TEMPLATE_READY`
  - `TLDW_SANDBOX_VZ_MACOS_AVAILABLE`
  - `TLDW_SANDBOX_VZ_MACOS_TEMPLATE_READY`
  - `TLDW_SANDBOX_SEATBELT_AVAILABLE`
  - `TLDW_SANDBOX_SEATBELT_STANDARD_ENABLED`
