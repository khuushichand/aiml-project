from __future__ import annotations

import os
import stat
import tempfile
import time
from pathlib import Path
from typing import Callable

import pytest

from tldw_Server_API.app.core.MCP_unified.command_runtime.executor import CommandRuntimeExecutor
from tldw_Server_API.app.core.MCP_unified.command_runtime.models import CommandSpillReference, CommandStepResult
from tldw_Server_API.app.core.MCP_unified.command_runtime.parser import parse_command


class _FakeBackend:
    def __init__(self, handlers: dict[str, Callable[[list[str], str], CommandStepResult]]):
        self.handlers = handlers
        self.calls: list[tuple[list[str], str]] = []

    async def execute(self, argv: list[str], stdin: str) -> CommandStepResult:
        self.calls.append((list(argv), stdin))
        handler = self.handlers[argv[0]]
        return handler(argv, stdin)


@pytest.mark.asyncio
async def test_execution_pipes_stdout_into_next_command_without_formatting(tmp_path):
    backend = _FakeBackend(
        {
            "first": lambda argv, stdin: CommandStepResult(stdout="alpha\n", stderr="", exit_code=0),
            "second": lambda argv, stdin: CommandStepResult(stdout=f"seen:{stdin}", stderr="", exit_code=0),
        }
    )
    executor = CommandRuntimeExecutor(backend=backend, spill_dir=tmp_path)

    result = await executor.execute(parse_command("first | second"))

    assert backend.calls == [(["first"], ""), (["second"], "alpha\n")]
    assert result.stdout == "seen:alpha\n"
    assert result.exit_code == 0
    assert "[exit:" not in result.stdout
    assert "stderr" not in result.stdout.lower()


@pytest.mark.asyncio
async def test_execution_normalizes_utf8_bytes_stdout_to_text(tmp_path):
    backend = _FakeBackend(
        {
            "bytes": lambda argv, stdin: CommandStepResult(stdout=b"hello\n", stderr=b"", exit_code=0),
        }
    )
    executor = CommandRuntimeExecutor(backend=backend, spill_dir=tmp_path)

    result = await executor.execute(parse_command("bytes"))

    assert result.stdout == "hello\n"
    assert result.stdout_is_binary is False


@pytest.mark.asyncio
async def test_execution_preserves_binary_like_bytes_stdout_losslessly(tmp_path):
    payload = b"\xff\xfehello"
    backend = _FakeBackend(
        {
            "bytes": lambda argv, stdin: CommandStepResult(stdout=payload, stderr=b"", exit_code=0),
        }
    )
    executor = CommandRuntimeExecutor(backend=backend, spill_dir=tmp_path)

    result = await executor.execute(parse_command("bytes"))

    assert result.stdout == payload
    assert result.stdout_is_binary is True


@pytest.mark.asyncio
async def test_execution_preserves_early_pipeline_stderr_in_aggregate_result(tmp_path):
    backend = _FakeBackend(
        {
            "first": lambda argv, stdin: CommandStepResult(stdout="alpha", stderr="warn: first", exit_code=0),
            "second": lambda argv, stdin: CommandStepResult(stdout=f"seen:{stdin}", stderr="", exit_code=0),
        }
    )
    executor = CommandRuntimeExecutor(backend=backend, spill_dir=tmp_path)

    result = await executor.execute(parse_command("first | second"))

    assert backend.calls == [(["first"], ""), (["second"], "alpha")]
    assert result.stderr == "warn: first"
    assert result.steps[0].stderr == "warn: first"


@pytest.mark.asyncio
async def test_execution_preserves_adjacent_stderr_fragments_without_injecting_newlines(tmp_path):
    backend = _FakeBackend(
        {
            "first": lambda argv, stdin: CommandStepResult(stdout="alpha", stderr="warn", exit_code=0),
            "second": lambda argv, stdin: CommandStepResult(stdout="done", stderr="tail", exit_code=1),
        }
    )
    executor = CommandRuntimeExecutor(backend=backend, spill_dir=tmp_path)

    result = await executor.execute(parse_command("first | second"))

    assert result.exit_code == 1
    assert result.stderr == "warntail"


