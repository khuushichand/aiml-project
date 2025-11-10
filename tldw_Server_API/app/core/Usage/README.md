# Usage

## 1. Descriptive of Current Feature Set

- Purpose: Track usage and quotas for selected modules (e.g., audio) and support pricing catalogs.
- Capabilities:
  - Per-user usage counters; simple quota checks for audio
  - Pricing catalog utilities for cost estimation
- Inputs/Outputs:
  - Inputs: usage events (audio seconds, requests)
  - Outputs: counters and quota decisions
- Related Modules:
  - `tldw_Server_API/app/core/Usage/audio_quota.py:1`, `pricing_catalog.py:1`, `usage_tracker.py:1`

## 2. Technical Details of Features

- Architecture & Data Flow:
  - Utilities consumed by endpoints/services to increment counters and enforce quotas
- Key Classes/Functions:
  - `audio_quota`: quota checks and updates
  - `pricing_catalog`: catalog lookups for provider/model pricing
  - `usage_tracker`: simple in-memory/file-backed patterns
- Dependencies:
  - Internal: Metrics module for counters (if configured)
- Data Models & DB:
  - No dedicated DB by default; pluggable backends as needed
- Configuration:
  - Provider pricing via config/env; limits via env
- Concurrency & Performance:
  - Lightweight, called in hot paths (keep O(1))
- Error Handling:
  - Fail-safe decisions when catalog missing; log warnings
- Security:
  - Enforce per-user scope

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure:
  - `Usage/` with `audio_quota.py`, `pricing_catalog.py`, `usage_tracker.py`
- Extension Points:
  - Add new sinks (DB/prometheus) and resources; wire into endpoints
- Coding Patterns:
  - Keep counters consistent with Metrics; minimize global state
- Tests:
  - (Add module-level tests as behaviors expand)
- Local Dev Tips:
  - Start with generous limits to avoid noisy tests; enable metrics to observe counters
- Pitfalls & Gotchas:
  - High-cardinality labels if exported to metrics; cap keys
- Roadmap/TODOs:
  - Persistent usage store; richer pricing per tier
