# Code Ingestion Improvements - v1

This document outlines targeted, high-impact improvements for the code ingestion pathway and structure-aware code chunking. It focuses on accuracy, metadata depth, performance, safety, and UX.

## Chunking Accuracy
- Use AST or Tree-sitter parsers per language for precise function/class boundaries, with heuristic fallback.
- Support multi-line signatures, decorators/annotations, receiver methods (Go), async defs, nested scopes.
- Harden brace tracking: ignore braces in strings/comments (C/C++/Java/JS template strings), handle macro blocks.

## Metadata Richness
- Add symbol kind, name, signature, and immediate docstring/first comment.
- Include decorators/annotations, visibility (public/private) where applicable.
- Stable chunk IDs (e.g., hash of path + start_line:end_line + symbol name).
- Per-chunk metrics: LoC, approximate cyclomatic complexity, import list, dependency hints.
- Explicit, documented semantics for line ranges (inclusive/exclusive) and character offsets.

## Adaptive Sizing
- Token-aware chunk sizing via tokenizer; adapt size by language/file type.
- Optional inter-chunk overlap; split oversized blocks at nearest blank line or symbol boundary.
- Per-language packing heuristics (e.g., keep small helper functions together).

## Language Detection
- Detect via shebang, modelines, content sniffing (Pygments/Linguist), then extension mapping.
- Better mapping for headers (.h → c/cpp), extensionless scripts, mixed TSX/JSX.

## Endpoint UX
- Accept archives (.zip) and repo URLs (git) with include/exclude globs; respect .gitignore.
- Return a batch summary (files processed, skipped, per-language counts, total chunks, warnings).
- New parameters: `max_file_size_mb`, `exclude_patterns`, `respect_gitignore`, `skip_minified`.

## RAG Integration
- Emit code-fenced text with contextual header (path, symbol breadcrumb).
- Option to use code-aware embedding models; enrich chunks with simple symbol graph (callers/callees) when available.
- Provide a “preview summary” per chunk for faster retrieval scans.

## Performance & Caching
- Memory-map reads for large files; concurrency for multi-file batches; streaming output for long runs.
- Disk-backed LRU cache keyed by (path, mtime, size, config) to reuse chunk results.
- Guardrails on total batch size and timeouts to keep latency predictable.

## Security & Validation
- Hard caps on file size/line count; configurable per endpoint.
- Robust encoding detection with safe fallbacks; reject binary/unknown encodings.
- Optional redaction of probable secrets in returned content.
- Maintain strong allowlist for extensions; audit minified files and vendored directories.

## Test Coverage
- Cases for multi-line defs, nested classes, decorators, macros, template strings, odd brace noise.
- Property tests: random brace/comment noise should not crash or cross boundaries; fuzz large files.
- Non-UTF8 encodings and extremely long lines; mixed-language files (e.g., TSX).

## Documentation
- Document code metadata schema: `chunk_method`, `language`, `start_line`, `end_line`, `blocks[]` (type/name/range), stable IDs.
- Clarify sizing semantics (chars vs. lines vs. tokens) and per-method defaults.
- Provide end-to-end examples: Python, JS/TS, C/C++, Go, Rust.

## Configurability
- Per-language defaults (size/overlap) via config.
- Toggle to include imports into first chunk only or dedupe across chunks.
- Feature flags for AST/Tree-sitter mode vs. heuristic mode.

## Future Extensions
- Build symbol/call graphs (Python `ast`, Go `go/parser`, TS via tsserver) to enable smarter retrieval.
- Auto-summaries per chunk and symbol cross-references.
- Repo-level embeddings for architectural context; dependency graph summaries.

---

Suggested first milestone: AST-backed Python chunking (precise function/class/docstring boundaries) with heuristic fallback for other languages, plus token-aware sizing and stable chunk IDs. This provides immediate quality gains with limited blast radius.
