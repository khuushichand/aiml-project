# OpenAI OAuth First-Time Setup (BYOK)

This guide covers first-time setup for linking a user's existing OpenAI subscription to `tldw_server` through OAuth (instead of pasting an API key), while still supporting API-key fallback.

## Who This Is For

- **Operators/admins** configuring a deployment
- **End users** linking their own OpenAI account in the BYOK UI

This flow requires **multi-user mode** with BYOK enabled.

## One-Time Deployment Prerequisites (Operator)

Minimum required configuration:

```bash
AUTH_MODE=multi_user
BYOK_ENABLED=true
BYOK_ENCRYPTION_KEY=<base64-encoded-32-byte-key>
BYOK_ALLOWED_PROVIDERS=openai

OPENAI_OAUTH_ENABLED=true
OPENAI_OAUTH_CLIENT_ID=<client-id>
OPENAI_OAUTH_CLIENT_SECRET=<client-secret>
OPENAI_OAUTH_AUTH_URL=<provider-authorize-url>
OPENAI_OAUTH_TOKEN_URL=<provider-token-url>
```

Recommended optional settings:

```bash
OPENAI_OAUTH_SCOPES=openid profile api
OPENAI_OAUTH_STATE_TTL_MINUTES=10
OPENAI_OAUTH_REDIRECT_URI=https://<your-host>/api/v1/users/keys/openai/oauth/callback
OPENAI_OAUTH_ALLOWED_RETURN_PATH_PREFIXES=/,/byok,/settings
```

Notes:

- If `OPENAI_OAUTH_REDIRECT_URI` is not set, the server computes it from request base URL.
- OAuth setup fails closed if required OAuth settings are missing.
- If OpenAI is not in `BYOK_ALLOWED_PROVIDERS`, OAuth endpoints return `403`.

## First-Time User Workflow (WebUI)

1. Sign in to `tldw_server` in multi-user mode.
2. Open the BYOK page (`/byok`) and find **OpenAI OAuth (Personal)**.
3. Click **Connect OpenAI**.
4. Complete the provider consent flow in the opened tab/window.
5. After callback, return to BYOK and click **Refresh status**.
6. Confirm the card shows:
   - `Source: oauth`
   - `connected=true` (badge/source now indicates OAuth)
   - `Expires` and `Scope` populated when provided by token response.
7. Start using OpenAI normally (chat/embeddings/audio). Runtime resolves OpenAI credentials from your active BYOK source.

Current behavior:

- The callback endpoint returns a JSON response in the OAuth tab.
- You can close that tab and refresh status in BYOK.

## If You Also Have an API Key Stored

When both API key and OAuth credentials exist, you can switch active source:

- **Use OAuth**: set active source to OAuth.
- **Use API Key Instead**: switch back to API key.

If API key source is unavailable, switching to API key returns `409 Requested auth source is unavailable`.

## API Workflow (Equivalent)

User endpoints:

- `POST /api/v1/users/keys/openai/oauth/authorize`
- `GET /api/v1/users/keys/openai/oauth/callback`
- `GET /api/v1/users/keys/openai/oauth/status`
- `POST /api/v1/users/keys/openai/oauth/refresh`
- `POST /api/v1/users/keys/openai/source`
- `DELETE /api/v1/users/keys/openai/oauth`

Typical sequence:

1. Call `authorize` to get `auth_url`.
2. Redirect user to `auth_url`.
3. Provider redirects to callback with `code` and `state`.
4. Callback stores OAuth credentials and sets active source to `oauth`.
5. Query `status` to confirm connection.

## Troubleshooting

### `403 OpenAI OAuth is disabled in this deployment`

- Set `OPENAI_OAUTH_ENABLED=true` and restart.

### `501 OpenAI OAuth is not fully configured`

- Ensure all required OAuth settings are set:
  - `OPENAI_OAUTH_CLIENT_ID`
  - `OPENAI_OAUTH_CLIENT_SECRET`
  - `OPENAI_OAUTH_AUTH_URL`
  - `OPENAI_OAUTH_TOKEN_URL`

### `403 Invalid or expired OAuth state`

- Restart flow from **Connect OpenAI**.
- Complete provider consent before `OPENAI_OAUTH_STATE_TTL_MINUTES` expires (default: 10 minutes).

### `400 return_path is not allowed`

- Keep return path app-relative (example: `/byok`).
- Add allowed prefixes in `OPENAI_OAUTH_ALLOWED_RETURN_PATH_PREFIXES`.

### Refresh/disconnect returns `404 OAuth credential not found`

- User is not connected yet, or already disconnected.
- Run **Connect OpenAI** again.

### Browser popup blocked

- Allow popups for the site, or repeat and complete flow in same tab if browser falls back to redirect.

## Security and Auditing Notes

- OAuth state is one-time use and short-lived.
- PKCE (`S256`) is used for authorization-code exchange.
- OAuth tokens are encrypted at rest via BYOK encryption.
- Audit events are emitted for authorize/connect/refresh/disconnect/source-switch actions.
- Metrics are emitted for OAuth authorize/callback/refresh outcomes.

