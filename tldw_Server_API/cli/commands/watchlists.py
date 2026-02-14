"""Watchlists operational commands for the unified CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click


def _resolve_audio_smoke_script_path() -> Path:
    """Return repository path to the watchlists audio smoke helper script."""
    # commands/watchlists.py -> cli/commands -> cli -> tldw_Server_API -> repo root
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "Helper_Scripts" / "watchlists" / "watchlists_audio_smoke.py"


@click.group()
def watchlists_group():
    """Watchlists operational commands."""
    pass


@watchlists_group.command(
    "audio-smoke",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option(
    "--python-bin",
    type=click.Path(path_type=Path),
    default=None,
    help="Optional Python interpreter to execute the helper script.",
)
@click.pass_context
def watchlists_audio_smoke(ctx, python_bin: Path | None):
    """Run the watchlists audio smoke helper with passthrough options."""
    script_path = _resolve_audio_smoke_script_path()
    if not script_path.exists():
        raise click.ClickException(f"Audio smoke script not found: {script_path}")

    python_exec = str(python_bin) if python_bin else sys.executable
    cmd = [python_exec, str(script_path), *ctx.args]

    try:
        completed = subprocess.run(cmd, check=False)
    except OSError as exc:  # pragma: no cover - platform-specific process launch failures
        raise click.ClickException(f"Failed to execute audio smoke script: {exc}") from exc

    if completed.returncode != 0:
        ctx.exit(completed.returncode)
