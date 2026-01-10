# tldw_server Browser Extension — Product Requirements Document (PRD)

- Version: 1.0
- Owner: Product/Engineering (You)
- Stakeholders: tldw_server backend, Extension frontend, QA
- Target Browsers: Chrome/Edge (MV3), Firefox (MV2)

## Background
You’ve inherited the project and an in‑progress extension. The goal is to ship an official, whitelabeled extension that uses tldw_server as the single backend for chat, RAG, media ingestion, notes, prompts, and audio (STT/TTS). The server provides OpenAI‑compatible APIs and mature AuthNZ (single‑user API key and multi‑user JWT modes).

## Goals
- Deliver an integrated research assistant in the browser that:
  - Chats via `/api/v1/chat/completions` with streaming and model selection.
  - Searches via RAG (`POST /api/v1/rag/search` and `GET /api/v1/rag/simple` if exposed).
  - Ingests content (current page URL or manual URL) via `/api/v1/media/process` and related helpers.
  - Manages notes and prompts through their REST endpoints.
  - Transcribes audio via `/api/v1/audio/transcriptions`; synthesizes speech via `/api/v1/audio/speech`.
- Provide smooth setup (server URL + auth) and a robust, CORS‑safe network layer.
- Ship an MVP first and iterate with clear milestones.

## Non‑Goals
- Building a general proxy for arbitrary third‑party LLM services.
- Adding server features not exposed by tldw_server APIs.
- Collecting telemetry on user content or behavior.

## Personas
- Researcher/Student: Captures web content, asks questions, organizes notes.
- Developer/Analyst: Tries multiple models/providers, tweaks prompts, exports snippets.
- Power user: Uses voice (STT/TTS), batch ingest, and RAG filters.

## User Stories (MVP‑critical)
- As a user, I configure the server URL and authenticate (API key or login).
- As a user, I see available models/providers and select one for chat.
- As a user, I ask a question and receive streaming replies with cancel.
- As a user, I search with RAG and insert results into chat context.
- As a user, I send the current page URL to the server for processing and get status.
- As a user, I quickly capture selected text as a note and search/export notes.
- As a user, I upload a short audio clip for transcription and view the result.

## Scope

### MVP (v0)
- Settings: server URL, auth mode (single/multi), credentials, health check.
- Auth: X‑API‑KEY and JWT (login/refresh/logout); error UX for 401/403.
- Models: discover and select model/provider from server.
- Chat: non‑stream and SSE stream; cancel; basic local message history.
- RAG: simple search UI; insert snippets into chat context.
- Media: ingest current tab URL or entered URL; progress/status.
- Notes/Prompts: basic create/search/import/export.
- STT: upload wav/mp3/m4a; show transcript.

### v1
- TTS playback; voice catalog/picker.
- Context menu “Send to tldw_server”.
- Improved RAG filters (type/date/tags).
- Robust error recovery and queued retries.

### v1.x
- Batch operations; offscreen processing where safe.
- MCP surface (if required later).

## Functional Requirements

### Settings and Auth
- Allow any `serverUrl` (http/https); validate via a health check.
- Health check path: `GET /api/v1/health` (optional lightweight: `/healthz`, readiness: `/readyz`). Treat non-200 as not ready.
- Modes: Single‑User uses `X-API-KEY: <key>`. Multi‑User uses `Authorization: Bearer <access_token>`.
- Manage access token in memory; persist refresh token only when necessary.
- Auto‑refresh on 401 with single‑flight queue; one retry per request.
- Never log secrets; redact sensitive fields in errors.

- MV3 token lifecycle: persist refresh token in `chrome.storage.local` to survive service worker suspension/restart; keep access token in memory (or `chrome.storage.session`). On background start, attempt auto‑refresh when a refresh token exists; use single‑flight refresh queue on 401.

### Network Proxy (Background/Service Worker)
- All API calls originate from background; UI/content never handles tokens directly.
- Optional host permissions per configured origin at runtime; least privilege.
- SSE support: set `Accept: text/event-stream`, parse events (including handling `[DONE]` sentinel), keep‑alive handling, `AbortController` cancellation.
- Timeouts with exponential backoff (jitter). Offline queue for small writes.
- Propagate an `X-Request-ID` header per request for correlation and idempotent retries.

