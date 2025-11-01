# Infrastructure Module PRD

## 1. Summary
- **Problem:** Multiple subsystems (embeddings workers, rate limiting, backpressure, chat throttling) depend on Redis. Contributors were re-implementing connection/plumbing logic, and local development regularly failed when Redis was unavailable.
- **Solution:** Centralize connectivity, configuration, and fallbacks inside the Infrastructure module so every caller uses a consistent factory that auto-detects real Redis vs. an in-memory stub. Provide clear guidance for deploying real Redis in production while keeping CI/dev hermetic.
- **Status (2025-10-20):** `redis_factory.py` is live. All major Redis consumers import `create_async_redis_client` / `create_sync_redis_client`. When Redis is unreachable, tests transparently fall back to the stub implementation that covers the commands we use today (streams, sets, sorted sets, hashes, scripting primitives). Stage 1 observability counters (connection attempts, duration, fallbacks, and errors) now emit through the shared metrics registry.

## 2. Goals
1. Give developers a single entry point for infrastructure clients (starting with Redis) with sensible defaults.
2. Eliminate duplicated connection logic and implicit environment assumptions.
3. Keep automated tests and local dev resilient without requiring a running Redis instance.
4. Document production expectations (real Redis, observability, security) and future expansion plans (additional infrastructure helpers).

### Non-Goals
- Replacing Redis with another queueing/datastore technology.
- Managing Redis deployments (Docker, Terraform). Those remain ops concerns.
- Covering every Redis command; the stub intentionally mirrors only the subset used by tldw_server.

## 3. Stakeholders
- **Backend contributors:** Need predictable helpers and docs for embedding queues, rate limiting, watchlists ingestion.
- **Infra/Ops maintainers:** Need to know config knobs, connection patterns, and observability hooks.
- **QA/CI owners:** Need hermetic tests that do not flake when Redis is offline.

## 4. Current Scope
| Capability | Details |
| --- | --- |
| Redis URL resolution | Reads `EMBEDDINGS_REDIS_URL` → `REDIS_URL` → default `redis://localhost:6379`. Settings layer overrides Env when available. |
| Async + sync clients | `create_async_redis_client` and `create_sync_redis_client` return redis-py instances or the stub. Both accept `preferred_url`, `decode_responses`, `fallback_to_fake`, `context`, and `redis_kwargs`. |
| In-memory stub | `InMemoryAsyncRedis` / `InMemorySyncRedis` share `_InMemoryRedisCore`. Supported commands: `ping`, `close`, strings (`get`, `set`, `delete`, expiry), sets (`sadd`, `srem`, `smembers`), sorted sets (`zadd`, `zrange`, `zrem`, `zscore`, `zincrby`), hashes (`hset`, `hget`, `hgetall`, `hincrby`), basic stream usage (`xadd`, `xlen`, `xrange`, `xreadgroup`, consumer groups), Lua script caching (`script_load`, `evalsha`, fallback to `eval`), simple pattern matching for `scan`. Expiry logic is time-based. |
| Observability | Metrics registered in `MetricsRegistry`: `infra_redis_connection_attempts_total`, `infra_redis_connection_duration_seconds`, `infra_redis_connection_errors_total`, and `infra_redis_fallback_total`. Labels capture `mode`, `context`, outcomes, and error reasons for dashboards/alerts. |
| Logging & telemetry | When falling back the factory logs a warning with context. Production callers should keep `fallback_to_fake=False` to surface outages. |
| Test coverage | `tldw_Server_API/tests/Infrastructure/test_redis_factory.py` verifies stub behaviors (ping, strings, sets, streams, scripts, expiry). |

### Key Integration Points
- **Embeddings:** `app/core/Embeddings/job_manager.py`, worker base classes, re-embed consumers all use `create_async_redis_client`.
- **Backpressure & Rate limiting:** `app/api/v1/API_Deps/backpressure.py`, `app/core/RateLimiting/Rate_Limit.py`, and MCP rate limiter rely on the shared factory.
- **Character chat throttling:** `app/core/Character_Chat/character_rate_limiter.py` pulls sync clients for streaming limits.
- **Watchlists/Collections ingestion:** Embedding enqueue operations (via job manager) now benefit from the stub in CI.

