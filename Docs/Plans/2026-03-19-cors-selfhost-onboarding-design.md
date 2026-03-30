# CORS Self-Host Onboarding Design

**Date:** 2026-03-19

## Goal

Keep browser-based local self-hosted setup working out of the box while removing a confusing startup failure that forces new users to understand CORS before they can run the server.

## Problem

The backend currently enables CORS by default with a localhost allowlist so the separately hosted local WebUI can connect during development and first-run setup. That default is correct for local browser access, but the startup path becomes confusing when configuration resolves to an explicit empty origin list. In that case the app raises a hard startup error focused on `ALLOWED_ORIGINS`, which is not actionable for new self-hosters who only want the server to start.

## Decision

Do not disable CORS by default.

Instead:

- Preserve the existing localhost/loopback default allowlist for local browser-based onboarding.
- In non-production environments, treat an explicitly empty configured allowlist as a compatibility fallback to the built-in local origins instead of a fatal startup error.
- In production environments, keep startup strict: explicit origin configuration remains required, and wildcard/empty configurations should still fail fast.

## Why This Approach

- It keeps the current out-of-box local frontend flow working.
- It fixes the reported onboarding confusion without widening production behavior.
- It avoids teaching first-time self-hosters about CORS unless they are intentionally changing browser-origin behavior.

## Scope

### Runtime

- Adjust CORS origin resolution so non-production startup can recover from an explicit empty resolved origin list.
- Keep production validation unchanged for wildcard and empty origin lists.

### Tests

- Add a failing test for the non-production explicit-empty case.
- Preserve the existing production tests that enforce explicit origin configuration.

### Documentation

- Update environment/config examples to explain the local default in plain language.
- Reduce emphasis on manual CORS configuration for first-run self-hosted local setup.

## Non-Goals

- No change to production hardening guidance.
- No change to credentialed CORS behavior.
- No change to the separate MCP CORS configuration.
