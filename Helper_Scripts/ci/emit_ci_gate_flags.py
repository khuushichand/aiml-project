from __future__ import annotations

import os
import sys
from typing import Iterable

from Helper_Scripts.ci.path_classifier import classify_paths


def emit(paths: Iterable[str]) -> None:
    flags = classify_paths(paths)
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        raise RuntimeError("GITHUB_OUTPUT is required")

    with open(output_path, "a", encoding="utf-8") as output_file:
        for key, value in flags.items():
            output_file.write(f"{key}={'true' if value else 'false'}\n")


def main() -> None:
    emit(sys.argv[1:])


if __name__ == "__main__":
    main()
