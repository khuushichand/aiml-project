# Metrics Cheatsheet

The server exports metrics across HTTP, DB, LLM, RAG, embeddings, uploads, system, security, chat, chunking, MCP, and Prompt Studio. Some categories require OpenTelemetry or module-specific collectors to be enabled (noted below).

- Text format: `GET /metrics` (or `GET /api/v1/metrics/text`)
- JSON: `GET /api/v1/metrics/json`
- Health: `GET /api/v1/metrics/health`
- Chat metrics (JSON): `GET /api/v1/metrics/chat` (includes `token_costs`)
- Reset metrics: `POST /api/v1/metrics/reset` (admin-only; clears in-memory counters; enforced by AuthNZ)

Installation (optional OpenTelemetry):
- To enable OTel exporters and auto-instrumentation, install extras:
  - `pip install "tldw-server[otel]"` or `pip install -r requirements-otel.txt`
  - Set env: `OTEL_METRICS_EXPORTER=prometheus,otlp`, `OTEL_TRACES_EXPORTER=otlp`, `PROMETHEUS_PORT=9090`

## HTTP
- `http_requests_total{method,endpoint,status}`: Counter of HTTP requests.
- `http_request_duration_seconds{method,endpoint}`: Histogram of request latency.

Example PromQL:
- P95 latency by route: `histogram_quantile(0.95, sum by (le,endpoint) (rate(http_request_duration_seconds_bucket[5m])))`
- Error rate: `sum by (endpoint) (increase(http_requests_total{status=~"5.."}[5m]))`

## Database
- `db_connections_active{database}`: Gauge of active DB connections.
- `db_queries_total{database,operation}`: Counter of DB queries.
- `db_query_duration_seconds{database,operation}`: Histogram of DB latency.
- `privilege_snapshots_table_rows`: Gauge of retained privilege snapshots (daily retention job).
- `privilege_snapshots_table_bytes`: Gauge of on-disk size for privilege snapshots (Postgres only).
Note: DB metrics are available when the corresponding operations use the instrumented DB wrappers; not all code paths emit these yet.

## LLM
- `llm_requests_total{provider,model,status}`: Counter of LLM calls.
- `llm_tokens_used_total{provider,model,type}`: Counter of tokens by type `prompt|completion`.
- `llm_request_duration_seconds{provider,model}`: Histogram of call latency.
- `llm_cost_dollars{provider,model}`: Counter of cumulative cost (USD).

Example PromQL:
- P95 latency per model: `histogram_quantile(0.95, sum by (le,provider,model) (rate(llm_request_duration_seconds_bucket[5m])))`
- Cost per minute by provider: `sum by (provider) (rate(llm_cost_dollars[5m]))`

## RAG
- `rag_queries_total{pipeline,status}`: Counter of RAG queries.
- `rag_retrieval_latency_seconds{source,pipeline}`: Histogram of retrieval latency.
- `rag_documents_retrieved{source,pipeline}`: Histogram of docs retrieved.
- `rag_cache_hits_total{cache_type}` / `rag_cache_misses_total{cache_type}`: Counters of cache results.
Note: The new RAG service also emits `rag_pipeline_duration_ms` and related metrics via OpenTelemetry. To see those in Prometheus/Grafana, configure your OTel → Prometheus exporter.

Example PromQL:
- P95 retrieval latency by source: `histogram_quantile(0.95, sum by (le,source) (rate(rag_retrieval_latency_seconds_bucket[5m])))`
- Cache hit rate: `sum(rate(rag_cache_hits_total[5m])) / (sum(rate(rag_cache_hits_total[5m])) + sum(rate(rag_cache_misses_total[5m])))`

## Embeddings (core)
- `embeddings_generated_total{provider,model}`: Counter of embeddings created.
- `hyde_questions_generated_total{provider,model,source}`: HYDE/doc2query questions emitted by embedding pipeline or backfill.
- `hyde_generation_failures_total{provider,model,source,reason}`: HYDE question generation failures (non-blocking).
- `hyde_vectors_written_total{store}`: HYDE vectors written to the configured vector store adapter.
- `embedding_generation_duration_seconds{provider,model}`: Histogram of generation time.

