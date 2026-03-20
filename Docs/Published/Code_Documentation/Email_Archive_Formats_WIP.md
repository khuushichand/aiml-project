# Email Archive Formats - WIP Design Notes

Status: Draft/WIP
Owner: Ingestion/Email pipeline
Last updated: 2025-10-11

## Context

Phase A (done): zip of .eml support with guardrails is implemented and tested for:
- POST `/api/v1/media/process-emails` (flattened children results)
- POST `/api/v1/media/add` (synthetic parent; child emails persisted)

This note sketches Phase B/C for additional email archive formats: MBOX and PST/OST.

## Goals

- Add ingestion of common email archive formats beyond individual `.eml` and `.zip` of EMLs.
- Maintain safety and performance guardrails comparable to current archive scanning.
- Reuse the existing email parsing pipeline so downstream behavior (chunking, analysis, persistence) stays consistent.

## Non-Goals (for now)

- Full fidelity export of all proprietary metadata from PST/OST.
- Arbitrary nested archive formats or multi-level compression.

## Formats

1) MBOX (`.mbox`, `.mbx`)
- Parser: Python `mailbox.mbox`.
- Strategy: iterate messages; for each, get bytes and feed our existing `process_email_task`/`parse_eml_bytes`.
- Grouping: add keyword `email_mbox:<file_stem>` to each child and parent.
- Limits: message count cap; cumulative byte cap; early stop with warnings.

2) PST/OST (Microsoft Outlook)
- Parser options:
  - Python: `pypff` / `libpff` (native dep)
  - External: `readpst` CLI (parse to mbox or eml); invoke with a sandboxed subprocess where allowed
- Strategy: extract mail items to bytes (EML if available; or reconstruct MIME from fields when needed). Feed each to `process_email_task`.
- Grouping: `email_pst:<file_stem>`
- Limits: item count and total extracted size; configurable.
- Deployment note: PST is heavier and should be feature-flagged/optional due to dependencies.

## API Contract Options

- Keep current opt-in flag for ZIP: `accept_archives=true`.
- Introduce opt-ins per format to avoid surprising behavior:
  - `accept_mbox: bool = false`
  - `accept_pst: bool = false` (or `accept_outlook`)

Alternatively, a single `archive_formats: List[str]` field (e.g., `["zip_eml","mbox","pst"]`).

Minimal viable next step: add `accept_mbox` behind which `.mbox` becomes allowed for `media_type=email`.

## Validation & Guardrails

- ZIP (existing): enforce max member files and max uncompressed bytes.
- MBOX: enforce max messages and max cumulative bytes read; stop + warn on exceed.
- PST: enforce max items and max bytes; consider denying large attachments by policy.
- Skip non-EML payloads for ZIP; for MBOX/PST only treat recognizable mail items.
- Ensure filenames and content are decoded safely; normalize newlines.

## Processing Flow (per format)

Common steps:
- Read container → iterate children → child_bytes → `process_email_task(...)`
- Add grouping keyword to each child result.
- `/process-emails`: return child list.
- `/media/add`: synthetic parent with `children`, persist children; reflect grouping keyword(s) on parent.

MBOX specifics:
- `mailbox.mbox(path)` → for each message `m`, use `m.as_bytes()` if available; else rebuild from headers+payload.
- Track counters and size; stop on limits.

PST specifics:
- If using `pypff`, walk folders; for each mail item, convert to EML bytes (if available) or compose MIME.
- If using `readpst`, run once to convert to mbox/eml in a temp dir and then process as MBOX/EML; clean up temp files.
- Wrap subprocess with timeouts and size caps; make it optional.

## Keywording & Metadata

- Children: include `email_mbox:<stem>` or `email_pst:<stem>`.
- Parent: reflect final keywords (includes grouping tag) for discoverability/UI filters.
- Preserve existing email metadata mapping (subject, from, to, date, message-id, etc.).

## Configuration

- Add format-specific caps to the existing upload/validation config (similar to `archive` section):
  - `max_internal_files` / `max_messages`
  - `max_internal_uncompressed_size_mb`
  - `pst.enabled` (bool), `pst.handler` ("pypff" | "readpst")

## Testing Plan

- Unit tests for new archive readers:
  - Small `.mbox` containing 2 trivial messages → both parsed; subjects extracted; grouping keyword present.
  - Oversized `.mbox` → error/warning path with clear message.
- Integration tests for endpoints:
  - `/process-emails` with `.mbox` + `accept_mbox=true` → returns children; keywords include `email_mbox:<stem>`.
  - `/media/add` with `.mbox` + `accept_mbox=true` → children persisted; parent reflects grouping keyword; child DB rows created.
- (Optional) PST tests behind marker `external_api` or `local_llm_service`, skipped by default unless deps available.

## Risks & Considerations

- PST parsing reliability varies; prefer explicit feature flag and clear errors.
- Performance: large containers can be slow; keep caps conservative by default.
- Encoding edge cases: ensure robust handling of charsets and malformed inputs.
- Security: continue to ignore executables/binaries in containers; maintain SSRF/file path safety.

## Incremental Plan

1. Add `accept_mbox` flag and `.mbox` acceptance; implement mbox reader with guardrails.
2. Mirror parent/child persistence pattern + grouping keyword (done for ZIP; reuse pattern).
3. Add tests and docs for MBOX.
4. (Optional) Add PST behind `accept_pst` with `pypff` or `readpst` integration.

## References

- Python `mailbox` docs: https://docs.python.org/3/library/mailbox.html
- libpff / pypff: https://github.com/libyal/libpff
- readpst: https://www.five-ten-sg.com/libpst/
