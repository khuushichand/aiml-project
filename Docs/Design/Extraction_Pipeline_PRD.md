# Extraction Pipeline PRD (Split from Curl-Scraping-PRD)

Author: tldw_server team
Status: Draft
Last Updated: 2025-10-26

This document consolidates the lifted concepts related to extraction strategies that were previously appended to Curl-Scraping-PRD. It focuses on modular extraction, schema/regex/LLM strategies, clustering, caching, security/privacy for outputs, and observability specific to extraction.

## 1. Extraction Strategy Router

Introduce a modular extraction pipeline that pairs with the fetch/router. The router decides both the fetch backend and the extraction strategy order per domain.

- Default pipeline order: JSON-LD/Microdata → Schema (CSS/XPath/LXML) → Regex (entities) → LLM (blocks/schema) → Clustering fallback.
- Domain rules can override strategy order and parameters (e.g., prefer Schema then Regex for ecommerce sites).
- Each stage returns structured results or signals a fallback; include reason codes for observability.

## 2. LLM-Based Extraction

- Chunking knobs: `chunk_token_threshold`, `overlap_rate`, `word_token_rate` to control token budgets.
- Provider-aware throttling: per-provider concurrency caps and optional inter-call delay/jitter.
- Robust JSON handling: tolerate multiple JSON objects, XML-wrapped JSON, or malformed payloads; provide a strict mode that forces JSON-only output.
- Token usage accounting: collect per-call and total usage; export to metrics instead of printing.
- Modes: extract “blocks”, extract “schema”, or “infer schema” when none is provided.

## 3. Schema-Driven Extraction

- Schema format fields:
  - `name`, `baseSelector`, `baseFields`, `fields`.
  - Field types: `text`, `attribute`, `html`, `regex`, `nested`, `list`, `nested_list`, `computed`.
- Transform library (safe, no eval): `lowercase`, `uppercase`, `strip`, `regex_replace`, `urljoin`, `date_normalize`, `number_normalize`.
- LLM schema generation: CSS or XPath schema from sample HTML with optional “query” and “example JSON”.
- Selector validation and stability tests: compile selectors, ensure uniqueness, and run against sample pages to catch fragile/base64-like classes.

## 4. Regex Extraction Fallback

- Built-in pattern catalog (selectable via flags): email, phone (intl/US), URL, IPv4/IPv6, UUID, currency, percentage, number, date/time, postal codes (US/UK), hex color, social handles, MAC, IBAN, credit card.
- Output per match: `{url, label, value, span}`.
- Optional privacy features: PII masking/redaction; Luhn validation for credit cards before output.
- LLM-assisted one-off pattern generator: `generate_pattern(label, html, query, examples)` for page-specific patterns.

## 5. Clustering-Based Extraction

- Embedding-based prefiltering with a similarity threshold to keep relevant chunks.
- Hierarchical clustering groups similar text; cluster-level tagging via multilabel classifier.
- Tunables: similarity threshold, linkage method, word-count threshold, top-k tags per cluster.

## 6. Performance & Caching

- Selector/result caches with bounded LRU and lifecycle hooks to clear after runs.
- Concurrency limits per strategy and per provider; standardized retry/backoff with jitter.
- Memory hygiene: cap embedding buffers and provide `clear_cache` hooks.
- Fast-path nth-child/table handling and context-sensitive selector evaluation for LXML.

## 7. Security & Privacy

- Safe computed fields: replace arbitrary `eval` with a sandboxed mini-DSL/whitelisted transform functions.
- PII-aware outputs: optional masking for sensitive labels (email/phone/credit_card).
- Maintain centralized egress/SSRF checks pre-fetch; respect robots.txt by default (configurable).
- Do not log secrets or PII; redact sensitive header/cookie values in logs.

## 8. Observability

- Per-strategy metrics: success/failure counts, latency histograms, fallback counters, content-length histograms.
- Token usage exposed via metrics; remove direct prints from library paths.
- Optional extraction trace: selected strategy, rules applied, selector match counts, and fallback reasons.

## 9. Configuration Additions

- YAML per domain:
  - `strategy_order`: e.g., `[jsonld, schema_css, regex, llm, cluster]`.
  - Strategy settings: transforms, privacy policies (PII masking), LLM settings.
- Env vars:
  - `EXTRACTOR_MAX_WORKERS`, `LLM_MAX_CONCURRENCY`, `LLM_DELAY_MS`.
  - `CLUSTER_LINKAGE`, `SIM_THRESHOLD`, `WORD_COUNT_THRESHOLD`.
  - `REGEX_PII_MASK=true|false`.

## 10. Testing Additions

- Unit tests: selector compilation and uniqueness, transform functions, safe-eval DSL, JSON parsing robustness, clustering for small inputs.
- Integration (external_api): schema-driven extraction on known pages, regex catalog correctness, LLM block extraction happy-path, end-to-end with curl backend.
- Security tests: egress-denied URLs blocked; PII masking enforced when enabled.
