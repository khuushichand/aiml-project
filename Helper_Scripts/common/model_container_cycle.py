from __future__ import annotations

import subprocess
import time


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _run(cmd: list[str], *, dry_run: bool, capture_output: bool = False) -> subprocess.CompletedProcess[str] | None:
    printable = " ".join(cmd)
    if dry_run:
        print(f"[dry-run] {printable}")
        return None

    try:
        return subprocess.run(
            cmd,
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required command not found: {cmd[0]}") from exc


def list_running_containers() -> list[str]:
    result = _run(
        ["docker", "ps", "--format", "{{.Names}}"],
        dry_run=False,
        capture_output=True,
    )
    assert result is not None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def stop_container(name: str, dry_run: bool = False) -> None:
    _run(["docker", "stop", name], dry_run=dry_run)


def start_container(name: str, boot_wait: float = 0.0, dry_run: bool = False) -> None:
    _run(["docker", "start", name], dry_run=dry_run)
    if boot_wait > 0:
        if dry_run:
            print(f"[dry-run] sleep {boot_wait}")
            return
        time.sleep(boot_wait)


def stop_all_except(excluded: list[str], dry_run: bool = False) -> None:
    excluded_set = set(excluded)
    for name in list_running_containers():
        if name not in excluded_set:
            stop_container(name, dry_run=dry_run)


def swap_containers(
    *,
    first_container: str,
    second_container: str,
    excluded: list[str] | None = None,
    first_boot_wait: float = 0.0,
    second_boot_wait: float = 0.0,
    dry_run: bool = False,
) -> None:
    excluded_list = excluded or []
    stop_all_except(excluded_list, dry_run=dry_run)
    start_container(first_container, boot_wait=first_boot_wait, dry_run=dry_run)
    stop_container(first_container, dry_run=dry_run)
    start_container(second_container, boot_wait=second_boot_wait, dry_run=dry_run)
