#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow direct script execution from the repo root via `python Helper_Scripts/...`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Helper_Scripts.common.model_container_cycle import parse_csv, swap_containers


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Cycle Docker model containers for low-VRAM workflows: "
            "stop all non-excluded containers, start first model, stop it, then start second model."
        )
    )
    parser.add_argument("--first-container", required=True, help="Container to start first.")
    parser.add_argument("--second-container", required=True, help="Container to start second.")
    parser.add_argument(
        "--excluded",
        default="",
        help="Comma-separated container names to keep running while cycling.",
    )
    parser.add_argument(
        "--first-boot-wait",
        type=float,
        default=0.0,
        help="Seconds to wait after starting the first container.",
    )
    parser.add_argument(
        "--second-boot-wait",
        type=float,
        default=0.0,
        help="Seconds to wait after starting the second container.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print Docker commands without executing them.",
    )
    args = parser.parse_args()

    swap_containers(
        first_container=args.first_container,
        second_container=args.second_container,
        excluded=parse_csv(args.excluded),
        first_boot_wait=args.first_boot_wait,
        second_boot_wait=args.second_boot_wait,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
