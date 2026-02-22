# Chat Dictionaries Guide

## What This Feature Does

Chat Dictionaries let you transform text before model processing using literal or regex-based entries. Typical uses:

- Expand abbreviations (`BP` -> `blood pressure`)
- Normalize terminology (`ETA` -> `estimated time of arrival`)
- Apply style/roleplay text conventions

## Quick Start with Starter Templates

When creating a new dictionary, choose an optional **Starter Template**:

- `Medical Abbreviations`
- `Chat Speak Translator`
- `Custom Terminology`

Templates prefill example entries so you can edit instead of building from zero.

## Organize Dictionaries with Category and Tags

Use dictionary metadata fields in create/edit:

- `Category`: one broad grouping (example: `Medical`, `Roleplay`, `Product`)
- `Tags`: free-form searchable labels (example: `clinical`, `abbreviations`, `support`)

The list view supports metadata-aware filtering/search, so consistent tagging improves discoverability.

## Keyboard Shortcuts

- `Ctrl/Cmd + N`: open **New Dictionary**
- `Ctrl/Cmd + Enter`: submit open dictionary or entry form
- `Ctrl/Cmd + Shift + V`: open validation panel and run validation (entry manager)

Notes:

- Shortcuts are ignored while typing inside text inputs/textareas.
- `Cmd` works on macOS, `Ctrl` on Windows/Linux.

## Regex Helper (Entry Authoring)

When entry type is `regex`, use these common patterns:

- `.*` means any text
- `\b` means word boundary
- `(group)` creates capture groups you can reuse as `$1`, `$2` in replacement text

Example:

- Pattern: `\bKCl\b`
- Replacement: `potassium chloride`

Regex safety:

- Client-side syntax checks run while authoring.
- Server-side validation is also used to catch unsafe patterns (including ReDoS-style risks).

## Composition (Include Other Dictionaries)

Dictionaries support include semantics through `included_dictionary_ids` (API-level metadata):

- Included dictionaries run before the including dictionary.
- Include cycles are rejected.
- Includes are validated against existing dictionary IDs.

This allows a base dictionary plus specialized overlays without duplicating entries.

## Version History and Revert

Version snapshots are stored for dictionary lifecycle actions (create/update/import/reorder/clone/revert). You can:

- List history: `GET /api/v1/chat/dictionaries/{dictionary_id}/versions`
- Read one revision: `GET /api/v1/chat/dictionaries/{dictionary_id}/versions/{revision}`
- Revert to revision: `POST /api/v1/chat/dictionaries/{dictionary_id}/versions/{revision}/revert`

Revert restores dictionary metadata and entries from that revision.

## Export Guidance

- Use `JSON` export/import for full fidelity (metadata + advanced entry fields).
- Markdown export is useful for human-readable sharing but may not preserve every advanced field with the same fidelity as JSON.

