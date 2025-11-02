Exemplar Sampling

The RAG pipeline can optionally sample redacted payload “exemplars” on failure conditions (e.g., post-verification low confidence, generation gating, retrieval/rerank errors).

Where
- Default sink: `Databases/observability/rag_payload_exemplars.jsonl` (JSONL). One exemplar per line.
- Override path via `RAG_PAYLOAD_EXEMPLAR_PATH`.

Controls
- `RAG_PAYLOAD_EXEMPLAR_SAMPLING` (default `0.05`) controls the random sampling rate (0..1).
- Safe redaction removes emails, URLs, long numbers; long texts are truncated.

Record shape
```json
{
  "ts": 1728864571.123,
  "reason": "post_verification_low_confidence",
  "user": "abc123",
  "query": "how to ...",
  "answer": "...",
  "docs": [
    { "id": "...", "score": 0.73, "content": "..." }
  ]
}
```

Ingestion
- See `Docs/Deployment/Monitoring/exemplar-sink-sample.yml` for a basic file scrape/shipper configuration (e.g., vector/fluent-bit/Loki) to ingest exemplars into your observability stack.
- Exemplar lines include enough context to correlate with metrics/traces using timestamps. If using OTEL tracing, enrich by adding `trace_id` as a label in your shipper if desired.

Security
- Exemplars are redacted and truncated, but still contain user queries and snippets. Keep the JSONL file restricted and rotate/purge regularly.