@pytest.mark.asyncio
async def test_execution_respects_shell_chain_operators(tmp_path):
    backend = _FakeBackend(
        {
            "fail": lambda argv, stdin: CommandStepResult(stdout="", stderr="boom", exit_code=1),
            "after_success": lambda argv, stdin: CommandStepResult(stdout="skip-me", stderr="", exit_code=0),
            "after_failure": lambda argv, stdin: CommandStepResult(stdout="recovered", stderr="", exit_code=0),
            "final": lambda argv, stdin: CommandStepResult(stdout="done", stderr="", exit_code=0),
        }
    )
    executor = CommandRuntimeExecutor(backend=backend, spill_dir=tmp_path)

    result = await executor.execute(parse_command("fail && after_success || after_failure; final"))

    assert backend.calls == [(["fail"], ""), (["after_failure"], ""), (["final"], "")]
    assert result.stdout == "done"
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_execution_spills_large_stdout_to_disk_while_preserving_terminal_stream(tmp_path):
    big_output = "x" * 128
    backend = _FakeBackend(
        {
            "big": lambda argv, stdin: CommandStepResult(stdout=big_output, stderr="", exit_code=0),
        }
    )
    executor = CommandRuntimeExecutor(
        backend=backend,
        spill_dir=tmp_path,
        spill_threshold_bytes=32,
        preview_bytes=12,
    )

    result = await executor.execute(parse_command("big"))

    assert result.stdout_spill is not None
    assert result.stdout_spill.bytes_written == len(big_output)
    assert result.stdout_spill.preview == big_output[:12]
    assert Path(result.stdout_spill.path).read_text(encoding="utf-8") == big_output
    assert result.stdout == big_output
    assert result.steps[0].stdout == ""


@pytest.mark.asyncio
async def test_execution_passes_spill_reference_downstream_for_large_pipeline_stdout(tmp_path):
    big_output = "y" * 128
    backend = _FakeBackend(
        {
            "big": lambda argv, stdin: CommandStepResult(stdout=big_output, stderr="", exit_code=0),
            "consume": lambda argv, stdin: CommandStepResult(
                stdout="recovered" if (
                    stdin.read_text() if isinstance(stdin, CommandSpillReference) else str(stdin)
                ) == big_output else "mismatch",
                stderr="",
                exit_code=0,
            ),
        }
    )
    executor = CommandRuntimeExecutor(
        backend=backend,
        spill_dir=tmp_path,
        spill_threshold_bytes=32,
        preview_bytes=12,
    )

    result = await executor.execute(parse_command("big | consume"))

    assert isinstance(backend.calls[1][1], CommandSpillReference)
    assert backend.calls[1][1].bytes_written == len(big_output)
    assert backend.calls[1][1].read_text() == big_output
    assert result.steps[0].stdout == ""
    assert isinstance(result.steps[1].stdin, CommandSpillReference)
    assert result.steps[1].stdin.bytes_written == len(big_output)
    assert result.stdout == "recovered"


@pytest.mark.asyncio
async def test_execution_rejects_binary_payloads_inside_pipelines(tmp_path):
    payload = b"\xff\xfebinary"
    backend = _FakeBackend(
        {
            "first": lambda argv, stdin: CommandStepResult(stdout=payload, stderr="", exit_code=0),
            "second": lambda argv, stdin: CommandStepResult(stdout="should-not-run", stderr="", exit_code=0),
        }
    )
    executor = CommandRuntimeExecutor(backend=backend, spill_dir=tmp_path)

    result = await executor.execute(parse_command("first | second"))

    assert backend.calls == [(["first"], "")]
    assert result.exit_code == 1
    assert "utf-8 text" in result.stderr.lower()


@pytest.mark.asyncio
async def test_execution_preserves_binary_stderr_when_binary_stdout_aborts_pipeline(tmp_path):
    stdout_payload = b"\xff\xfeout"
    stderr_payload = b"\xff\xfeerr"
    backend = _FakeBackend(
        {
            "first": lambda argv, stdin: CommandStepResult(stdout=stdout_payload, stderr=stderr_payload, exit_code=0),
            "second": lambda argv, stdin: CommandStepResult(stdout="should-not-run", stderr="", exit_code=0),
        }
    )
    executor = CommandRuntimeExecutor(backend=backend, spill_dir=tmp_path)

    result = await executor.execute(parse_command("first | second"))

    assert result.exit_code == 1
    assert result.stderr_contains_binary is True
    assert result.steps[0].stderr_contains_binary is True
    assert "utf-8 text" in result.steps[0].stderr.lower()
    assert result.steps[0].stderr_spill is not None
    assert Path(result.steps[0].stderr_spill.path).read_bytes() == stderr_payload


@pytest.mark.asyncio
async def test_execution_preserves_latest_spilled_stderr_reference_for_failures(tmp_path):
    big_stderr = "warn" * 64
    backend = _FakeBackend(
        {
            "first": lambda argv, stdin: CommandStepResult(stdout="alpha", stderr=big_stderr, exit_code=0),
            "second": lambda argv, stdin: CommandStepResult(stdout="done", stderr="", exit_code=1),
        }
    )
    executor = CommandRuntimeExecutor(
        backend=backend,
        spill_dir=tmp_path,
        spill_threshold_bytes=32,
        preview_bytes=12,
    )

    result = await executor.execute(parse_command("first | second"))

    assert result.exit_code == 1
    assert result.stderr == big_stderr
    assert result.stderr_spill is not None
    assert len(result.stderr_spills) == 1
    assert Path(result.stderr_spill.path).read_text(encoding="utf-8") == big_stderr
    assert result.steps[0].stderr == ""
    assert result.steps[0].stderr_spill is not None


