from __future__ import annotations

import os
from pathlib import Path

import pytest

from tldw_Server_API.app.core.LLM_Calls.providers.mlx_model_discovery import (
    discover_mlx_models,
)


def _create_candidate_dir(
    root: Path,
    rel_path: str,
    *,
    config: bool = True,
    tokenizer: bool = True,
    weights: bool = True,
    tokenizer_file: str = "tokenizer.json",
    weights_file: str = "weights.safetensors",
) -> Path:
    model_dir = root / rel_path
    model_dir.mkdir(parents=True, exist_ok=True)
    if config:
        (model_dir / "config.json").write_text("{}")
    if tokenizer:
        (model_dir / tokenizer_file).write_text("{}")
    if weights:
        (model_dir / weights_file).write_text("x")
    return model_dir


@pytest.mark.unit
def test_discovery_returns_warning_when_model_dir_missing():
    result = discover_mlx_models(None)
    assert result["model_dir"] is None
    assert result["model_dir_configured"] is False
    assert result["available_models"] == []
    assert result["warnings"]


@pytest.mark.unit
def test_discovery_marks_manifest_selectability_and_reasons(tmp_path: Path):
    root = tmp_path / "mlx-models"
    _create_candidate_dir(root, "good/model-a")
    _create_candidate_dir(root, "missing-tokenizer/model-b", tokenizer=False)
    _create_candidate_dir(root, "missing-weights/model-c", weights=False)
    _create_candidate_dir(root, "missing-config/model-d", config=False)

    result = discover_mlx_models(root)
    models = {m["id"]: m for m in result["available_models"]}

    assert "good/model-a" in models
    assert models["good/model-a"]["selectable"] is True
    assert models["good/model-a"]["reasons"] == []

    assert models["missing-tokenizer/model-b"]["selectable"] is False
    assert "Missing tokenizer.json or tokenizer.model" in models["missing-tokenizer/model-b"]["reasons"]

    assert models["missing-weights/model-c"]["selectable"] is False
    assert "Missing *.safetensors or *.bin weights" in models["missing-weights/model-c"]["reasons"]

    assert models["missing-config/model-d"]["selectable"] is False
    assert "Missing config.json" in models["missing-config/model-d"]["reasons"]


@pytest.mark.unit
def test_discovery_is_recursive_and_sorted_by_name(tmp_path: Path):
    root = tmp_path / "mlx-models"
    _create_candidate_dir(root, "zulu/model-z")
    _create_candidate_dir(root, "alpha/model-a")
    _create_candidate_dir(root, "nested/charlie/model-c")

    result = discover_mlx_models(root)
    names = [m["name"] for m in result["available_models"]]
    assert names == sorted(names)

    ids = [m["id"] for m in result["available_models"]]
    assert "nested/charlie/model-c" in ids


@pytest.mark.unit
def test_discovery_ignores_symlink_entries(tmp_path: Path):
    root = tmp_path / "mlx-models"
    _create_candidate_dir(root, "real/model-a")

    target = root / "real/model-a"
    link_path = root / "linked-model"
    try:
        os.symlink(target, link_path, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("Symlink creation not supported in this environment")

    result = discover_mlx_models(root)
    ids = [m["id"] for m in result["available_models"]]
    assert "real/model-a" in ids
    assert "linked-model" not in ids
