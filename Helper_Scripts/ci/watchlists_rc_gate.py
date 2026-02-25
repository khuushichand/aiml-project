"""Run Watchlists release-candidate quality gates and emit go/no-go summary."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import sys
# Required to execute fixed local CI gate commands.
import subprocess  # nosec B404
import time
from pathlib import Path
from typing import Any


WATCHLISTS_RC_GATES: list[dict[str, str]] = [
    {"id": "help", "command": "bun run test:watchlists:help"},
    {"id": "onboarding", "command": "bun run test:watchlists:onboarding"},
    {"id": "uc2", "command": "bun run test:watchlists:uc2"},
    {"id": "a11y", "command": "bun run test:watchlists:a11y"},
    {"id": "scale", "command": "bun run test:watchlists:scale"},
]


def _build_run_url_from_env() -> str:
    explicit_url = os.environ.get("GITHUB_RUN_URL")
    if explicit_url:
        return explicit_url

    server_url = os.environ.get("GITHUB_SERVER_URL", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    if server_url and repository and run_id:
        return f"{server_url}/{repository}/actions/runs/{run_id}"

    return "n/a"


def collect_metadata() -> dict[str, str]:
    return {
        "ref": os.environ.get("GITHUB_REF", "local"),
        "sha": os.environ.get("GITHUB_SHA", "local"),
        "run_url": _build_run_url_from_env(),
        "generated_at_utc": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
    }


def run_gate_command(*, command: str, working_directory: Path) -> dict[str, Any]:
    started = time.perf_counter()
    argv = shlex.split(command)
    process = subprocess.run(
        argv,
        cwd=str(working_directory),
        text=True,
        capture_output=True,
        check=False,
    )  # nosec B603
    duration_seconds = time.perf_counter() - started
    return {
        "status": "passed" if process.returncode == 0 else "failed",
        "returncode": process.returncode,
        "duration_seconds": duration_seconds,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def execute_all_gates(*, gates: list[dict[str, str]], working_directory: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for gate in gates:
        gate_result = run_gate_command(command=gate["command"], working_directory=working_directory)
        results.append(
            {
                "id": gate["id"],
                "command": gate["command"],
                "status": gate_result["status"],
                "returncode": gate_result["returncode"],
                "duration_seconds": float(gate_result["duration_seconds"]),
                "stdout": gate_result["stdout"],
                "stderr": gate_result["stderr"],
            }
        )
    return results


def determine_decision(results: list[dict[str, Any]]) -> str:
    if all(result.get("status") == "passed" for result in results):
        return "GO"
    return "NO-GO"


def build_summary_markdown(
    *, results: list[dict[str, Any]], metadata: dict[str, str], decision: str
) -> str:
    lines: list[str] = []
    lines.append("## Watchlists RC Gate Summary")
    lines.append("")
    lines.append(f"- Ref: `{metadata.get('ref', 'n/a')}`")
    lines.append(f"- SHA: `{metadata.get('sha', 'n/a')}`")
    lines.append(f"- Run URL: {metadata.get('run_url', 'n/a')}")
    lines.append(f"- Generated (UTC): `{metadata.get('generated_at_utc', 'n/a')}`")
    lines.append("")
    lines.append("| Gate | Status | Duration |")
    lines.append("|---|---|---|")
    for result in results:
        duration = float(result.get("duration_seconds", 0.0))
        lines.append(f"| {result.get('id', 'unknown')} | {result.get('status', 'unknown')} | {duration:.2f}s |")
    lines.append("")
    lines.append(f"### Decision: {decision}")
    if decision == "NO-GO":
        lines.append("")
        lines.append("At least one Watchlists gate failed. Inspect failed gate logs before promoting this RC.")
    return "\n".join(lines) + "\n"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Watchlists RC gates and produce go/no-go summary output.")
    parser.add_argument(
        "--summary-output",
        default=str(Path("tmp") / "watchlists_rc_gate_summary.md"),
        help="Path to write markdown summary output.",
    )
    parser.add_argument(
        "--json-output",
        default=str(Path("tmp") / "watchlists_rc_gate_results.json"),
        help="Path to write JSON gate results output.",
    )
    parser.add_argument(
        "--working-directory",
        default=str(Path("apps") / "packages" / "ui"),
        help="Directory where watchlists gate commands will run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    working_directory = Path(args.working_directory)
    summary_output = Path(args.summary_output)
    json_output = Path(args.json_output)

    results = execute_all_gates(gates=WATCHLISTS_RC_GATES, working_directory=working_directory)
    decision = determine_decision(results)
    metadata = collect_metadata()
    summary = build_summary_markdown(results=results, metadata=metadata, decision=decision)

    summary_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(summary, encoding="utf-8")
    json_output.write_text(
        json.dumps({"metadata": metadata, "decision": decision, "results": results}, indent=2),
        encoding="utf-8",
    )

    return 0 if decision == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
