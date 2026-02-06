# Character Card Import and Export (ST v2 JSON and PNG) - PRD

## Summary
Support importing and exporting SillyTavern v2 character cards in JSON and PNG
formats with strict validation, size limits, and safe handling of untrusted
content.

## Goals
- Import ST v2 JSON and PNG cards into the character manager.
- Export characters to ST v2 JSON in MVP, and to ST v2 PNG in v2.
- Enforce schema validation, size limits, and security checks.

## Non-Goals
- Full parity with all SillyTavern metadata extensions.
- Changes to world book logic beyond linking existing entries.

## Users and Use Cases
- User imports a ST v2 card from another tool.
- Creator exports a character for portability.
- Admin wants clear validation errors on malformed cards.

## Scope
1. Stage E1 (MVP). Import ST v2 JSON and PNG with embedded JSON, export ST v2
   JSON, field mapping, validation, and size limits.
2. Stage E2. Export ST v2 PNG with embedded JSON and avatar image, plus import
   preview and confirmation showing diffs and validation errors.

## Requirements
Functional requirements:
- Import ST v2 JSON and PNG with embedded JSON chunk.
- Export current character to ST v2 JSON.
- Map fields: name, avatar, system prompt, personality, scenario, greetings,
  examples, creator notes, tags.
- Validate incoming JSON against the ST v2 card schema and reject malformed payloads.
- Enforce size limits for avatar bytes, prompt length, and total file size.
- Validate avatar MIME types (allow `image/png`, `image/jpeg`, and `image/webp` only).
- Validate PNG chunks, MIME type, and checksum for embedded JSON and avatar data.
- Sanitize and escape all imported text fields before storage or rendering.
- Report explicit validation errors and rejection reasons to the user.
- Rate limit import attempts, including failed validations, per session and per user.

Security requirements:
- Treat all imports as untrusted input and block script or prompt-injection patterns.
- Verify PNG integrity and reject malformed chunk structures.
- Store avatars with content type validation and AV scan where supported.

Non-functional requirements:
- Preserve existing character fields and world book links when possible.
- Keep import and export operations deterministic and testable.

## UX Notes
- Stage E1 provides a direct import flow with clear error messages.
- Stage E2 adds a preview confirmation showing field diffs and validation results.

## Data and Persistence
- Store imported characters in the existing character manager data model.
- Avatar storage strategy: cap size at 200KB, store in blob storage with
  content type validation and AV scan, reject oversized images.

## API and Integration
- If server-side storage is required, add endpoints to upload and validate
  cards and return structured validation errors.
- If local-only import is supported, reuse existing client storage with
  validation performed in the client.

## Edge Cases
- PNG card without embedded JSON is rejected with a specific error.
- JSON card with missing required fields is rejected with schema errors.
- Avatar data is present but exceeds size or fails MIME validation.

## Risks and Open Questions
- Locating or authoring the authoritative ST v2 schema for validation.
- Balancing strict validation with backward compatibility for older cards.

## Testing
- Unit tests for JSON schema validation and field mapping.
- Unit tests for PNG chunk parsing and checksum validation.
- Security tests for malformed PNG and JSON payloads and prompt injection patterns.
- Integration tests for import rate limits and error messaging.
- Regression tests for existing character creation flows.
