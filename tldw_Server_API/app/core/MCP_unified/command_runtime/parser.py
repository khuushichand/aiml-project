"""Parser for the phase-1 virtual CLI command language."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .models import CommandChain, CommandInvocation, Pipeline

CHAIN_OPERATORS: Final[set[str]] = {";", "&&", "||"}
PIPE_OPERATOR: Final[str] = "|"
ALL_OPERATORS: Final[set[str]] = CHAIN_OPERATORS | {PIPE_OPERATOR}


@dataclass(frozen=True, slots=True)
class _Token:
    value: str
    quoted: bool = False
    escaped: bool = False


def _tokenize(command: str) -> list[_Token]:
    if not isinstance(command, str):
        raise TypeError("command must be a string")

    tokens: list[_Token] = []
    position = 0
    length = len(command)

    while position < length:
        char = command[position]
        if char.isspace():
            position += 1
            continue

        if char in {'"', "'"}:
            quote = char
            position += 1
            value: list[str] = []
            escaped = False
            while position < length:
                current = command[position]
                if escaped:
                    value.append(current)
                    escaped = False
                    position += 1
                    continue
                if current == "\\":
                    escaped = True
                    position += 1
                    continue
                if current == quote:
                    position += 1
                    tokens.append(_Token("".join(value), quoted=True))
                    break
                value.append(current)
                position += 1
            else:
                raise ValueError("Malformed command: unterminated quoted token")
            continue

        if char == "&":
            if position + 1 < length and command[position + 1] == "&":
                tokens.append(_Token("&&"))
                position += 2
                continue
            raise ValueError("Malformed command near: '&'")

        if char == "|":
            if position + 1 < length and command[position + 1] == "|":
                tokens.append(_Token("||"))
                position += 2
                continue
            tokens.append(_Token("|"))
            position += 1
            continue

        if char == ";":
            tokens.append(_Token(";"))
            position += 1
            continue

        value: list[str] = []
        escaped = False
        while position < length:
            current = command[position]
            if current == "\\":
                next_char = command[position + 1] if position + 1 < length else ""
                if next_char and (next_char.isspace() or next_char in {'|', ';', '&', '"', "'"}):
                    value.append(next_char)
                    escaped = True
                    position += 2
                    continue
                value.append("\\")
                position += 1
                continue
            if current.isspace() or current in {'"', "'", "|", ";", "&"}:
                break
            value.append(current)
            position += 1
        if not value:
            raise ValueError(f"Malformed command near: {command[position:position + 1]!r}")
        tokens.append(_Token("".join(value), escaped=escaped))

    if not tokens:
        raise ValueError("command must not be empty")
    return tokens


def parse_command(command: str) -> CommandChain:
    """Parse a command string into a chain of pipelines."""

    tokens = _tokenize(command)

    segments: list[Pipeline] = []
    links: list[str] = []
    current_pipeline: list[CommandInvocation] = []
    current_argv: list[str] = []
    expect_command = True

    def flush_command() -> None:
        nonlocal current_argv
        if not current_argv:
            raise ValueError("Malformed command: missing command before operator")
        current_pipeline.append(CommandInvocation(argv=current_argv))
        current_argv = []

    def flush_pipeline() -> None:
        if not current_pipeline:
            raise ValueError("Malformed command: empty pipeline")
        segments.append(Pipeline(commands=list(current_pipeline)))
        current_pipeline.clear()

    for token in tokens:
        if not token.quoted and not token.escaped and token.value in ALL_OPERATORS:
            if expect_command:
                raise ValueError("Malformed command: operator cannot appear here")
            flush_command()
            if token.value in CHAIN_OPERATORS:
                flush_pipeline()
                links.append(token.value)
            expect_command = True
            continue

        if expect_command:
            current_argv = [token.value]
            expect_command = False
        else:
            current_argv.append(token.value)

    if expect_command:
        raise ValueError("Malformed command: dangling operator")

    flush_command()
    flush_pipeline()

    return CommandChain(segments=segments, links=links)
