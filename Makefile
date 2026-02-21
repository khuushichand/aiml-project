# -----------------------------------------------------------------------------
# Quickstart targets (first-time setup)
# -----------------------------------------------------------------------------
.PHONY: quickstart quickstart-install quickstart-prereqs quickstart-docker quickstart-docker-bootstrap quickstart-docker-webui verify pypi-build pypi-check

PYTHON ?= python3
VENV_DIR ?= .venv
VENV_PYTHON ?= $(VENV_DIR)/bin/python
TLDW_ENV_FILE ?= tldw_Server_API/Config_Files/.env
TLDW_ENV_TEMPLATE ?= tldw_Server_API/Config_Files/.env.quickstart
DOCKER_BASE_COMPOSE ?= Dockerfiles/docker-compose.yml
DOCKER_WEBUI_COMPOSE ?= Dockerfiles/docker-compose.webui.yml
NEXT_PUBLIC_API_URL ?= http://localhost:8000
PYPI_BUILD_ARGS ?= --no-isolation

quickstart-prereqs:
	@command -v $(PYTHON) >/dev/null 2>&1 || (echo "[quickstart] $(PYTHON) not found. Install Python 3.10+ and retry." && exit 1)
	@$(PYTHON) -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || (echo "[quickstart] Python 3.10+ is required." && exit 1)
	@$(PYTHON) -c 'import loguru, fastapi, uvicorn, dotenv' >/dev/null 2>&1 || (echo "[quickstart] Missing Python dependencies. Run: make quickstart-install" && exit 1)
	@if ! command -v ffmpeg >/dev/null 2>&1; then \
		echo "[quickstart] Warning: ffmpeg not found; audio/video features will be limited."; \
		case "$$(uname -s)" in \
			Darwin) echo "[quickstart] Install on macOS: brew install ffmpeg" ;; \
			Linux) \
				. /etc/os-release 2>/dev/null || true; \
				case "$${ID:-}" in \
					ubuntu|debian|linuxmint|pop) echo "[quickstart] Install on Ubuntu/Debian: sudo apt update && sudo apt install -y ffmpeg" ;; \
					fedora|rhel|centos|rocky|almalinux) echo "[quickstart] Install on Fedora/RHEL: sudo dnf install -y ffmpeg (RPM Fusion may be required)" ;; \
					arch) echo "[quickstart] Install on Arch: sudo pacman -S --needed ffmpeg" ;; \
					*) echo "[quickstart] Install ffmpeg via your Linux package manager." ;; \
				esac; \
				echo "[quickstart] Linux audio note: for PyAudio support install portaudio19-dev/python3-pyaudio (Debian/Ubuntu)." ;; \
		esac; \
	fi

quickstart-install:
	@command -v $(PYTHON) >/dev/null 2>&1 || (echo "[quickstart-install] $(PYTHON) not found. Install Python 3.10+ and retry." && exit 1)
	@$(PYTHON) -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || (echo "[quickstart-install] Python 3.10+ is required." && exit 1)
	@if [ ! -x "$(VENV_PYTHON)" ]; then \
		echo "[quickstart-install] Creating virtualenv at $(VENV_DIR)"; \
		$(PYTHON) -m venv $(VENV_DIR); \
	fi
	@echo "[quickstart-install] Installing Python dependencies into $(VENV_DIR)..."
	@$(VENV_PYTHON) -m pip install --upgrade pip setuptools wheel
	@$(VENV_PYTHON) -m pip install -e .
	@if [ "$$(uname -s)" = "Linux" ]; then \
		echo "[quickstart-install] Linux audio note: if PyAudio build/install fails, install PortAudio headers (e.g., sudo apt install -y portaudio19-dev python3-pyaudio)."; \
	fi
	@$(MAKE) quickstart PYTHON=$(VENV_PYTHON)

quickstart: quickstart-prereqs
	@echo "[quickstart] Setting up tldw_server for first-time use..."
	@mkdir -p $(dir $(TLDW_ENV_FILE))
	@test -f $(TLDW_ENV_FILE) || (cp $(TLDW_ENV_TEMPLATE) $(TLDW_ENV_FILE) && echo "[quickstart] Created $(TLDW_ENV_FILE) from template - set SINGLE_USER_API_KEY before exposing beyond localhost.")
	@echo "[quickstart] Initializing auth (non-interactive)..."
	$(PYTHON) -m tldw_Server_API.app.core.AuthNZ.initialize --non-interactive
	@echo "[quickstart] Starting server on http://127.0.0.1:8000"
	@echo "[quickstart] Verify with: curl http://localhost:8000/health"
	@echo "[quickstart] API docs at: http://127.0.0.1:8000/docs"
	$(PYTHON) -m uvicorn tldw_Server_API.app.main:app --host 127.0.0.1 --port 8000

