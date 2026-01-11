## Stage 1: Async Stream Overlap Tail Fix
**Goal**: Prevent duplicate tail chunks when async streaming ends at a buffer boundary with overlap enabled.
**Success Criteria**: `AsyncChunker.chunk_stream` does not re-chunk overlap-only tail when `buffer` is empty.
**Tests**: `pytest -k async_chunk_stream_overlap_no_tail_dup_on_boundary`
**Status**: Complete

## Stage 2: Option Alias Mapping
**Goal**: Map API/legacy option names to strategy-native keys so semantic/JSON/proposition settings are honored.
**Success Criteria**: Semantic similarity/overlap, JSON chunkable key, and proposition min length are forwarded correctly.
**Tests**: `pytest -k option_aliases`
**Status**: Complete

## Stage 3: Japanese Language Autodetect
**Goal**: Prefer Japanese detection when kana is present, avoiding misclassification as Chinese.
**Success Criteria**: Japanese text with kana yields `language == "ja"` in `Chunker.process_text`.
**Tests**: `pytest -k language_autodetect_japanese`
**Status**: Not Started
