import ast
from pathlib import Path


def test_user_db_handling_mode_helper_defined_once() -> None:
    module_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "core"
        / "AuthNZ"
        / "User_DB_Handling.py"
    )
    module_ast = ast.parse(module_path.read_text(encoding="utf-8"))
    helper_defs = [
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name == "is_single_user_mode"
    ]
    assert len(helper_defs) == 1  # nosec B101
