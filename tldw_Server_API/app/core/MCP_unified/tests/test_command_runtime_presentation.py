from __future__ import annotations

from pathlib import Path

import pytest

from tldw_Server_API.app.core.MCP_unified.command_runtime.executor import CommandRuntimeExecutor
from tldw_Server_API.app.core.MCP_unified.command_runtime.models import (
    CommandExecutionResult,
    CommandExecutionStep,
    CommandSpillReference,
    CommandStepResult,
)
from tldw_Server_API.app.core.MCP_unified.command_runtime.parser import parse_command
from tldw_Server_API.app.core.MCP_unified.command_runtime.presentation import (
    present_command_execution_result,
)


def test_presentation_guards_binary_stdout() -> None:
    result = CommandExecutionResult(
        stdout=b"\x00\x01binary",
        stderr="",
        exit_code=0,
        duration_ms=8.0,
        stdout_is_binary=True,
    )

    rendered = present_command_execution_result(result)

    assert "binary" in rendered.lower()
    assert "\x00" not in rendered
    assert "[exit:0 | 8ms]" in rendered


def test_presentation_renders_utf8_bytes_stdout_as_text() -> None:
    result = CommandExecutionResult(
        stdout=b"hello\n",
        stderr=b"",
        exit_code=0,
        duration_ms=4.0,
        stdout_is_binary=False,
    )

    rendered = present_command_execution_result(result)

    assert "hello" in rendered
    assert "[binary output omitted]" not in rendered


def test_presentation_mentions_internal_storage_when_stdout_is_truncated() -> None:
    spill = CommandSpillReference(path="/tmp/spill-output.txt", bytes_written=128, line_count=1, preview="abcd")
    result = CommandExecutionResult(stdout="x" * 128, stderr="", exit_code=0, duration_ms=1.0, stdout_spill=spill)

    rendered = present_command_execution_result(result, preview_limit=4)

    assert "xxxx" in rendered
    assert "--- stdout truncated (1 lines, 128 bytes) ---" in rendered
    assert "stored internally" in rendered
    assert "/tmp/spill-output.txt" not in rendered
    assert "Refine and rerun with:" in rendered
    assert "[exit:0 | 1ms]" in rendered


def test_presentation_reads_spilled_stdout_from_disk_instead_of_executor_preview(tmp_path: Path) -> None:
    spill_path = tmp_path / "stdout-spill.txt"
    spill_path.write_text("0123456789ABCDEFG", encoding="utf-8")
    spill = CommandSpillReference(
        path=str(spill_path),
        bytes_written=17,
        line_count=1,
        preview="0123",
    )
    result = CommandExecutionResult(stdout="", stderr="", exit_code=0, duration_ms=1.0, stdout_spill=spill)

    rendered = present_command_execution_result(result, byte_limit=10)

    assert "0123456789" in rendered
    assert "0123\n\n--- stdout truncated" not in rendered


def test_presentation_does_not_claim_truncation_when_spilled_output_fits_preview_limits(tmp_path: Path) -> None:
    text = "x" * 128
    spill_path = tmp_path / "stdout-spill.txt"
    spill_path.write_text(text, encoding="utf-8")
    spill = CommandSpillReference(
        path=str(spill_path),
        bytes_written=len(text.encode("utf-8")),
        line_count=1,
        preview="short",
    )
    result = CommandExecutionResult(stdout="", stderr="", exit_code=0, duration_ms=1.0, stdout_spill=spill)

    rendered = present_command_execution_result(result, byte_limit=4000, line_limit=200)

    assert text in rendered
    assert "--- stdout truncated" not in rendered


def test_presentation_truncates_utf8_output_on_byte_boundary() -> None:
    rendered = present_command_execution_result(
        CommandExecutionResult(stdout="ééé", stderr="", exit_code=0, duration_ms=2.0),
        preview_limit=3,
    )

    assert "é" in rendered
    assert "éé" not in rendered
    assert "�" not in rendered
    assert "[exit:0 | 2ms]" in rendered


def test_presentation_truncates_when_line_limit_is_exceeded_under_byte_cap() -> None:
    result = CommandExecutionResult(stdout="a\n" * 4, stderr="", exit_code=0, duration_ms=2.0)

    rendered = present_command_execution_result(result, byte_limit=128, line_limit=2)

    assert "a\na\n" in rendered
    assert "--- stdout truncated (4 lines, 8 bytes) ---" in rendered


