from __future__ import annotations

from pathlib import Path

import pytest


ENTRYPOINT_PATH = (
    Path(__file__).resolve().parents[3] / "Dockerfiles" / "ACP" / "entrypoint.sh"
)


@pytest.mark.unit
def test_entrypoint_rejects_explicit_root_runtime_home_before_trim_and_fallback() -> None:
    script = ENTRYPOINT_PATH.read_text(encoding="utf-8")

    assignment_idx = script.find('RUNTIME_HOME="${ACP_RUNTIME_HOME:-${USER_HOME}}"')
    guard_idx = script.find('if [ "${ACP_RUNTIME_HOME:-}" = "/" ]; then')
    trim_idx = script.find('RUNTIME_HOME="${RUNTIME_HOME%/}"')
    fallback_idx = script.find('RUNTIME_HOME="/workspace/.acp-home"')

    if assignment_idx == -1:
        pytest.fail("Expected ACP runtime-home assignment line in entrypoint.sh")
    if guard_idx == -1:
        pytest.fail("Expected explicit ACP_RUNTIME_HOME='/' guard in entrypoint.sh")
    if trim_idx == -1:
        pytest.fail("Expected runtime-home trim normalization line in entrypoint.sh")
    if fallback_idx == -1:
        pytest.fail("Expected runtime-home fallback assignment line in entrypoint.sh")
    if not (assignment_idx < guard_idx < trim_idx < fallback_idx):
        pytest.fail(
            "Expected explicit ACP_RUNTIME_HOME='/' guard between assignment and trim/fallback logic"
        )
