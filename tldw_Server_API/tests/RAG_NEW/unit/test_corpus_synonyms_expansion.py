import json
from pathlib import Path
import os
import pytest

from tldw_Server_API.app.core.RAG.rag_service.query_expansion import multi_strategy_expansion


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