## Embeddings v5 endpoint
- `embedding_requests_total{provider,model,status}`: Counter of embedding requests.
- `embedding_request_duration_seconds{provider,model}`: Histogram of request latency.
- `embedding_cache_hits_total{provider,model}`: Counter of cache hits.
- `embedding_cache_size`: Gauge of current embedding cache size.
- `active_embedding_requests`: Gauge of in-flight embedding requests.

## Uploads & Storage
- `uploads_total{user_id,media_type}`: Counter of uploaded files.
- `upload_bytes_total{user_id,media_type}`: Counter of uploaded bytes.
- `user_storage_used_mb{user_id}`: Gauge of current storage used (MB).
- `user_storage_quota_mb{user_id}`: Gauge of configured storage quota (MB).

Example PromQL:
- Upload throughput (bytes/s): `rate(upload_bytes_total[1m])`
- Top users by bytes (1h): `sum by (user_id) (increase(upload_bytes_total[1h]))`
- Users near quota: `user_storage_used_mb / user_storage_quota_mb > 0.9`

## System
- `system_cpu_usage_percent`: Gauge of CPU usage percent.
- `system_memory_usage_bytes`: Gauge of memory usage.
- `system_disk_usage_bytes{mount_point}`: Gauge of disk usage by mount.
Note: System gauges appear when a resource monitor/collector is running; they are not continuously sampled by default.

## Errors & Security
- `errors_total{component,error_type}`: Counter of errors by component.
- `security_ssrf_block_total`: Counter of outbound URL validations blocked.
- `security_headers_responses_total`: Counter of responses with security headers applied.

## Circuit Breakers
- `circuit_breaker_state{service}`: Gauge of state (0=closed, 1=open, 2=half-open).
- `circuit_breaker_trips_total{service,reason}`: Counter of trips.

## Chat (OpenAI-compatible Chat API)
- Requests: `chat_requests_total{provider,model,status}`; latency: `chat_request_duration_seconds{provider,model}`.
- Streaming: `chat_streaming_duration_seconds{conversation_id}`, `chat_streaming_chunks_total{conversation_id}`, `chat_streaming_heartbeats_total{conversation_id}`, `chat_streaming_timeouts_total{conversation_id}`.
- Tokens: `chat_tokens_prompt{provider,model}`, `chat_tokens_completion{provider,model}`, `chat_tokens_total{provider,model}`.
- LLM calls: `chat_llm_requests_total{provider,model,status}`, `chat_llm_latency_seconds{provider,model}`, `chat_llm_errors_total{provider,model,error_type}`, `chat_llm_cost_estimate_usd{provider,model}`.
- Conversations: `chat_conversations_created_total{conversation_id}`, `chat_conversations_resumed_total{conversation_id}`, `chat_messages_saved_total{conversation_id,message_type}`.
- Validation & DB: `chat_validation_failures_total`, `chat_validation_duration_seconds`, `chat_db_transactions_total{status}`, `chat_db_retries_total{retry_count}`, `chat_db_rollbacks_total`, `chat_db_operation_duration_seconds{operation}`.
- Auth/limits: `chat_rate_limits_total{client_id}`, `chat_auth_failures_total`.

Example PromQL:
- Chat error rate: `sum(increase(chat_errors_total[5m]))`
- Streaming timeouts (rate): `rate(chat_streaming_timeouts_total[5m])`

Notes:
- Chat metrics are produced via OpenTelemetry meters; Prometheus export depends on your OTel → Prom exporter configuration.
- The JSON endpoint `GET /api/v1/metrics/chat` always returns `active_operations` and `token_costs`; counter/histogram stats appear only if exported.
 - Function decorators in `app/core/Metrics/decorators.py` auto-register their metrics on first use; no manual pre-registration needed.
 - General `cache_hits_total`/`cache_misses_total` are aliased to `rag_cache_hits_total`/`rag_cache_misses_total` in Prometheus exposition with label `cache_type` for consistency with RAG dashboards.