quickstart-docker-bootstrap:
	@echo "[quickstart-docker-bootstrap] Ensuring $(TLDW_ENV_FILE) has safe first-use auth defaults..."
	@bash Helper_Scripts/docker_prepare_env.sh "$(TLDW_ENV_FILE)" "$(TLDW_ENV_TEMPLATE)"

quickstart-docker: quickstart-docker-bootstrap
	@echo "[quickstart-docker] Starting tldw_server via Docker Compose..."
	@command -v docker >/dev/null 2>&1 || (echo "[quickstart-docker] docker not found. Install Docker and retry." && exit 1)
	docker compose --env-file $(TLDW_ENV_FILE) -f $(DOCKER_BASE_COMPOSE) up -d --build
	@echo "[quickstart-docker] First-use auth initialization is handled automatically by the app entrypoint."
	@echo "[quickstart-docker] Server running at http://localhost:8000"
	@echo "[quickstart-docker] Verify with: curl http://localhost:8000/health"
	@echo "[quickstart-docker] API docs at: http://localhost:8000/docs"

quickstart-docker-webui: quickstart-docker-bootstrap
	@echo "[quickstart-docker-webui] Starting API + WebUI via Docker Compose..."
	@command -v docker >/dev/null 2>&1 || (echo "[quickstart-docker-webui] docker not found. Install Docker and retry." && exit 1)
	@echo "[quickstart-docker-webui] Using NEXT_PUBLIC_API_URL=$(NEXT_PUBLIC_API_URL)"
	NEXT_PUBLIC_API_URL="$(NEXT_PUBLIC_API_URL)" docker compose --env-file $(TLDW_ENV_FILE) -f $(DOCKER_BASE_COMPOSE) -f $(DOCKER_WEBUI_COMPOSE) up -d --build
	@echo "[quickstart-docker-webui] First-use auth initialization is handled automatically by the app entrypoint."
	@echo "[quickstart-docker-webui] API:   http://localhost:8000"
	@echo "[quickstart-docker-webui] WebUI: http://localhost:8080"

verify:
	@echo "[verify] Checking server health..."
	@curl -sf http://localhost:8000/health > /dev/null && echo "[verify] Health check PASSED" || (echo "[verify] Health check FAILED - is the server running?" && exit 1)

# -----------------------------------------------------------------------------
# PyPI packaging helpers
# -----------------------------------------------------------------------------

pypi-build:
	@command -v $(PYTHON) >/dev/null 2>&1 || (echo "[pypi-build] $(PYTHON) not found." && exit 1)
	@$(PYTHON) -m pip show build >/dev/null 2>&1 || (echo "[pypi-build] Missing 'build'. Install with: $(PYTHON) -m pip install build" && exit 1)
	@echo "[pypi-build] Cleaning previous artifacts..."
	@rm -rf build dist *.egg-info tldw_server.egg-info
	@echo "[pypi-build] Building sdist + wheel ($(PYPI_BUILD_ARGS))..."
	@$(PYTHON) -m build $(PYPI_BUILD_ARGS)

pypi-check: pypi-build
	@$(PYTHON) -m pip show twine >/dev/null 2>&1 || (echo "[pypi-check] Missing 'twine'. Install with: $(PYTHON) -m pip install twine" && exit 1)
	@echo "[pypi-check] Validating distributions..."
	@$(PYTHON) -m twine check dist/*

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
# Watchlists smoke
# -----------------------------------------------------------------------------
.PHONY: watchlists-audio-smoke

WATCHLISTS_BASE_URL ?= http://127.0.0.1:8000
WATCHLISTS_API_KEY ?= $(SINGLE_USER_API_KEY)
WATCHLISTS_AUDIO_SMOKE_ARGS ?=

watchlists-audio-smoke:
	@echo "[watchlists-audio-smoke] Running watchlists audio smoke against $(WATCHLISTS_BASE_URL)"
	$(PYTHON) Helper_Scripts/watchlists/watchlists_audio_smoke.py \
		--base-url "$(WATCHLISTS_BASE_URL)" \
		--api-key "$(WATCHLISTS_API_KEY)" \
		$(WATCHLISTS_AUDIO_SMOKE_ARGS)

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
# Lint (changed files only)
# -----------------------------------------------------------------------------
.PHONY: lint-changed

BASE ?=

lint-changed:
	@bash Helper_Scripts/Testing-related/lint-changed.sh $(BASE)

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

# -----------------------------------------------------------------------------
# Bandit (project-scoped)
# -----------------------------------------------------------------------------
.PHONY: bandit-b110-project

BANDIT_INI ?= .bandit
BANDIT_OUTPUT ?= /tmp/bandit_b110_project.json

bandit-b110-project:
	@echo "[bandit] Running project-scoped B110 scan with excludes from $(BANDIT_INI)"
	$(PYTHON) -m bandit --ini "$(BANDIT_INI)" -r . -t B110 -f json -o "$(BANDIT_OUTPUT)"
	@echo "[bandit] Wrote $(BANDIT_OUTPUT)"
