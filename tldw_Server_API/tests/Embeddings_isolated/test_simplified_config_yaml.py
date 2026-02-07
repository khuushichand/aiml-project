from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Embeddings.simplified_config import EmbeddingsConfig


@pytest.mark.unit
def test_embeddings_config_from_yaml_empty_file_uses_defaults():
    with tempfile.NamedTemporaryFile("w", delete=False) as handle:
        path = Path(handle.name)

    try:
        cfg = EmbeddingsConfig.from_yaml(str(path))
        assert isinstance(cfg, EmbeddingsConfig)
        assert cfg.default_provider == "openai"
        assert cfg.default_model == "text-embedding-3-small"
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.unit
def test_embeddings_config_from_yaml_rejects_non_mapping_root():
    with tempfile.NamedTemporaryFile("w", delete=False) as handle:
        handle.write("- not\n- a\n- mapping\n")
        path = Path(handle.name)

    try:
        with pytest.raises(ValueError, match="must be a mapping"):
            EmbeddingsConfig.from_yaml(str(path))
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.unit
def test_embeddings_config_from_dict_rejects_non_mapping():
    with pytest.raises(ValueError, match="must be a mapping"):
        EmbeddingsConfig.from_dict(["bad"])  # type: ignore[arg-type]
