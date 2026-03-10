# macOS Sandbox Runtime Operator Notes

## Scope

These notes cover the current macOS runtime scaffolding for the sandbox subsystem:

- `vz_linux`
- `vz_macos`
- `seatbelt`

This is not a guide for shipping real guest execution yet. The current implementation exposes runtime identities, policy admission, discovery metadata, helper/image-store contracts, and fake-backed runner paths.

## Host Assumptions

- Target host platform: Apple silicon macOS
- The VM-oriented runtimes assume Apple `Virtualization.framework`
- `vz_linux` and `vz_macos` preflights fail closed when the host is not macOS or not Apple silicon

## Trust-Level Policy

- `untrusted`:
  - must use a VM runtime
  - `seatbelt` is rejected
- `standard`:
  - allowed on VM runtimes
  - allowed on `seatbelt` only when `TLDW_SANDBOX_SEATBELT_STANDARD_ENABLED=1`
- `trusted`:
  - allowed on all current runtime identities

## Helper And Template Readiness

The VM scaffolding is controlled by explicit readiness signals.

Required env flags today:

- `TLDW_SANDBOX_MACOS_HELPER_READY=1`
- `TLDW_SANDBOX_VZ_LINUX_AVAILABLE=1`
- `TLDW_SANDBOX_VZ_LINUX_FAKE_EXEC=1`
- `TLDW_SANDBOX_VZ_LINUX_TEMPLATE_READY=1`
- `TLDW_SANDBOX_VZ_MACOS_AVAILABLE=1`
- `TLDW_SANDBOX_VZ_MACOS_FAKE_EXEC=1`
- `TLDW_SANDBOX_VZ_MACOS_TEMPLATE_READY=1`

Without the fake execution flag, the VZ runtimes stay unavailable and expose
`real_execution_not_implemented` in preflight/discovery.

The helper contract lives under `tldw_Server_API/app/core/Sandbox/macos_virtualization/`.

The intended production shape is a native signed helper or service that owns `Virtualization.framework` lifecycle operations. The current Python-side helper client is a contract stub with fake transport in test mode.

## Template Preparation Flow

Current image handling is manifest-driven rather than real APFS cloning.

Expected operator flow later:

1. Prepare a sealed template image per runtime family.
2. Register the template in the sandbox image store.
3. Create run-scoped clone manifests from that template.
4. Hand clone metadata to the native helper for VM boot.
5. Destroy the run-scoped clone state after completion.

Today, the image store implements template registration plus deterministic run-clone manifests only.

## Networking

- `deny_all` is the intended strict baseline for the new macOS runtimes.
- `strict_allowlist_not_supported` is still the expected result for:
  - `vz_linux`
  - `vz_macos`
  - `seatbelt`
- Warm-session optimization is not implemented yet and should not be assumed by operators.

## Discovery And ACP

`/api/v1/sandbox/runtimes` now exposes:

- runtime availability
- preflight reasons
- supported trust levels
- enforcement readiness
- host facts

`/api/v1/sandbox/admin/macos-diagnostics` is the operator-focused companion surface.
It is admin-only and returns:

- detailed host readiness, including macOS version
- helper readiness, with optional configured path and transport metadata
- template readiness for `vz_linux` and `vz_macos`, with optional template source metadata
- per-runtime execution mode and remediation hints

Use the admin endpoint when you are validating host setup or trying to explain why a
runtime is unavailable. Use `/api/v1/sandbox/runtimes` for client-facing discovery;
that payload stays summarized and does not expose helper/template internals.

ACP sandbox session creation now performs runtime preflight validation before calling the sandbox service, and converts failures into `ACPResponseError` instead of leaking raw sandbox exceptions.

## Current Limits

- No real `vz_linux` or `vz_macos` guest command execution yet
- `seatbelt` fake execution uses `TLDW_SANDBOX_SEATBELT_FAKE_EXEC=1`; real seatbelt execution is still absent
- No APFS clone execution path yet
- No allowlist networking for the new macOS runtimes
- No warm-session VM reuse yet

Current diagnostics are still env-driven scaffolding:

- helper readiness is gated by `TLDW_SANDBOX_MACOS_HELPER_READY`
- helper path metadata is optional and comes from `TLDW_SANDBOX_MACOS_HELPER_PATH`
- template readiness is gated by `TLDW_SANDBOX_VZ_LINUX_TEMPLATE_READY` and `TLDW_SANDBOX_VZ_MACOS_TEMPLATE_READY`
- template source metadata is optional and comes from `TLDW_SANDBOX_VZ_LINUX_TEMPLATE_SOURCE` and `TLDW_SANDBOX_VZ_MACOS_TEMPLATE_SOURCE`
- `execution_mode=fake` depends on the corresponding `*_FAKE_EXEC=1` flag
