# Test Suite Guide

This directory contains the end-to-end, integration, and unit tests for `tldw_server`. The notes below summarize how to run the suite and the knobs that control which tests execute.

## Quick Start
- Install dependencies with `pip install -e .[dev]`.
- Run the whole suite: `python -m pytest tldw_Server_API/tests -q`.
- Run by marker: `python -m pytest -m "unit"` or `pytest -m "integration and not slow"`.
- Use `pytest --maxfail=1 -x` while iterating to stop on the first failure.

## Pytest Markers & CLI Switches
- Common markers registered across the suite: `unit`, `integration`, `slow`, `stress`, `external_api`, `pg_jobs`, `requires_model`, `multi_user`, `single_user`.
- View the full list any time with `pytest --markers`.
- ChromaDB tests accept `--run-model-tests` (or `RUN_MODEL_TESTS=1`) to pull lightweight embedding models.
- E2E tests add `--skip-slow`, `--critical-only`, and `--auth-mode={auto|single_user|multi_user}` (see `tests/e2e/README.md` for the full flow).

## Environment Toggles

### Database & Auth
| Setting | Default | Effect | Notes |
| --- | --- | --- | --- |
| `RUN_PG_INTEGRATION` | disabled | Enables Postgres-backed AuthNZ integration tests such as `AuthNZ/test_media_permission_enforcement.py`. | Requires `DATABASE_URL`/`TEST_DATABASE_URL` pointing at PostgreSQL and credentials (`TEST_DB_*`). |
| `TLDW_TEST_POSTGRES_REQUIRED` | disabled | Fail fast instead of skipping when Postgres cannot be reached. | Used by AuthNZ and Prompt Studio heavy suites; combine with the Postgres variables below. |
| `TEST_DATABASE_URL` / `DATABASE_URL` | varies | Provides a full Postgres DSN for AuthNZ fixtures. | Overrides `TEST_DB_HOST`, `TEST_DB_PORT`, `TEST_DB_NAME`, `TEST_DB_USER`, `TEST_DB_PASSWORD`. |
| `TLDW_TEST_NO_DOCKER` | disabled | Prevents AuthNZ fixtures from auto-starting a local Postgres Docker container. | Set when you manage Postgres yourself. |
| `TLDW_TEST_PG_IMAGE` | `postgres:18` | Selects the Docker image used when the fixtures auto-start Postgres. | Combine with `TLDW_TEST_PG_CONTAINER_NAME` if needed. |
| `RUN_PG_JOBS_STRESS` | disabled | Enables `tests/Jobs/test_jobs_pg_concurrency_stress.py` (heavy multi-process stress). | Requires `JOBS_DB_URL`/`POSTGRES_TEST_DSN`. |
| `RUN_PG_JOBS_STRESS_STRICT` | disabled | Extends the PG jobs stress test with stricter coverage assertions. | Only meaningful when `RUN_PG_JOBS_STRESS=1`. |

### Prompt Studio & Research
| Setting | Default | Effect | Notes |
| --- | --- | --- | --- |
| `TLDW_PS_BACKEND` | `sqlite` | Chooses the backend (`sqlite` or `postgres`) for the heavy Prompt Studio dual-backend suite. | Located in `prompt_studio/integration/test_optimizations_dual_backend_heavy.py`. |
| `TLDW_PS_STRESS` | disabled | Expands Prompt Studio heavy tests with larger corpora and more iterations. | Optional tuning knobs: `TLDW_PS_TC_COUNT`, `TLDW_PS_ITERATIONS`, `TLDW_PS_OPT_COUNT`. |
| `RUN_EXTERNAL_API_TESTS` | disabled | Enables PaperSearch tests that hit live third-party APIs. | Provide provider keys such as `SPRINGER_NATURE_API_KEY`, `IEEE_API_KEY`, `ELSEVIER_API_KEY` before enabling. |

