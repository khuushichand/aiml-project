# Lima VM Provider Support in Sandbox Module (Design)

Date: 2026-02-27
Status: Approved for planning
Owner: Sandbox/MCP/ACP maintainers

## 1. Summary

This design adds **LimaVM as a first-class sandbox runtime provider** with strict security semantics across REST, MCP, and ACP surfaces.

The selected direction is a **capability-driven provider layer** (Approach 2), not ad hoc runtime branching.

### User-confirmed decisions

1. Scope: full hardening and provider parity.
2. Platform goal: cross-platform aspirational.
3. `network_policy=deny_all`: strict only.
4. `network_policy=allowlist`: strict only.
5. If strict guarantees are not satisfiable: hard fail, no fallback.
6. ACP support: in scope now (first-class).
7. Windows/WSL: may fail closed in phase 1 until strict host enforcement backend exists.

## 2. Problem

The codebase already has partial Lima runtime support (`RuntimeType.lima`, runner wiring, API schema support), but behavior is inconsistent:

- MCP `sandbox.run` only allows `docker|firecracker`.
- Runtime capability and strict policy enforcement are not modeled uniformly.
- `SANDBOX_DEFAULT_RUNTIME=lima` is not honored correctly in policy config parsing.
- ACP runtime parity is not guaranteed by capability checks.
- Strict deny-all/allowlist semantics are not provable across hosts.

## 3. Goals and Non-Goals

### Goals

1. Make Lima a first-class provider across REST, MCP, and ACP.
2. Enforce strict network policies (`deny_all`, `allowlist`) with fail-closed behavior.
3. Provide host-aware capability/preflight contracts that apply consistently to all runtimes.
4. Expose deterministic error semantics for unsupported or unprovable guarantees.
5. Add tests covering policy correctness, capability gating, and no-fallback behavior.

### Non-Goals (this phase)

1. Shipping strict Windows/WSL host firewall enforcement in phase 1.
2. Implementing full interactive support for Lima if underlying capability is not yet safe/ready.
3. Introducing a separate privileged supervisor daemon (reserved for later if needed).

## 4. Selected Architecture

### 4.1 Capability-driven provider contract

Introduce provider-level contracts used by policy/service entrypoints:

- `RuntimeCapabilities`
  - `supports_strict_deny_all`
  - `supports_strict_allowlist`
  - `supports_interactive`
  - `supports_port_mappings`
  - `supports_acp_session_mode`

- `RuntimePreflightResult`
  - `runtime`
  - `available`
  - `reasons[]`
  - `host` (os/arch/variant, including WSL marker)
  - `enforcement_ready` (`deny_all`, `allowlist`)

### 4.2 Lima host-enforcement abstraction

Add `LimaSecurityEnforcer` with host backends:

- `LinuxLimaEnforcer`
- `MacOSLimaEnforcer`
- `WindowsLimaEnforcer` (initially unsupported/fail-closed)

Each backend must implement:

1. `preflight_capabilities()`
2. `apply_deny_all(instance_ctx)`
3. `apply_allowlist(instance_ctx, targets)`
4. `verify(instance_ctx, mode)`
5. `cleanup(instance_ctx)`

### 4.3 Integration points

- `SandboxPolicy`: uses capabilities/preflight, not ad hoc bool checks.
- `SandboxService`: calls provider preflight + enforcer before run start.
- `LimaRunner`: lifecycle hooks for network apply/verify/cleanup.
- MCP module: schema/validation/runtime parsing includes `lima`.
- ACP manager: runtime requests validated against same capability gates.

## 5. Request/Execution Data Flow

1. Parse request into `SessionSpec`/`RunSpec`.
2. Resolve runtime (explicit request or default).
3. Run provider preflight to produce `RuntimePreflightResult`.
4. Evaluate strict policy requirements:
   - deny-all requires strict deny-all capability + enforcement readiness.
   - allowlist requires strict allowlist capability + enforcement readiness.
