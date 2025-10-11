# Email Ingest Plan 1

Goal: Add first‑class support for ingesting and parsing emails (EML, optionally MSG/P7M) into the existing media pipeline, producing searchable content and rich metadata, with safe handling of attachments.

## Scope
- Accept `.eml` uploads (phase 1), extract text/HTML body, headers, and key fields: From, To, CC, BCC, Subject, Date, Message‑ID.
- Persist extracted content and metadata via existing media ingestion flow; make content searchable (FTS5) and eligible for RAG chunking/analysis.
- Safely enumerate attachments and include their metadata; optionally ingest texty attachments as child documents (behind a flag in phase 2).
- Optional/Phase 2: MSG (`.msg`) parsing, S/MIME (`.p7m`) envelope handling (signature stripping), nested emails, charset edge cases.

Out of Scope (for v1):
- Full S/MIME verification, DKIM/ARC verification, spam/phishing analysis.
- Email download (IMAP/Graph) connectors; this plan focuses on file uploads only.

Assumptions
- No DB schema change required; store email‑specific fields in `metadata` JSON and persist extracted body as `content`.
- Reuse standard library `email` for EML; defer heavy optional deps for MSG/Rich‑Text to phase 2.
- Follow project conventions for processors and endpoints under `Ingestion_Media_Processing` and `/api/v1/endpoints/media.py`.

## Architecture Overview
- Parser: `tldw_Server_API/app/core/Ingestion_Media_Processing/Email/Email_Processing_Lib.py`
  - `parse_eml(file_bytes: bytes, filename: str, *, max_depth:int=1, parse_only_headers:bool=False) -> Dict`
  - Walk MIME tree; collect plain text and HTML (prefer HTML->text fallback where needed), normalize encodings, unfold headers.
  - Collect `attachments` metadata list: name, content‑type, size, content‑id, disposition. Phase 2: return bytes for texty attachments behind a flag.
  - Return a normalized result dict compatible with existing ingestion contract: `{ content, metadata, summary?, keywords?, analysis_details?, warnings? }`.
- Dispatcher: Extend media processing endpoint to route `media_type == 'email'` to the new email processor.
- Validation: Allow `.eml` (phase 1) and later `.msg`/`.p7m` via `FileValidator` configuration; MIME sniff via existing validator.
- Persistence: Use existing persistence logic in `media.py` so email body lands in FTS and metadata is retained.
- RAG: Chunking applies to the extracted `content` as with other documents; keep chunk defaults from `document`.

## Data Model (metadata)
- `metadata.email`: object with
  - `from`, `to`, `cc`, `bcc`, `subject`, `date`, `message_id`, `headers_map` (flattened), `format` (content‑type)
  - `attachments`: list of `{ name, content_type, size, content_id, disposition }`
  - `parser_used`: `"builtin-email"` (phase 1) | `"msg-ole"` (phase 2)

## API Additions
- New processing‑only endpoint: `POST /api/v1/media/process-emails` (mirrors `/process-documents` but for emails).
  - Form model: `ProcessEmailsForm(AddMediaForm)` with `media_type: Literal['email'] = 'email'`.
  - Accept uploads (URLs optional and likely unused).
- General ingest: extend main `/api/v1/media/add` flow to accept `media_type='email'` and map to the email processor.

## Security & Safety
- Update `FileValidator`:
  - Add new media type config `email` allowing `['.eml']` in phase 1; later `['.eml', '.msg', '.p7m']`.
  - For attachments, do not write to disk nor persist raw bytes by default; only surface metadata unless explicitly enabled.
- Strip dangerous HTML elements when converting to text (phase 2); sanitize HTML output or store as‑is but not rendered.
- Enforce size limits for email and attachment enumeration timeouts.

## Error Handling
- Return meaningful errors for: bad format, empty content, malformed MIME, unsupported charset.
- Fallbacks: if only HTML exists, extract text via simple tag remover (phase 1) or robust conversion later.

## Performance
- Linear MIME traversal; no external calls in phase 1.
- Respect existing chunking defaults; no special streaming needed.

## Implementation Stages