### API Path Hygiene
- Match the server’s OpenAPI exactly, including trailing slashes where specified, to avoid redirects and CORS quirks.
- Core endpoints:
  - Chat: `POST /api/v1/chat/completions`
  - RAG: `POST /api/v1/rag/search`, `POST /api/v1/rag/search/stream`, `GET /api/v1/rag/simple`
  - Media: `POST /api/v1/media/process`
  - Notes: `/api/v1/notes/...` (search may require a trailing slash; align to spec)
  - Prompts: `/api/v1/prompts/...`
  - STT: `POST /api/v1/audio/transcriptions`
  - TTS: `POST /api/v1/audio/speech`
  - Voices: `GET /api/v1/audio/voices/catalog`
  - Providers/Models: `GET /api/v1/llm/providers` (and `/llm/models` if present)
- Centralize route constants; do not rely on client‑side redirects.

#### Trailing Slash Rules (Notes/Prompts)
- Notes:
  - List/Create: `GET/POST /api/v1/notes/` (trailing slash required)
  - Search: `GET /api/v1/notes/search/` (trailing slash required)
  - Item: `GET/DELETE/PATCH /api/v1/notes/{id}` (no trailing slash)
  - Keywords collections use trailing slash, e.g., `/api/v1/notes/keywords/`, `/api/v1/notes/keywords/search/`, `/api/v1/notes/{note_id}/keywords/`
- Prompts:
  - Base: `GET/POST /api/v1/prompts` (no trailing slash)
  - Search: `POST /api/v1/prompts/search` (no trailing slash)
  - Export: `GET /api/v1/prompts/export` (no trailing slash)
  - Import: `POST /api/v1/prompts/import` (no trailing slash)
  - Versions: `GET /api/v1/prompts/{id}/versions` (no trailing slash)
  - Restore: `POST /api/v1/prompts/{id}/versions/{version}/restore` (no trailing slash)
  - Templates: `POST /api/v1/prompts/templates/variables`, `POST /api/v1/prompts/templates/render`
  - Bulk: `POST /api/v1/prompts/bulk/delete`, `POST /api/v1/prompts/bulk/keywords`
  - Keywords collection: `/api/v1/prompts/keywords/` (trailing slash)

### API Semantics
- Chat SSE shape: Expect OpenAI-style chunks with "delta" objects, then "[DONE]". Parse lines like `data: {"choices":[{"delta":{"role":"assistant","content":"..."}}]}` and terminate on `[DONE]`.
- RAG streaming is NDJSON (not SSE). Treat each line as a complete JSON object; do not expect `[DONE]`. Endpoints: `POST /api/v1/rag/search/stream` (stream), `GET /api/v1/rag/simple` (simple retrieval).
- Health signals: `GET /api/v1/health` returns status "ok" (200) or "degraded" (206). Treat any non-200 as not ready during setup. Use `/readyz` (readiness) and `/healthz` (liveness) for lightweight probes.

References:
- Chat SSE generator: `tldw_Server_API/app/api/v1/endpoints/chat.py:1256`
- RAG endpoints: `tldw_Server_API/app/api/v1/endpoints/rag_unified.py:664, 1110, 1174`
- Health endpoints: `tldw_Server_API/app/api/v1/endpoints/health.py:97, 110`

### Auth & Tokens
- Token response shape: `access_token`, `refresh_token`, `token_type=bearer`, `expires_in` (seconds). Reference: `tldw_Server_API/app/api/v1/schemas/auth_schemas.py:181`.
- Refresh rotation: if refresh call returns a `refresh_token`, replace the stored value (treat as authoritative).
- Prefer header auth over cookies: use `Authorization: Bearer` or `X-API-KEY`; CSRF middleware is present but skipped for Bearer/X-API-KEY flows. Reference: `tldw_Server_API/app/main.py:2396`.
- Service worker lifecycle: on background start, check for a stored refresh token and proactively refresh the access token (single-flight), so UI works after suspension/restart without prompting.

