# -----------------------------------------------------------------------------
# Quickstart targets (first-time setup)
# -----------------------------------------------------------------------------
.PHONY: quickstart quickstart-docker verify

quickstart:
	@echo "[quickstart] Setting up tldw_server for first-time use..."
	@test -f .env || (cp tldw_Server_API/Config_Files/.env.quickstart .env && echo "[quickstart] Created .env from template - edit SINGLE_USER_API_KEY!")
	@echo "[quickstart] Initializing auth (non-interactive)..."
	python -m tldw_Server_API.app.core.AuthNZ.initialize --non-interactive
	@echo "[quickstart] Starting server on http://127.0.0.1:8000"
	@echo "[quickstart] Verify with: curl http://localhost:8000/health"
	@echo "[quickstart] API docs at: http://127.0.0.1:8000/docs"
	uvicorn tldw_Server_API.app.main:app --host 127.0.0.1 --port 8000

quickstart-docker:
	@echo "[quickstart-docker] Starting tldw_server via Docker Compose..."
	docker compose -f Dockerfiles/docker-compose.yml up -d --build
	@echo "[quickstart-docker] Initializing auth..."
	docker compose -f Dockerfiles/docker-compose.yml exec app python -m tldw_Server_API.app.core.AuthNZ.initialize --non-interactive
	@echo "[quickstart-docker] Server running at http://localhost:8000"
	@echo "[quickstart-docker] Verify with: curl http://localhost:8000/health"
	@echo "[quickstart-docker] API docs at: http://localhost:8000/docs"

verify:
	@echo "[verify] Checking server health..."
	@curl -sf http://localhost:8000/health > /dev/null && echo "[verify] Health check PASSED" || (echo "[verify] Health check FAILED - is the server running?" && exit 1)

# -----------------------------------------------------------------------------
# PostgreSQL backup/restore
# -----------------------------------------------------------------------------
.PHONY: pg-backup pg-restore

# Defaults (override on command line)
PG_BACKUP_DIR ?= ./tldw_DB_Backups/postgres
PG_LABEL ?= content
PG_DUMP_FILE ?=

pg-backup:
	@echo "[pg-backup] Writing backup to $(PG_BACKUP_DIR) (label=$(PG_LABEL))"
	@python Helper_Scripts/pg_backup_restore.py backup --backup-dir "$(PG_BACKUP_DIR)" --label "$(PG_LABEL)"

pg-restore:
	@test -n "$(PG_DUMP_FILE)" || (echo "[pg-restore] Set PG_DUMP_FILE=path/to.dump" && exit 1)
	@echo "[pg-restore] Restoring from $(PG_DUMP_FILE)"
	@python Helper_Scripts/pg_backup_restore.py restore --dump-file "$(PG_DUMP_FILE)"

# -----------------------------------------------------------------------------
# Monitoring stack (Prometheus + Grafana)
# -----------------------------------------------------------------------------
.PHONY: monitoring-up monitoring-down monitoring-logs

MON_STACK := Dockerfiles/Monitoring/docker-compose.monitoring.yml

monitoring-up:
	@echo "[monitoring] Starting Prometheus + Grafana"
	docker compose -f $(MON_STACK) up -d
	@echo "[monitoring] Grafana: http://localhost:3000 (admin/admin). Prometheus: http://localhost:9090"

monitoring-down:
	@echo "[monitoring] Stopping Prometheus + Grafana"
	docker compose -f $(MON_STACK) down -v

monitoring-logs:
	docker compose -f $(MON_STACK) logs -f

# -----------------------------------------------------------------------------
# Dev Server (mock mode)
# -----------------------------------------------------------------------------
.PHONY: server-up-dev

# Defaults (override on command line)
HOST ?= 127.0.0.1
PORT ?= 8000
API_KEY ?= REPLACE-THIS-WITH-A-SECURE-API-KEY-123

server-up-dev:
	@echo "[server] Starting uvicorn in mock mode on $(HOST):$(PORT)"
	AUTH_MODE=single_user \
	SINGLE_USER_API_KEY="$(API_KEY)" \
	DEFAULT_LLM_PROVIDER=openai \
	CHAT_FORCE_MOCK=1 \
	STREAMS_UNIFIED=1 \
	uvicorn tldw_Server_API.app.main:app --host $(HOST) --port $(PORT) --reload

# -----------------------------------------------------------------------------
# Prompt Studio tests
# -----------------------------------------------------------------------------
.PHONY: prompt-studio-test prompt-studio-test-sqlite prompt-studio-test-postgres

PS_TEST_PATH ?= tldw_Server_API/tests/prompt_studio
PS_TEST_ARGS ?= -v

prompt-studio-test:
	@echo "[prompt-studio] Running Prompt Studio tests (sqlite + postgres when available)"
	python -m pytest $(PS_TEST_PATH) $(PS_TEST_ARGS)

prompt-studio-test-sqlite:
	@echo "[prompt-studio] Running Prompt Studio tests (sqlite only)"
	python -m pytest $(PS_TEST_PATH) -k sqlite $(PS_TEST_ARGS)

