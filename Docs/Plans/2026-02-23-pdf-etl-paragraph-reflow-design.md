# PDF ETL Paragraph Reflow Design

## Metadata
- Date: 2026-02-23
- Status: `agreed-and-ready`
- Tags: `agreed`, `ready`, `pdf`, `etl`, `normalization`, `ingestion`
- Scope: Newly ingested PDFs only
- Decision Owner: User + Codex session

## Problem
Current PDF ingestion can preserve soft line wraps from extraction output, producing paragraph text like:

```text
...models that perform well on a
single physical task...
```

Target is canonical flowed paragraph text:

```text
...models that perform well on a single physical task...
```

without damaging structure (headings, lists, tables, code fences, page markers).

## Goals
1. Store canonical flowed paragraph text at ingest time.
2. Apply the same behavior across all PDF parsers: `pymupdf4llm`, `pymupdf`, and `docling`.
3. Preserve markdown/document structure while fixing soft line wraps.
4. Keep downstream chunking/search/analysis behavior deterministic.

## Non-Goals
1. Backfilling existing ingested items.
2. UI-only normalization as the source of truth.
3. Parser-specific behavior divergence for this first pass.

## Approaches Considered

### 1. Shared normalization stage after extraction (Recommended)
- One normalization function runs after parser extraction (and after OCR merge when applicable) and before chunking/persistence.
- Pros: consistent behavior, easiest to test/maintain, single policy surface.
- Cons: requires robust structure detection.

### 2. Parser-specific normalization
- Each parser manages its own reflow policy.
- Pros: per-parser tuning.
- Cons: duplicated logic and long-term drift risk.

### 3. UI-only reflow fallback
- Keep stored text mostly untouched, flow only at display.
- Pros: low ETL risk.
- Cons: inconsistent storage/retrieval/chunking; rejected based on agreed requirements.

## Agreed Architecture

Add one shared ingest-time normalizer in the PDF processing path:

1. `normalize_pdf_text_for_storage(text: str) -> str` as the single entrypoint.
2. Internal block classifier to detect structural lines/blocks.
3. Paragraph reflow function for non-structural paragraph blocks.
4. Light instrumentation for observability.

Integration point:
- `tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/PDF_Processing_Lib.py`
- Run after parser output is finalized (including OCR append/replace) and before chunking/analysis/persist.

## Agreed Data Flow

For each newly ingested PDF:

1. Extract text using selected parser (`pymupdf4llm`/`pymupdf`/`docling`).
2. Merge OCR result if enabled.
3. Normalize final text via `normalize_pdf_text_for_storage`.
4. Send normalized text to chunking.
5. Persist normalized text as canonical `content`.

## Normalization Rules (Paragraph-Safe)

1. Newline baseline:
- Convert `\r\n` to `\n`.

2. Preserve structural blocks unchanged:
- Markdown headings: `#`, `##`, `###`...
- List items: unordered and ordered markers.
- Blockquotes (`>`).
- Fenced code blocks and content inside them.
- Table-like row blocks.
- Explicit page markers/separators (e.g., `## Page <n>`, `---`).

3. Paragraph block detection:
- Consecutive non-empty, non-structural lines form a paragraph block.
- Replace single newlines inside a paragraph block with one space.
- Preserve one blank line between blocks.

4. Hyphenation repair:
- If a line ends with hyphen and next token begins lowercase alpha, join with no space.
- Otherwise join with one space.

5. Whitespace control:
- Collapse repeated spaces/tabs to a single space inside paragraph blocks.
- Keep output idempotent (second pass yields same result).

6. Safety guardrails:
- Skip reflow for suspicious artifact-heavy blocks (high delimiter density or likely table/math/code noise).

## Error Handling
1. Normalizer must fail soft: if normalization raises, log warning and continue with original extracted text for that item.
2. Metrics/log context should include parser used, chars before/after, and fallback reason (if any).

## Testing Strategy

### Unit Tests
1. Joins soft-wrapped paragraph lines into one sentence.
2. Preserves headings/lists/tables/code fences/page separators.
3. Repairs true hyphenated wraps, avoids false joins.
4. Keeps blank-line paragraph boundaries.
5. Idempotency test (`normalize(normalize(x)) == normalize(x)`).

### Integration Tests
1. `process_pdf_task(..., parser=<each parser>)` verifies normalized `content`.
2. OCR append/replace path still normalizes final merged text.
3. Chunking receives flowed text and creates stable chunks.

## Acceptance Criteria
1. Newly ingested PDFs store flowed paragraph text (no soft-wrap artifacts like media item 146 pattern).
2. Structural markdown blocks remain intact.
3. Behavior is consistent across all three parsers.
4. Existing ingested records remain untouched.
5. Test suite additions cover both happy path and structure-preservation edge cases.

## Rollout
1. Implement behind the existing PDF ingestion path (no API contract changes).
2. Ship for new ingests only.
3. Observe metrics/warnings for normalization fallback events.

## Final Decision
This design is **agreed and ready** for implementation.
