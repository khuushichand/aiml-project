"""Generate subtitle files from alignment payloads."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Iterable, List, Optional, Sequence

from loguru import logger

from tldw_Server_API.app.core.Utils.common import parse_boolean
from tldw_Server_API.app.core.config import get_config_value
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
    source_text: Optional[str] = None,
    enable_spacy: Optional[bool] = None,
    words_per_cue: Optional[int] = None,
    max_chars: Optional[int] = None,
    max_lines: Optional[int] = None,
    max_duration_ms: Optional[int] = None,
) -> str:
    """Generate subtitle content for the requested format."""
    words = alignment.words
    if not words:
        raise ValueError("alignment words must not be empty")

    effective_words_per_cue = words_per_cue or 1
    if effective_words_per_cue <= 0:
        raise ValueError("words_per_cue must be positive")

    effective_max_chars = _resolve_max_chars(max_chars, variant)
    if mode == "sentence":
        cues = _chunk_sentences(words, source_text=source_text, enable_spacy=enable_spacy)
        duration_limit = max_duration_ms if max_duration_ms is not None else 6000
        if _should_fallback_sentence(cues, effective_max_chars, duration_limit):
            cues = _chunk_words(words, effective_words_per_cue)
    else:
        cues = _build_cues(words, mode, effective_words_per_cue)
    line_sep = "\\N" if format == "ass" else "\n"

    rendered: List[SubtitleCue] = []
    for idx, cue_words in enumerate(cues, start=1):
        start_ms = cue_words[0].start_ms
        end_ms = cue_words[-1].end_ms
        if end_ms < start_ms:
            raise ValueError("alignment end_ms must be >= start_ms")
        if mode == "highlight":
            word = cue_words[0]
            if format == "vtt":
                text = f"<c.hl>{word.word}</c>"
            elif format == "ass":
                duration_cs = max(1, (end_ms - start_ms) // 10)
                text = f"{{\\k{duration_cs}}}{word.word}"
            else:
                text = word.word
        else:
            text = _render_text(cue_words, effective_max_chars, max_lines, line_sep)
        if mode == "word_count":
            start_ms, end_ms = _clamp_cue_duration(start_ms, end_ms)
        rendered.append(SubtitleCue(index=idx, start_ms=start_ms, end_ms=end_ms, text=text))

    if format == "srt":
        return _format_srt(rendered)
    if format == "vtt":
        return _format_vtt(rendered, variant)
    if format == "ass":
        return _format_ass(rendered, variant)
    raise ValueError(f"unsupported subtitle format: {format}")


def _resolve_max_chars(max_chars: Optional[int], variant: SubtitleVariant) -> Optional[int]:
    if max_chars is not None:
        return max_chars
    if variant == "narrow":
        return 28
    if variant in {"wide", "centered"}:
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
        return _chunk_sentences(words, source_text=None, enable_spacy=None)
    return _chunk_lines(words)


def _chunk_words(words: Sequence[AlignmentWord], words_per_cue: int) -> List[List[AlignmentWord]]:
    cues: List[List[AlignmentWord]] = []
    for i in range(0, len(words), words_per_cue):
        cues.append(list(words[i : i + words_per_cue]))
    return cues


def _chunk_sentences(
    words: Sequence[AlignmentWord],
    *,
    source_text: Optional[str],
    enable_spacy: Optional[bool],
) -> List[List[AlignmentWord]]:
    if source_text and _should_use_spacy(enable_spacy):
        spacy_cues = _chunk_sentences_spacy(words, source_text)
        if spacy_cues:
            return spacy_cues
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


def _chunk_sentences_spacy(
    words: Sequence[AlignmentWord],
    source_text: str,
) -> Optional[List[List[AlignmentWord]]]:
    nlp = _load_spacy_model()
    if nlp is None:
        return None
    try:
        doc = nlp(source_text)
    except Exception as exc:
        logger.warning("spaCy sentence parsing failed: %s", exc)
        return None
    sentences = list(getattr(doc, "sents", []) or [])
    if not sentences:
        return None

    cues: List[List[AlignmentWord]] = []
    current: List[AlignmentWord] = []
    sent_idx = 0
    current_end = sentences[0].end_char
    for word in words:
        if word.char_start is not None:
            while sent_idx < len(sentences) and word.char_start >= current_end:
                if current:
                    cues.append(current)
                    current = []
                sent_idx += 1
                if sent_idx < len(sentences):
                    current_end = sentences[sent_idx].end_char
        current.append(word)
    if current:
        cues.append(current)
    return cues if cues else None


def _should_use_spacy(enable_spacy: Optional[bool]) -> bool:
    if enable_spacy is not None:
        return enable_spacy
    env_value = os.getenv("AUDIOBOOK_ENABLE_SPACY")
    if env_value is not None:
        return parse_boolean(env_value, default=False)
    cfg_value = get_config_value("Audiobooks", "enable_spacy_sentence_splitting")
    return parse_boolean(cfg_value, default=False)


@lru_cache(maxsize=1)
def _load_spacy_model():
    try:
        import spacy  # type: ignore
    except Exception as exc:
        logger.warning("spaCy unavailable: %s", exc)
        return None

    model_name = os.getenv("AUDIOBOOK_SPACY_MODEL") or get_config_value(
        "Audiobooks", "spacy_model", "en_core_web_sm"
    )
    try:
        return spacy.load(model_name)
    except Exception as exc:
        logger.warning("Failed to load spaCy model '%s': %s", model_name, exc)
        return None


def _chunk_lines(words: Sequence[AlignmentWord]) -> List[List[AlignmentWord]]:
    cues: List[List[AlignmentWord]] = []
    current: List[AlignmentWord] = []
    for word in words:
        current.append(word)
        if "\n" in word.word:
            cues.append(current)
            current = []
    if current:
        cues.append(current)
    return cues


def _should_fallback_sentence(
    cues: Sequence[Sequence[AlignmentWord]],
    max_chars: Optional[int],
    max_duration_ms: int,
) -> bool:
    for cue in cues:
        if not cue:
            continue
        duration = cue[-1].end_ms - cue[0].start_ms
        if duration > max_duration_ms:
            return True
        if max_chars is not None:
            text = " ".join(word.word for word in cue).replace("\n", " ").strip()
            if len(text) > max_chars:
                return True
    return False


def _clamp_cue_duration(start_ms: int, end_ms: int) -> tuple[int, int]:
    min_duration = 800
    max_duration = 6000
    duration = end_ms - start_ms
    if duration < min_duration:
        end_ms = start_ms + min_duration
    elif duration > max_duration:
        end_ms = start_ms + max_duration
    return start_ms, end_ms


def _render_text(
    words: Sequence[AlignmentWord],
    max_chars: Optional[int],
    max_lines: Optional[int],
    line_sep: str,
) -> str:
    tokens = [word.word for word in words]
    if max_lines is not None and max_lines <= 0:
        raise ValueError("max_lines must be positive")
    if max_chars is not None and max_chars <= 0:
        raise ValueError("max_chars must be positive")

    if line_sep == "\n":
        raw_text = " ".join(tokens).replace("\n", " ").strip()
    else:
        raw_text = " ".join(tokens).strip()
    if max_chars is None and max_lines is None:
        return raw_text

    if max_chars is None:
        if max_lines is None:
            return raw_text
        # split lines only on explicit newlines for line mode cues
        if line_sep == "\n":
            lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        else:
            lines = [raw_text]
        if max_lines is not None and len(lines) > max_lines:
            merged = " ".join(lines[max_lines - 1 :])
            lines = lines[: max_lines - 1] + [merged]
        return line_sep.join(lines).strip()
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
    if line_sep == "\n":
        rendered = line_sep.join(lines).replace("\n\n", "\n").strip()
    else:
        rendered = line_sep.join(lines).strip()
    return rendered


def _format_srt(cues: Iterable[SubtitleCue]) -> str:
    blocks: List[str] = []
    for cue in cues:
        start = _format_srt_time(cue.start_ms)
        end = _format_srt_time(cue.end_ms)
        blocks.append(f"{cue.index}\n{start} --> {end}\n{cue.text}")
    return "\n\n".join(blocks).strip()


def _format_vtt(cues: Iterable[SubtitleCue], variant: SubtitleVariant) -> str:
    blocks: List[str] = ["WEBVTT"]
    settings = " align:center" if variant == "centered" else ""
    for cue in cues:
        start = _format_vtt_time(cue.start_ms)
        end = _format_vtt_time(cue.end_ms)
        blocks.append(f"{start} --> {end}{settings}\n{cue.text}")
    return "\n\n".join(blocks).strip()


def _format_ass(cues: Iterable[SubtitleCue], variant: SubtitleVariant) -> str:
    alignment = "2" if variant == "centered" else "1"
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,"
        "Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        "Style: Default,Arial,28,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,"
        f"0,0,0,0,100,100,0,0,1,2,0,{alignment},10,10,10,1\n\n"
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
