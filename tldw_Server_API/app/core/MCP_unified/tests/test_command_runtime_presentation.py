from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path

import pytest

from tldw_Server_API.app.core.MCP_unified.command_runtime.executor import CommandRuntimeExecutor
from tldw_Server_API.app.core.MCP_unified.command_runtime.models import (
    CommandExecutionResult,
    CommandExecutionStep,
    CommandStepResult,
    CommandSpillReference,
)
from tldw_Server_API.app.core.MCP_unified.command_runtime.parser import parse_command
from tldw_Server_API.app.core.MCP_unified.command_runtime.presentation import (
    present_command_execution_result,
)


def test_presentation_guards_binary_stdout():
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


def test_presentation_renders_utf8_bytes_stdout_as_text():
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


def test_presentation_mentions_spill_file_when_stdout_is_truncated():
    spill = CommandSpillReference(path="/tmp/spill-output.txt", bytes_written=128, line_count=1, preview="abcd")
    result = CommandExecutionResult(stdout="x" * 128, stderr="", exit_code=0, duration_ms=1.0, stdout_spill=spill)

    rendered = present_command_execution_result(result, preview_limit=4)

    assert "xxxx" in rendered
    assert "--- stdout truncated (1 lines, 128 bytes) ---" in rendered
    assert "/tmp/spill-output.txt" in rendered
    assert "spill" in rendered.lower()
    assert "[exit:0 | 1ms]" in rendered
    assert "x" * 16 not in rendered


def test_presentation_reads_spilled_stdout_from_disk_instead_of_executor_preview(tmp_path):
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


def test_presentation_does_not_claim_truncation_when_spilled_output_fits_preview_limits(tmp_path):
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


def test_presentation_truncates_utf8_output_on_byte_boundary():
    rendered = present_command_execution_result(
        CommandExecutionResult(stdout="ééé", stderr="", exit_code=0, duration_ms=2.0),
        preview_limit=3,
    )

    assert "é" in rendered
    assert "éé" not in rendered
    assert "�" not in rendered
    assert "[exit:0 | 2ms]" in rendered


def test_presentation_truncates_when_line_limit_is_exceeded_under_byte_cap():
    result = CommandExecutionResult(stdout="a\n" * 4, stderr="", exit_code=0, duration_ms=2.0)

    rendered = present_command_execution_result(result, byte_limit=128, line_limit=2)

    assert "a\na\n" in rendered
    assert "--- stdout truncated (4 lines, 8 bytes) ---" in rendered


def test_presentation_attaches_stderr_on_failure():
    result = CommandExecutionResult(stdout="ok", stderr="boom", exit_code=3, duration_ms=12.0)

    rendered = present_command_execution_result(result)

    assert "ok" in rendered
    assert "boom" in rendered
    assert "stderr" in rendered.lower()
    assert "[exit:3 | 12ms]" in rendered


def test_presentation_omits_leading_blank_lines_for_stderr_only_failures():
    result = CommandExecutionResult(stdout="", stderr="boom", exit_code=3, duration_ms=12.0)

    rendered = present_command_execution_result(result)

    assert rendered.startswith("stderr:\nboom")


def test_presentation_guards_binary_stderr_on_failure():
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
    assert "\ufffd" not in rendered
    assert "[exit:2 | 6ms]" in rendered


def test_presentation_spill_guidance_uses_cli_surface():
    spill = CommandSpillReference(path="/tmp/spill-output.txt", bytes_written=128, line_count=1, preview="abcd")
    result = CommandExecutionResult(stdout="x" * 128, stderr="", exit_code=0, duration_ms=1.0, stdout_spill=spill)

    rendered = present_command_execution_result(result, preview_limit=4)

    assert "cat /tmp/spill-output.txt | grep <pattern>" in rendered
    assert "cat /tmp/spill-output.txt | tail 100" in rendered


def test_presentation_creates_spill_guidance_for_truncated_stdout_without_spill_ref():
    result = CommandExecutionResult(stdout="é" * 16, stderr="", exit_code=0, duration_ms=1.0)

    rendered = present_command_execution_result(result, preview_limit=4)

    match = re.search(r"Full stdout spilled to (.+)", rendered)
    assert match is not None
    spill_path = match.group(1)
    assert f"cat {spill_path} | grep <pattern>" in rendered
    assert f"cat {spill_path} | tail 100" in rendered
    assert "grep <pattern>" in rendered
    assert "tail 100" in rendered
    assert "[exit:0 | 1ms]" in rendered