prompt-studio-test-postgres:
	@echo "[prompt-studio] Running Prompt Studio tests (postgres only)"
	TLDW_TEST_POSTGRES_REQUIRED=1 python -m pytest $(PS_TEST_PATH) -k postgres $(PS_TEST_ARGS)

# -----------------------------------------------------------------------------
# Benchmarks (LLM Gateway)
# -----------------------------------------------------------------------------
.PHONY: bench-sweep bench-stream bench-rps

# Defaults (override on command line)
BASE_URL ?= http://127.0.0.1:8000
API_KEY ?= $(SINGLE_USER_API_KEY)
CONCURRENCY ?= 1 2 4 8
DURATION ?= 20
PROMPT_BYTES ?= 256
OUTDIR ?= .benchmarks

bench-sweep:
	@mkdir -p $(OUTDIR)
	@echo "[bench] Non-stream sweep: $(CONCURRENCY) for $(DURATION)s (prompt $(PROMPT_BYTES)B)"
	python Helper_Scripts/benchmarks/llm_gateway_bench.py \
		--base-url $(BASE_URL) \
		--path /api/v1/chat/completions \
		--api-key "$(API_KEY)" \
		--concurrency $(CONCURRENCY) \
		--duration $(DURATION) \
		--prompt-bytes $(PROMPT_BYTES) \
		--out $(OUTDIR)/bench_nonstream.json

bench-stream:
	@mkdir -p $(OUTDIR)
	@echo "[bench] Streaming sweep: $(CONCURRENCY) for $(DURATION)s (prompt $(PROMPT_BYTES)B)"
	python Helper_Scripts/benchmarks/llm_gateway_bench.py \
		--stream \
		--base-url $(BASE_URL) \
		--path /api/v1/chat/completions \
		--api-key "$(API_KEY)" \
		--concurrency $(CONCURRENCY) \
		--duration $(DURATION) \
		--prompt-bytes $(PROMPT_BYTES) \
		--out $(OUTDIR)/bench_stream.json

# Approximate open-loop RPS plan via Locust
RPS_PLAN ?= 10:30,20:30,40:60,20:30,10:30
TASKS_PER_USER_PER_SEC ?= 1
LOCUST_T ?= 3m

bench-rps:
	@echo "[bench-rps] RPS plan: $(RPS_PLAN) (tasks/user/sec=$(TASKS_PER_USER_PER_SEC))"
	TLDW_RPS_PLAN="$(RPS_PLAN)" \
	TLDW_TASKS_PER_USER_PER_SEC="$(TASKS_PER_USER_PER_SEC)" \
	SINGLE_USER_API_KEY="$(API_KEY)" \
	locust -f Helper_Scripts/benchmarks/locustfile.py --host $(BASE_URL) --headless -t $(LOCUST_T)

# -----------------------------------------------------------------------------
# Full run: bring up monitoring, run non-stream + stream sweeps, print links
# -----------------------------------------------------------------------------
.PHONY: bench-full

FULL_CONCURRENCY ?= 1 2 4 8
FULL_STREAM_CONCURRENCY ?= 4 8 16
FULL_DURATION ?= 20

bench-full:
	@echo "[full] Starting monitoring stack (Prometheus + Grafana)"
	$(MAKE) monitoring-up
	@echo "[full] Running non-stream sweep: $(FULL_CONCURRENCY) for $(FULL_DURATION)s"
	$(MAKE) bench-sweep CONCURRENCY="$(FULL_CONCURRENCY)" DURATION=$(FULL_DURATION)
	@echo "[full] Running stream sweep: $(FULL_STREAM_CONCURRENCY) for $(FULL_DURATION)s"
	$(MAKE) bench-stream CONCURRENCY="$(FULL_STREAM_CONCURRENCY)" DURATION=$(FULL_DURATION)
	@echo "[full] Done. Results in .benchmarks/bench_nonstream.json and .benchmarks/bench_stream.json"
	@echo "[full] Grafana: http://localhost:3000/d/tldw-llm-gateway (admin/admin)"
	@echo "[full] Prometheus: http://localhost:9090"
	@echo "[full] Tip: enable STREAMS_UNIFIED=1 on the server to populate SSE panels"
	@echo "[full] Stopping monitoring stack"
	$(MAKE) monitoring-down

# -----------------------------------------------------------------------------
# Chat Streaming Load Harness (Scenario A starter)
# -----------------------------------------------------------------------------
.PHONY: load-chat-stream

LOAD_CONCURRENCY ?= 100
LOAD_STREAMS_PER_CLIENT ?= 1
LOAD_PROMPT_BYTES ?= 512
CHAT_MODEL ?= gpt-4o-mini

