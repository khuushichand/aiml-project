# Sandbox Module Design

## Overview

The Sandbox module provides isolated code execution environments with configurable runtimes,
security policies, and session management. It enables safe execution of user-provided code
in containerized or virtualized environments.

## Architecture

### Runtimes

| Runtime | Isolation Level | Platform | Startup Time | Use Case |
|---------|-----------------|----------|--------------|----------|
| Docker | Container | Any | ~1s | Fast, general purpose |
| Firecracker | MicroVM | Linux | ~3-5s | Strong isolation, multi-tenant |
| Lima | Full VM | macOS/Linux | ~10-30s | macOS development, maximum isolation |

#### Docker (Default)
- Uses Docker containers with configurable security profiles
- Supports seccomp and AppArmor for additional hardening
- Fastest startup, suitable for high-throughput workloads

#### Firecracker
- MicroVM technology from AWS
- Strong isolation through KVM-based virtualization
- Requires Linux host with `/dev/kvm` access
- See `Docs/Deployment/Operations/Firecracker_Host_Checklist.md`

#### Lima
- Full VM isolation using Virtualization.framework (macOS) or QEMU (Linux)
- Best for macOS development where Docker isolation is weaker
- Slowest startup but strongest isolation guarantees

### Trust-Level System

Risk-based resource allocation automatically constrains runs based on code trustworthiness:

| Level | Max CPU | Max Memory | Timeout | Network | PIDs | File Descriptors |
|-------|---------|------------|---------|---------|------|------------------|
| `trusted` | 8 | 16GB | 600s | allowlist | 512 | 4096 |
| `standard` | 4 | 8GB | 300s | deny_all | 256 | 1024 |
| `untrusted` | 1 | 1GB | 60s | deny_all | 64 | 256 |

- **Trusted**: For verified internal code; relaxed limits, configurable egress
- **Standard**: Default profile; balanced security and usability
- **Untrusted**: For user-submitted code; maximum restrictions

### Sessions and Runs

```
Session (container lifecycle)
├── Workspace (persistent across runs)
│   ├── uploaded files
│   ├── run outputs
│   └── snapshots
├── Run 1 (execution)
├── Run 2 (execution)
└── Run N (execution)
```

Sessions provide a persistent workspace that survives across multiple run executions.
This enables iterative development workflows.

### Snapshots

Workspace checkpointing for:
- **Safe experimentation**: Revert on failure
- **Session cloning**: Parallel exploration of different approaches
- **State preservation**: Checkpoint before risky operations

Implementation:
- Snapshots are stored as compressed tarballs
- Metadata tracks creation time, size, and session association
- Quota enforcement prevents unbounded storage consumption

### Network Isolation

- **deny_all** (default): No network access via Docker `--network=none` or VM isolation
- **allowlist**: Selective egress via iptables rules (Docker only)
  - DNS pinning prevents TOCTOU attacks
  - Rules tagged with run ID for cleanup

## Key Components

```
tldw_Server_API/app/core/Sandbox/
├── models.py          # RuntimeType, TrustLevel, RunSpec, SessionSpec
├── policy.py          # SandboxPolicy, TRUST_PROFILES, policy hash
├── service.py         # SandboxService (main orchestrator facade)
├── orchestrator.py    # Session/run lifecycle, idempotency
├── snapshots.py       # SnapshotManager for checkpointing
├── streams.py         # WebSocket event hub for log streaming
├── store.py           # Memory/SQLite/cluster storage backends
├── network_policy.py  # Egress allowlist, DNS pinning
└── runners/
    ├── docker_runner.py      # Docker container execution
    ├── firecracker_runner.py # Firecracker MicroVM execution
    └── lima_runner.py        # Lima VM execution
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SANDBOX_DEFAULT_RUNTIME` | `docker` | Default runtime backend |
| `SANDBOX_SNAPSHOT_PATH` | `tmp_dir/sandbox_snapshots` | Snapshot storage location |
| `TLDW_SANDBOX_LIMA_AVAILABLE` | auto-detect | Override Lima availability check |
| `SANDBOX_MAX_CPU` | `4.0` | Global CPU limit |
| `SANDBOX_MAX_MEM_MB` | `8192` | Global memory limit |
| `SANDBOX_WORKSPACE_CAP_MB` | `256` | Workspace size cap |
| `SANDBOX_ARTIFACT_TTL_HOURS` | `24` | Artifact retention period |
| `SANDBOX_ENABLE_EXECUTION` | `false` | Enable real code execution |
| `SANDBOX_BACKGROUND_EXECUTION` | `false` | Run execution in background threads |
| `SANDBOX_EGRESS_ENFORCEMENT` | `false` | Enable egress allowlist enforcement |
| `SANDBOX_WS_SIGNED_URLS` | `false` | Enable signed WebSocket URLs |
| `SANDBOX_WS_SIGNING_SECRET` | none | Secret for URL signing |

### Firecracker-specific

| Variable | Description |
|----------|-------------|
| `SANDBOX_FC_KERNEL_PATH` | Path to vmlinux kernel |
| `SANDBOX_FC_ROOTFS_PATH` | Path to root filesystem image |

### Test/Development

| Variable | Description |
|----------|-------------|
| `TLDW_SANDBOX_DOCKER_FAKE_EXEC` | Enable fake Docker execution for tests |
| `TLDW_SANDBOX_LIMA_FAKE_EXEC` | Enable fake Lima execution for tests |

## Security Considerations

1. **Container Escapes**: Docker provides namespace isolation but shares kernel
2. **MicroVMs**: Firecracker provides KVM-based isolation with minimal attack surface
3. **Full VMs**: Lima provides strongest isolation but with performance cost
4. **Network**: Default deny-all prevents data exfiltration
5. **Resources**: Trust levels prevent resource exhaustion attacks
6. **Path Traversal**: Artifact downloads validate paths to prevent escapes

## References

- [Sandbox API Guide](../API-related/Sandbox_API.md)
- [Firecracker Host Checklist](../Deployment/Operations/Firecracker_Host_Checklist.md)
- [Lima VM](https://github.com/lima-vm/lima)
- [Firecracker](https://firecracker-microvm.github.io/)
- [Docker Security](https://docs.docker.com/engine/security/)