#### Background: Single‑Flight Refresh (MV3 example)
```ts
// background.ts (MV3 service worker)

type TokenResponse = {
  access_token: string;
  refresh_token?: string;
  token_type: 'bearer';
  expires_in: number; // seconds
};

let serverUrl = '';
let authMode: 'single_user' | 'multi_user' = 'multi_user';

// Ephemeral in-memory access token + expiry
let accessToken: string | null = null;
let accessExpiresAt = 0; // epoch ms

// Single-flight guard
let refreshInFlight: Promise<string> | null = null;

async function getRefreshToken(): Promise<string | null> {
  const { refresh_token } = await chrome.storage.local.get('refresh_token');
  return (refresh_token as string) || null;
}

async function setTokens(tr: TokenResponse) {
  accessToken = tr.access_token;
  // Renew slightly early
  accessExpiresAt = Date.now() + Math.max(0, (tr.expires_in - 30) * 1000);
  if (tr.refresh_token) {
    await chrome.storage.local.set({ refresh_token: tr.refresh_token });
  }
}

function isAccessValid(): boolean {
  return !!accessToken && Date.now() < accessExpiresAt;
}

async function refreshAccessTokenSingleFlight(): Promise<string> {
  if (isAccessValid()) return accessToken!;
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const rt = await getRefreshToken();
    if (!rt) throw new Error('No refresh token');
    const res = await fetch(`${serverUrl}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) {
      // Clear tokens on hard failure
      await chrome.storage.local.remove('refresh_token');
      accessToken = null; accessExpiresAt = 0;
      throw new Error(`Refresh failed: ${res.status}`);
    }
    const body = (await res.json()) as TokenResponse;
    await setTokens(body);
    return accessToken!;
  })().finally(() => {
    refreshInFlight = null;
  });

  return refreshInFlight;
}

export async function bgFetch(input: RequestInfo, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers || {});

  // Attach auth
  if (authMode === 'single_user') {
    // X-API-KEY for single-user mode (store separately)
    const { api_key } = await chrome.storage.local.get('api_key');
    if (api_key) headers.set('X-API-KEY', api_key as string);
  } else {
    // Ensure access token is fresh
    const token = await refreshAccessTokenSingleFlight();
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Correlation header
  headers.set('X-Request-ID', crypto.randomUUID());

  let res = await fetch(input, { ...init, headers });
  if (res.status === 401 && authMode === 'multi_user') {
    try {
      const token = await refreshAccessTokenSingleFlight();
      headers.set('Authorization', `Bearer ${token}`);
      res = await fetch(input, { ...init, headers });
    } catch (_) {
      // Bubble up 401 after failed refresh
    }
  }
  return res;
}

// On SW start: auto-refresh so UI is ready
chrome.runtime.onStartup.addListener(async () => {
  try { await refreshAccessTokenSingleFlight(); } catch { /* no-op */ }
});