## 5. Functional Requirements
1. **Client provisioning:** A caller can request a Redis client and receive a connected instance or a stub without additional branching.
2. **Fallback behavior:** By default the factory silently switches to the in-memory stub if Redis cannot be reached. Callers can opt out (`fallback_to_fake=False`) when they require strict availability.
3. **Thread/async safety:** Stub implementations must be thread-safe enough for test workloads, matching redis-py semantics (the async stub wraps sync methods with `asyncio.to_thread` where needed).
4. **Command parity:** Whenever a new Redis command is introduced in tldw_server, the stub must be extended and tests updated.
5. **Observability hooks:** Factories emit log events on fallbacks; production instrumentation can build on these hooks.

## 6. Architecture Overview
```
┌───────────────────────┐      ┌────────────────────┐      ┌────────────────────────┐
│ Caller (e.g. Watchlist│ ---> │ Infrastructure     │ ---> │ Redis Client Instance  │
│ ingestion, rate limit)│      │ redis_factory      │      │ (real or in-memory)    │
└───────────────────────┘      └────────────────────┘      └──────────┬─────────────┘
                                                            Real Redis │  In-memory Stub
                                                                      (feature-parity subset)
```
- URL resolution order: `preferred_url` › settings › environment › default.
- Connection attempt: if `ping()` succeeds, return the real client; otherwise log + switch to stub (unless disabled).
- Stub core stores strings, sets, sorted sets, hashes, streams, and scripts in Python dictionaries while honoring expirations and consumer groups.

## 7. Configuration & Deployment
- **Environment variables:** `EMBEDDINGS_REDIS_URL`, `REDIS_URL`. Additional callers can pass `preferred_url`.
- **Recommended production setup:** Real Redis (single instance or cluster). Set `fallback_to_fake=False` for mission-critical flows (e.g., rate limiting) so outages surface immediately.
- **Observability:** Hook into log stream for `"Redis unavailable"` warnings. Future roadmap includes metrics (success/fallback counters).
- **Security:** Configure TLS/ACL in the upstream Redis and embed credentials in `REDIS_URL`.

## 8. Testing Strategy
- Unit tests for stub coverage (`test_redis_factory.py`) must grow with each new Redis command usage.
- Integration tests should continue to run with the stub in CI, but developers should periodically run with a real Redis instance to catch protocol drift.
- Planned follow-up: add smoke tests that set `fallback_to_fake=False` to ensure real Redis is exercised in staging environments.

## 9. Roadmap
| Stage | Timeline | Scope |
| --- | --- | --- |
| **Stage 0 - Completed** | Q4 2025 | Centralized factory, in-memory stub, updated call sites, unit tests, documentation. |
| **Stage 1 - Observability Enhancements (in progress)** | Q4 2025 | Connection attempt/duration/fallback/error metrics shipped; next step is wiring dashboards/alerts that consume these series and adding optional trace attributes. |
| **Stage 2 - Additional Infrastructure Helpers** | Q1 2026 | Introduce similar factories for Postgres pools, object storage, and optional task queues (Celery/Redis Streams). Keep a consistent pattern (centralized config + stubs). |
| **Stage 3 - Deployment Tooling** | Q1 2026 | Provide Docker Compose overlays and Terraform snippets for Redis (standalone + HA) plus health-check scripts. |

## 10. Risks & Mitigations
- **Stub drift:** New Redis commands might be unsupported. Mitigate via gatekeeping in PR review + expanding tests.
- **Silent fallback in prod:** If teams forget to disable fallback, outages might go unnoticed. Mitigate with runbooks recommending `fallback_to_fake=False` for production-critical paths and by emitting structured alerts.
- **Performance difference:** Stub does not replicate Redis performance characteristics; load/perf tests must run against real Redis.

## 11. Open Questions
1. Do we need a shared abstraction for Pub/Sub or only Streams? (Currently unused; revisit before adoption.)
2. Should we promote sentinel/cluster awareness in the factory? (Out of scope now; evaluate when multi-node deployments are requested.)
3. Is a lightweight CLI needed to verify connectivity and stub behavior (`python -m infrastructure check-redis`)? (Could help new contributors.)

## 12. Contributor Guidance
- Always import clients via `tldw_Server_API.app.core.Infrastructure.redis_factory`.
- Extend `_InMemoryRedisCore` whenever you add a command. Update the corresponding test to lock behavior.
- Prefer passing `context="module_name"` to improve log clarity.
- Document any new environment variables in `Docs/Deployment` and add runbook notes if the infrastructure footprint changes.
