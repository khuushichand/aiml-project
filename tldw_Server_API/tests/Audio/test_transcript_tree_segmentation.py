import asyncio
from typing import List

import numpy as np

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Transcript_TreeSegmentation import (
    TreeSegmenter,
)


def _one_hot_for_line(line: str) -> List[float]:
    if "TOPIC_A" in line:
        return [1.0, 0.0, 0.0]
    if "TOPIC_B" in line:
        return [0.0, 1.0, 0.0]
    if "TOPIC_C" in line:
        return [0.0, 0.0, 1.0]
    # default small noise for unexpected
    return [0.1, 0.1, 0.1]


async def _stub_embedder(chunks: List[str]) -> List[List[float]]:
    embs: List[List[float]] = []
    for chunk in chunks:
        lines = [l for l in chunk.splitlines() if l.strip()]
        if not lines:
            embs.append([0.0, 0.0, 0.0])
            continue
        vec = np.zeros(3, dtype=float)
        for ln in lines:
            vec += np.array(_one_hot_for_line(ln))
        vec = (vec / max(1, len(lines))).tolist()
        embs.append(vec)
    return embs


def test_tree_segmentation_three_topics():
    # Build 30 utterances: 10 of A, 10 of B, 10 of C
    entries = []
    for i in range(10):
        entries.append({"composite": f"TOPIC_A: statement {i}", "speaker": "A"})
    for i in range(10):
        entries.append({"composite": f"TOPIC_B: comment {i}", "speaker": "B"})
    for i in range(10):
        entries.append({"composite": f"TOPIC_C: remark {i}", "speaker": "C"})

    configs = {
        "MIN_SEGMENT_SIZE": 3,
        "LAMBDA_BALANCE": 0.01,
        # Keep width 0 for deterministic splits exactly at 10 and 20
        "UTTERANCE_EXPANSION_WIDTH": 0,
    }

    segmenter = TreeSegmenter(configs=configs, entries=entries, embedder=_stub_embedder)
    transitions = segmenter.segment_meeting(K=3)

    ones = [i for i, v in enumerate(transitions) if v == 1]
    assert ones == [10, 20]

    segs = segmenter.get_segments()
    assert len(segs) == 3
    assert segs[0]["start_index"] == 0 and segs[0]["end_index"] == 9
    assert segs[1]["start_index"] == 10 and segs[1]["end_index"] == 19
    assert segs[2]["start_index"] == 20 and segs[2]["end_index"] == 29


def test_tree_segmentation_small_transcript_no_split():
    # N=6, MIN_SEGMENT_SIZE=4 => 2*min=8 > N, cannot split
    entries = [{"composite": f"TOPIC_A {i}"} for i in range(6)]
    configs = {
        "MIN_SEGMENT_SIZE": 4,
        "LAMBDA_BALANCE": 0.01,
        "UTTERANCE_EXPANSION_WIDTH": 0,
    }
    segmenter = TreeSegmenter(configs=configs, entries=entries, embedder=_stub_embedder)
    transitions = segmenter.segment_meeting(K=2)
    assert transitions == [0] * 6
    segs = segmenter.get_segments()
    assert len(segs) == 1
    assert segs[0]["start_index"] == 0 and segs[0]["end_index"] == 5


def test_segments_metadata_preserved():
    # 8 entries, 4 A then 4 B, with times
    entries = []
    t = 0.0
    for i in range(4):
        entries.append({
            "composite": f"TOPIC_A {i}",
            "speaker": "Alice",
            "start": t,
            "end": t + 1.0,
        })
        t += 1.1
    for i in range(4):
        entries.append({
            "composite": f"TOPIC_B {i}",
            "speaker": "Bob",
            "start": t,
            "end": t + 1.0,
        })
        t += 1.1

    configs = {
        "MIN_SEGMENT_SIZE": 2,
        "LAMBDA_BALANCE": 0.01,
        "UTTERANCE_EXPANSION_WIDTH": 0,
    }
    segmenter = TreeSegmenter(configs=configs, entries=entries, embedder=_stub_embedder)
    _ = segmenter.segment_meeting(K=2)
    segs = segmenter.get_segments()

    assert len(segs) == 2
    assert segs[0]["start_index"] == 0 and segs[0]["end_index"] == 3
    assert segs[1]["start_index"] == 4 and segs[1]["end_index"] == 7
    assert "Alice" in segs[0]["speakers"] and "Bob" in segs[1]["speakers"]
    assert segs[0]["start_time"] == entries[0]["start"]
    assert segs[1]["end_time"] == entries[-1]["end"]