// Also attempt onInstalled (first install/update)
chrome.runtime.onInstalled.addListener(async () => {
  try { await refreshAccessTokenSingleFlight(); } catch { /* no-op */ }
});
```

### Streaming & SSE
- Chat SSE: set `Accept: text/event-stream`; keep the service worker alive via a long‑lived `Port` from the side panel/popup; recognize `[DONE]` and release reader/locks.
- RAG stream (NDJSON): tolerate heartbeats/blank lines and partial chunks; reassemble safe JSON boundaries before parse.
- Cancellation: use `AbortController`; expect network to close within ≈200ms after abort.

Note:
- `/api/v1/rag/search/stream` requires `enable_generation=true` in the request body; otherwise the server returns HTTP 400.
- Default retrieval knobs are `search_mode="hybrid"` and `top_k=10` unless overridden. Discover the server’s current defaults and ranges via `GET /api/v1/rag/capabilities`.

#### Background: Chat SSE Reader (MV3 example)
```ts
export async function streamChatSSE(
  url: string,
  body: unknown,
  opts: {
    headers?: HeadersInit;
    signal?: AbortSignal;
    port?: chrome.runtime.Port; // Long-lived port from UI to keep SW alive
    onDelta?: (text: string) => void;
    onDone?: () => void;
  } = {}
) {
  const controller = opts.signal ? null : new AbortController();
  const signal = opts.signal ?? controller!.signal;

  const headers = new Headers(opts.headers || {});
  headers.set('Accept', 'text/event-stream');
  headers.set('Content-Type', 'application/json');

  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body ?? {}),
    signal,
    // credentials not needed for header auth; keep simple
  });
  if (!res.ok || !res.body) throw new Error(`SSE failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const eventBlock = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        // Join all data: lines per SSE spec
        const dataLines = eventBlock
          .split('\n')
          .filter(l => l.startsWith('data:'))
          .map(l => l.slice(5).trim());
        if (dataLines.length === 0) continue;
        const dataStr = dataLines.join('\n');
        if (dataStr === '[DONE]') {
          opts.onDone?.();
          return; // normal termination
        }
        try {
          const obj = JSON.parse(dataStr);
          const delta = obj?.choices?.[0]?.delta?.content ?? '';
          if (delta) {
            opts.onDelta?.(delta);
            opts.port?.postMessage({ type: 'chat-delta', data: delta });
          }
        } catch { /* ignore parse errors */ }
      }
    }
    opts.onDone?.();
  } finally {
    try { reader.releaseLock(); } catch { /* no-op */ }
    // Caller may disconnect the port when UI is done
  }

  return {
    cancel: () => controller?.abort(),
  };
}
```

#### Background: RAG NDJSON Reader (MV3 example)
```ts
export async function streamRagNDJSON(
  url: string,
  body: unknown,
  opts: {
    headers?: HeadersInit;
    signal?: AbortSignal;
    port?: chrome.runtime.Port;
    onEvent?: (obj: any) => void;
  } = {}
) {
  const controller = opts.signal ? null : new AbortController();
  const signal = opts.signal ?? controller!.signal;

  const headers = new Headers(opts.headers || {});
  headers.set('Accept', 'application/x-ndjson');
  headers.set('Content-Type', 'application/json');

  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body ?? {}),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`NDJSON failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let nl;
      while ((nl = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (!line) continue; // tolerate heartbeats/blank lines
        try {
          const obj = JSON.parse(line);
          opts.onEvent?.(obj);
          opts.port?.postMessage({ type: 'rag-event', data: obj });
        } catch {
          // Partial or invalid JSON; prepend back to buffer (rare)
          buffer = line + '\n' + buffer;
          break;
        }
      }
    }
  } finally {
    try { reader.releaseLock(); } catch { /* no-op */ }
  }

  return {
    cancel: () => controller?.abort(),
  };
}
```

#### Quick Examples (curl)
```bash
# RAG streaming (JWT)
curl -sN "http://127.0.0.1:8000/api/v1/rag/search/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/x-ndjson" \
  -d '{"query":"What is machine learning?","top_k":5,"enable_generation":true}'

# RAG simple (Single-user API key)
curl -s "http://127.0.0.1:8000/api/v1/rag/simple?query=vector%20databases" \
  -H "X-API-KEY: $API_KEY" | jq .
```

### Media & Audio Details
- STT multipart fields: `file` (UploadFile), `model` (default `whisper-1`), optional `language`, `prompt`, `response_format`, and TreeSeg controls (`segment`, `seg_*`). Allowed mimetypes include wav/mp3/m4a/ogg/opus/webm/flac; default max size ≈25MB (tiered). Reference: `tldw_Server_API/app/api/v1/endpoints/audio.py:464`.
- TTS JSON body: `model`, `input` (text), `voice`, `response_format` (e.g., mp3, wav), optional `stream` boolean. Response sets `Content-Disposition: attachment; filename=speech.<format>`. Reference: `tldw_Server_API/app/api/v1/endpoints/audio.py:272`.
- Voices catalog: `GET /api/v1/audio/voices/catalog?provider=...` returns mapping of provider→voices; filter via `provider`. Reference: `tldw_Server_API/app/api/v1/endpoints/audio.py:1131`.
- Media timeouts: adopt endpoint-specific timeouts similar to WebUI defaults (videos/audios ~10m, docs/pdfs ~5m). Reference: `tldw_Server_API/WebUI/js/api-client.js:290`.

#### Quick Examples (curl)
```bash
# STT (JWT)
curl -X POST "http://127.0.0.1:8000/api/v1/audio/transcriptions" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/abs/path/to/audio.wav" \
  -F "model=whisper-1" \
  -F "language=en" \
  -F "response_format=json"

