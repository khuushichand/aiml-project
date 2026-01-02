# API Key KDF Hardening

## Summary
Introduce a new API key format with an embedded key identifier (kid) and
store a slow KDF hash (PBKDF2-HMAC-SHA256) in the database. This enables
constant-time lookups by `key_id` without relying on fast HMAC hashes for
low-entropy, user-chosen keys. Legacy keys remain supported via the existing
HMAC-based lookup path.

## Goals
- Protect weak/user-chosen API keys from fast offline guessing even if DB
  contents leak.
- Preserve efficient lookups by using a key identifier in the API key format.
- Maintain backward compatibility for legacy keys.
- Tighten test fallback guardrails so deterministic secrets cannot leak into
  production.

## Non-Goals
- Breaking or automatically rotating existing legacy keys.
- Adding new cryptographic dependencies (e.g., Argon2).

## Proposed API Key Format
- **New format**: `tldw_<kid>.<secret>`
- `kid` is a short, random hex identifier (e.g., 12 hex chars).
- `secret` remains a long, high-entropy token (`secrets.token_urlsafe`).

Parsing logic:
- If the key matches the format, extract `kid` and use it to find the DB row.
- Otherwise, treat as a legacy key and fall back to HMAC lookup.

## Storage & Verification
- Store the KDF output in `api_keys.key_hash` using a string encoding:
  `pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>`.
- Store `kid` in a new column `api_keys.key_id` (indexed, unique when present).
- Verification recomputes PBKDF2 with the stored parameters and uses
  `hmac.compare_digest` on the raw hash bytes.

## Legacy Compatibility
- Keys without a `kid` continue to use the existing HMAC-SHA256 lookup via
  `key_hash` and `derive_hmac_key_candidates`.
- Legacy keys are not migrated automatically because the raw key is unknown.

## Guardrails
- Production should reject legacy-format `SINGLE_USER_API_KEY` unless a
  specific override flag is set.
- Deterministic test fallback secrets must only be enabled in explicit test
  contexts (e.g., `TEST_MODE=1`), and never in production.

## Migration / Rollout
- Add `key_id` column and index for SQLite and Postgres.
- Generate new keys in the new format.
- Update API key validation and resolution to prefer the `kid` lookup path.

## Testing
- Unit tests for:
  - Key format parsing (`kid` extraction, legacy detection).
  - KDF hash encoding/verification.
  - Validation for new-format keys.
  - Legacy fallback still works.
  - Production guardrails for legacy single-user keys.
