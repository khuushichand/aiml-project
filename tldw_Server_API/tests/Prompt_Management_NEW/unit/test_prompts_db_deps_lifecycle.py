"""
Lifecycle regression tests for Prompts DB dependency wiring.
"""

import os
import subprocess
import sys

import pytest

from tldw_Server_API.app.api.v1.API_Deps import Prompts_DB_Deps


@pytest.mark.unit
def test_prompts_db_deps_import_has_no_unawaited_coroutine_warning() -> None:
    script = (
        "import gc\n"
        "import tldw_Server_API.app.api.v1.API_Deps.Prompts_DB_Deps\n"
        "gc.collect()\n"
    )
    env = os.environ.copy()
    env["PYTHONWARNINGS"] = "always"
    proc = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    combined = f"{proc.stdout}\n{proc.stderr}"
    assert proc.returncode == 0, combined
    assert "was never awaited" not in combined
    assert "_process_pending_closes" not in combined


@pytest.mark.asyncio
@pytest.mark.unit
async def test_prompts_pending_close_worker_start_stop_cycle() -> None:
    started = Prompts_DB_Deps.start_prompts_pending_close_worker()
    assert started is True
    assert Prompts_DB_Deps._pending_close_task is not None
    await Prompts_DB_Deps.stop_prompts_pending_close_worker()
    assert Prompts_DB_Deps._pending_close_task is None
