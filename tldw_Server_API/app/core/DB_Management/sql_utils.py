"""SQL utility helpers shared across database backends."""

from __future__ import annotations


def split_sql_statements(sql: str) -> list[str]:
    """Split SQL into executable statements, respecting quotes and dollar blocks.

    Handles:
    - Single-quoted strings (') and doubled quotes ('')
    - Double-quoted identifiers (") and doubled quotes ("")
    - Line comments (--) and block comments (/* */)
    - Dollar-quoted strings ($$...$$ or $tag$...$tag$)
    """
    statements: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    in_line_comment = False
    in_block_comment = False
    dollar_delim: str | None = None

    i = 0
    length = len(sql)

    while i < length:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < length else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                buf.append("\n")
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                buf.append(" ")
                continue
            i += 1
            continue

        if dollar_delim is not None:
            if sql.startswith(dollar_delim, i):
                buf.append(dollar_delim)
                i += len(dollar_delim)
                dollar_delim = None
                continue
            buf.append(ch)
            i += 1
            continue

        if in_single:
            buf.append(ch)
            if ch == "'" and nxt == "'":
                buf.append(nxt)
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue

        if in_double:
            buf.append(ch)
            if ch == '"' and nxt == '"':
                buf.append(nxt)
                i += 2
                continue
            if ch == '"':
                in_double = False
            i += 1
            continue

        if ch == "-" and nxt == "-":
            in_line_comment = True
            i += 2
            continue

        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue

        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue

        if ch == '"':
            in_double = True
            buf.append(ch)
            i += 1
            continue

        if ch == "$":
            j = i + 1
            while j < length and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            if j < length and sql[j] == "$":
                dollar_delim = sql[i : j + 1]
                buf.append(dollar_delim)
                i = j + 1
                continue

        if ch == ";":
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)

    return statements