@pytest.mark.asyncio
async def test_execution_collects_mixed_inline_and_spilled_stderr_for_failures(tmp_path):
    big_stderr = "warn" * 64
    backend = _FakeBackend(
        {
            "first": lambda argv, stdin: CommandStepResult(stdout="alpha", stderr=big_stderr, exit_code=0),
            "second": lambda argv, stdin: CommandStepResult(stdout="done", stderr="tail", exit_code=1),
        }
    )
    executor = CommandRuntimeExecutor(
        backend=backend,
        spill_dir=tmp_path,
        spill_threshold_bytes=32,
        preview_bytes=12,
    )

    result = await executor.execute(parse_command("first | second"))

    assert result.exit_code == 1
    assert result.stderr == big_stderr + "tail"
    assert len(result.stderr_spills) == 1
    assert Path(result.stderr_spills[0].path).read_text(encoding="utf-8") == big_stderr


@pytest.mark.asyncio
async def test_execution_tracks_binary_stderr_without_masking_textual_fragments(tmp_path):
    payload = b"\xff\xfebad"
    backend = _FakeBackend(
        {
            "first": lambda argv, stdin: CommandStepResult(stdout="alpha", stderr=payload, exit_code=0),
            "second": lambda argv, stdin: CommandStepResult(stdout="done", stderr="tail", exit_code=1),
        }
    )
    executor = CommandRuntimeExecutor(backend=backend, spill_dir=tmp_path)

    result = await executor.execute(parse_command("first | second"))

    assert result.exit_code == 1
    assert result.stderr == payload + b"tail"
    assert result.stderr_contains_binary is True
    assert result.stderr_is_binary is False


@pytest.mark.asyncio
async def test_execution_counts_newline_terminated_spill_lines_correctly(tmp_path):
    big_output = "line\n" * 8
    backend = _FakeBackend(
        {
            "big": lambda argv, stdin: CommandStepResult(stdout=big_output, stderr="", exit_code=0),
        }
    )
    executor = CommandRuntimeExecutor(
        backend=backend,
        spill_dir=tmp_path,
        spill_threshold_bytes=16,
        preview_bytes=12,
    )

    result = await executor.execute(parse_command("big"))

    assert result.stdout_spill is not None
    assert result.stdout_spill.line_count == 8


@pytest.mark.asyncio
async def test_execution_reuses_matching_spill_file_for_identical_payloads(tmp_path):
    big_output = "reuse" * 32
    backend = _FakeBackend(
        {
            "big": lambda argv, stdin: CommandStepResult(stdout=big_output, stderr="", exit_code=0),
        }
    )
    executor = CommandRuntimeExecutor(
        backend=backend,
        spill_dir=tmp_path,
        spill_threshold_bytes=16,
        preview_bytes=12,
    )

    first = await executor.execute(parse_command("big"))
    second = await executor.execute(parse_command("big"))

    assert first.stdout_spill is not None
    assert second.stdout_spill is not None
    assert first.stdout_spill.path == second.stdout_spill.path
    assert Path(first.stdout_spill.path).read_text(encoding="utf-8") == big_output


@pytest.mark.asyncio
async def test_execution_prunes_expired_spills_before_writing_new_payload(tmp_path):
    stale = tmp_path / "mcp-command-stdout-stale.txt"
    stale.write_text("old", encoding="utf-8")
    old_time = time.time() - 120
    os.utime(stale, (old_time, old_time))

    big_output = "fresh" * 32
    backend = _FakeBackend(
        {
            "big": lambda argv, stdin: CommandStepResult(stdout=big_output, stderr="", exit_code=0),
        }
    )
    executor = CommandRuntimeExecutor(
        backend=backend,
        spill_dir=tmp_path,
        spill_threshold_bytes=16,
        spill_retention_seconds=1,
    )

    result = await executor.execute(parse_command("big"))

    assert result.stdout_spill is not None
    assert not stale.exists()