def test_presentation_creates_spill_guidance_for_truncated_stderr_without_spill_ref():
    result = CommandExecutionResult(stdout="ok", stderr="ß" * 16, exit_code=2, duration_ms=1.0)

    rendered = present_command_execution_result(result, preview_limit=4)

    assert "stderr" in rendered.lower()
    assert "--- stderr truncated (" in rendered
    assert "Full stderr spilled to " in rendered
    assert "grep <pattern>" in rendered
    assert "tail 100" in rendered


def test_presentation_attaches_spilled_text_stderr_on_failure():
    spill = CommandSpillReference(path="/tmp/stderr-spill.txt", bytes_written=128, line_count=1, preview="warn")
    result = CommandExecutionResult(stdout="ok", stderr="", stderr_spill=spill, exit_code=2, duration_ms=5.0)

    rendered = present_command_execution_result(result, preview_limit=4)

    assert "stderr" in rendered.lower()
    assert "warn" in rendered
    assert "--- stderr truncated (1 lines, 128 bytes) ---" in rendered
    assert "/tmp/stderr-spill.txt" in rendered
    assert "grep <pattern>" in rendered
    assert "[exit:2 | 5ms]" in rendered


def test_presentation_attaches_spilled_text_stderr_when_stdout_is_binary():
    spill = CommandSpillReference(path="/tmp/stderr-spill.txt", bytes_written=128, line_count=1, preview="warn")
    result = CommandExecutionResult(
        stdout=b"\x00\x01binary",
        stdout_is_binary=True,
        stderr="",
        stderr_spill=spill,
        exit_code=2,
        duration_ms=5.0,
    )

    rendered = present_command_execution_result(result, preview_limit=4)

    assert "[binary output omitted]" in rendered
    assert "stderr" in rendered.lower()
    assert "warn" in rendered
    assert "/tmp/stderr-spill.txt" in rendered
    assert "tail 100" in rendered


def test_presentation_preserves_inline_and_spilled_stderr_together():
    spill = CommandSpillReference(path="/tmp/stderr-spill.txt", bytes_written=128, line_count=1, preview="warn")
    result = CommandExecutionResult(
        stdout="ok",
        stderr="tail",
        stderr_spill=spill,
        stderr_spills=[spill],
        exit_code=2,
        duration_ms=5.0,
    )

    rendered = present_command_execution_result(result, preview_limit=16)

    assert "tail" in rendered
    assert "--- stderr truncated (1 lines, 128 bytes) ---" in rendered
    assert "/tmp/stderr-spill.txt" in rendered


def test_presentation_reports_exact_line_count_for_newline_terminated_output():
    result = CommandExecutionResult(stdout="line\n" * 3, stderr="", exit_code=0, duration_ms=1.0)

    rendered = present_command_execution_result(result, preview_limit=4)

    assert "--- stdout truncated (3 lines," in rendered


def test_presentation_uses_binary_safe_spill_notice_for_binary_stderr():
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
    assert "Binary stderr spill: /tmp/binary-stderr.bin" in rendered
    assert "grep <pattern>" not in rendered
    assert "tail 100" not in rendered


def test_presentation_keeps_textual_stderr_visible_when_binary_fragments_exist():
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
async def test_presentation_keeps_pipe_abort_explanation_alongside_binary_stderr_spill(tmp_path):
    class _Backend:
        async def execute(self, argv, stdin):
            if argv[0] == "first":
                return CommandStepResult(stdout=b"\xff\xfeout", stderr=b"\xff\xfeerr", exit_code=0)
            return CommandStepResult(stdout="should-not-run", stderr="", exit_code=0)

    executor = CommandRuntimeExecutor(backend=_Backend(), spill_dir=tmp_path)
    result = await executor.execute(parse_command("first | second"))

    rendered = present_command_execution_result(result, preview_limit=128)

    assert "Pipe payloads must be UTF-8 text" in rendered
    assert "[binary stderr omitted]" in rendered
    assert "Binary stderr spill:" in rendered


def test_presentation_treats_fallback_mixed_stderr_spills_as_binary():
    spill = CommandSpillReference(path="/tmp/binary-stderr.bin", bytes_written=128, line_count=0, preview="")
    result = CommandExecutionResult(
        stdout="ok",
        stderr="tail",
        stderr_spill=spill,
        stderr_spills=[spill],
        stderr_contains_binary=True,
        exit_code=2,
        duration_ms=5.0,
    )

    rendered = present_command_execution_result(result, preview_limit=16)

    assert "tail" in rendered
    assert "[binary stderr omitted]" in rendered
    assert "Binary stderr spill: /tmp/binary-stderr.bin" in rendered
    assert "grep <pattern>" not in rendered



