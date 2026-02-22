from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


def _embeddings_create_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "app"
        / "core"
        / "Embeddings"
        / "Embeddings_Server"
        / "Embeddings_Create.py"
    )


def test_embeddings_create_has_no_top_level_optimum_import() -> None:
    module_path = _embeddings_create_path()
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module_path))

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(
                    "optimum"
                ), "Embeddings_Create should not import optimum at module import time"
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not module_name.startswith(
                "optimum"
            ), "Embeddings_Create should not import optimum at module import time"


def test_embeddings_create_import_does_not_load_optimum_module() -> None:
    script = (
        "import sys\n"
        "import tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create as mod\n"
        "print('optimum.onnxruntime' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("False"), result.stdout
