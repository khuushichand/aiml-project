# macOS Sandbox Runtimes Design

Date: 2026-03-10
Status: Approved for planning
Scope: `tldw_Server_API/app/core/Sandbox/` and related REST/MCP/ACP runtime contracts

## 1. Summary

This design adds first-class macOS-focused sandbox runtimes for Apple silicon hosts:

- `vz_linux`: Linux guest VMs backed by Apple's `Virtualization.framework`
- `vz_macos`: macOS guest VMs backed by Apple's `Virtualization.framework`
- `seatbelt`: host-local restricted process execution for lower-trust cases

The primary security rule is simple:

- `untrusted` execution requires a full VM runtime
- `seatbelt` is never accepted for `untrusted`
- runtime admission stays capability-driven and fail-closed

The provisioning baseline is per-run ephemeral VMs created from sealed templates plus APFS copy-on-write cloning. Warm sessions are a later optimization and should reuse the same template/control-plane model rather than introduce a weaker path.

## 2. User-Confirmed Decisions

1. The feature should support both macOS-native guest execution and Linux guests on macOS hosts.
2. Apple silicon is the target host platform for the serious VM path.
3. API/runtime exposure should use separate runtimes rather than hiding behavior behind a generic macOS selector.
4. Per-run ephemeral VMs are the security baseline.
5. Warm reusable sessions may be added later as an optimization.
6. `untrusted` runs must use a full VM boundary, not seatbelt-only isolation.

## 3. Problem

The sandbox subsystem already has a capability-driven runtime seam and partial Lima support, but macOS support is still limited:

- macOS-specific enforcement is mostly a stub today.
- There is no first-class runtime for Apple `Virtualization.framework`.
- Host-local restricted execution is not modeled as a distinct runtime with clear trust limits.
- Fast macOS-specific provisioning via APFS copy-on-write cloning is not yet represented in the runtime lifecycle.

Without explicit runtime contracts, it is too easy to blur together:

- Linux-on-macOS execution versus macOS-on-macOS execution
- VM isolation versus host-local restrictions
- per-run ephemeral isolation versus long-lived session reuse

That would weaken policy semantics and make the API misleading.

## 4. Goals and Non-Goals

### Goals

1. Add first-class runtime types for `vz_linux`, `vz_macos`, and `seatbelt`.
2. Preserve fail-closed policy admission across REST, MCP, and ACP.
3. Make `untrusted` execution require a VM runtime on macOS hosts.
4. Use sealed templates and APFS clone-based provisioning for fast ephemeral VM startup.
5. Design warm sessions as an optimization layer on top of the same VM image/control-plane architecture.
6. Keep host/runtime capability reporting explicit and descriptive.

### Non-Goals

1. Achieving parity on Intel Macs in the first phase.
2. Treating seatbelt as equivalent to a VM boundary.
3. Implementing broad allowlist networking on day one.
4. Committing the implementation to Python-only runtime control if a native helper is the more defensible choice.

## 5. Selected Architecture

### 5.1 Runtime taxonomy

Add new `RuntimeType` values:

- `vz_linux`
- `vz_macos`
- `seatbelt`

These are first-class runtime values, not aliases for `lima`.

### 5.2 Trust-level rules

- `vz_linux`
  - allowed for `trusted`, `standard`, `untrusted`
- `vz_macos`
  - allowed for `trusted`, `standard`, `untrusted`
- `seatbelt`
  - allowed for `trusted`
  - optionally allowed for `standard` only if explicitly enabled and the host policy is proven sufficient
  - rejected for `untrusted`

Phase 1 should bias conservative: if there is any doubt about `seatbelt` support for `standard`, ship it as `trusted`-only first.

### 5.3 Capability-driven admission

Extend runtime capability and preflight reporting to include:

- host OS and version
- Apple silicon requirement
- helper readiness
- template image readiness
- trust-level support per runtime
- support for `ephemeral_run_vm`
- support for `warm_session_vm`
- network policy readiness (`deny_all`, `allowlist`)
- filesystem isolation guarantees

The existing capability/preflight seam under `runtime_capabilities.py` is the right integration point.

## 6. Control Plane Design

### 6.1 Native helper requirement

The VM control plane should not assume Python is the production-quality interface to Apple's virtualization APIs.

The recommended model is a small native macOS helper, likely Swift-based, responsible for:

- template validation
- VM creation and boot
- guest agent transport setup
- suspend/resume support
- structured lifecycle status reporting

This helper should be treated as a constrained local control plane, similar in spirit to the privileged-helper direction already identified in the Lima design work.

### 6.2 Hardened runtime clarification

`hardened runtime` should be treated as a property of the signed native helper binary and its launch model, not as a per-request toggle on arbitrary subprocesses.

That means the design should not promise "limited per-process isolation via seatbelt and the hardened runtime" as though both are runtime flags. The correct contract is:

- a signed helper/launcher may operate under hardened-runtime constraints
- the `seatbelt` runtime applies generated host policy to a launched process tree

### 6.3 Guest command transport

The VM runtimes should not depend on guest networking just to execute commands. Prefer a non-network control channel such as:

- virtio socket / vsock style transport where available
- serial/control socket fallback

This keeps `deny_all` practical and avoids turning command transport into a hidden network dependency.

## 7. Provisioning Model

### 7.1 Image store

Introduce an image/template store with:

- sealed template manifests
- versioned template metadata
- template readiness checks
- APFS clone lifecycle management
- garbage collection and usage accounting