def test_presentation_materializes_spill_for_oversized_inline_stderr_even_with_existing_spills():
    existing_spill = CommandSpillReference(path="/tmp/existing-stderr.txt", bytes_written=128, line_count=1, preview="warn")
    result = CommandExecutionResult(
        stdout="ok",
        stderr="z" * 64,
        stderr_spill=existing_spill,
        stderr_spills=[existing_spill],
        exit_code=2,
        duration_ms=5.0,
    )

    rendered = present_command_execution_result(result, preview_limit=8)

    paths = re.findall(r"Full stderr spilled to (.+)", rendered)
    assert "/tmp/existing-stderr.txt" in paths
    assert len(paths) == 2


def test_presentation_reuses_same_materialized_spill_path_for_repeated_renders():
    result = CommandExecutionResult(stdout="line\n" * 8, stderr="", exit_code=0, duration_ms=1.0)

    first = present_command_execution_result(result, preview_limit=4)
    second = present_command_execution_result(result, preview_limit=4)

    first_path = re.search(r"Full stdout spilled to (.+)", first)
    second_path = re.search(r"Full stdout spilled to (.+)", second)
    assert first_path is not None
    assert second_path is not None
    assert first_path.group(1) == second_path.group(1)


def test_presentation_materialized_spill_uses_requested_dir_and_restricted_permissions(tmp_path):
    result = CommandExecutionResult(stdout="line\n" * 8, stderr="", exit_code=0, duration_ms=1.0)
    spill_dir = tmp_path / "spill"
    spill_dir.mkdir(mode=0o700)

    rendered = present_command_execution_result(result, preview_limit=4, spill_dir=spill_dir)

    match = re.search(r"Full stdout spilled to (.+)", rendered)
    assert match is not None
    spill_path = Path(match.group(1))
    assert spill_path.parent == spill_dir
    assert stat.S_IMODE(spill_path.stat().st_mode) == 0o600


def test_presentation_materialized_spill_refuses_to_reuse_tampered_deterministic_file(tmp_path):
    text = "line\n" * 8
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    compromised_path = tmp_path / f"stdout-{digest}.txt"
    compromised_path.write_text("tampered", encoding="utf-8")
    result = CommandExecutionResult(stdout=text, stderr="", exit_code=0, duration_ms=1.0)

    rendered = present_command_execution_result(result, preview_limit=4, spill_dir=tmp_path)

    match = re.search(r"Full stdout spilled to (.+)", rendered)
    assert match is not None
    spill_path = Path(match.group(1))
    assert spill_path.read_text(encoding="utf-8") == text
    assert spill_path != compromised_path


def test_presentation_materialized_spill_refuses_to_reuse_symlinked_deterministic_file(tmp_path):
    text = "line\n" * 8
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    deterministic_path = tmp_path / f"stdout-{digest}.txt"
    external_path = tmp_path / "external.txt"
    external_path.write_text(text, encoding="utf-8")
    deterministic_path.symlink_to(external_path)
    result = CommandExecutionResult(stdout=text, stderr="", exit_code=0, duration_ms=1.0)

    rendered = present_command_execution_result(result, preview_limit=4, spill_dir=tmp_path)

    match = re.search(r"Full stdout spilled to (.+)", rendered)
    assert match is not None
    spill_path = Path(match.group(1))
    assert spill_path.read_text(encoding="utf-8") == text
    assert spill_path != deterministic_path


def test_presentation_shell_quotes_spill_paths_in_explore_guidance():
    spill = CommandSpillReference(
        path="/tmp/path with spaces/stdout.txt",
        bytes_written=128,
        line_count=1,
        preview="abcd",
    )
    result = CommandExecutionResult(stdout="x" * 128, stderr="", exit_code=0, duration_ms=1.0, stdout_spill=spill)

    rendered = present_command_execution_result(result, preview_limit=4)

    assert "Full stdout spilled to /tmp/path with spaces/stdout.txt" in rendered
    assert "cat '/tmp/path with spaces/stdout.txt' | grep <pattern>" in rendered
    assert "cat '/tmp/path with spaces/stdout.txt' | tail 100" in rendered


def test_presentation_rejects_symlinked_spill_dir(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    symlink = tmp_path / "spill-link"
    symlink.symlink_to(target, target_is_directory=True)
    result = CommandExecutionResult(stdout="line\n" * 8, stderr="", exit_code=0, duration_ms=1.0)

    with pytest.raises(PermissionError, match="symlink"):
        present_command_execution_result(result, preview_limit=4, spill_dir=symlink)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission test")
def test_presentation_rejects_non_private_existing_spill_dir(tmp_path):
    spill_dir = tmp_path / "spill"
    spill_dir.mkdir(mode=0o755)
    result = CommandExecutionResult(stdout="line\n" * 8, stderr="", exit_code=0, duration_ms=1.0)

    with pytest.raises(PermissionError, match="non-private permissions"):
        present_command_execution_result(result, preview_limit=4, spill_dir=spill_dir)
