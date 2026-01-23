import re

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from tldw_Server_API.app.api.v1.schemas.audiobook_schemas import AlignmentPayload, AlignmentWord
from tldw_Server_API.app.core.Audiobooks.subtitle_generator import generate_subtitles

pytestmark = pytest.mark.unit

_TIME_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)


def _to_ms(h: str, m: str, s: str, ms: str) -> int:
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)


def _parse_srt_times(content: str) -> list[tuple[int, int]]:
    times: list[tuple[int, int]] = []
    for line in content.splitlines():
        match = _TIME_RE.search(line)
        if not match:
            continue
        start_ms = _to_ms(match.group(1), match.group(2), match.group(3), match.group(4))
        end_ms = _to_ms(match.group(5), match.group(6), match.group(7), match.group(8))
        times.append((start_ms, end_ms))
    return times


@st.composite
def _alignment_payloads(draw):
    count = draw(st.integers(min_value=1, max_value=20))
    gaps = draw(st.lists(st.integers(min_value=0, max_value=300), min_size=count, max_size=count))
    durations = draw(st.lists(st.integers(min_value=50, max_value=1500), min_size=count, max_size=count))
    words = []
    current = 0
    for i, (gap, duration) in enumerate(zip(gaps, durations)):
        current += gap
        end = current + duration
        words.append(
            AlignmentWord.model_construct(
                word=f"w{i}",
                start_ms=current,
                end_ms=end,
                char_start=None,
                char_end=None,
            )
        )
        current = end
    return AlignmentPayload.model_construct(engine="kokoro", sample_rate=24000, words=words)


@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=50)
@given(alignment=_alignment_payloads(), mode=st.sampled_from(["line", "sentence", "word_count"]))
def test_subtitle_invariants_monotonic(alignment, mode):
    content = generate_subtitles(
        alignment,
        format="srt",
        mode=mode,
        variant="wide",
        words_per_cue=3,
    )
    times = _parse_srt_times(content)
    assert times
    prev_start = 0
    prev_end = 0
    for start_ms, end_ms in times:
        assert start_ms >= 0
        assert end_ms >= start_ms
        assert start_ms >= prev_start
        assert end_ms >= prev_end or end_ms == prev_end
        prev_start = start_ms
        prev_end = end_ms