### Stage 1: Minimal EML parsing (v1)
Goal: End‑to‑end parsing for `.eml` uploads with safe metadata and content persistence.
Success Criteria:
- Uploading an `.eml` via `/media/add` with `media_type=email` yields `status=Success`, persists `content` with subject present in metadata, and is retrievable via search.
- Unit tests pass for header decoding, folded headers, basic multipart with attachments (metadata only), and HTML/plain.
Tests:
- Unit: parser returns expected fields for sample EMLs (UTF‑8, BOM, folded headers, multipart/alternative).
- Integration: `/process-emails` and `/media/add` round‑trip stores content and metadata; RAG chunk count > 0 when chunking enabled.
Tasks:
- Create `Email/Email_Processing_Lib.py` with `parse_eml` and `process_email_task(file_bytes, filename, ...)` that returns the normalized dict consumed by `media.py`.
- Extend `FileValidator.DEFAULT_MEDIA_TYPE_CONFIG` and `EXT_TO_MEDIA_TYPE_KEY` with `email` and `['.eml']`.
- In `media.py`, add dispatch: `elif media_type == 'email': processing_func = email_lib.process_email_task`.
- Add `ProcessEmailsForm` + `get_process_emails_form` and new endpoint `/process-emails` (processing only, no DB).
- Unit tests for parser; small integration tests mirroring document flow.

### Stage 2: Attachments and nested emails
Goal: Support nested `message/rfc822` and attachment promotion (optional child docs).
Success Criteria:
- EML with attached EML produces 2 records in processing‑only response; in DB flow, parent persists, and child ingestion is optionally created when `ingest_attachments=true`.
Tests:
- Unit: nested parts traversal; attachment list contains correct names and content‑types.
- Integration: flag‑controlled child ingestion; parent retains `attachments` metadata with child linkage IDs.
Tasks:
- Add `ingest_attachments: bool=False` option; on true, create child ingestion jobs for texty attachments (txt/html/md/pdf/eml) using existing processors.

### Stage 3: MSG and S/MIME (optional)
Goal: Provide optional `.msg` and `.p7m` support behind extras.
Success Criteria:
- `.msg` parses basic headers and body; `.p7m` envelope (signed) yields underlying message when OpenSSL available; graceful fallback otherwise.
Tests:
- Unit: sample `.msg` with plain/html and attachments.
- Integration: `.p7m` with signature only surfaces metadata/warning if not decryptable.
Tasks:
- Introduce optional deps: `olefile`, `compressed_rtf`, `chardet`; feature flag `ENABLE_MSG_PARSING`.
- Implement `parse_msg()` behind try/except; map into same normalized dict.

### Stage 4: HTML normalization and charset hardening
Goal: Improve HTML→text, sanitize HTML, and add robust charset handling.
Success Criteria:
- HTML bodies are converted to readable text; unknown‑8bit/broken charsets don’t crash; warnings emitted.
Tasks:
- Add lightweight sanitizer and fallback decoding paths.

## File Changes (planned)
- New: `tldw_Server_API/app/core/Ingestion_Media_Processing/Email/Email_Processing_Lib.py`
- Update: `tldw_Server_API/app/api/v1/endpoints/media.py` (dispatch + new `/process-emails`)
- Update: `tldw_Server_API/app/core/Ingestion_Media_Processing/Upload_Sink.py` (validator: email type and ext map)
- New tests:
  - `tldw_Server_API/tests/Email/test_eml_parser.py`
  - `tldw_Server_API/tests/Email/test_process_emails_endpoint.py`

## Rollout & Config
- Default enabled for `.eml`; MSG/P7M behind config flags.
- No migration required; docs updated under Docs/API and Docs/Code_Documentation.

## Risks / Mitigations
- Malformed MIME trees: use defensive traversal + exceptions → warnings.
- Large attachments: enumerate only metadata by default; gate promotion behind a flag and size limits.
- Dependency bloat for MSG: keep optional, lazy‑imported.

## Open Questions
- Should email be its own `media_type` or ride `document`? Plan proposes distinct `email` for clarity and validation; easy to merge into `document` if preferred.
- Attachment promotion defaults: default off; confirm desired UI/UX in WebUI.

---

## Stage Tracking

### Stage 1: Minimal EML parsing (v1)
Status: Complete
Notes:
- Implemented parser and processing task: `Email_Processing_Lib.py`.
- Integrated into `/media/add` and added `/process-emails` endpoint.
- Unit and integration tests added.

### Stage 2: Attachments and nested emails
Status: In Progress
Notes:
- Implemented nested `.eml` traversal and optional child persistence via `ingest_attachments` + `max_depth`.
- Grouping keyword `email_group:<Message-ID>` applied to parent/children when child ingest is enabled.
- Current scope ingests only attached `.eml` as children (metadata collected for other attachment types; ingestion of "texty" non-EML attachments is deferred).

### Stage 3: MSG and S/MIME (optional)
Status: Not Started

### Stage 4: HTML normalization and charset hardening
Status: Not Started
