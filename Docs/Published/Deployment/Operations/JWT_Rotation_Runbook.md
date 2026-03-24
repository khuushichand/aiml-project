# JWT Rotation & Maintenance Runbook

This guide describes how to rotate JWT signing configuration for the AuthNZ module and what to expect operationally.

## Summary

- AuthNZ supports both symmetric (HS256) and asymmetric (RS256/ES256) JWT signing.
- Recommended for multi-service deployments: RS256 with keypair (`JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`).
- Refresh tokens are session-bound; rotation can invalidate tokens depending on strategy.
- Session encryption (`SESSION_ENCRYPTION_KEY`) is independent; by default it’s derived from a configured key, not the JWT secret. If you used the JWT secret to derive it previously, plan for session token re-encrypt.

## Rotation Scenarios

### 1) HS256 → HS256 (replace `JWT_SECRET_KEY`)

- Steps:
  1. Generate new secret: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
  2. Set `JWT_SECRET_KEY_NEW` in your secret store or staging env.
  3. Deploy code that can read from the new key (rollout window) and accept tokens signed with the old key if needed (optional dual-validate code path) - or perform a brief cutover window.
  4. Switch `JWT_SECRET_KEY` to the new value.
  5. Restart server processes.
- Impact:
  - Existing access/refresh tokens signed with the old secret become invalid immediately after cutover.
  - Active sessions continue to exist in the DB; users need to log in again (or handle refresh retry and show a login prompt).

### 2) HS256 → RS256 (asymmetric migration)

- Steps:
  1. Generate an RSA keypair (e.g., `openssl genrsa -out jwt_private.pem 2048` and `openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem`).
  2. Set `JWT_ALGORITHM=RS256`, `JWT_PRIVATE_KEY=<contents of jwt_private.pem>`, `JWT_PUBLIC_KEY=<contents of jwt_public.pem>`.
  3. Remove `JWT_SECRET_KEY` once cutover is complete.
  4. Restart server processes.
- Impact:
  - Tokens signed under HS256 will no longer validate.
  - New tokens will be signed with RS256 and verified using the public key.

### 3) RS256 → RS256 (keypair rotation)

- Steps:
  1. Generate a new keypair.
  2. Update `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY`.
  3. Restart.
- Impact:
  - Previously issued tokens become invalid at cutover.
  - Consider a dual-key validation window if you need zero disruption (requires custom verifier that accepts both old and new keys for a limited time).

### Dual-Key Validation (Smooth Cutover)

AuthNZ supports a temporary dual-validation window during rotations:

- HS256: set `JWT_SECONDARY_SECRET=<old_secret>` while `JWT_SECRET_KEY=<new_secret>` is active.
- RS256/ES256: set `JWT_SECONDARY_PUBLIC_KEY=<old_public_key>` while `JWT_PUBLIC_KEY`/`JWT_PRIVATE_KEY` point to the new pair.

Tokens validate first against the primary key and, on signature error, against the secondary key. Remove the secondary key after the window.

## Sessions & Refresh Tokens

- The `/auth/refresh` endpoint is session-bound and (by default) rotates refresh tokens.
- After rotation or algorithm change, previously minted refresh tokens will fail verification; clients need to re-authenticate.

## Issuer/Audience Hardening

- Set `JWT_ISSUER` (e.g., `tldw_server`) and `JWT_AUDIENCE` (e.g., `tldw_api`) in production.
- Tokens are minted with `iss`/`aud` and validated on decode.

## Logging & PII

- Enable `PII_REDACT_LOGS=true` to reduce usernames/IPs in auth logs during sensitive rotations.

## Rollback

- To roll back a failed rotation, restore the previous secrets/keys and restart servers.

## Checklist

- [ ] Pick rotation window and notify users.
- [ ] Generate new key/secret.
- [ ] Update environment/secret store.
- [ ] Deploy and restart.
- [ ] Verify `/auth/login` and `/auth/refresh`.
- [ ] Monitor logs for auth failures.
