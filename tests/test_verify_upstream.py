from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_verify_upstream_fails_when_checkout_missing(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "scripts").mkdir()

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "verify-upstream.sh"

    env = os.environ.copy()
    env["TLDW_HOSTED_ROOT"] = str(repo_root)

    result = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "upstream/tldw_server" in result.stderr
