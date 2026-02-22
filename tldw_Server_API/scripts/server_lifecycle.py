"""
Thin wrapper that delegates to the test utility at
`tldw_Server_API/tests/scripts/server_lifecycle.py` so CI workflows can
invoke a stable path: `python tldw_Server_API/scripts/server_lifecycle.py ...`.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    # Compute the path to the real implementation
    here = Path(__file__).resolve()
    impl = here.parent.parent / "tests" / "scripts" / "server_lifecycle.py"
    if not impl.exists():
        raise SystemExit(f"Server lifecycle script not found at {impl}")

    # Emulate running the target script as __main__ so its argparse works
    # Preserve argv (command, args) for the target
    sys.argv = sys.argv[:]  # pass through
    runpy.run_path(str(impl), run_name="__main__")


if __name__ == "__main__":
    main()