5. If checks fail: return deterministic failure (`runtime_unavailable` or `policy_unsupported`).
6. If checks pass:
   - apply network enforcement
   - verify enforcement
   - execute run
7. In `finally`: revoke/cleanup all enforcement artifacts.

No runtime fallback is allowed at any step.

## 6. API and Contract Changes

### 6.1 REST

- `GET /api/v1/sandbox/runtimes`
  - include capability/readiness details for Lima.
- `POST /sessions` and `POST /runs`
  - strict policy rejection when guarantees are not provable.
- Default runtime parsing must honor `lima` from `SANDBOX_DEFAULT_RUNTIME`.

### 6.2 MCP

`SandboxModule` changes:

- Tool schema runtime enum: `docker|firecracker|lima`.
- Validation path accepts `lima`.
- Runtime and policy failures map to explicit MCP error details.

### 6.3 ACP

- `ACP_SANDBOX_RUNTIME=lima` supported as first-class.
- Session bootstrap and run start require capability validation.
- If strict guarantees not available for Lima on host: fail closed.

## 7. Error Semantics

Unify error taxonomy across surfaces:

1. `runtime_unavailable` (503)
   - runtime binary missing, host unsupported, enforcement backend unavailable.
2. `policy_unsupported` (4xx)
   - runtime exists but cannot satisfy strict requested network policy.
3. `permission_denied_host_enforcement` (5xx/503)
   - required host privileges/capabilities unavailable.
4. `runtime_execution_failed` (5xx)
   - runtime execution path failed after admission.

All failures should include structured details:

- runtime
- host facts
- required capabilities
- missing capabilities
- preflight reasons

## 8. Cross-Platform Behavior

### Linux/macOS (phase 1 target)

- Strict deny-all: required and enforced.
- Strict allowlist: required and enforced.

### Windows/WSL (phase 1)

- If strict enforcement backend is not implemented/verified, return fail-closed.
- No fallback to Docker/Firecracker.

## 9. Testing Strategy

### Unit

1. Policy config parsing honors `SANDBOX_DEFAULT_RUNTIME=lima`.
2. Capability gate logic for strict deny-all/allowlist pass/fail.
3. Host preflight reason mapping for Linux/macOS/Windows/WSL.
4. MCP validator/runtime parsing accepts `lima`.
5. ACP config/runtime path supports `lima` and fail-closed checks.

### Integration

1. REST session/run with runtime `lima` success path (fake mode).
2. Strict deny-all/allowlist reject path when enforcer not ready.
3. No-fallback assertions when Lima selected but strict guarantees unavailable.
4. Runtimes discovery payload includes Lima capability/readiness fields.

### Security/cleanup

1. Enforcement apply failure aborts run before command execution.
2. Cleanup/revocation runs in all paths (success, timeout, cancel, exception).
3. Allowlist target expansion and DNS pinning paths validated via existing `network_policy` utilities.

## 10. Implementation Staging (for planning)

1. Contract foundation: capability/preflight models and policy wiring.
2. Lima enforcer interfaces + Linux/macOS implementations.
3. MCP + ACP runtime parity updates.
4. Error payload normalization.
5. Test matrix expansion and docs refresh.

## 11. Risks and Mitigations

1. Host firewall differences across Linux distros/macOS versions.
   - Mitigation: backend-specific preflight checks with explicit reason codes.
2. Lima networking internals vary by host setup.
   - Mitigation: enforce only when instance identity and rule binding are verifiable.
3. Complexity creep in service branching.
   - Mitigation: provider contract centralizes capability logic.

## 12. Acceptance Criteria

1. Lima runtime is selectable and validated in REST, MCP, and ACP.
2. Strict deny-all and allowlist behavior is fail-closed and verifiable.
3. No silent fallback occurs when Lima strict requirements are unmet.
4. `SANDBOX_DEFAULT_RUNTIME=lima` is honored by policy config.
5. Added tests cover new policy, contract, and surface behavior.