# STT (Single-user API key)
curl -X POST "http://127.0.0.1:8000/api/v1/audio/transcriptions" \
  -H "X-API-KEY: $API_KEY" \
  -F "file=@/abs/path/to/audio.m4a" \
  -F "model=whisper-1" \
  -F "response_format=json" \
  -F "segment=true" -F "seg_K=6"

# TTS (JWT)
curl -X POST "http://127.0.0.1:8000/api/v1/audio/speech" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"tts-1","input":"Hello world","voice":"alloy","response_format":"mp3","stream":false}' \
  --output speech.mp3

# TTS (Single-user API key)
curl -X POST "http://127.0.0.1:8000/api/v1/audio/speech" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"tts-1","input":"Testing TTS","voice":"alloy","response_format":"wav"}' \
  --output speech.wav

# Voices catalog (JWT)
curl -s "http://127.0.0.1:8000/api/v1/audio/voices/catalog" \
  -H "Authorization: Bearer $TOKEN" | jq .

# Voices catalog (Single-user API key, filtered)
curl -s "http://127.0.0.1:8000/api/v1/audio/voices/catalog?provider=elevenlabs" \
  -H "X-API-KEY: $API_KEY" | jq .
```

### Rate Limits & Backoff
- Typical limits (subject to server config): RAG search ≈ 30/min, RAG batch ≈ 10/min, STT ≈ 20/min, TTS ≈ 10/min. Back off on 429 and honor the `Retry-After` header.
- Show user-friendly retry timing (e.g., countdown) based on `Retry-After`. Avoid infinite retries on 5xx/network; cap attempts and use exponential backoff with jitter.

References:
- RAG limits: `tldw_Server_API/app/api/v1/endpoints/rag_unified.py` (limit_search 30/min, limit_batch 10/min)
- STT limit: `tldw_Server_API/app/api/v1/endpoints/audio.py:461` (20/min)
- TTS limit: `tldw_Server_API/app/api/v1/endpoints/audio.py` (10/min)

Example (bounded backoff wrapper, MV3 background):
```ts
export async function backoffFetch(
  input: RequestInfo,
  init: RequestInit = {},
  opts: { maxRetries?: number; baseDelayMs?: number } = {}
): Promise<Response> {
  const maxRetries = opts.maxRetries ?? 2; // keep small to avoid user surprise
  const base = opts.baseDelayMs ?? 300;
  let attempt = 0;
  // Copy headers so we can mutate between retries
  const headers = new Headers(init.headers || {});

  while (true) {
    let res: Response | null = null;
    try {
      res = await fetch(input, { ...init, headers });
    } catch (e) {
      // Network error: retry with backoff (bounded)
      if (attempt >= maxRetries) throw e;
      const jitter = 0.8 + Math.random() * 0.4;
      await new Promise(r => setTimeout(r, Math.pow(2, attempt) * base * jitter));
      attempt++; continue;
    }

    if (res.status === 429) {
      // Honor Retry-After
      const ra = res.headers.get('Retry-After');
      const waitSec = ra ? Math.max(0, parseInt(ra, 10)) : Math.pow(2, attempt) * (base / 1000);
      // Emit UI hint: next retry time (optional message bus)
      // port?.postMessage({ type: 'retry-after', seconds: waitSec });
      if (attempt >= maxRetries) return res; // surface to UI if we’ve already retried
      await new Promise(r => setTimeout(r, waitSec * 1000));
      attempt++; continue;
    }

    if (res.status >= 500 && res.status < 600) {
      if (attempt >= maxRetries) return res; // bubble to UI
      const jitter = 0.8 + Math.random() * 0.4;
      await new Promise(r => setTimeout(r, Math.pow(2, attempt) * base * jitter));
      attempt++; continue;
    }

    return res; // 2xx/3xx/4xx (non-429) -> caller handles
  }
}
```

#### Backoff + Auth Wrapper (centralized)
```ts
// Uses single-flight refresh + backoffFetch for rate limits and transient errors
export async function apiFetch(
  input: RequestInfo,
  init: RequestInit = {},
  opts: { backoff?: { maxRetries?: number; baseDelayMs?: number } } = {}
): Promise<Response> {
  const headers = new Headers(init.headers || {});
  if (!headers.has('X-Request-ID')) headers.set('X-Request-ID', crypto.randomUUID());

  // Attach auth
  if (authMode === 'single_user') {
    const { api_key } = await chrome.storage.local.get('api_key');
    if (api_key) headers.set('X-API-KEY', api_key as string);
  } else {
    const token = await refreshAccessTokenSingleFlight();
    headers.set('Authorization', `Bearer ${token}`);
  }

  const doFetch = () => backoffFetch(input, { ...init, headers }, opts.backoff);

  // First attempt with current token/key and bounded backoff
  let res = await doFetch();

  // On 401, attempt a single refresh + retry (multi-user only)
  if (res.status === 401 && authMode === 'multi_user') {
    try {
      const token = await refreshAccessTokenSingleFlight();
      headers.set('Authorization', `Bearer ${token}`);
      res = await doFetch();
    } catch {
      // Return original 401 if refresh fails
    }
  }
  return res;
}

