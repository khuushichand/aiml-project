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
API_KEY ?= dev-key-123

server-up-dev:
	@echo "[server] Starting uvicorn in mock mode on $(HOST):$(PORT)"
	AUTH_MODE=single_user \
	SINGLE_USER_API_KEY="$(API_KEY)" \
	DEFAULT_LLM_PROVIDER=openai \
	CHAT_FORCE_MOCK=1 \
	STREAMS_UNIFIED=1 \
	uvicorn tldw_Server_API.app.main:app --host $(HOST) --port $(PORT) --reload

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
