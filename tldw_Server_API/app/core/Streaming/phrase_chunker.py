"""Phrase-level chunker for streaming TTS synthesis."""

from __future__ import annotations


class PhraseChunker:
    """Incrementally chunk streaming text into phrase-sized synthesis units."""

    _SENTENCE_PUNCT = {".", "!", "?"}
    _STRONG_PUNCT = {";", ":"}

    def __init__(self, min_chars: int = 15, max_chars: int = 80) -> None:
        self.min_chars = max(1, int(min_chars))
        self.max_chars = max(self.min_chars, int(max_chars))
        self._buffer = ""

    def push(self, delta: str) -> list[str]:
        """Append *delta* to the buffer and return any complete phrase chunks."""
        if not isinstance(delta, str) or not delta:
            return []
        self._buffer += delta
        return self._drain_ready_chunks()

    def flush(self) -> str:
        """Return any remaining buffered text and reset the buffer."""
        tail = self._buffer.strip()
        self._buffer = ""
        return tail

    def _drain_ready_chunks(self) -> list[str]:
        chunks: list[str] = []
        while True:
            cut_idx = self._find_cut_index()
            if cut_idx is None:
                break
            chunk = self._buffer[:cut_idx].strip()
            self._buffer = self._buffer[cut_idx:].lstrip()
            if chunk:
                chunks.append(chunk)
        return chunks

    def _find_cut_index(self) -> int | None:
        text = self._buffer
        if not text:
            return None

        if len(text) > self.max_chars:
            sentence_idx = self._find_last_punct(self._SENTENCE_PUNCT, upper=self.max_chars)
            if sentence_idx is not None:
                return sentence_idx + 1
            strong_idx = self._find_last_punct(self._STRONG_PUNCT, upper=self.max_chars)
            if strong_idx is not None:
                return strong_idx + 1
            ws_idx = self._find_last_whitespace(lower=self.min_chars, upper=self.max_chars)
            if ws_idx is not None:
                return ws_idx
            return self.max_chars

        sentence_idx = self._find_last_punct(self._SENTENCE_PUNCT)
        if sentence_idx is not None and sentence_idx < len(text) - 1:
            return sentence_idx + 1

        strong_idx = self._find_last_punct(self._STRONG_PUNCT)
        if strong_idx is not None and strong_idx < len(text) - 1:
            return strong_idx + 1

        if len(text) < self.min_chars:
            return None

        sentence_idx = self._find_last_punct(self._SENTENCE_PUNCT)
        if sentence_idx is not None:
            return sentence_idx + 1

        strong_idx = self._find_last_punct(self._STRONG_PUNCT)
        if strong_idx is not None:
            return strong_idx + 1

        ws_idx = self._find_last_whitespace(lower=self.min_chars, upper=len(text))
        if ws_idx is not None:
            return ws_idx
        return None

    def _find_last_punct(self, punct_set: set[str], upper: int | None = None) -> int | None:
        limit = len(self._buffer) if upper is None else min(len(self._buffer), max(0, int(upper)))
        for idx in range(limit - 1, -1, -1):
            if self._buffer[idx] in punct_set:
                return idx
        return None

    def _find_last_whitespace(self, *, lower: int, upper: int) -> int | None:
        lo = max(0, int(lower))
        hi = min(len(self._buffer), max(lo, int(upper)))
        for idx in range(hi - 1, lo - 1, -1):
            if self._buffer[idx].isspace():
                return idx
        return None
