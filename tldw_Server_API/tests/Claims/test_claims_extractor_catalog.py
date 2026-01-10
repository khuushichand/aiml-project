import pytest

from tldw_Server_API.app.core.Claims_Extraction.extractor_catalog import (
    resolve_claims_extractor_mode,
    split_claims_sentences,
)


@pytest.mark.unit
def test_resolve_claims_extractor_mode_auto_detects_no_space_language():
    text = "这是一个比较长的中文句子。这里还有另一个比较长的句子。"
    mode, language = resolve_claims_extractor_mode("auto", text)
    assert mode == "heuristic"
    assert language == "zh"


@pytest.mark.unit
def test_split_claims_sentences_no_space_language():
    text = "这是一个比较长的中文句子。这里还有另一个比较长的句子。"
    sentences = split_claims_sentences(text, "zh")
    assert len(sentences) == 2
    assert all(sentence.endswith("。") for sentence in sentences)
