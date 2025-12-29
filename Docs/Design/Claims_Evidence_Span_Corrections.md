# Claims Evidence Span Alignment and Correction Workflow

## Summary
Improve evidence span alignment for long or irregularly formatted text and ensure reviewer corrections update stored span metadata. This reduces citation drift and preserves reviewer edits in downstream analytics and embeddings.

## Goals
- Align evidence spans when exact matching fails due to whitespace/case differences.
- Use normalized and windowed matching for long documents.
- When reviewers submit corrected claim text, update `span_start`/`span_end` if the corrected text is found in the original chunk.
- Preserve corrected text in review logs and re-embed claims when configured.

## Non-goals
- Changing verification logic or evidence retrieval ranking.
- Rewriting chunking behavior or storage schema.
- Auto-correcting claims without human input.

## Span Alignment Strategy
The alignment flow uses a best-effort matcher:
1. Exact match of claim text.
2. Exact match of snippet text (ellipsis trimmed).
3. Normalized match (case/whitespace folded) of claim/snippet.
4. Windowed match on large texts to find an anchor.
5. Fallback to a minimal span when no alignment is possible.

Normalization collapses whitespace and lowercases text while retaining an index map to produce original offsets.

## Review Corrections
When `corrected_text` is provided in review:
- The review update stores corrected text on the claim.
- The service attempts to map corrected text to the original chunk to derive `span_start`/`span_end`.
- If a span is resolved, it is persisted with the review update.
- Embeddings are refreshed when `CLAIMS_EMBED` is enabled and corrected text changes.

## Data Dependencies
Span correction uses `UnvectorizedMediaChunks` to resolve chunk text and `start_char` offsets. If chunk metadata is unavailable, the span update is skipped without failing the review update.

## Tests
- Unit tests for normalized span alignment.
- Integration test for corrected text span updates in the review endpoint.
