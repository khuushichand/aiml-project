## Stage 1: Design Doc
**Goal**: Define ACP-in-sandbox architecture with SSH proxy, session lifecycle, and security model.
**Success Criteria**: Doc includes APIs, data flow, runtime requirements, and migration notes.
**Tests**: N/A
**Status**: In Progress

## Stage 2: Backend Core
**Goal**: Run ACP runner inside sandbox container and expose SSH proxy + ACP WS bridging.
**Success Criteria**: ACP session creates sandbox session/run; ACP traffic flows via sandbox WS; SSH proxy endpoint available.
**Tests**: New unit tests for ACP<->sandbox bridge; integration tests for WS auth + SSH proxy stub.
**Status**: Not Started

## Stage 3: Frontend UX
**Goal**: Add ACP Workspace terminal (xterm.js) and session wiring.
**Success Criteria**: ACP Playground shows live terminal; connect/disconnect flows; errors surfaced.
**Tests**: UI unit tests for terminal component; e2e (if available) for ACP workspace route.
**Status**: Not Started

## Stage 4: Docs + Hardening
**Goal**: Update docs and add deployment notes; tighten security defaults.
**Success Criteria**: Docs describe new Dockerfile, envs, ports, and SSH key handling.
**Tests**: Doc lint if applicable.
**Status**: Not Started