def test_presentation_attaches_stderr_on_failure() -> None:
    result = CommandExecutionResult(stdout="ok", stderr="boom", exit_code=3, duration_ms=12.0)

    rendered = present_command_execution_result(result)

    assert "ok" in rendered
    assert "boom" in rendered
    assert "stderr" in rendered.lower()
    assert "[exit:3 | 12ms]" in rendered


def test_presentation_omits_leading_blank_lines_for_stderr_only_failures() -> None:
    result = CommandExecutionResult(stdout="", stderr="boom", exit_code=3, duration_ms=12.0)

    rendered = present_command_execution_result(result)

    assert rendered.startswith("stderr:\nboom")


def test_presentation_guards_binary_stderr_on_failure_without_path_leak() -> None:
    result = CommandExecutionResult(
        stdout="ok",
        stderr=b"\xff\xfebad",
        exit_code=2,
        duration_ms=6.0,
        stderr_is_binary=True,
    )

    rendered = present_command_execution_result(result)

    assert "ok" in rendered
    assert "binary stderr omitted" in rendered.lower()
    assert "stored internally" not in rendered.lower() or "binary stderr was stored internally" in rendered
    assert "/tmp/" not in rendered
    assert "\ufffd" not in rendered
    assert "[exit:2 | 6ms]" in rendered


def test_presentation_attaches_spilled_text_stderr_on_failure_without_path_leak() -> None:
    spill = CommandSpillReference(path="/tmp/stderr-spill.txt", bytes_written=128, line_count=1, preview="warn")
    result = CommandExecutionResult(stdout="ok", stderr="", stderr_spill=spill, exit_code=2, duration_ms=5.0)

    rendered = present_command_execution_result(result, preview_limit=4)

    assert "stderr" in rendered.lower()
    assert "warn" in rendered
    assert "--- stderr truncated (1 lines, 128 bytes) ---" in rendered
    assert "stored internally" in rendered
    assert "/tmp/stderr-spill.txt" not in rendered
    assert "[exit:2 | 5ms]" in rendered


def test_presentation_uses_binary_safe_notice_for_binary_stderr_without_path_leak() -> None:
    spill = CommandSpillReference(path="/tmp/binary-stderr.bin", bytes_written=128, line_count=0, preview="")
    result = CommandExecutionResult(
        stdout="ok",
        stderr="",
        stderr_spill=spill,
        stderr_spills=[spill],
        stderr_is_binary=True,
        stderr_contains_binary=True,
        exit_code=2,
        duration_ms=5.0,
    )

    rendered = present_command_execution_result(result, preview_limit=16)

    assert "[binary stderr omitted]" in rendered
    assert "Binary stderr was stored internally." in rendered
    assert "/tmp/binary-stderr.bin" not in rendered
    assert "grep <pattern>" not in rendered


def test_presentation_keeps_textual_stderr_visible_when_binary_fragments_exist() -> None:
    result = CommandExecutionResult(
        stdout="ok",
        stderr=b"\xff\xfebadtail",
        steps=[
            CommandExecutionStep(argv=["first"], stderr=b"\xff\xfebad", exit_code=0, stderr_is_binary=True),
            CommandExecutionStep(argv=["second"], stderr="tail", exit_code=2),
        ],
        stderr_contains_binary=True,
        exit_code=2,
        duration_ms=5.0,
    )

    rendered = present_command_execution_result(result, preview_limit=16)

    assert "tail" in rendered
    assert "[binary stderr omitted]" in rendered
    assert "\ufffd" not in rendered


@pytest.mark.asyncio
async def test_presentation_keeps_pipe_abort_explanation_alongside_binary_stderr_notice(tmp_path: Path) -> None:
    class _Backend:
        async def execute(self, argv, stdin):  # noqa: ANN001
            if argv[0] == "first":
                return CommandStepResult(stdout=b"\xff\xfeout", stderr=b"\xff\xfeerr", exit_code=0)
            return CommandStepResult(stdout="should-not-run", stderr="", exit_code=0)

    executor = CommandRuntimeExecutor(backend=_Backend(), spill_dir=tmp_path)
    result = await executor.execute(parse_command("first | second"))

    rendered = present_command_execution_result(result, preview_limit=128)

    assert "Pipe payloads must be UTF-8 text" in rendered
    assert "[binary stderr omitted]" in rendered
    assert "Binary stderr was stored internally." in rendered
