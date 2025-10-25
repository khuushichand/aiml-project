"""
Code-aware chunking strategy that segments source files into logical blocks
(imports, classes, functions) across multiple languages using heuristic parsing.

Notes:
- Supports brace-based languages (C/C++/Java/C#/Go/Rust/JS/TS/Swift/Kotlin) and
  indentation-based languages (Python, Ruby) with best-effort detection.
- Returns chunks as plain strings; metadata can be added by the caller.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional
from loguru import logger

from ..base import BaseChunkingStrategy, ChunkResult, ChunkMetadata


@dataclass
class _Header:
    kind: str
    name: Optional[str]
    line_index: int


class CodeChunkingStrategy(BaseChunkingStrategy):
    """Heuristic, language-agnostic code chunker."""

    # Regex patterns for various languages
    PY_HEADER_RE = re.compile(r"^\s*(def|class)\s+([A-Za-z_][\w]*)[\(:]", re.UNICODE)
    # JS/TS
    JSTYPE_FUNC_RE = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\(")
    JSTYPE_CLASS_RE = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_][\w]*)\b")
    JSTYPE_EXPORT_DEFAULT_CLASS_RE = re.compile(r"^\s*export\s+default\s+class\s+([A-Za-z_][\w]*)\b")
    JSTYPE_CONST_ARROW_RE = re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_]\w*)\s*=\s*\([^;{}]*\)\s*=>\s*\{\s*$")
    JSTYPE_CONST_FUNC_RE = re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_]\w*)\s*=\s*function\s*\(")
    JSTYPE_EXPORT_DEFAULT_FUNC_NAMED_RE = re.compile(r"^\s*export\s+default\s+(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\(")
    JSTYPE_EXPORT_DEFAULT_FUNC_ANON_RE = re.compile(r"^\s*export\s+default\s+(?:async\s+)?function\s*\(")
    JSTYPE_EXPORT_DEFAULT_ARROW_RE = re.compile(r"^\s*export\s+default\s*\([^;{}]*\)\s*=>\s*\{\s*$")
    TSTYPE_INTERFACE_RE = re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_][\w]*)\b")
    TSTYPE_TYPE_RE = re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_][\w]*)\s*=")
    JSTYPE_METHOD_RE = re.compile(r"^\s*(?:public|private|protected|static|async)?\s*([A-Za-z_][\w]*)\s*\([^;{}]*\)\s*\{\s*$")
    # C/C++/Java/C# (very heuristic)
    C_LIKE_FUNC_RE = re.compile(r"^\s*(?:template\s*<[^>]+>\s*)?(?:[\w:\*\&\[\]<>]+\s+)+([A-Za-z_][\w]*)\s*\([^;{]*\)\s*(?:const\s*)?\{\s*$")
    C_LIKE_CLASS_RE = re.compile(r"^\s*(?:public|private|protected|abstract|final|sealed|partial|static)?\s*class\s+([A-Za-z_][\w]*)\b")
    GO_FUNC_RE = re.compile(r"^\s*func\s+(?:\([^)]*\)\s+)?([A-Za-z_]\w*)\s*\(")
    RUST_FUNC_RE = re.compile(r"^\s*fn\s+([A-Za-z_]\w*)\s*\(")
    RUST_TYPE_RE = re.compile(r"^\s*(struct|enum|trait|impl)\s+([A-Za-z_][\w]*)\b")
    RUBY_HEADER_RE = re.compile(r"^\s*(def|class|module)\s+([A-Za-z_][\w]*)")
    SHELL_FUNC_RE = re.compile(r"^\s*([A-Za-z_][\w]*)\s*\(\)\s*\{\s*$")

    IMPORT_LINE_RE = re.compile(
        r"^\s*(?:import\b|from\s+\S+\s+import\b|#include\b|using\s+\w+;|package\b)"
    )

    def _is_brace_lang(self, language: str) -> bool:
        return language.lower() in {
            'c', 'cpp', 'csharp', 'java', 'go', 'rust', 'swift', 'kotlin', 'javascript', 'typescript', 'tsx', 'jsx',
        }

    def _find_headers(self, lines: List[str], language: str) -> List[_Header]:
        headers: List[_Header] = []
        lang = language.lower()
        for idx, line in enumerate(lines):
            m = None
            if lang == 'python':
                m = self.PY_HEADER_RE.match(line)
                if m:
                    headers.append(_Header(m.group(1), m.group(2), idx))
                    continue
            if lang in ('javascript', 'typescript', 'tsx', 'jsx'):
                m = self.JSTYPE_EXPORT_DEFAULT_CLASS_RE.match(line)
                if m:
                    headers.append(_Header('class', m.group(1), idx)); continue
                m = self.JSTYPE_CLASS_RE.match(line)
                if m:
                    headers.append(_Header('class', m.group(1), idx)); continue
                m = self.JSTYPE_FUNC_RE.match(line)
                if m:
                    headers.append(_Header('function', m.group(1), idx)); continue
                m = self.JSTYPE_EXPORT_DEFAULT_FUNC_NAMED_RE.match(line)
                if m:
                    headers.append(_Header('function', m.group(1), idx)); continue
                m = self.JSTYPE_EXPORT_DEFAULT_FUNC_ANON_RE.match(line)
                if m:
                    headers.append(_Header('function', 'default', idx)); continue
                m = self.JSTYPE_EXPORT_DEFAULT_ARROW_RE.match(line)
                if m:
                    headers.append(_Header('function', 'default', idx)); continue
                m = self.JSTYPE_CONST_ARROW_RE.match(line)
                if m:
                    headers.append(_Header('function', m.group(1), idx)); continue
                m = self.JSTYPE_CONST_FUNC_RE.match(line)
                if m:
                    headers.append(_Header('function', m.group(1), idx)); continue
                m = self.TSTYPE_INTERFACE_RE.match(line)
                if m:
                    headers.append(_Header('interface', m.group(1), idx)); continue
                m = self.TSTYPE_TYPE_RE.match(line)
                if m:
                    headers.append(_Header('type', m.group(1), idx)); continue
                # methods will be handled inside class blocks via braces
            if lang in ('c', 'cpp', 'csharp', 'java'):
                m = self.C_LIKE_CLASS_RE.match(line)
                if m:
                    headers.append(_Header('class', m.group(1), idx)); continue
                m = self.C_LIKE_FUNC_RE.match(line)
                if m:
                    headers.append(_Header('function', m.group(1), idx)); continue
            if lang == 'go':
                m = self.GO_FUNC_RE.match(line)
                if m:
                    headers.append(_Header('func', m.group(1), idx)); continue
            if lang == 'rust':
                m = self.RUST_TYPE_RE.match(line)
                if m:
                    headers.append(_Header(m.group(1), m.group(2), idx)); continue
                m = self.RUST_FUNC_RE.match(line)
                if m:
                    headers.append(_Header('fn', m.group(1), idx)); continue
            if lang == 'ruby':
                m = self.RUBY_HEADER_RE.match(line)
                if m:
                    headers.append(_Header(m.group(1), m.group(2), idx)); continue
            # Shell-like
            m = self.SHELL_FUNC_RE.match(line)
            if m:
                headers.append(_Header('function', m.group(1), idx)); continue
        headers.sort(key=lambda h: h.line_index)
        return headers

    def _indent(self, s: str) -> int:
        return len(s) - len(s.lstrip(' '))

    def _block_end_indent(self, lines: List[str], start_idx: int) -> int:
        return self._indent(lines[start_idx])

    def _find_block_for_header_indent(self, lines: List[str], header_idx: int) -> int:
        # For indentation-based (Python/Ruby). End before next header at same or shallower indent
        base_indent = self._indent(lines[header_idx])
        i = header_idx + 1
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1; continue
            if self._indent(line) <= base_indent and (self.PY_HEADER_RE.match(line) or self.RUBY_HEADER_RE.match(line)):
                return i
            i += 1
        return len(lines)

    def _find_block_for_header_braces(self, lines: List[str], header_idx: int) -> int:
        # For brace languages: find first '{' after header, then match braces
        i = header_idx
        # find start brace
        brace_count = 0
        found = False
        while i < len(lines):
            brace_count += lines[i].count('{') - lines[i].count('}')
            if '{' in lines[i]:
                found = True
                break
            # In some languages, the brace may be on the next line after signature
            i += 1
        if not found:
            # Fallback: single-line or no brace; use until next header or blank line
            j = header_idx + 1
            while j < len(lines) and lines[j].strip():
                j += 1
            return j
        # Now find when brace_count returns to zero from this point
        i += 1
        while i < len(lines):
            brace_count += lines[i].count('{') - lines[i].count('}')
            if brace_count <= 0:
                return i + 1
            i += 1
        return len(lines)

    def _extract_import_block(self, lines: List[str]) -> Tuple[int, int]:
        # From start of file to last consecutive import-like line (skipping comments and blanks)
        start = 0
        end = 0
        i = 0
        seen_non_import = False
        while i < len(lines):
            s = lines[i]
            if not s.strip() or s.strip().startswith(('#', '//', '/*')):
                # Keep leading comments as part of header block until imports end
                if not seen_non_import:
                    end = i + 1
                i += 1
                continue
            if self.IMPORT_LINE_RE.match(s):
                end = i + 1
                i += 1
                continue
            # First non-import code line
            seen_non_import = True
            break
        return (start, end)

    def _pack_blocks(self, blocks: List[Tuple[int, int]], lines: List[str], max_chars: int, overlap_chars: int) -> List[str]:
        # Greedy pack blocks into chunks respecting max_chars; use simple character overlap
        chunks: List[str] = []
        buf = ''
        for (s, e) in blocks:
            text = '\n'.join(lines[s:e]).rstrip()
            if not text:
                continue
            if not buf:
                buf = text
            elif len(buf) + 2 + len(text) <= max_chars:
                buf = f"{buf}\n\n{text}"
            else:
                if buf:
                    chunks.append(buf)
                if len(text) > max_chars:
                    # Split oversized block into windows
                    t = text
                    while t:
                        part = t[:max_chars]
                        chunks.append(part)
                        if len(t) <= max_chars:
                            t = ''
                        else:
                            # apply overlap
                            t = t[max(1, max_chars - max(0, overlap_chars)) : ]
                    buf = ''
                else:
                    buf = text
        if buf:
            chunks.append(buf)
        # Add overlap between consecutive chunks if requested
        if overlap_chars > 0 and len(chunks) > 1:
            overlapped: List[str] = []
            prev = ''
            for i, ch in enumerate(chunks):
                if i == 0:
                    overlapped.append(ch)
                    prev = ch
                    continue
                tail = prev[-overlap_chars:] if prev else ''
                if tail:
                    overlapped.append(f"{tail}{ch}")
                else:
                    overlapped.append(ch)
                prev = ch
            return overlapped
        return chunks

    def chunk(self, text: str, max_size: int, overlap: int = 0, **options) -> List[str]:
        if not self.validate_parameters(text, max_size, overlap):
            return []
        language = str(options.get('language') or self.language or 'text')
        lines = text.splitlines()
        if not lines:
            return []

        try:
            # Identify headers per language
            headers = self._find_headers(lines, language)
            blocks: List[Tuple[int, int]] = []
            # Add import/header block first if present
            imp_s, imp_e = self._extract_import_block(lines)
            if imp_e > imp_s:
                blocks.append((imp_s, imp_e))
            if headers:
                for idx, h in enumerate(headers):
                    start = h.line_index
                    if self._is_brace_lang(language):
                        end = self._find_block_for_header_braces(lines, start)
                    else:
                        end = self._find_block_for_header_indent(lines, start)
                    # Ensure monotonic and non-overlapping
                    if blocks and start < blocks[-1][1]:
                        start = blocks[-1][1]
                    if end <= start:
                        continue
                    blocks.append((start, end))
            else:
                # Fallback: treat the whole file as one block
                blocks.append((0, len(lines)))

            chunks = self._pack_blocks(blocks, lines, max_chars=max_size, overlap_chars=overlap)
            logger.info(f"CodeChunkingStrategy produced {len(chunks)} chunks (language={language})")
            return chunks
        except Exception as e:
            logger.warning(f"Code chunking failed, falling back to whole text: {e}")
            return [text]

    def chunk_with_metadata(self, text: str, max_size: int, overlap: int = 0, **options) -> List[ChunkResult]:
        if not self.validate_parameters(text, max_size, overlap):
            return []
        language = str(options.get('language') or self.language or 'text')
        # Preserve line endings for accurate char offsets
        lines_ke = text.splitlines(keepends=True)
        if not lines_ke:
            return []
        # Build cumulative char positions for each line start
        line_starts = []
        pos = 0
        for ln in lines_ke:
            line_starts.append(pos)
            pos += len(ln)
        total_chars = pos

        # Helper to convert (start_line, end_line_exclusive) -> (start_char, end_char)
        def span_chars(s_line: int, e_line: int) -> tuple:
            # Clamp indices safely
            if not (0 <= s_line < len(line_starts)):
                s_char = 0
            else:
                s_char = line_starts[s_line]
            if 0 <= e_line < len(line_starts):
                e_char = line_starts[e_line]
            else:
                e_char = total_chars
            if e_char < s_char:
                e_char = s_char
            return s_char, e_char

        # Derive structured blocks (imports and headers)
        # Use non-keepends lines for regex detection
        lines = [ln.rstrip('\n').rstrip('\r') for ln in lines_ke]
        blocks: List[Tuple[int, int, str, Optional[str]]] = []  # (s_line, e_line_excl, block_type, name)
        imp_s, imp_e = self._extract_import_block(lines)
        if imp_e > imp_s:
            blocks.append((imp_s, imp_e, 'imports', None))
        headers = self._find_headers(lines, language)
        if headers:
            for h in headers:
                s = h.line_index
                if self._is_brace_lang(language):
                    e = self._find_block_for_header_braces(lines, s)
                else:
                    e = self._find_block_for_header_indent(lines, s)
                if blocks and s < blocks[-1][1]:
                    s = blocks[-1][1]
                if e <= s:
                    continue
                # Normalize header kinds
                kind_map = {
                    'def': 'function', 'func': 'function', 'function': 'function', 'fn': 'function',
                    'class': 'class', 'struct': 'struct', 'enum': 'enum', 'trait': 'trait', 'impl': 'impl', 'module': 'module',
                }
                btype = kind_map.get(h.kind, h.kind)
                blocks.append((s, e, btype, h.name))
        if not blocks:
            blocks.append((0, len(lines), 'module', None))

        # Greedy pack blocks into chunks
        results: List[ChunkResult] = []
        buf_start_char = None
        buf_end_char = None
        buf_blocks: List[Tuple[int, int, str, Optional[str]]] = []

        def flush_chunk():
            nonlocal buf_start_char, buf_end_char, buf_blocks
            if buf_start_char is None or buf_end_char is None:
                return
            ch_text = text[buf_start_char:buf_end_char]
            # Compute line span for this chunk
            # Find first line index where start_char >= line_start
            start_line_idx = 0
            for i, ls in enumerate(line_starts):
                if ls <= buf_start_char:
                    start_line_idx = i
                else:
                    break
            end_line_idx = start_line_idx
            for i, ls in enumerate(line_starts):
                if ls < buf_end_char:
                    end_line_idx = i
                else:
                    break
            # Expand end bound to avoid splitting graphemes in metadata
            try:
                buf_end_char = self._expand_end_to_grapheme_boundary(text, buf_end_char)
            except Exception:
                pass
            md = ChunkMetadata(
                index=len(results),
                start_char=buf_start_char,
                end_char=buf_end_char,
                word_count=len(ch_text.split()),
                language=language,
                method='code',
                options={
                    'start_line': start_line_idx + 1,
                    'end_line': end_line_idx + 1,
                    'lines_in_chunk': (end_line_idx - start_line_idx + 1),
                    'blocks': [
                        {
                            'type': btype,
                            'name': name,
                            'start_line': s + 1,
                            'end_line': e,
                        }
                        for (s, e, btype, name) in buf_blocks
                    ],
                }
            )
            results.append(ChunkResult(text=ch_text, metadata=md))
            buf_start_char = None
            buf_end_char = None
            buf_blocks = []

        for (s_line, e_line, btype, name) in blocks:
            s_char, e_char = span_chars(s_line, e_line)
            blen = e_char - s_char
            if buf_start_char is None:
                if blen <= max_size:
                    buf_start_char = s_char
                    buf_end_char = e_char
                    buf_blocks = [(s_line, e_line, btype, name)]
                else:
                    # Split oversized block into windows with intra-block overlap
                    start = s_char
                    while start < e_char:
                        end = min(e_char, start + max_size)
                        md_blocks = [(s_line, e_line, btype, name)]
                        ch_text = text[start:end]
                        # Calculate line indices
                        start_line_idx = max(0, max([i for i, ls in enumerate(line_starts) if ls <= start], default=0))
                        end_line_idx = max(start_line_idx, max([i for i, ls in enumerate(line_starts) if ls < end], default=start_line_idx))
                        try:
                            end = self._expand_end_to_grapheme_boundary(text, end)
                        except Exception:
                            pass
                        md = ChunkMetadata(
                            index=len(results),
                            start_char=start,
                            end_char=end,
                            word_count=len(ch_text.split()),
                            language=language,
                            method='code',
                            options={
                                'start_line': start_line_idx + 1,
                                'end_line': end_line_idx + 1,
                                'lines_in_chunk': (end_line_idx - start_line_idx + 1),
                                'blocks': [
                                    {'type': btype, 'name': name, 'start_line': s_line + 1, 'end_line': e_line}
                                ],
                                'partial_block': True,
                            }
                        )
                        results.append(ChunkResult(text=ch_text, metadata=md))
                        if end >= e_char:
                            break
                        # Apply intra-block overlap when continuing
                        step = max(1, max_size - max(0, overlap))
                        start = start + step
                    # Reset buffer
                    buf_start_char = None
                    buf_end_char = None
                    buf_blocks = []
            else:
                # Try to add current block into buffer
                new_len = (e_char - buf_start_char)
                if new_len <= max_size:
                    buf_end_char = e_char
                    buf_blocks.append((s_line, e_line, btype, name))
                else:
                    flush_chunk()
                    # Start new buffer with current block (or split if needed)
                    if (e_char - s_char) <= max_size:
                        buf_start_char = s_char
                        buf_end_char = e_char
                        buf_blocks = [(s_line, e_line, btype, name)]
                    else:
                        # Split oversized block as above
                        start = s_char
                        while start < e_char:
                            end = min(e_char, start + max_size)
                            ch_text = text[start:end]
                            start_line_idx = max(0, max([i for i, ls in enumerate(line_starts) if ls <= start], default=0))
                            end_line_idx = max(start_line_idx, max([i for i, ls in enumerate(line_starts) if ls < end], default=start_line_idx))
                            try:
                                end = self._expand_end_to_grapheme_boundary(text, end)
                            except Exception:
                                pass
                            md = ChunkMetadata(
                                index=len(results),
                                start_char=start,
                                end_char=end,
                                word_count=len(ch_text.split()),
                                language=language,
                                method='code',
                                options={
                                    'start_line': start_line_idx + 1,
                                    'end_line': end_line_idx + 1,
                                    'lines_in_chunk': (end_line_idx - start_line_idx + 1),
                                    'blocks': [
                                        {'type': btype, 'name': name, 'start_line': s_line + 1, 'end_line': e_line}
                                    ],
                                    'partial_block': True,
                                }
                            )
                            results.append(ChunkResult(text=ch_text, metadata=md))
                            if end >= e_char:
                                break
                            step = max(1, max_size - max(0, overlap))
                            start = start + step
                        buf_start_char = None
                        buf_end_char = None
                        buf_blocks = []

        # Flush any remaining buffer
        flush_chunk()
        logger.info(f"CodeChunkingStrategy produced {len(results)} chunks with metadata (language={language})")
        return results
