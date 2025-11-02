# strategies/words.py
"""
Word-based chunking strategy.
Splits text into chunks based on word count with optional overlap.
"""

import re
from typing import List, Optional, Dict, Any, Generator
from loguru import logger

from ..base import BaseChunkingStrategy, ChunkResult, ChunkMetadata


class WordChunkingStrategy(BaseChunkingStrategy):
    """
    Chunks text by word count.
    Supports multiple languages and various word tokenization methods.
    """

    def __init__(self, language: str = 'en'):
        """
        Initialize word chunking strategy.

        Args:
            language: Language code for text processing
        """
        super().__init__(language)

        # Language-specific word tokenizers
        self._word_tokenizers = {
            'zh': self._tokenize_chinese,
            'zh-cn': self._tokenize_chinese,
            'zh-tw': self._tokenize_chinese,
            'ja': self._tokenize_japanese,
            'ko': self._tokenize_korean,
            'th': self._tokenize_thai,
            'default': self._tokenize_default
        }

        logger.debug(f"WordChunkingStrategy initialized for language: {language}")

    def chunk(self,
              text: str,
              max_size: int,
              overlap: int = 0,
              **options) -> List[str]:
        """
        Chunk text by word count.

        Args:
            text: Text to chunk
            max_size: Maximum words per chunk
            overlap: Number of words to overlap between chunks
            **options: Additional options:
                - preserve_sentences: Try to break at sentence boundaries
                - min_chunk_size: Minimum words per chunk

        Returns:
            List of text chunks
        """
        if not self.validate_parameters(text, max_size, overlap):
            return []

        # Adjust overlap if needed
        if overlap >= max_size:
            logger.warning(f"Overlap ({overlap}) >= max_size ({max_size}), setting to max_size - 1")
            overlap = max_size - 1

        records, tokens, _spans = self._prepare_chunk_records(text, max_size, overlap, **options)
        if not tokens or not records:
            return []

        logger.debug(f"Chunking {len(tokens)} words with max_size={max_size}, overlap={overlap}")
        chunks = [record['text'] for record in records]
        logger.debug(f"Created {len(chunks)} chunks from {len(tokens)} words")
        return chunks

    def _tokenize_text(self, text: str) -> List[str]:
        """
        Tokenize text into words based on language.

        Args:
            text: Text to tokenize

        Returns:
            List of words
        """
        # Get appropriate tokenizer for language
        tokenizer = self._word_tokenizers.get(
            self.language,
            self._word_tokenizers['default']
        )

        return tokenizer(text)

    def _tokenize_with_spans(self, text: str) -> tuple[List[str], List[tuple[int, int]]]:
        """Tokenize text and return tokens with character spans.

        Implementation notes:
        - Uses a single forward scan with bounded lookups to avoid O(n^2) behavior
          on adversarial/repeated tokens.
        - We never rescan the entire string from the beginning; if a token cannot be
          found ahead of the rolling cursor, we conservatively place it at the cursor
          to maintain monotonic spans. This guarantees linear-time progress.
        """
        tokens = self._tokenize_text(text)
        spans: List[tuple[int, int]] = []
        n = len(text)
        cursor = 0

        # Languages without inter-word spaces
        no_space_languages = {'zh', 'zh-cn', 'zh-tw', 'ja', 'th'}
        is_no_space_lang = (self.language or '').lower() in no_space_languages

        for token in tokens:
            if token == "":
                spans.append((cursor, cursor))
                continue

            # For space-delimited languages, skip whitespace between tokens
            if not is_no_space_lang:
                while cursor < n and text[cursor].isspace():
                    cursor += 1

            tlen = len(token)
            # Fast-path: direct match at cursor
            if cursor + tlen <= n and text[cursor:cursor + tlen] == token:
                idx = cursor
            else:
                # Bounded forward search only; do not rescan from the beginning
                idx = text.find(token, cursor)
                if idx == -1:
                    idx = cursor

            end = min(n, idx + tlen)
            spans.append((idx, end))
            cursor = end

        return tokens, spans

    def _prepare_chunk_records(
        self,
        text: str,
        max_size: int,
        overlap: int,
        **options,
    ) -> tuple[List[Dict[str, Any]], List[str], List[tuple[int, int]]]:
        """Generate chunk records with token index mappings."""
        tokens, spans = self._tokenize_with_spans(text)
        if not tokens:
            return [], tokens, spans
        records: List[Dict[str, Any]] = []
        step = max(1, max_size - overlap)
        try:
            min_size = int(options.get('min_chunk_size', 0))
        except Exception:
            min_size = 0
        min_size = max(0, min_size)
        preserve_sentences = bool(options.get('preserve_sentences', False))
        no_space_languages = {'zh', 'zh-cn', 'zh-tw', 'ja', 'th'}

        for i in range(0, len(tokens), step):
            end = min(i + max_size, len(tokens))
            if end <= i:
                continue
            token_indices = list(range(i, end))
            chunk_tokens = [tokens[idx] for idx in token_indices]

            # Optional sentence boundary preservation (mirrors original logic)
            if preserve_sentences and end < len(tokens) and self.language not in no_space_languages:
                chunk_text_tmp = ' '.join(chunk_tokens)
                last_period = chunk_text_tmp.rfind('. ')
                last_question = chunk_text_tmp.rfind('? ')
                last_exclaim = chunk_text_tmp.rfind('! ')
                boundary = max(last_period, last_question, last_exclaim)
                if boundary > len(chunk_text_tmp) * 0.8:
                    partial_text = chunk_text_tmp[:boundary + 2]
                    boundary_words = partial_text.split()
                    count = len(boundary_words)
                    if count > 0:
                        token_indices = token_indices[:count]
                        chunk_tokens = chunk_tokens[:count]

            if not token_indices:
                continue

            chunk_text = self._join_words(chunk_tokens)

            if len(token_indices) >= min_size or not records:
                records.append({
                    'token_indices': token_indices[:],
                    'text': chunk_text,
                })
            else:
                prev = records[-1]
                prev['token_indices'].extend(token_indices)
                merge_suffix = ' ' + chunk_text if chunk_text else ' '
                prev['text'] = prev['text'] + merge_suffix

        return records, tokens, spans

    def _tokenize_default(self, text: str) -> List[str]:
        """
        Default word tokenization using simple splitting.

        Args:
            text: Text to tokenize

        Returns:
            List of words
        """
        # Simple word splitting on whitespace and punctuation
        words = text.split()
        return words

    def _tokenize_chinese(self, text: str) -> List[str]:
        """
        Chinese word tokenization.

        Args:
            text: Chinese text to tokenize

        Returns:
            List of words
        """
        try:
            import jieba
            words = list(jieba.cut(text))
            logger.debug(f"Tokenized Chinese text into {len(words)} words using jieba")
            return words
        except ImportError:
            logger.warning("jieba not available, falling back to character splitting for Chinese")
            # For Chinese without jieba, split on characters
            # Remove spaces and newlines first
            text = text.replace(' ', '').replace('\n', ' ')
            # Split into characters but keep some punctuation as boundaries
            import re
            # Capture punctuation so it can be reinserted when joining tokens
            punct_pattern = re.compile(r'[。！？，；：、]')
            words = []
            last_end = 0
            for match in punct_pattern.finditer(text):
                segment = text[last_end:match.start()]
                if segment:
                    words.extend(list(segment))
                words.append(match.group())
                last_end = match.end()
            tail = text[last_end:]
            if tail:
                words.extend(list(tail))
            return words

    def _tokenize_japanese(self, text: str) -> List[str]:
        """
        Japanese word tokenization.

        Args:
            text: Japanese text to tokenize

        Returns:
            List of words
        """
        try:
            import fugashi
        except ImportError:
            logger.warning("fugashi not available, falling back to character splitting for Japanese")
        else:
            try:
                tagger = fugashi.Tagger('-Owakati')
                words = tagger.parse(text).split()
                logger.debug(f"Tokenized Japanese text into {len(words)} words using fugashi")
                return words
            except Exception as exc:
                logger.warning(f"fugashi initialization failed, falling back to character splitting for Japanese: {exc}")
        # Fallback path when fugashi is unavailable or fails at runtime
        text = text.replace(' ', '').replace('\n', ' ')
        import re
        punct_pattern = re.compile(r'[。！？、]')
        words = []
        last_end = 0
        for match in punct_pattern.finditer(text):
            segment = text[last_end:match.start()]
            if segment:
                words.extend(list(segment))
            words.append(match.group())
            last_end = match.end()
        tail = text[last_end:]
        if tail:
            words.extend(list(tail))
        return words

    def _tokenize_korean(self, text: str) -> List[str]:
        """
        Korean word tokenization.

        Args:
            text: Korean text to tokenize

        Returns:
            List of words
        """
        try:
            from konlpy.tag import Okt
            okt = Okt()
            words = okt.morphs(text)
            logger.debug(f"Tokenized Korean text into {len(words)} words using KoNLPy")
            return words
        except ImportError:
            logger.warning("KoNLPy not available, using space splitting for Korean")
            return text.split()

    def _tokenize_thai(self, text: str) -> List[str]:
        """
        Thai word tokenization.

        Args:
            text: Thai text to tokenize

        Returns:
            List of words
        """
        try:
            from pythainlp import word_tokenize
            words = word_tokenize(text, engine='newmm')
            logger.debug(f"Tokenized Thai text into {len(words)} words using PyThaiNLP")
            return words
        except ImportError:
            logger.warning("PyThaiNLP not available, using character splitting for Thai")
            # Thai doesn't use spaces between words
            return [ch for ch in text if ch != '\r']

    def _join_words(self, words: List[str]) -> str:
        """
        Join words back into text based on language.

        Args:
            words: List of words to join

        Returns:
            Joined text
        """
        if self.language in ['zh', 'zh-cn', 'zh-tw', 'ja', 'th']:
            # For languages without spaces between words
            return ''.join(words)
        else:
            # For languages with spaces
            return ' '.join(words)

    def chunk_generator(self,
                       text: str,
                       max_size: int,
                       overlap: int = 0,
                       **options) -> Generator[str, None, None]:
        """
        Memory-efficient generator version of chunk.

        Args:
            text: Text to chunk
            max_size: Maximum words per chunk
            overlap: Number of words to overlap between chunks
            **options: Additional options

        Yields:
            Individual text chunks
        """
        if not self.validate_parameters(text, max_size, overlap):
            return

        # Adjust overlap if needed
        if overlap >= max_size:
            overlap = max_size - 1

        words = self._tokenize_text(text)
        step = max(1, max_size - overlap)

        for i in range(0, len(words), step):
            chunk_words = words[i:i + max_size]
            chunk = self._join_words(chunk_words)

            # Apply minimum size if specified
            min_size = options.get('min_chunk_size', 0)
            if len(chunk_words) >= min_size:
                yield chunk

    def chunk_with_metadata(self,
                            text: str,
                            max_size: int,
                            overlap: int = 0,
                            **options) -> List[ChunkResult]:
        """Chunk text and return metadata with accurate offsets."""
        if not self.validate_parameters(text, max_size, overlap):
            return []

        if overlap >= max_size:
            logger.warning(f"Overlap ({overlap}) >= max_size ({max_size}), setting to max_size - 1")
            overlap = max_size - 1

        records, tokens, spans = self._prepare_chunk_records(text, max_size, overlap, **options)
        if not records:
            return []

        try:
            min_size_opt = int(options.get('min_chunk_size', 0))
        except Exception:
            min_size_opt = 0

        results: List[ChunkResult] = []
        total = len(records)
        for idx, record in enumerate(records):
            token_indices: List[int] = record.get('token_indices', [])
            if not token_indices:
                continue
            start_idx = token_indices[0]
            end_idx = token_indices[-1]
            start_char, end_char = spans[start_idx][0], spans[end_idx][1]
            try:
                end_char = self._expand_end_to_grapheme_boundary(text, end_char, options=options)
            except Exception:
                pass
            chunk_text = record.get('text', '')
            word_count = len(token_indices)
            metadata = ChunkMetadata(
                index=idx,
                start_char=start_char,
                end_char=end_char,
                word_count=word_count,
                token_count=word_count,
                language=self.language,
                overlap_with_previous=overlap if idx > 0 else 0,
                overlap_with_next=overlap if idx < total - 1 else 0,
                method='words',
                options={
                    'preserve_sentences': bool(options.get('preserve_sentences', False)),
                    'min_chunk_size': min_size_opt,
                }
            )
            results.append(ChunkResult(text=chunk_text, metadata=metadata))

        logger.debug(f"Created {len(results)} chunks with metadata from {len(tokens)} words")
        return results
