# Token Encryption and Key Management

This project can encrypt third-party connector tokens at rest using an envelope JSON stored in `external_accounts.access_token`. When enabled, the plaintext OAuth `access_token`/`refresh_token` are not stored directly; instead, an authenticated ciphertext envelope is persisted.

## Enable Encryption

- Set `WORKFLOWS_ARTIFACT_ENC_KEY` to a base64-encoded 32-byte key (AES-256) in your environment before starting the server.
- Example (macOS/Linux):
  - `export WORKFLOWS_ARTIFACT_ENC_KEY=$(openssl rand -base64 32)`

When this variable is present, the connectors service will:
- Use `encrypt_json_blob` to encrypt `{access_token, refresh_token, token_type, expires_in, expires_at, scope}` into a JSON envelope.
- Store that envelope (as JSON) in `external_accounts.access_token` and omit a separate `refresh_token` when possible.
- On read, use `decrypt_json_blob` to recover the token fields at runtime.

If the variable is not set, tokens are stored as plaintext in `access_token` and `refresh_token` columns.

## Rotation Guidance

- Generate a new key and deploy alongside the old key for a limited window.
- Implement rotation by:
  1) Loading accounts and decrypting their envelopes with the old key.
  2) Re-encrypting with the new key using `encrypt_json_blob`.
  3) Persisting updated envelopes to `external_accounts.access_token`.

During the rotation window, you can run a background task to re-write each account’s envelope. If both old and new keys cannot co-exist, schedule a short downtime window and perform the rotation offline. Ensure you have DB backups.

## Verification Paths

- Creation path: `connectors_service.create_account` envelopes tokens when `WORKFLOWS_ARTIFACT_ENC_KEY` is set.
- Read path: `connectors_service.get_account_tokens` decrypts the envelope.
- Update path: `connectors_service.update_account_tokens` re-envelopes refreshed tokens and persists them.

## Security Notes

- Never log tokens or keys. The logging pipeline redacts secrets where possible.
- Store the key only in environment/config management; never commit to source control.
- Consider separate keys per environment (dev/staging/prod); keep rotation docs with your runbook.
