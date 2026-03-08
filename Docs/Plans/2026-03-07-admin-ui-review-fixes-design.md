# Admin UI Review Fixes Design

Date: 2026-03-07
Branch: `codex/admin-ui-fixes`

## Context

Follow-up review on the admin UI hardening branch identified three regressions:

1. Enterprise mode still allows API-key login if the allow-login flag is left on.
2. Privileged-action reauthentication breaks high-risk admin actions in non-enterprise single-user deployments.
3. Cookie-backed auth still treats cached `localStorage.user` data as a durable auth signal during bootstrap.

## Design

### 1. Fail-Closed Enterprise API-Key Login

The server-side API-key login route must explicitly reject requests when `ADMIN_UI_ENTERPRISE_MODE` is enabled, regardless of any API-key login toggle. This makes enterprise mode authoritative and removes configuration-order ambiguity.

### 2. Preserve Single-User Admin Workflows Outside Enterprise Mode

Privileged admin actions will continue requiring an audit reason in all modes. Password reauthentication will remain mandatory for multi-user admins, but true single-user principals in non-enterprise mode will use a controlled fallback that skips password verification. Enterprise mode keeps strict reauthentication semantics.

### 3. Bootstrap Auth Only From Real Session Signals

Client auth bootstrap will trust only:

- the readable session marker cookie for cookie-backed sessions
- in-memory API-key state for the legacy non-enterprise path

Cached `localStorage.user` remains a profile cache only and must not be treated as authenticated state.

## Testing Strategy

- Add a route test proving enterprise mode rejects API-key login even when API-key login is otherwise enabled.
- Add backend tests proving privileged-action verification allows non-enterprise single-user principals and still rejects enterprise-mode single-user principals without a password.
- Add auth client tests proving cached profile data alone does not count as stored auth.
