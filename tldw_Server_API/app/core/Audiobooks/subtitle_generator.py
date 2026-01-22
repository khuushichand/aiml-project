"""Generate subtitle files from alignment payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from tldw_Server_API.app.api.v1.schemas.audiobook_schemas import (
    AlignmentPayload,
    AlignmentWord,
    SubtitleFormat,
    SubtitleMode,
    SubtitleVariant,
)


@dataclass(frozen=True)
class SubtitleCue:
    index: int
    start_ms: int
    end_ms: int
    text: str


def generate_subtitles(
    alignment: AlignmentPayload,
    *,
    format: SubtitleFormat,
    mode: SubtitleMode,
    variant: SubtitleVariant,
    words_per_cue: Optional[int] = None,
    max_chars: Optional[int] = None,
    max_lines: Optional[int] = None,
) -> str:
    """Generate subtitle content for the requested format."""
    words = alignment.words
    if not words:
        raise ValueError("alignment words must not be empty")

    effective_words_per_cue = words_per_cue or 1
    if effective_words_per_cue <= 0:
        raise ValueError("words_per_cue must be positive")

    effective_max_chars = _resolve_max_chars(max_chars, variant)
    cues = _build_cues(words, mode, effective_words_per_cue)
    line_sep = "\\N" if format == "ass" else "\n"

    rendered: List[SubtitleCue] = []
    for idx, cue_words in enumerate(cues, start=1):
        start_ms = cue_words[0].start_ms
        end_ms = cue_words[-1].end_ms
        if end_ms < start_ms:
            raise ValueError("alignment end_ms must be >= start_ms")
        text = _render_text(cue_words, effective_max_chars, max_lines, line_sep)
        rendered.append(SubtitleCue(index=idx, start_ms=start_ms, end_ms=end_ms, text=text))

    if format == "srt":
        return _format_srt(rendered)
    if format == "vtt":
        return _format_vtt(rendered)
    if format == "ass":
        return _format_ass(rendered)
    raise ValueError(f"unsupported subtitle format: {format}")


def _resolve_max_chars(max_chars: Optional[int], variant: SubtitleVariant) -> Optional[int]:
    if max_chars is not None:
        return max_chars
    if variant == "narrow":
        return 42
    return None


def _build_cues(
    words: Sequence[AlignmentWord],
    mode: SubtitleMode,
    words_per_cue: int,
) -> List[List[AlignmentWord]]:
    if mode == "highlight":
        return [[word] for word in words]
    if mode == "word_count":
        return _chunk_words(words, words_per_cue)
    if mode == "sentence":
        return _chunk_sentences(words)
    # line mode defaults to a single cue unless word_count requested
    return [list(words)]


def _chunk_words(words: Sequence[AlignmentWord], words_per_cue: int) -> List[List[AlignmentWord]]:
    cues: List[List[AlignmentWord]] = []
    for i in range(0, len(words), words_per_cue):
        cues.append(list(words[i : i + words_per_cue]))
    return cues


def _chunk_sentences(words: Sequence[AlignmentWord]) -> List[List[AlignmentWord]]:
    cues: List[List[AlignmentWord]] = []
    current: List[AlignmentWord] = []
    for word in words:
        current.append(word)
        if word.word.strip().endswith((".", "!", "?")):
            cues.append(current)
            current = []
    if current:
        cues.append(current)
    return cues


def _render_text(
    words: Sequence[AlignmentWord],
    max_chars: Optional[int],
    max_lines: Optional[int],
    line_sep: str,
) -> str:
    tokens = [word.word for word in words]
    if max_chars is None:
        return " ".join(tokens).strip()
    lines: List[str] = []
    current: List[str] = []
    for token in tokens:
        candidate = " ".join(current + [token]) if current else token
        if len(candidate) <= max_chars or not current:
            current.append(token)
            continue
        lines.append(" ".join(current))
        current = [token]
    if current:
        lines.append(" ".join(current))
    if max_lines is not None and len(lines) > max_lines:
        merged = " ".join(lines[max_lines - 1 :])
        lines = lines[: max_lines - 1] + [merged]
    return line_sep.join(lines).strip()


def _format_srt(cues: Iterable[SubtitleCue]) -> str:
    blocks: List[str] = []
    for cue in cues:
        start = _format_srt_time(cue.start_ms)
        end = _format_srt_time(cue.end_ms)
        blocks.append(f"{cue.index}\n{start} --> {end}\n{cue.text}")
    return "\n\n".join(blocks).strip()


def _format_vtt(cues: Iterable[SubtitleCue]) -> str:
    blocks: List[str] = ["WEBVTT"]
    for cue in cues:
        start = _format_vtt_time(cue.start_ms)
        end = _format_vtt_time(cue.end_ms)
        blocks.append(f"{start} --> {end}\n{cue.text}")
    return "\n\n".join(blocks).strip()


def _format_ass(cues: Iterable[SubtitleCue]) -> str:
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,"
        "Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        "Style: Default,Arial,28,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,"
        "0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text"
    )
    lines: List[str] = [header]
    for cue in cues:
        start = _format_ass_time(cue.start_ms)
        end = _format_ass_time(cue.end_ms)
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{cue.text}")
    return "\n".join(lines).strip()


def _format_srt_time(ms: int) -> str:
    hours, minutes, seconds, millis = _split_time(ms)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _format_vtt_time(ms: int) -> str:
    hours, minutes, seconds, millis = _split_time(ms)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _format_ass_time(ms: int) -> str:
    hours, minutes, seconds, millis = _split_time(ms)
    centis = millis // 10
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}"


def _split_time(ms: int) -> tuple[int, int, int, int]:
    total_seconds, millis = divmod(ms, 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return hours, minutes, seconds, millis
