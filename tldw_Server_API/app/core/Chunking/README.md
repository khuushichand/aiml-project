# Chunking Module – Developer README

This module provides robust, extensible text chunking for ingestion, RAG, embeddings, analytics, and downstream tasks. It includes a strategy registry, hierarchical chunking, and a template system that now supports learning rules from a “seed” document.

## Overview
- Entry point: `Chunker` in `chunker.py` (methods: `words`, `sentences`, `paragraphs`, `tokens`, `semantic`, `json`, `xml`, `ebook_chapters`, `rolling_summarize`, …).
- Template pipeline: `TemplateProcessor` and `TemplateManager` in `templates.py`.
- Built-in templates: JSON files under `template_library/`, seeded into DB by `template_initialization.py`.
- New: Seed-driven templates via learned “boundary” rules inferred from example (“seed/template”) documents.

## Layout
- `base.py` — core types and interfaces (`ChunkingMethod`, `ChunkResult`, `ChunkerConfig`, `BaseChunkingStrategy`)
- `chunker.py` — orchestrator, strategy registry, hierarchical helpers
- `strategies/` — implementation of strategies (words, sentences, tokens, structure-aware, semantic, etc.)
- `templates.py` — `TemplateProcessor`, `TemplateManager`, `TemplateClassifier`, `TemplateLearner`
- `template_initialization.py` — seeds built-in templates to DB
- `template_library/` — built-in template JSONs (auto-loaded/seeded)

## Using the Template System
Two supported template schemas:
1) Stage-based:
  {
    "name": "...",
    "base_method": "words",
    "stages": [
      { "name": "preprocess", "operations": [...] },
      { "name": "chunk", "operations": [{ "method": "sentences", "config": {...}}] },
      { "name": "postprocess", "operations": [...] }
    ],
    "default_options": { ... },
    "metadata": { ... }
  }
2) Simple (DB/file format) with explicit blocks:
  {
    "name": "...",
    "preprocessing": [ { "operation": "normalize_whitespace", "config": {...} } ],
    "chunking": { "method": "sentences", "config": { "max_size": 8, "overlap": 2 } },
    "postprocessing": [ { "operation": "filter_empty", "config": {...} } ]
  }

Both are supported by `TemplateManager.load_template(...)`.

## Hierarchical + Seed-Driven Templates
Hierarchical chunking segments a document into sections/blocks (headers, hrules, code fences, lists, etc.) and chunks the leaf blocks. You can steer segmentation with custom “boundary” rules:
- Enable hierarchical mode:
  "chunking": {
    "method": "sentences",
    "config": {
      "hierarchical": true,
      "hierarchical_template": {
        "boundaries": [
          { "kind": "header_atx", "pattern": "^\\s*#{1,6}\\s+.+$", "flags": "m" }
        ]
      }
    }
  }

### Learning from a seed (“template”) document
- Programmatic: `TemplateLearner.learn_boundaries(example_text)` returns:
  { "boundaries": [{ "kind": "...", "pattern": "...", "flags": "im" }, ...] }
- API: `POST /api/v1/chunking/templates/learn`
  Body:
  {
    "name": "my_seeded_template",
    "example_text": "Your sample content here...",
    "save": true,
    "classifier": { "media_types": ["document"], "title_regex": ".*MyCorpus.*" }
  }
  The API responds with a usable template config and optionally saves it.

Notes and limits:
- Keep boundary rules concise and safe. Validation caps boundaries to ≤ 20 and enforces pattern length.
- Prefer anchored, case-insensitive patterns for stable matching (e.g., `^\\s*Abstract\\b`, flags `im`).

## Classifying Templates (Optional)
Add a simple classifier (top-level or under `chunking.config`) for `/chunking/templates/match`:
  "classifier": {
    "media_types": ["document", "ebook"],
    "filename_regex": ".*\\.(pdf|epub)$",
    "title_regex": "(paper|thesis)",
    "min_score": 0.3,
    "priority": 1
  }

`TemplateClassifier` computes a simple score from media type + regex matches to help auto-select templates.

## Adding/Updating Built-in Templates
1) Add a JSON template under `template_library/` (see examples in this folder).
2) Set method + config, and optionally:
   - `hierarchical: true` + `hierarchical_template.boundaries` (if you want seeded/learned rules)
   - `classifier` for auto-matching
   - `tags`, `metadata.seed_source`, etc. for traceability
3) On startup, `ensure_templates_initialized()` seeds or updates the DB-wide built-ins.

## Testing
- API tests: `tldw_Server_API/tests/Chunking/test_chunking_templates.py`
- Template apply/validate endpoints
- Strategy-level tests under `tests/Chunking_NEW/`

## Gotchas & Best Practices
- Do not exceed boundary/regex limits; prefer a few robust patterns over many fragile ones.
- Use `structure_aware` for code/docs when possible; otherwise seed headers/fences with `hierarchical_template`.
- Keep templates JSON-only; put operational notes in `metadata` (never secrets).

