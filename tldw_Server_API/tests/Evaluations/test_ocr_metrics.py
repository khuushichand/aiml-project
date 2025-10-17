from tldw_Server_API.app.core.Evaluations.ocr_evaluator import char_error_rate, word_error_rate, OCREvaluator
import asyncio


def test_cer_basic():
    ref = "hello world"
    hyp = "hello wurld"
    cer = char_error_rate(hyp, ref)
    # 1 substitution out of 11 chars -> ~0.0909
    assert 0.08 < cer < 0.12


def test_wer_basic():
    ref = "the quick brown fox"
    hyp = "the quick brown fx"
    wer = word_error_rate(hyp, ref)
    # 1 substitution out of 4 words -> 0.25
    assert abs(wer - 0.25) < 1e-6


def test_ocr_evaluator_extracted_text_only():
    items = [
        {
            "id": "doc1",
            "extracted_text": "hello world",
            "ground_truth_text": "hello world",
        },
        {
            "id": "doc2",
            "extracted_text": "hello wurld",
            "ground_truth_text": "hello world",
        },
    ]
    ev = OCREvaluator()
    results = asyncio.run(ev.evaluate(items=items))
    assert results["summary"]["count"] == 2
    # first item perfect
    doc1 = next(r for r in results["results"] if r["id"] == "doc1")
    assert doc1.get("cer", 0.0) == 0.0
    assert doc1.get("wer", 0.0) == 0.0
    # second item has small error
    doc2 = next(r for r in results["results"] if r["id"] == "doc2")
    assert doc2.get("cer", 0.0) > 0.0
    assert doc2.get("wer", 0.0) >= 0.0
