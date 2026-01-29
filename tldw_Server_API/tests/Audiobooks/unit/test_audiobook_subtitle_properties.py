import math
import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tldw_Server_API.app.api.v1.schemas.audiobook_schemas import AlignmentPayload, AlignmentWord
from tldw_Server_API.app.core.Audiobooks.subtitle_generator import generate_subtitles

pytestmark = pytest.mark.unit


def _extract_srt_times(content: str) -> list[tuple[int, int]]:
    times: list[tuple[int, int]] = []
    for line in content.splitlines():
        if "-->" not in line:
            continue
        match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2}),(\d{3})", line)
        if not match:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, match.groups())
        start = ((h1 * 60 + m1) * 60 + s1) * 1000 + ms1
        end = ((h2 * 60 + m2) * 60 + s2) * 1000 + ms2
        times.append((start, end))
    return times


def _extract_srt_words(content: str) -> list[str]:
    tokens: list[str] = []
    for line in content.splitlines():
        if not line or "-->" in line or line.strip().isdigit():
            continue
        tokens.extend(line.split())
    return tokens


@st.composite
def alignment_payloads(draw):
    word_count = draw(st.integers(min_value=1, max_value=12))
    words = draw(
        st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("Ll", "Lu")),
                min_size=1,
                max_size=8,
            ),
            min_size=word_count,
            max_size=word_count,
        )
    )
    durations = draw(
        st.lists(
            st.integers(min_value=20, max_value=400),
            min_size=word_count,
            max_size=word_count,
        )
    )
    gaps = draw(
        st.lists(
            st.integers(min_value=0, max_value=60),
            min_size=word_count,
            max_size=word_count,
        )
    )
    current = 0
    alignment_words: list[AlignmentWord] = []
    for word, duration, gap in zip(words, durations, gaps):
        current += gap
        end = current + duration
        alignment_words.append(AlignmentWord(word=word, start_ms=current, end_ms=end))
        current = end
    return AlignmentPayload(engine="kokoro", sample_rate=24000, words=alignment_words)


@settings(max_examples=25)
@given(alignment=alignment_payloads(), words_per_cue=st.integers(min_value=1, max_value=5))
def test_word_count_cue_count_and_ordering(alignment: AlignmentPayload, words_per_cue: int):
    content = generate_subtitles(
        alignment,
        format="srt",
        mode="word_count",
        variant="wide",
        words_per_cue=words_per_cue,
    )
    blocks = [block for block in content.strip().split("\n\n") if block]
    expected_blocks = math.ceil(len(alignment.words) / words_per_cue)
    assert len(blocks) == expected_blocks

    times = _extract_srt_times(content)
    assert len(times) == expected_blocks
    for start, end in times:
        assert start <= end
    for earlier, later in zip(times, times[1:]):
        assert earlier[0] <= later[0]
        assert earlier[1] <= later[1]
        assert earlier[1] - earlier[0] >= 800
        assert earlier[1] - earlier[0] <= 6000

    output_words = _extract_srt_words(content)
    assert output_words == [word.word for word in alignment.words]


@settings(max_examples=25)
@given(alignment=alignment_payloads())
def test_highlight_mode_emits_one_cue_per_word(alignment: AlignmentPayload):
    content = generate_subtitles(
        alignment,
        format="srt",
        mode="highlight",
        variant="wide",
    )
    blocks = [block for block in content.strip().split("\n\n") if block]
    assert len(blocks) == len(alignment.words)
