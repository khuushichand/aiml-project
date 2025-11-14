from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from loguru import logger

from .utils import detect as detect_utils
from .utils import env as env_utils
from .utils import files as files_utils
from .utils import format as format_utils
from .utils import git as git_utils


app = typer.Typer(add_completion=False, no_args_is_help=True, help="tldw_server setup wizard CLI")


def _emit(result: Dict[str, Any], use_json: bool) -> None:
    if use_json:
        typer.echo(json.dumps(result, indent=2))
    else:
        # Minimal human-friendly print
        status = result.get("status", "ok")
        typer.echo(f"Status: {status}")
        for k in ("actions", "facts", "notes"):
            if k in result and result[k]:
                typer.echo(f"{k.capitalize()}: {result[k]}")


@app.command()
def init(
    default: bool = typer.Option(False, "--default", help="Apply safe defaults without prompting"),
    install_dir: Path = typer.Option(Path.cwd(), "--install-dir", help="Installation directory (default: CWD)"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Run without prompts using env vars"),
    debug: bool = typer.Option(False, "--debug", help="Verbose logging"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview actions without writing"),
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output"),
    yes: bool = typer.Option(False, "--yes", "--no-input", help="Assume 'yes' for prompts (non-interactive)"),
    no_format: bool = typer.Option(False, "--no-format", help="Skip formatting changed files"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output"),
    quiet: bool = typer.Option(False, "--quiet", help="Minimal output"),
):
    """Full guided setup (scaffold)."""
    if debug:
        logger.remove()
        logger.add(lambda m: typer.echo(m, nl=False), level="DEBUG")

    base = Path(install_dir).resolve()
    facts = {
        "cwd": str(Path.cwd()),
        "install_dir": str(base),
        "git": git_utils.is_git_repo(base),
        "ffmpeg": detect_utils.has_ffmpeg(),
        "cuda": detect_utils.has_cuda(),
    }

    # Plan actions (skeleton)
    env_path = base / ".env"
    actions = []
    if not env_path.exists():
        actions.append({"create": str(env_path)})
    actions.append({"ensure_gitignore": [".env", ".env.local", "wizard.log"]})

    if dry_run:
        result = {
            "command": "init",
            "status": "ok",
            "facts": facts,
            "actions": actions,
            "notes": [
                "dry-run only; no changes made",
                "this is a scaffold; future steps will initialize DBs and verify endpoints",
            ],
        }
        _emit(result, json_out)
        raise typer.Exit(0)

    # Write .env safely (idempotent)
    defaults: Dict[str, Optional[str]] = {
        "AUTH_MODE": os.getenv("AUTH_MODE", "single_user" if default or yes else ""),
        # Placeholders only; real key generation happens in full implementation
        "SINGLE_USER_API_KEY": os.getenv("SINGLE_USER_API_KEY", ""),
    }
    env_utils.ensure_env(env_path, defaults=defaults)

    # Ensure .gitignore entries
    files_utils.ensure_gitignore(base / ".gitignore", entries=[".env", ".env.local", "wizard.log"])

    # Optional formatting (scaffold: only runs if tools present and in git repo)
    if not no_format and facts["git"]:
        try:
            changed = git_utils.changed_or_untracked_files(base)
            if changed:
                format_utils.maybe_format(changed)
        except Exception as e:
            logger.debug(f"format step skipped: {e}")

    result = {
        "command": "init",
        "status": "ok",
        "facts": facts,
        "actions": actions,
        "paths": {"env": str(env_path)},
    }
    _emit(result, json_out)


@app.command()
def auth(
    mode: str = typer.Option(
        "single_user",
        "--mode",
        help="Authentication mode",
        case_sensitive=False,
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview actions without writing"),
):
    """Configure Auth mode (scaffold)."""
    mode = mode.lower().strip()
    if mode not in {"single_user", "multi_user"}:
        typer.echo("Invalid mode. Use single_user or multi_user.")
        raise typer.Exit(2)
    actions = [{"set_env": {"AUTH_MODE": mode}}]
    result = {"command": "auth", "status": "ok", "mode": mode, "actions": actions, "dry_run": dry_run}
    _emit(result, json_out)


@app.command()
def verify(
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output"),
    check_provider: bool = typer.Option(False, "--check-provider", help="Attempt provider checks (offline/mock in scaffold)"),
):
    """Run verification checks (scaffold)."""
    facts = {
        "ffmpeg": detect_utils.has_ffmpeg(),
        "cuda": detect_utils.has_cuda(),
    }
    notes = ["health endpoints check will be added in full implementation"]
    result = {"command": "verify", "status": "ok", "facts": facts, "check_provider": bool(check_provider), "notes": notes}
    _emit(result, json_out)


@app.command()
def providers(
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview actions without writing"),
    check_provider: bool = typer.Option(False, "--check-provider", help="Attempt provider checks (offline/mock in scaffold)"),
):
    """Collect/store provider keys (scaffold)."""
    actions = ["write .env keys (preferred)", "optionally generate Config_Files/config.txt if requested"]
    result = {"command": "providers", "status": "ok", "actions": actions, "dry_run": dry_run, "check_provider": bool(check_provider)}
    _emit(result, json_out)


@app.command()
def db(
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output"),
):
    """Initialize/validate databases (scaffold)."""
    actions = [
        "ensure per-user SQLite structure exists",
        "validate Postgres if DATABASE_URL is set",
    ]
    result = {"command": "db", "status": "ok", "actions": actions}
    _emit(result, json_out)


@app.command()
def mcp(
    action: str = typer.Argument("add", metavar="[add|remove]", help="Add or remove MCP client configs"),
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview actions without writing"),
):
    """Install/remove MCP client config (scaffold)."""
    action = action.lower().strip()
    if action not in {"add", "remove"}:
        typer.echo("Invalid action. Use add or remove.")
        raise typer.Exit(2)
    actions = [{action: ["cursor", "claude", "vscode", "zed"]}]
    result = {"command": "mcp", "status": "ok", "actions": actions, "dry_run": dry_run}
    _emit(result, json_out)


@app.command()
def format(
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output"),
):
    """Format changed files with Black/Ruff when available (scaffold)."""
    base = Path.cwd()
    actions: Dict[str, Any] = {"formatted": []}
    if git_utils.is_git_repo(base):
        changed = git_utils.changed_or_untracked_files(base)
        if changed:
            try:
                format_utils.maybe_format(changed)
                actions["formatted"] = changed
            except Exception as e:
                actions["error"] = str(e)
    result = {"command": "format", "status": "ok", "actions": actions}
    _emit(result, json_out)


@app.command()
def doctor(
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON output"),
):
    """Detect issues and propose/apply fixes (scaffold)."""
    facts = {
        "ffmpeg": detect_utils.has_ffmpeg(),
        "git": git_utils.is_git_repo(Path.cwd()),
    }
    actions = [
        "check .env presence and permissions",
        "check .gitignore contains .env entries",
        "suggest installing ffmpeg if missing",
    ]
    result = {"command": "doctor", "status": "ok", "facts": facts, "actions": actions}
    _emit(result, json_out)


def main() -> None:
    """Console script entry point for tldw-setup."""
    app()


if __name__ == "__main__":  # pragma: no cover - script mode
    main()