// Note: For SSE/NDJSON streaming, use the streaming helpers to initiate the
// connection (optional single attempt with backoff on connect). Do not auto-retry
// mid-stream to avoid duplicating streamed content.
```

### Notes/Prompts Concurrency & Shapes
- Notes optimistic concurrency: `PUT/PATCH/DELETE /api/v1/notes/{id}` require the `expected-version` header. On HTTP 409, refetch the note to get the latest `version` and retry the operation with the updated header. Reference: `tldw_Server_API/app/api/v1/endpoints/notes.py:347`.
- Notes search: `GET /api/v1/notes/search/?query=...` with optional `limit`, `offset`, `include_keywords`. Returns a list of notes (NoteResponse). The notes list endpoint (`GET /api/v1/notes/`) returns an object with `notes/items/results` aliases for back‑compat along with `count/limit/offset/total`. Reference: `tldw_Server_API/app/api/v1/endpoints/notes.py:480`.
- Prompts keywords: create via `POST /api/v1/prompts/keywords/` with JSON `{ "keyword_text": "..." }`. Reference: `tldw_Server_API/app/api/v1/endpoints/prompts.py:240`.

#### Quick Examples (curl)
```bash
# Notes search (JWT)
curl -s "http://127.0.0.1:8000/api/v1/notes/search/?query=project&limit=5&include_keywords=true" \
  -H "Authorization: Bearer $TOKEN" | jq .

# Notes update with optimistic locking (X-API-KEY)
NOTE_ID="abc123"
CURR=$(curl -s "http://127.0.0.1:8000/api/v1/notes/$NOTE_ID" -H "X-API-KEY: $API_KEY")
VER=$(echo "$CURR" | jq -r .version)
curl -s -X PUT "http://127.0.0.1:8000/api/v1/notes/$NOTE_ID" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -H "expected-version: $VER" \
  -d '{"title":"Updated Title"}' | jq .

