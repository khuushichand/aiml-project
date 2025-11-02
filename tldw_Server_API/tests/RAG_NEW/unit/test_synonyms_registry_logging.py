from pathlib import Path
from loguru import logger


def test_get_corpus_synonyms_logs_selection_and_does_not_create(tmp_path, monkeypatch):
    # Ensure no env overrides so defaults are used
    monkeypatch.delenv("TLDW_CONFIG_DIR", raising=False)
    monkeypatch.delenv("TLDW_CONFIG_PATH", raising=False)

    # Import module under test
    from tldw_Server_API.app.core.RAG.rag_service import synonyms_registry as sr

    # Capture loguru output
    messages = []

    def _sink(msg):
        try:
            messages.append(str(msg))
        except Exception:
            pass

    sink_id = logger.add(_sink, level="DEBUG", format="{message}")
    try:
        corpus = "nonexistent_corpus_pytest_xyz"
        # Compute expected target path (should not be created by the function)
        cfg_root = sr._get_config_root()  # type: ignore[attr-defined]
        expected = cfg_root / "Synonyms" / f"{corpus}.json"
        if expected.exists():
            # If present for some reason in the environment, pick a new unique name
            corpus = corpus + "_2"
            expected = cfg_root / "Synonyms" / f"{corpus}.json"

        # Call the function (should not create files/dirs) and return empty mapping
        out = sr.get_corpus_synonyms(corpus)
        assert out == {}, f"Expected empty mapping for missing corpus, got: {out}"

        # Validate log contains path selection and existence flag
        joined = "\n".join(messages)
        assert "Synonyms file selection:" in joined, "Missing selection log"
        assert f"corpus='{corpus}'" in joined, "Missing corpus in selection log"
        assert "exists=False" in joined or "exists=False" in joined, "Missing existence status in log"

        # Ensure the file (and parent) were not created
        assert not expected.exists(), f"Function should not create: {expected}"
        assert not expected.parent.exists() or expected.parent.is_dir(), "Parent presence should not be forced by function"
    finally:
        try:
            logger.remove(sink_id)
        except Exception:
            pass
