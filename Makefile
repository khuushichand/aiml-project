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

