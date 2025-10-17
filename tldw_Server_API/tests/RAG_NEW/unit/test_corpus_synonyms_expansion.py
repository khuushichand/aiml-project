import json
from pathlib import Path
import os
import pytest

from tldw_Server_API.app.core.RAG.rag_service.query_expansion import multi_strategy_expansion
from tldw_Server_API.app.core.RAG.rag_service.synonyms_registry import get_corpus_synonyms


@pytest.mark.asyncio
async def test_multi_strategy_expansion_uses_corpus_synonyms(tmp_path):
    # Create a temporary corpus synonyms file
    project_root = Path(__file__).resolve().parents[5]
    syn_dir = project_root / "tldw_Server_API" / "Config_Files" / "Synonyms"
    syn_dir.mkdir(parents=True, exist_ok=True)
    corpus = "test_corpus_xyz"
    syn_file = syn_dir / f"{corpus}.json"
    data = {"cuda": ["compute unified device architecture"]}
    syn_file.write_text(json.dumps(data), encoding="utf-8")

    try:
        q = "cuda memory model"
        out = await multi_strategy_expansion(q, strategies=["synonym", "domain"], corpus=corpus)
        assert isinstance(out, str)
        # Ensure alias appears in the expanded text
        assert "compute unified device architecture" in out
    finally:
        # Cleanup
        try:
            syn_file.unlink()
        except Exception:
            pass


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
