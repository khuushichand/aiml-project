import json
from pathlib import Path
import os
import pytest

from tldw_Server_API.app.core.RAG.rag_service.query_expansion import multi_strategy_expansion
from tldw_Server_API.app.core.RAG.rag_service.synonyms_registry import get_corpus_synonyms


@pytest.mark.asyncio
async def test_multi_strategy_expansion_uses_corpus_synonyms(tmp_path, monkeypatch):
    # Create an isolated config root with Synonyms under a temporary directory
    config_dir = tmp_path / "etc" / "tldw"
    syn_dir = config_dir / "Synonyms"
    syn_dir.mkdir(parents=True, exist_ok=True)

    # Minimal config file to anchor TLDW_CONFIG_PATH
    config_file = config_dir / "config.txt"
    config_file.write_text("# dummy config", encoding="utf-8")

    # Write corpus-specific synonyms into the isolated Synonyms/ directory
    corpus = "test_corpus_xyz"
    syn_file = syn_dir / f"{corpus}.json"
    data = {"cuda": ["compute unified device architecture"]}
    syn_file.write_text(json.dumps(data), encoding="utf-8")

    # Point loader to the isolated config root
    monkeypatch.setenv("TLDW_CONFIG_PATH", str(config_file))

    q = "cuda memory model"
    out = await multi_strategy_expansion(q, strategies=["synonym", "domain"], corpus=corpus)
    assert isinstance(out, str)
    # Ensure alias appears in the expanded text
    assert "compute unified device architecture" in out


def test_get_corpus_synonyms_respects_config_env(tmp_path, monkeypatch):
    config_dir = tmp_path / "etc" / "tldw"
    syn_dir = config_dir / "Synonyms"
    syn_dir.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / "config.txt"
    config_file.write_text("# dummy config", encoding="utf-8")

    corpus = "custom_corpus"
    (syn_dir / f"{corpus}.json").write_text(
        json.dumps({"CUDA": ["Compute Unified Device Architecture"]}),
        encoding="utf-8",
    )

    monkeypatch.setenv("TLDW_CONFIG_PATH", str(config_file))
    try:
        synonyms = get_corpus_synonyms(corpus)
        assert synonyms == {"cuda": ["compute unified device architecture"]}
    finally:
        monkeypatch.delenv("TLDW_CONFIG_PATH", raising=False)
