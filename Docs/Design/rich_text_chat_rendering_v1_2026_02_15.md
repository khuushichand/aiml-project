# Rich Text Chat Rendering v1 (SillyTavern-style Compatibility)

## Objective
Add an opt-in rich-text rendering mode for chat messages that better matches SillyTavern-style behavior while preserving safe defaults.

## Scope
This applies to the shared UI package (`apps/packages/ui`) so behavior is available in both:
- WebUI chat
- Extension chat

## Modes
1. `safe_markdown` (default)
- Current behavior using `react-markdown` + GFM + math rendering.
- No raw HTML rendering.

2. `st_compat`
- Rich markdown-to-HTML rendering with:
  - GFM-compatible markdown
  - single-line break handling (`breaks: true`)
  - inline spoiler syntax: `||spoiler||`
  - block spoiler syntax: `[spoiler]...[/spoiler]`
  - sanitized rich HTML output

## Syntax Support (v1)
- `**bold**`, `*italic*`, `~~strikethrough~~`
- code spans and fenced code blocks
- ordered/unordered lists, blockquotes
- tables/task lists (via markdown parser behavior)
- KaTeX behavior remains in `safe_markdown`; `st_compat` focuses on rich text compatibility and safety
- spoiler forms:
  - `||text||` -> inline spoiler span
  - `[spoiler]...[/spoiler]` -> `<details><summary>Spoiler</summary>...</details>`

## Safety Model
`st_compat` rendering is sanitized before insertion into DOM:
- Remove executable/unsafe tags (`script`, `style`, `iframe`, etc.)
- Remove inline event handlers (`onclick`, etc.)
- Remove unsafe URL schemes (`javascript:`, `file:`, etc.)
- Keep output constrained to safe rich HTML

Image policy:
- Existing `allowExternalImages` setting still controls remote image rendering.
- If disabled, external images are replaced by a safe placeholder with an "Open" link.

## Settings UX
Add new Chat setting:
- Label: `Rich text rendering mode`
- Values:
  - `Safe Markdown (default)`
  - `SillyTavern-compatible`
- Include a compact side-by-side preview panel in settings so users can compare both renderers on the same sample message before switching.

## Out of Scope (v1)
- Full parser parity with SillyTavern plugins/macros.
- Per-message mode override.
- Server-side markdown normalization.

## Testing
Unit tests cover:
- spoiler preprocessing
- XSS sanitization
- image blocking policy when external images are disabled
- mode normalization fallback behavior

## Rollout
Default remains `safe_markdown`; users can opt into `st_compat`.