### 7.2 APFS clone assumptions

The design should be explicit about the unit of cloning.

Do not describe provisioning as "clone the whole VM bundle" unless the implementation chooses a bundle format that is actually safe and efficient to clone as a unit. Instead, define a concrete clone strategy such as:

- clone the disk image file(s) as the fast path
- keep mutable run metadata outside the sealed template
- maintain a manifest describing which files are cloned, generated, or immutable

This avoids overstating what APFS copy-on-write cloning gives us.

### 7.3 Ephemeral run baseline

Per-run ephemeral VMs are the baseline path:

1. Select runtime and validate policy.
2. Validate host/helper/template readiness.
3. Create a run-scoped clone from the template.
4. Create the run bundle and workspace attachment.
5. Boot the VM and wait for guest agent readiness.
6. Execute the command, stream logs, capture artifacts.
7. Destroy run state and revoke resources in `finally`.

## 8. Warm Sessions

Warm sessions are a later optimization, not the baseline security contract.

The preferred design is not "keep every VM running forever." Instead:

- support resumable VM sessions using save/restore or suspend/resume where the platform makes that practical
- keep the same trust/runtime restrictions as the ephemeral path
- ensure session resumption never bypasses authoritative preflight and policy checks

This reduces always-on resource cost and fits better with the desired fast provisioning model.

## 9. Networking and Filesystem Policy

### 9.1 Networking

Phase 1 network target:

- strict `deny_all` for `vz_linux`
- strict `deny_all` for `vz_macos`
- no promise of strict allowlist until it is provable and verified

`seatbelt` should only advertise the network guarantees that can actually be enforced and verified on the host. If those guarantees are not sufficient for the requested trust level, admission must fail closed.

### 9.2 Filesystem

- VM templates remain immutable.
- Only the run workspace is writable.
- Artifacts continue to flow through the existing artifact-root safety model.
- Snapshot/restore export should be conservative until clone lifecycle auditing is complete.

## 10. Error Semantics

Reuse and extend the existing taxonomy:

1. `runtime_unavailable`
   - unsupported host
   - helper missing
   - Apple silicon missing
   - template image missing
2. `policy_unsupported`
   - runtime exists but requested trust level or network mode is not allowed
3. `permission_denied_host_enforcement`
   - required helper capability or host control surface is not available
4. `runtime_execution_failed`
   - VM boot, guest handshake, or command path failed after admission

Structured error details should include:

- runtime
- host facts
- trust level
- required capabilities
- missing capabilities
- template/helper readiness reasons

## 11. Testing Strategy

### Unit tests

1. Runtime enum and schema acceptance for `vz_linux`, `vz_macos`, `seatbelt`
2. Trust-level admission rules, especially `seatbelt` rejection for `untrusted`
3. Preflight reason mapping for:
   - non-Apple-silicon host
   - helper missing
   - template missing
   - unsupported macOS version
4. No-fallback behavior for all new runtimes

### Fake integration tests

1. Per-run clone lifecycle success and failure
2. Cleanup on boot failure, cancelation, and timeout
3. Warm-session resume contract without real platform dependencies
4. Artifact and workspace isolation invariants

### macOS-gated integration tests

1. Apple silicon only
2. Feature-flagged and opt-in
3. Validate real helper handshake and real preflight
4. Prefer targeted smoke coverage over trying to run the full VM matrix in every CI environment

## 12. Rollout Recommendation

1. Add runtime enums, capability contracts, and fail-closed admission.
2. Add `seatbelt` as a lower-trust runtime with explicit restrictions.
3. Add `vz_linux` ephemeral VM support backed by sealed templates and APFS clone provisioning.
4. Add `vz_macos` ephemeral VM support after the control plane and image store are proven.
5. Add warm sessions using suspend/resume or save/restore semantics.
6. Add stricter allowlist networking only after deny-all and lifecycle cleanup are stable.

`vz_linux` should ship before `vz_macos`. It delivers immediate macOS host support while keeping the operational model simpler than macOS guest virtualization.

## 13. Key Risks and Improvements Identified During Review

1. The original design was too vague about the VM control plane.
   Improvement: require a native helper abstraction early instead of assuming Python can own production lifecycle management.

2. The original design blurred hardened runtime semantics.
   Improvement: model hardened runtime as a signed-helper property, not a run-level toggle.

3. The original warm-session idea risked becoming "resident VMs forever."
   Improvement: prefer suspend/resume or save/restore semantics over permanently running sessions.

4. The original APFS clone language was too hand-wavy.
   Improvement: define a concrete clone unit and manifest-driven template layout before promising "fast provisioning."

5. `seatbelt` support for `standard` is easy to over-claim.
   Improvement: ship conservative trust gating first, then expand only if the guarantees are demonstrably sufficient.

## 14. References

- Apple `Virtualization.framework`: https://developer.apple.com/documentation/virtualization
- WWDC 2023, "Create macOS or Linux virtual machines": https://developer.apple.com/videos/play/wwdc2023/10007/
- WWDC 2023, "Bring your virtual machine to life": https://developer.apple.com/videos/play/wwdc2023/10086/
- Apple App Sandbox overview: https://developer.apple.com/documentation/security/app_sandbox
- Apple Hardened Runtime overview: https://developer.apple.com/documentation/security/hardened_runtime
- Agent Safehouse overview: https://agent-safehouse.dev/docs/overview
- Agent Safehouse policy architecture: https://agent-safehouse.dev/docs/policy-architecture
