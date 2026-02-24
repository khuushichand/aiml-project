from pathlib import Path

import yaml


def test_action_exposes_required_outputs() -> None:
    action_path = Path(".github/actions/detect-required-gate-changes/action.yml")
    data = yaml.safe_load(action_path.read_text(encoding="utf-8"))
    outputs = data["outputs"]

    for output_name in [
        "backend_changed",
        "frontend_changed",
        "e2e_changed",
        "security_relevant_changed",
        "coverage_required",
    ]:
        assert output_name in outputs
