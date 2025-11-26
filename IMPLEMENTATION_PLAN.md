## Stage 1: Provider wiring
**Goal**: Add MLX chat/embeddings adapters with registry support and config defaults so `provider=mlx` is discoverable and callable.
**Success Criteria**: MLX shows in adapter registries and `/api/v1/llm/providers`; adapters guard missing installs/capability flags; config/env defaults surfaced (`MLX_MODEL_PATH`, `MLX_MAX_CONCURRENT=1`, compile+warmup on).
**Tests**: Unit stubs for adapter capability discovery and missing-install errors.
**Status**: In Progress

## Stage 2: Lifecycle endpoints
**Goal**: Management endpoints for load/unload/status guarded by admin/resource governance, single-session default, overflow→429, and compile/warmup toggle.
**Success Criteria**: `POST /api/v1/llm/providers/mlx/load|unload`, `GET /api/v1/llm/providers/mlx/status` enforce admin + rate limit; load keeps prior model on failure and returns status with capabilities/queue depth; status reflects active session or disabled state.
**Tests**: Unit/integration stubs for load failure (bad path/compile OOM simulated), overflow 429, unload while in-flight stub.
**Status**: In Progress

## Stage 3: CI/testability and metrics
**Goal**: CPU-only skip path for non-Apple runners, metrics parity hooks (load time, active sessions, latency, queue depth, token throughput), and doc/config updates.
**Success Criteria**: Tests marked/guarded for non-MPS, metrics emitted through existing provider hooks, docs/config updated with defaults and error contracts.
**Tests**: CPU-only smoke, skip markers asserted; metrics hook smoke (mocked).
**Status**: Not Started