load-chat-stream:
	@echo "[load] Chat streaming load: concurrency=$(LOAD_CONCURRENCY) streams/client=$(LOAD_STREAMS_PER_CLIENT) prompt_bytes=$(LOAD_PROMPT_BYTES)"
	python Helper_Scripts/load_tests/chat_streaming_load.py \
		--base-url $(BASE_URL) \
		--api-key "$(API_KEY)" \
		--model "$(CHAT_MODEL)" \
		--concurrency $(LOAD_CONCURRENCY) \
		--streams-per-client $(LOAD_STREAMS_PER_CLIENT) \
		--prompt-bytes $(LOAD_PROMPT_BYTES)

.PHONY: load-chat-stream-sweep load-chat-stream-sweep-http2

LOAD_CONCURRENCY_STEPS ?= 50 100 200

load-chat-stream-sweep:
	@echo "[load] Chat streaming sweep (HTTP/1.1): $(LOAD_CONCURRENCY_STEPS)"
	python Helper_Scripts/load_tests/chat_streaming_sweep.py \
		--base-url $(BASE_URL) \
		--api-key "$(API_KEY)" \
		--model "$(CHAT_MODEL)" \
		--concurrency-steps $(LOAD_CONCURRENCY_STEPS) \
		--streams-per-client $(LOAD_STREAMS_PER_CLIENT) \
		--prompt-bytes $(LOAD_PROMPT_BYTES)

load-chat-stream-sweep-http2:
	@echo "[load] Chat streaming sweep (HTTP/2): $(LOAD_CONCURRENCY_STEPS)"
	python Helper_Scripts/load_tests/chat_streaming_sweep.py \
		--base-url $(BASE_URL) \
		--api-key "$(API_KEY)" \
		--model "$(CHAT_MODEL)" \
		--concurrency-steps $(LOAD_CONCURRENCY_STEPS) \
		--streams-per-client $(LOAD_STREAMS_PER_CLIENT) \
		--prompt-bytes $(LOAD_PROMPT_BYTES) \
		--http2

# Canonical Scenario A sweeps (short vs longer prompts)
.PHONY: scenario-a-short-http1 scenario-a-short-http2 scenario-a-long-http1 scenario-a-long-http2

SCENARIO_A_CONC_STEPS ?= 50 100 200 400 800
SCENARIO_A_SHORT_PROMPT_BYTES ?= 256
SCENARIO_A_LONG_PROMPT_BYTES ?= 1024

scenario-a-short-http1:
	@echo "[scenario-a] Short prompt, HTTP/1.1 (concurrency=$(SCENARIO_A_CONC_STEPS), prompt_bytes=$(SCENARIO_A_SHORT_PROMPT_BYTES))"
	$(MAKE) load-chat-stream-sweep \
		LOAD_CONCURRENCY_STEPS="$(SCENARIO_A_CONC_STEPS)" \
		LOAD_PROMPT_BYTES=$(SCENARIO_A_SHORT_PROMPT_BYTES)

scenario-a-short-http2:
	@echo "[scenario-a] Short prompt, HTTP/2 (concurrency=$(SCENARIO_A_CONC_STEPS), prompt_bytes=$(SCENARIO_A_SHORT_PROMPT_BYTES))"
	$(MAKE) load-chat-stream-sweep-http2 \
		LOAD_CONCURRENCY_STEPS="$(SCENARIO_A_CONC_STEPS)" \
		LOAD_PROMPT_BYTES=$(SCENARIO_A_SHORT_PROMPT_BYTES)

scenario-a-long-http1:
	@echo "[scenario-a] Longer prompt, HTTP/1.1 (concurrency=$(SCENARIO_A_CONC_STEPS), prompt_bytes=$(SCENARIO_A_LONG_PROMPT_BYTES))"
	$(MAKE) load-chat-stream-sweep \
		LOAD_CONCURRENCY_STEPS="$(SCENARIO_A_CONC_STEPS)" \
		LOAD_PROMPT_BYTES=$(SCENARIO_A_LONG_PROMPT_BYTES)

scenario-a-long-http2:
	@echo "[scenario-a] Longer prompt, HTTP/2 (concurrency=$(SCENARIO_A_CONC_STEPS), prompt_bytes=$(SCENARIO_A_LONG_PROMPT_BYTES))"
	$(MAKE) load-chat-stream-sweep-http2 \
		LOAD_CONCURRENCY_STEPS="$(SCENARIO_A_CONC_STEPS)" \
		LOAD_PROMPT_BYTES=$(SCENARIO_A_LONG_PROMPT_BYTES)

# -----------------------------------------------------------------------------
# STT Golden Adapter Validation (local/GPU-only)
# -----------------------------------------------------------------------------
.PHONY: stt-golden

STT_GOLDEN_AUDIO_DIR ?= ./test_models/stt_golden

stt-golden:
	@echo "[stt-golden] Running STT golden adapter tests against $(STT_GOLDEN_AUDIO_DIR)"
	TLDW_STT_GOLDEN_ENABLE=1 \
	TLDW_STT_GOLDEN_AUDIO_DIR="$(STT_GOLDEN_AUDIO_DIR)" \
	python -m pytest tldw_Server_API/tests/Audio/test_stt_adapters_golden.py -m "stt_golden" -v
