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

# Disable auto-download of large models during tests to avoid network/hangs
os.environ.setdefault("TTS_AUTO_DOWNLOAD", "0")

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
