import os
from pathlib import Path
from typing import Optional


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

# Speed up embeddings auto-unload during tests to reduce idle timer waits
# Default in code is 300s; use 15s for test runs
os.environ.setdefault("TEST_EMBEDDINGS_UNLOAD_TIMEOUT_SECONDS", "15")

# Provide deterministic API key for single-user mode during tests
TEST_API_KEY = os.environ.setdefault("SINGLE_USER_API_KEY", "test-api-key-12345")
os.environ.setdefault("API_BEARER", TEST_API_KEY)

# Disable auto-download of large models during tests to avoid network/hangs
os.environ.setdefault("TTS_AUTO_DOWNLOAD", "0")

# Always isolate per-test user DBs to a writable temp path to avoid noisy migrations touching default DBs
os.environ.setdefault("USER_DB_BASE_DIR", str(TEST_TEMP / "user_databases"))

# Increase per-process file descriptor limit to avoid EMFILE during large suites
try:
    import resource  # type: ignore

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    # Aim for at least 4096, without exceeding the hard limit (unless it's RLIM_INFINITY)
    desired = 4096
    if hard == resource.RLIM_INFINITY:
        new_soft = max(soft, desired)
    else:
        new_soft = min(hard, max(soft, desired))
    if new_soft > soft:
        resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
except Exception:
    # Not all platforms allow raising limits (e.g., Windows). Best-effort only.
    pass

# Ensure the temp/cache/log directories exist
for _p in (TEST_TEMP, TEST_CACHE, TEST_LOGS):
    try:
        _p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def pytest_configure(config):
    config.addinivalue_line("markers", "legacy_tts: Legacy TTS integration tests hitting real models or providers")
    config.addinivalue_line("markers", "requires_api_key: Tests that require third-party API credentials")

# ------------------------------------------------------------------
# Fallback 'mocker' fixture when pytest-mock is not installed
# ------------------------------------------------------------------
try:
    import pytest_mock  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover - only used when plugin unavailable
    import pytest  # type: ignore
    from unittest.mock import patch as _unittest_patch

    @pytest.fixture
    def mocker():
        class _Mocker:
            def patch(self, *args, **kwargs):
                return _unittest_patch(*args, **kwargs)

        return _Mocker()