# Prompts keyword create (JWT)
curl -s -X POST "http://127.0.0.1:8000/api/v1/prompts/keywords/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"keyword_text":"writing"}' | jq .
```

### Chat
- Support `stream: true|false`, model selection, and OpenAI‑compatible request fields.
- Pause/cancel active streams; display partial tokens.
- Error UX: connection lost, server errors, token expiration.
- SSE streaming must detect and handle the `[DONE]` sentinel to terminate cleanly; keep the service worker alive during streams (e.g., via a long‑lived Port from the side panel).

### RAG
- Query field, minimal filters; result list with snippet, source, timestamp.
- Insert selected snippets into chat as system/context or user attachment.

### Media Ingestion
- Current tab URL ingestion; allow manual URL input.
- Show progress/toasts and final status; handle failures gracefully.
- Display progress logs from the server response where present; if a job identifier is returned, poll status with exponential backoff and provide cancel.

### Notes and Prompts
- Create note from selection or input; tag and search.
- Browse/import/export prompts; insert prompt into chat.

### STT
- Upload short audio (<= 25 MB MVP); show transcript with copy.
- Validate mime types; surface server validation errors.

### TTS (v1)
- Voice list fetch; synthesize short text; playback controls; save last voice.

## Non‑Functional Requirements

### Security & Privacy
- No telemetry; no content analytics; local‑only diagnostics toggled by user.
- Keep access tokens in memory in background; persist refresh tokens only if required.
- Never expose tokens to content scripts; sanitize logs.

### Performance
- Background memory budget < 50 MB steady‑state.
- Chat stream first token < 1.5s on LAN server.
- Bundle size targets: side panel < 500 KB gz (MVP); route‑level code splitting.

### Reliability
- Resilient to server restarts; retries with backoff; idempotent UI state.
- Offline queue for small writes (e.g., notes) with visible status.

### Compatibility
- Chrome/Edge MV3 using service worker; Firefox MV2 fallback.
- Feature‑detect offscreen API; don’t hard‑rely on it.

### Accessibility & i18n
- Keyboard navigation, ARIA roles for side panel.
- Strings ready for localization; English default.

## Architecture Overview

### Background/Service Worker
- Central fetch proxy, SSE parsing, retries, 401 refresh queue, permission prompts.

### UI Surfaces
- Side panel (chat, RAG, notes/prompts, STT/TTS).
- Options page (server/auth/settings).
- Popup (quick actions/status).

### Content Script
- Selection capture; page metadata for ingest; no secret handling.

### State & Storage Policy
- Background state store; message bus to UIs; `chrome.storage` for non‑sensitive prefs.
- Do not store user content by default beyond session state.
- Optional local cache for small artifacts with TTL and user clear.
- Persist only refresh tokens (encrypted at rest if available) in `chrome.storage.local`; keep access tokens ephemeral (memory or `chrome.storage.session`).

## CORS & Server Config
- Prefer background‑origin requests with explicit `host_permissions`/`optional_host_permissions`.
- Server should allow CORS for the extension origin; for dev, wildcard allowed on localhost.
- Avoid blocking `webRequest` in MV3; use direct fetch and headers in background.

## Success Metrics
- 80%+ users complete setup within 2 minutes.
- < 5% request error rate in normal operation.
- Streaming starts within 1.5s on LAN; steady memory < 50 MB.
- > 90% of API paths hit without 307 redirects (path hygiene).

## Milestones and Deliverables

### Milestone 1: Connectivity & Auth (Week 1–2)
- Options page with server URL and auth.
- Background proxy with health check.
- Acceptance: Successful health ping; auth tokens handled; 401 refresh working.

### Milestone 2: Chat & Models (Week 3–4)
- Fetch providers/models; chat non‑stream and stream; cancel.
- Acceptance: Streaming chat across at least two models; SSE cancel; exact path matching.

### Milestone 3: RAG & Media (Week 5–6)
- RAG search with snippet insertion; URL ingest with progress.
- Acceptance: RAG returns results; snippet insert; ingest completes with status notifications.

### Milestone 4: Notes/Prompts & STT (Week 7–8)
- Notes CRUD + search; prompts browse/import/export; STT upload/transcribe.
- Acceptance: Notes searchable; prompts import/export; successful transcript for a ~20s clip.

### Milestone 5: TTS & Polish (Week 9–10)
- TTS synthesis/playback; voice list; UX polish and accessibility checks.
- Acceptance: Voice picker works; playable audio from `/api/v1/audio/speech`.

## Acceptance Criteria (Key)
- Path Hygiene: All requests hit exact API paths defined by OpenAPI; no 307s observed in logs.
- Security: Tokens never appear in UI or console logs; content scripts lack access to tokens.
- SSE: Streaming responses parsed without memory leaks; recognizes `[DONE]`; cancel stops network within ~200ms.
- Retry/Refresh: 401 triggers single‑flight refresh; queued requests replay once; exponential backoff with jitter for network errors.
- Permissions: Optional host permissions requested only for user‑configured origin; revocation handled gracefully.
- Media: Ingest current tab URL; show progress and final status; errors actionable.
- STT/TTS: Supported formats accepted; errors surfaced with clear messages.
- 429 Handling: Honors `Retry-After` on rate limits; UI presents retry timing.
- Streaming Memory: No unbounded memory growth during 5‑minute continuous streams; remains within budget.

## Dependencies
- Server availability and correct CORS config.
- Accurate OpenAPI spec and stability of endpoints.
- Browser APIs: `storage`, `side_panel`, `contextMenus`, `notifications`, `offscreen` (optional), message passing.

## Risks & Mitigations
- Endpoint variance (e.g., trailing slashes): Centralize route constants; validate against OpenAPI on startup and warn.
- Large uploads: Enforce size caps in UI; add chunking later if required.
- Firefox MV2 constraints: Document broader host permissions; polyfill SSE parsing if needed.

## Out of Scope (for MVP)
- Full chat history sync with server.
- Advanced MCP tools integration.
- Batch operations and resumable uploads.

## Resolved Decisions
- Canonical API key header: `X-API-KEY` (single‑user). Multi‑user uses `Authorization: Bearer <token>`.
- Model discovery: Prefer `GET /api/v1/llm/providers` (authoritative provider→models); `GET /api/v1/llm/models` available as aggregate.
- Trailing slashes: See “Trailing Slash Rules (Notes/Prompts)” above (notes search and collections require trailing slash; prompts base/search do not).
- Dev HTTPS: Prefer HTTP on localhost; for HTTPS, trust a local CA or enable Chrome’s localhost invalid‑cert exception; ensure server CORS allows the extension origin.

## Developer Validation Checklist
- Connectivity & Auth
  - Set server URL and verify `GET /api/v1/health` succeeds.
  - Single‑user: requests with `X-API-KEY` succeed; Multi‑user: login/refresh/logout succeeds and access token auto‑refreshes after service worker suspend/resume.
- Path Hygiene
  - All calls are 2xx without redirects (no 307); Notes/Prompts follow trailing‑slash rules.
- Chat
  - Non‑stream and SSE stream both work; `[DONE]` handled; cancel closes network <200ms; models list loads from `/api/v1/llm/providers`.
- RAG
  - `POST /api/v1/rag/search` returns results; `GET /api/v1/rag/simple` works; `POST /api/v1/rag/search/stream` NDJSON parsed correctly.
- Media
  - Current tab URL ingest works; progress logs displayed; failures surface actionable errors; job polling (if job id present) functions with backoff.
- Notes & Prompts
  - Notes CRUD + `GET /api/v1/notes/search/` (with slash) work; Prompts base/search work; keywords endpoints reachable.
- Audio
  - STT accepts <= 25 MB and returns transcript; TTS synthesizes and plays; voices catalog fetched.
- Reliability
  - 429 responses respect `Retry-After`; 5xx/network use exponential backoff with jitter; offline queue for small writes visible.
- Permissions
  - Only the configured server origin is granted host permission; revocation handled gracefully.
- CORS/HTTPS
  - Extension origin allowed by server; dev HTTP works; dev HTTPS usable with trusted cert or localhost exception.
- Metrics/Headers
  - `X-Request-ID` sent on requests and echoed; `traceparent` present in responses.
- Performance
  - Background steady memory < 50 MB; streaming memory stable over 5 minutes; first chat token < 1.5s on LAN.

## Glossary
- SSE: Server‑Sent Events; streaming over HTTP.
- MV3: Chrome Manifest V3.
- Background Proxy: Service worker owning all network I/O and auth.
