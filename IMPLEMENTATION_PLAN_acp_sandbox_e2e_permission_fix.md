## Stage 1: Diagnose runtime failure
**Goal**: Reproduce ACP sandbox startup error and identify exact cause.
**Success Criteria**: Confirm concrete failing operation and why it occurs in current runtime hardening.
**Tests**: Local docker probes with ACP image under sandbox-like flags.
**Status**: Complete

## Stage 2: Fix ACP startup and SSH port lifecycle
**Goal**: Ensure ACP sandbox startup works under hardened docker flags and SSH port allocations are never leaked.
**Success Criteria**: Entrypoint no longer writes to user home as root; failed session setup always releases allocated SSH port.
**Tests**: Unit/linters for touched modules; targeted local ACP session creation failure path check.
**Status**: Complete

## Stage 3: Validate end-to-end ACP sandbox SSH flow
**Goal**: Validate build image, launch ACP session, and attach SSH websocket end-to-end locally.
**Success Criteria**: Session create returns success; SSH WS handshake works and interactive channel opens.
**Tests**: Local scripted E2E using FastAPI TestClient and ACP sandbox env.
**Status**: Complete

## Stage 4: Align docs/build guidance with sibling tldw-agent layout
**Goal**: Ensure ACP build instructions/config defaults match `../tldw-agent` workspace layout.
**Success Criteria**: Docs show build command/context that works with sibling repos.
**Tests**: Manual command check.
**Status**: In Progress
