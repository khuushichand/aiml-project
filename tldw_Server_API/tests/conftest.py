import os
from pathlib import Path


# Establish writable temp/cache/log dirs inside the repo to satisfy sandboxed runs
BASE = Path(__file__).resolve().parents[1]  # tldw_Server_API/
TEST_TEMP = BASE / "Test_Temp"
TEST_CACHE = BASE / "Test_Cache"
TEST_LOGS = BASE / "Test_Logs"

# Core temp envs used by Python and many libs
os.environ.setdefault("TMPDIR", str(TEST_TEMP))
os.environ.setdefault("TEMP", str(TEST_TEMP))
os.environ.setdefault("TMP", str(TEST_TEMP))

# Some libraries (e.g., matplotlib) require a writable config/cache dir
os.environ.setdefault("MPLCONFIGDIR", str(TEST_CACHE / "matplotlib"))

# Transformers / HF caches can otherwise try to use user dirs
os.environ.setdefault("HF_HOME", str(TEST_CACHE / "hf_home"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(TEST_CACHE / "transformers"))

# Direct file-based loggers to a local, writable folder; or disable if needed
os.environ.setdefault("TLDB_LOG_DIR", str(TEST_LOGS))
os.environ.setdefault("TLDB_DISABLE_FILE_LOGS", "1")