@pytest.mark.asyncio
async def test_execution_rejects_symlinked_spill_dir(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    symlink = tmp_path / "spill-link"
    symlink.symlink_to(target, target_is_directory=True)
    backend = _FakeBackend(
        {
            "big": lambda argv, stdin: CommandStepResult(stdout="x" * 128, stderr="", exit_code=0),
        }
    )
    executor = CommandRuntimeExecutor(
        backend=backend,
        spill_dir=symlink,
        spill_threshold_bytes=16,
    )

    with pytest.raises(PermissionError, match="symlink"):
        await executor.execute(parse_command("big"))


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="POSIX permission test")
async def test_execution_rejects_non_private_existing_spill_dir(tmp_path):
    spill_dir = tmp_path / "spill"
    spill_dir.mkdir(mode=0o755)
    backend = _FakeBackend(
        {
            "big": lambda argv, stdin: CommandStepResult(stdout="x" * 128, stderr="", exit_code=0),
        }
    )
    executor = CommandRuntimeExecutor(
        backend=backend,
        spill_dir=spill_dir,
        spill_threshold_bytes=16,
    )

    with pytest.raises(PermissionError, match="non-private permissions"):
        await executor.execute(parse_command("big"))


@pytest.mark.asyncio
async def test_execution_tolerates_raced_spill_root_creation(tmp_path, monkeypatch):
    spill_dir = tmp_path / "spill"
    original_mkdir = Path.mkdir
    injected_race = False

    def racing_mkdir(self: Path, *args, **kwargs):
        nonlocal injected_race
        if self == spill_dir and not injected_race:
            injected_race = True
            original_mkdir(self, *args, **kwargs)
            raise FileExistsError()
        return original_mkdir(self, *args, **kwargs)

    backend = _FakeBackend(
        {
            "big": lambda argv, stdin: CommandStepResult(stdout="x" * 128, stderr="", exit_code=0),
        }
    )
    monkeypatch.setattr(Path, "mkdir", racing_mkdir)
    executor = CommandRuntimeExecutor(
        backend=backend,
        spill_dir=spill_dir,
        spill_threshold_bytes=16,
    )

    result = await executor.execute(parse_command("big"))

    assert injected_race is True
    assert result.stdout_spill is not None
    assert Path(result.stdout_spill.path).parent == spill_dir


def test_execution_uses_unique_private_default_spill_roots(tmp_path, monkeypatch):
    backend = _FakeBackend(
        {
            "big": lambda argv, stdin: CommandStepResult(stdout="x" * 128, stderr="", exit_code=0),
        }
    )
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    first = CommandRuntimeExecutor(backend=backend, spill_threshold_bytes=16)
    second = CommandRuntimeExecutor(backend=backend, spill_threshold_bytes=16)

    first_root = first._resolve_spill_root()
    second_root = second._resolve_spill_root()

    assert first_root != second_root
    assert first_root.exists()
    assert second_root.exists()
    if os.name != "nt":
        assert stat.S_IMODE(first_root.stat().st_mode) == 0o700
        assert stat.S_IMODE(second_root.stat().st_mode) == 0o700


@pytest.mark.asyncio
async def test_execution_prunes_stale_default_spill_roots_across_executor_instances(tmp_path, monkeypatch):
    stale_root = tmp_path / "mcp-command-execution-stale"
    stale_root.mkdir(mode=0o700)
    stale = stale_root / "mcp-command-stdout-stale.txt"
    stale.write_text("old", encoding="utf-8")
    old_time = time.time() - 120
    os.utime(stale, (old_time, old_time))
    os.utime(stale_root, (old_time, old_time))

    backend = _FakeBackend(
        {
            "big": lambda argv, stdin: CommandStepResult(stdout="x" * 128, stderr="", exit_code=0),
        }
    )
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    executor = CommandRuntimeExecutor(
        backend=backend,
        spill_threshold_bytes=16,
        spill_retention_seconds=1,
    )

    result = await executor.execute(parse_command("big"))

    assert result.stdout_spill is not None
    assert Path(result.stdout_spill.path).parent != stale_root
    assert not stale_root.exists()


@pytest.mark.asyncio
async def test_execution_keeps_recently_reused_default_root_from_being_pruned(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    big_output = "reuse" * 32
    backend = _FakeBackend(
        {
            "big": lambda argv, stdin: CommandStepResult(stdout=big_output, stderr="", exit_code=0),
            "other": lambda argv, stdin: CommandStepResult(stdout="other" * 32, stderr="", exit_code=0),
        }
    )

    first = CommandRuntimeExecutor(
        backend=backend,
        spill_threshold_bytes=16,
        spill_retention_seconds=1,
    )
    first_result = await first.execute(parse_command("big"))
    first_root = Path(first_result.stdout_spill.path).parent
    first_spill = Path(first_result.stdout_spill.path)

    old_time = time.time() - 120
    os.utime(first_root, (old_time, old_time))

    reused = await first.execute(parse_command("big"))
    assert reused.stdout_spill is not None
    assert Path(reused.stdout_spill.path) == first_spill

    second = CommandRuntimeExecutor(
        backend=backend,
        spill_threshold_bytes=16,
        spill_retention_seconds=1,
    )
    await second.execute(parse_command("other"))

    assert first_root.exists()
    assert first_spill.exists()
