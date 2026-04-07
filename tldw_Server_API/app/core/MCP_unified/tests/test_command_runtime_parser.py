from __future__ import annotations

import pytest

from tldw_Server_API.app.core.MCP_unified.command_runtime.parser import parse_command


def test_parser_handles_quotes_pipes_and_and_operator():
    chain = parse_command('cat "notes one.txt" | grep ERROR && write out.txt "done"')

    assert chain.segments[0].commands[0].argv == ["cat", "notes one.txt"]
    assert chain.segments[0].commands[1].argv == ["grep", "ERROR"]
    assert chain.links == ["&&"]


def test_parser_handles_adjacent_and_operator():
    chain = parse_command("ls&&tail")

    assert len(chain.segments) == 2
    assert chain.segments[0].commands[0].argv == ["ls"]
    assert chain.segments[1].commands[0].argv == ["tail"]
    assert chain.links == ["&&"]


@pytest.mark.parametrize(
    ("command", "expected_argv"),
    [
        ('grep "|"', ["grep", "|"]),
        ('grep "&&"', ["grep", "&&"]),
        ('json "||"', ["json", "||"]),
        (r"cat notes\ one.txt", ["cat", "notes one.txt"]),
        (r"grep \|", ["grep", "|"]),
        (r"grep \;", ["grep", ";"]),
        (r"grep \&\&", ["grep", "&&"]),
        (r"grep \\d+", [r"grep", r"\\d+"]),
        (r"cat C:\\temp\\file.txt", ["cat", r"C:\\temp\\file.txt"]),
    ],
)
def test_parser_keeps_quoted_control_tokens_and_escaped_spaces_literal(command: str, expected_argv: list[str]):
    chain = parse_command(command)

    assert len(chain.segments) == 1
    assert chain.segments[0].commands[0].argv == expected_argv


def test_parser_handles_semicolon_and_or_operator():
    chain = parse_command("ls; tail -n 5 || head -n 1")

    assert len(chain.segments) == 3
    assert chain.links == [";", "||"]
    assert chain.segments[0].commands[0].argv == ["ls"]
    assert chain.segments[1].commands[0].argv == ["tail", "-n", "5"]
    assert chain.segments[2].commands[0].argv == ["head", "-n", "1"]


@pytest.mark.parametrize(
    "command",
    [
        "| grep ERROR",
        "cat notes.txt |",
        "ls &&",
        "cat notes.txt ||",
        "ls ; ; tail",
        "cat \"unterminated",
    ],
)
def test_parser_rejects_malformed_input(command: str):
    with pytest.raises(
        ValueError,
        match="operator cannot appear here|dangling operator|unterminated",
    ):
        parse_command(command)
