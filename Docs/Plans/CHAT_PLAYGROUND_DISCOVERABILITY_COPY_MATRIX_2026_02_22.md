# Chat Playground Discoverability Copy Matrix (2026-02-22)

## Purpose

Define the user-facing labels and helper copy that anchor first-use discoverability for the chat page.

## Control Copy Matrix

| Surface | Control | Label / Copy | Intent |
|---|---|---|---|
| Empty state | Primary CTA | `Start chatting` | Fast path to first send |
| Empty state | Region guide | `History (left), timeline (center), composer (bottom), Search & Context (right).` | Page IA orientation |
| Empty state | Starter card | `Compare models` | Multi-model side-by-side entry |
| Empty state | Starter card | `Character chat` | Persona entry path |
| Empty state | Starter card | `Knowledge-grounded Q&A` | RAG entry path |
| Header | New chat action | `New Saved Chat` | Persistent history session |
| Header | New chat action | `Temporary Chat` | Ephemeral/no-save mode |
| Header | New chat action | `Character Chat` | Character-first session |
| Composer placeholder | Input hint | `Type a message... (/ commands, @ mentions)` | Structured input discoverability |
| Composer context chip | Character hint | `Affects next response` semantics | Active persona clarity |
| Composer compare contract | Compare body copy | Shared prompt/context + persistence note | Compare mental model clarity |

## Telemetry Event Contract

| Event | Detail | Source |
|---|---|---|
| `tldw:playground-starter-selected` | `{ mode: "general" | "compare" | "character" | "rag" | "voice" }` | Empty-state starters + voice activation |
| `tldw:playground-starter` | `{ mode, prompt? }` | Empty-state starter action dispatch |

## Evidence

- `src/components/Option/Playground/__tests__/PlaygroundEmpty.test.tsx`
- `src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`
- Validation run (2026-02-22): `10 files / 45 tests passed` including discoverability + stage-closure suites.
