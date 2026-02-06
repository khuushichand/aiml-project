# Character Chat Settings Metadata (Server) - PRD

## Summary
Define a server-backed metadata record for per-chat settings used by character chat enhancements, with a concrete data schema and migration plan.

## Goals
- Store per-chat settings on the server for cross-device persistence.
- Keep settings schema versioned and forward compatible.
- Support last-write-wins reconciliation with per-entry timestamps where needed.

## Non-Goals
- Replacing existing conversation or message storage.
- Moving all chat history into metadata blobs.

## Storage Model
- Add a server-side table for per-conversation settings JSON.
- Keep settings content in a single JSON object with an explicit schema version.
- Update conversation `last_modified` on settings changes to make sync and cache invalidation straightforward.

## Data Schema
Table definition:
- Table name: `conversation_settings`
- Columns:
- `conversation_id` TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE
- `settings_json` TEXT NOT NULL
- `last_modified` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP

JSON schema keys:
- `schemaVersion` integer
- `updatedAt` ISO timestamp
- `greetingSelectionId` string or null
- `greetingsVersion` integer or null
- `greetingsChecksum` string or null
- `useCharacterDefault` boolean
- `greetingEnabled` boolean
- `greetingScope` string enum `chat` or `character`
- `presetScope` string enum `chat` or `character`
- `memoryScope` string enum `shared` or `character` or `both`
- `chatPresetOverrideId` string or null
- `authorNote` string
- `characterMemoryById` object map of characterId to note payload
- `chatGenerationOverride` object or null
- `summary` object or null

Recommended `characterMemoryById` entry schema:
- `note` string
- `updatedAt` ISO timestamp

Recommended `chatGenerationOverride` schema:
- `enabled` boolean
- `temperature` number or null
- `top_p` number or null
- `repetition_penalty` number or null
- `stop` array of strings
- `updatedAt` ISO timestamp

Recommended `summary` schema:
- `enabled` boolean
- `content` string
- `sourceRange` object with `fromMessageId` and `toMessageId`
- `updatedAt` ISO timestamp

Example `settings_json`:
```json
{
  "schemaVersion": 2,
  "updatedAt": "2026-02-05T19:40:00Z",
  "greetingSelectionId": "greet_03",
  "greetingsVersion": 5,
  "greetingsChecksum": "sha256:...",
  "useCharacterDefault": false,
  "greetingEnabled": true,
  "greetingScope": "chat",
  "presetScope": "character",
  "memoryScope": "shared",
  "chatPresetOverrideId": null,
  "authorNote": "",
  "characterMemoryById": {
    "char_7": {
      "note": "Prefer short replies.",
      "updatedAt": "2026-02-05T19:40:00Z"
    }
  },
  "chatGenerationOverride": {
    "enabled": false,
    "temperature": 0.7,
    "top_p": 0.9,
    "repetition_penalty": 1.05,
    "stop": [],
    "updatedAt": "2026-02-05T19:40:00Z"
  },
  "summary": {
    "enabled": true,
    "content": "Summary of earlier turns...",
    "sourceRange": {"fromMessageId": "m1", "toMessageId": "m20"},
    "updatedAt": "2026-02-05T19:40:00Z"
  }
}
```

## API and Integration
- Extend conversation fetch endpoints to optionally include `settings_json`.
- Add or extend a settings update endpoint to upsert `conversation_settings` by `conversation_id`.
- On settings update, bump `conversation.last_modified` and `conversation.version` to trigger sync and cache invalidation.

## Sync and Conflict Resolution
- Use last-write-wins for top-level fields based on `updatedAt`.
- For map merges such as `characterMemoryById`, use per-entry `updatedAt` when present.
- Tie-breaker when timestamps are missing or equal: server wins for server-backed chats, local wins for local-only chats.

## Migration Plan
1. Schema migration to create `conversation_settings` table.
2. Add DB helpers to upsert and fetch settings by conversation ID.
3. Add API read and write endpoints for settings.
4. Client migration reads local per-chat settings and pushes to server when a serverChatId exists.
5. On first sync, if server has no settings, push local. If both exist, merge using last-write-wins and persist merged to server.
6. For one release, keep a backward-compat read path from legacy local keys to populate settings once.

## Backward Compatibility
- `schemaVersion` defaults to 1 when absent and is set to 2 for new records.
- Older clients ignore settings they do not recognize.
- Server accepts unknown keys and preserves them on update.

## Security and Validation
- Validate JSON structure and enum values server-side.
- Enforce size limits on `settings_json` and `authorNote` fields.
- Reject malformed JSON with actionable error responses.

## Testing
- Unit tests for settings upsert, fetch, and merge logic.
- Integration tests for sync conflict resolution on first login.
- Regression tests ensuring existing conversations render with no settings present.
