# Embeddings Pipeline Benchmark

- Run ID: `0e73a1e5d341`
- Generated: `2026-01-12 15:48:17`

## Results

| Mode | Jobs | Completed | Failed | Duration (s) | Jobs/s | Chunks/s | p50 (ms) | p95 (ms) | p99 (ms) | Timed Out |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| redis | 200 | 200 | 0 | 1.039 | 192.509 | 1540.074 | 17.1 | 24.8 | 24.9 | False |
| jobs | 200 | 200 | 0 | 2.331 | 85.793 | 686.347 | 1961.1 | 2100.3 | 2112.1 | False |

## Comparison

- Throughput ratio (candidate/baseline): `0.446`
- p95 latency ratio (candidate/baseline): `84.690`