## Chunking Module
- Requests: `chunking_requests_total{method,status}`.
- Latency: `chunking_duration_seconds{method}`.
- Sizes: `chunk_size_characters{method}`, `chunking_input_size_bytes{method}`.
- Output: `chunks_per_request{method}`.
- Cache: `chunking_cache_hits_total{method}`, `chunking_cache_misses_total{method}`, `chunking_cache_size`.
- Errors: `chunking_errors_total{method,error_type}`.
- Additional server metrics: `chunk_time_seconds{method,unit,splitter,language,stream}`, `chunk_output_bytes{...}`, `chunk_input_bytes{...}`, `chunk_count{...}`, `chunk_avg_chunk_size_bytes{...}`; gauges `chunk_last_count{...}`, `chunk_last_output_bytes{...}`.

## MCP Unified
- Requests: `mcp_requests_total{method,status}`, latency: `mcp_request_duration_seconds{method}`.
- Modules: `mcp_module_health{module}`, `mcp_module_operations_total{module,operation,status}`.
- Connections: `mcp_active_connections{type}`, `mcp_connection_errors_total{type,error}`.
- Rate limits: `mcp_rate_limit_hits_total{key_type}`.
- Cache: `mcp_cache_hits_total{cache_name}`, `mcp_cache_misses_total{cache_name}`.
- System: `mcp_memory_usage_bytes`, `mcp_cpu_usage_percent`.
Notes:
- JSON metrics: `GET /api/v1/mcp/metrics` (admin-only).
- Prometheus scrape (unauthenticated, for internal networks): `GET /api/v1/mcp/metrics/prometheus`.
  - Security: expose only on trusted networks or behind an authing proxy.
  - If Prometheus client is not installed, the endpoint returns a placeholder comment.

Prometheus scrape_config example:
```yaml
scrape_configs:
  - job_name: 'tldw-mcp'
    metrics_path: /api/v1/mcp/metrics/prometheus
    static_configs:
      - targets: ['tldw-server.local:8000']
```

Sample PromQL queries:
- Total requests (5m): `sum(rate(mcp_requests_total[5m])) by (method, status)`
- p50 latency per method (5m):
  `histogram_quantile(0.50, sum(rate(mcp_request_duration_seconds_bucket[5m])) by (le, method))`
- p95 latency per method (5m):
  `histogram_quantile(0.95, sum(rate(mcp_request_duration_seconds_bucket[5m])) by (le, method))`
- p99 latency per method (5m):
  `histogram_quantile(0.99, sum(rate(mcp_request_duration_seconds_bucket[5m])) by (le, method))`

## Prompt Studio
- Executions: `prompt_studio.executions.total{provider,model,status}`, `prompt_studio.executions.duration_seconds{provider,model}`.
- Tokens/Cost: `prompt_studio.tokens.used{provider,model,type}`, `prompt_studio.cost.total{provider,model}`.
- Tests/Evals: `prompt_studio.tests.total{project,status}`, `prompt_studio.evaluations.score{project,metric_type}`, `prompt_studio.evaluations.duration_seconds{project}`.
- Optimizations: `prompt_studio.optimizations.total{strategy,status}`, `prompt_studio.optimizations.improvement{strategy}`, `prompt_studio.optimizations.iterations{strategy}`.
- Jobs: `jobs.queued{job_type}`, `jobs.processing{job_type}`, `jobs.completed{job_type,status}`, `jobs.duration_seconds{job_type}`.
- WebSocket: `prompt_studio.websocket.connections`, `prompt_studio.websocket.messages{event_type}`.
- DB: `prompt_studio.database.operations{operation,table}`, `prompt_studio.database.latency_ms{operation}`.

Grafana: Import `Docs/Deployment/Monitoring/security-dashboard.json` for a base dashboard (HTTP/security). Add panels for the metrics above to monitor app, RAG, embeddings, and chat health.

## Platform-Specific Notes

Windows: If you need CUDA support for transcription without full CUDA installation:
- Download Faster-Whisper-XXL (see README link in repo)
- Extract `cudnn_ops_infer64_8.dll` and `cudnn_cnn_infer64_8.dll` to the project directory

Linux/macOS: Install system dependencies:
```bash
# Debian/Ubuntu
sudo apt install ffmpeg portaudio19-dev gcc build-essential python3-dev

# Fedora
sudo dnf install ffmpeg portaudio-devel gcc gcc-c++ python3-devel

# macOS
brew install ffmpeg portaudio
```