### LLM / Embeddings / Chat
| Setting | Default | Effect | Notes |
| --- | --- | --- | --- |
| `RUN_MODEL_TESTS` or `--run-model-tests` | disabled | Allows ChromaDB tests marked `requires_model` to download tiny HuggingFace models. | Requires network access. |
| `RUN_REAL_EMBEDDINGS` | disabled | Allows embeddings integration tests to download and execute real HuggingFace models in CI. | Combine with `HF_TOKEN` if the model requires authentication. |
| `RUN_STRESS_TESTS` | disabled | Executes the concurrent load test inside `test_embeddings_v5_integration.py`. | Heavy; opt-in only. |
| `RUN_COMMERCIAL_CHAT_TESTS` | disabled | Exercises live commercial chat providers (OpenAI, Anthropic, etc.). | Ensure the related API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, etc.) are populated with real credentials. |

### Audio, TTS, and Media
| Setting | Default | Effect | Notes |
| --- | --- | --- | --- |
| `RUN_TTS_LEGACY_INTEGRATION` | disabled | Runs legacy TTS adapter tests under `tests/TTS/`. | Requires provider-specific keys (e.g., `ELEVENLABS_API_KEY`, local model paths). |
| `ALLOW_HEAVY_AUDIO_SMOKE` | disabled | Enables the audio worker smoke test (`tests/AudioJobs/test_audio_worker_smoke.py`). | Install `ffmpeg` and ensure audio models are available. |
| `RUN_AUDIO_E2E` | disabled | Allows the optional WebUI audio upload E2E test. | Requires a running server plus audio processing dependencies. |

### Workflows, MCP, and Services
| Setting | Default | Effect | Notes |
| --- | --- | --- | --- |
| `TLDW_WORKFLOW_STRESS` | disabled | Enables `tests/Workflows/test_workflow_stress.py` which hammers the workflow engine. | Intended for soak testing only. |
| `RUN_MCP_TESTS` | disabled | Activates MCP metrics endpoint tests. | Provide `SINGLE_USER_API_KEY` so the tests can authenticate. |

### End-to-End Harness
| Setting | Default | Effect | Notes |
| --- | --- | --- | --- |
| `E2E_TEST_BASE_URL` | `http://localhost:8000` | Base URL for WebUI/API E2E tests. | Ensure the server is running before starting the suite. |
| `E2E_AUTH_MODE` | `auto` | Overrides auth mode detection for E2E tests. | Choose `single_user` or `multi_user` to force a mode. |
| `E2E_RATE_LIMIT_DELAY` | `0.5` | Seconds to wait before retrying on rate-limit responses. | Adjust if the server is under heavy load. |
| `E2E_MAX_RETRIES` | `3` | Retry attempts after rate limits. | Increase for slower deployments. |
| `E2E_SERVER_STARTUP_TIMEOUT` | `30` | Seconds to wait for a server to boot before declaring a failure. | Helpful when bootstrapping against Docker. |
| `E2E_ADMIN_BEARER` | unset | Bearer token used for admin-level E2E scenarios. | Required for multi-user onboarding tests. |

### Audio / LLM Provider Keys
Many suites look for provider-specific credentials when the corresponding feature flags are set. Typical examples include:
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY`, `HF_TOKEN`
- `ELEVENLABS_API_KEY`, `EXTERNAL_TRANSCRIPTION_TEST_API_KEY`
- `SPRINGER_NATURE_API_KEY`, `IEEE_API_KEY`, `ELSEVIER_API_KEY`

When a key is missing, the individual test will usually skip with a descriptive message.

## Tips
- Export environment variables in your shell or create a temporary `.env` when running targeted suites.
- Many integration fixtures automatically set `TEST_MODE=true` and disable rate limiting; you can do the same when writing new tests.
- Keep heavy toggles disabled by default in CI to control runtime. Enable them locally when validating provider integrations or stress scenarios.
