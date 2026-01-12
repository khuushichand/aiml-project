from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

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


def _resolve_database_url(env_path: Path) -> Optional[str]:
    value = os.getenv("DATABASE_URL") or env_utils.load_env(env_path).get("DATABASE_URL")
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed or trimmed.lower() in {"none", "null", "nil"}:
        return None
    return trimmed


def _validate_database_url(db_url: str) -> tuple[bool, str]:
    try:
        parsed = urlsplit(db_url)
    except Exception:
        return False, "unable to parse DATABASE_URL"
    scheme = (parsed.scheme or "").split("+", 1)[0].lower()
    if scheme in {"postgres", "postgresql"}:
        if not parsed.netloc:
            return False, "missing host or credentials"
        return True, ""
    if scheme in {"sqlite", "file", ""}:
        return False, "sqlite/file URLs are not supported for multi_user"
    return False, f"unsupported scheme '{scheme}'"


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

    existing_env = env_utils.load_env(env_path)
    auth_mode = os.getenv("AUTH_MODE") or existing_env.get("AUTH_MODE") or ("single_user" if default or yes else "")
    updates: Dict[str, Optional[str]] = {}
    initializer_action: Optional[Dict[str, Any]] = None
    validation_action: Optional[Dict[str, Any]] = None
    if auth_mode:
        updates["AUTH_MODE"] = auth_mode
    if auth_mode == "single_user":
        existing_key = (
            os.getenv("SINGLE_USER_API_KEY")
            or os.getenv("API_KEY")
            or existing_env.get("SINGLE_USER_API_KEY")
        )
        if not existing_key:
            existing_key = env_utils.generate_single_user_api_key()
        updates["SINGLE_USER_API_KEY"] = existing_key
    if auth_mode == "multi_user":
        db_url = _resolve_database_url(env_path)
        if not db_url:
            result = {
                "command": "init",
                "status": "error",
                "facts": facts,
                "actions": [{"validate_database_url": {"present": False, "valid": False, "reason": "missing"}}],
                "notes": ["DATABASE_URL is required for multi_user mode."],
            }
            _emit(result, json_out)
            raise typer.Exit(2)
        valid, reason = _validate_database_url(db_url)
        if not valid:
            result = {
                "command": "init",
                "status": "error",
                "facts": facts,
                "actions": [{"validate_database_url": {"present": True, "valid": False, "reason": reason}}],
                "notes": [f"DATABASE_URL invalid for multi_user: {reason}"],
            }
            _emit(result, json_out)
            raise typer.Exit(2)
        validation_action = {"validate_database_url": {"present": True, "valid": True, "reason": None}}
        updates["DATABASE_URL"] = db_url
        cmd = [sys.executable, "-m", "tldw_Server_API.app.core.AuthNZ.initialize"]
        if dry_run:
            if yes:
                initializer_action = {"command": " ".join(cmd), "status": "would_run"}
            elif non_interactive or not sys.stdin.isatty():
                initializer_action = {"command": " ".join(cmd), "status": "skipped_non_interactive"}
            else:
                initializer_action = {"command": " ".join(cmd), "status": "would_prompt"}
        else:
            if yes:
                proc = subprocess.run(cmd, check=False)
                initializer_action = {"command": " ".join(cmd), "returncode": proc.returncode}
            elif non_interactive or not sys.stdin.isatty():
                initializer_action = {"command": " ".join(cmd), "status": "skipped_non_interactive"}
            else:
                if typer.confirm("Run AuthNZ initializer now?", default=False):
                    proc = subprocess.run(cmd, check=False)
                    initializer_action = {"command": " ".join(cmd), "returncode": proc.returncode}
                else:
                    initializer_action = {"command": "AuthNZ initializer", "status": "skipped"}

    if dry_run:
        if updates:
            actions.append({"set_env": env_utils.mask_env_values({k: v for k, v in updates.items() if v is not None})})
        if validation_action:
            actions.append(validation_action)
        if initializer_action:
            actions.append({"authnz_initializer": initializer_action})
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
    env_utils.ensure_env(env_path, updates=updates)

    # Ensure .gitignore entries
    files_utils.ensure_gitignore(base / ".gitignore", entries=[".env", ".env.local", "wizard.log"])

    if updates:
        actions.append({"set_env": env_utils.mask_env_values({k: v for k, v in updates.items() if v is not None})})
    if validation_action:
        actions.append(validation_action)
    if initializer_action:
        actions.append({"authnz_initializer": initializer_action})

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
    yes: bool = typer.Option(False, "--yes", "--no-input", help="Assume 'yes' for prompts (non-interactive)"),
):
    """Configure Auth mode (scaffold)."""
    mode = mode.lower().strip()
    if mode not in {"single_user", "multi_user"}:
        typer.echo("Invalid mode. Use single_user or multi_user.")
        raise typer.Exit(2)
    env_path = Path.cwd() / ".env"
    existing_env = env_utils.load_env(env_path)
    updates: Dict[str, Optional[str]] = {"AUTH_MODE": mode}
    notes = []
    actions = []
    validation: Dict[str, Any] = {}
    initializer_action: Optional[Dict[str, Any]] = None
    if mode == "single_user":
        existing_key = (
            os.getenv("SINGLE_USER_API_KEY")
            or os.getenv("API_KEY")
            or existing_env.get("SINGLE_USER_API_KEY")
        )
        if not existing_key:
            if dry_run:
                notes.append("would_generate_single_user_api_key")
            else:
                existing_key = env_utils.generate_single_user_api_key()
        if existing_key:
            updates["SINGLE_USER_API_KEY"] = existing_key
    if mode == "multi_user":
        db_url = _resolve_database_url(env_path)
        if not db_url:
            validation = {"database_url": {"present": False, "valid": False, "reason": "missing"}}
            notes.append("DATABASE_URL is required for multi_user mode.")
            result = {
                "command": "auth",
                "status": "error",
                "mode": mode,
                "actions": [{"validate_database_url": validation}],
                "dry_run": dry_run,
                "notes": notes,
                "paths": {"env": str(env_path)},
            }
            _emit(result, json_out)
            raise typer.Exit(2)
        valid, reason = _validate_database_url(db_url)
        validation = {"database_url": {"present": True, "valid": valid, "reason": reason or None}}
        if not valid:
            notes.append(f"DATABASE_URL invalid for multi_user: {reason}")
            result = {
                "command": "auth",
                "status": "error",
                "mode": mode,
                "actions": [{"validate_database_url": validation}],
                "dry_run": dry_run,
                "notes": notes,
                "paths": {"env": str(env_path)},
            }
            _emit(result, json_out)
            raise typer.Exit(2)
        cmd = [sys.executable, "-m", "tldw_Server_API.app.core.AuthNZ.initialize"]
        if dry_run:
            if yes:
                initializer_action = {"command": " ".join(cmd), "status": "would_run"}
            elif sys.stdin.isatty():
                initializer_action = {"command": " ".join(cmd), "status": "would_prompt"}
            else:
                initializer_action = {"command": " ".join(cmd), "status": "skipped_non_interactive"}
                notes.append("Non-interactive session; skipping AuthNZ initializer prompt.")
        else:
            if yes:
                proc = subprocess.run(cmd, check=False)
                initializer_action = {"command": " ".join(cmd), "returncode": proc.returncode}
                if proc.returncode != 0:
                    notes.append("AuthNZ initializer failed; see output for details.")
            elif sys.stdin.isatty():
                if typer.confirm("Run AuthNZ initializer now?", default=False):
                    proc = subprocess.run(cmd, check=False)
                    initializer_action = {"command": " ".join(cmd), "returncode": proc.returncode}
                    if proc.returncode != 0:
                        notes.append("AuthNZ initializer failed; see output for details.")
                else:
                    initializer_action = {"command": "AuthNZ initializer", "status": "skipped"}
                    notes.append("Skipped AuthNZ initializer; run it later if needed.")
            else:
                notes.append("Non-interactive session; skipping AuthNZ initializer prompt.")
    env_result = env_utils.ensure_env(env_path, updates=updates, dry_run=dry_run)
    masked = env_utils.mask_env_values({k: v for k, v in updates.items() if v is not None})
    actions.append({"set_env": masked})
    if env_result.backup_path:
        actions.append({"backup": str(env_result.backup_path)})
    if validation:
        actions.append({"validate_database_url": validation})
    if initializer_action:
        actions.append({"authnz_initializer": initializer_action})
    result = {
        "command": "auth",
        "status": "ok",
        "mode": mode,
        "actions": actions,
        "dry_run": dry_run,
        "notes": notes,
        "paths": {"env": str(env_path)},
    }
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
