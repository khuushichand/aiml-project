"""Guardrail test to prevent stdlib-style `%s` logger placeholders."""

import ast
from pathlib import Path
import re


LOG_LEVEL_METHODS = {"trace", "debug", "info", "warning", "error", "critical", "success", "exception"}
PERCENT_PLACEHOLDER_PATTERN = re.compile(r"%(?:\([^)]+\))?[#0\- +]?\d*(?:\.\d+)?[a-zA-Z]")


def test_loguru_calls_use_brace_style_placeholders():
    app_root = Path(__file__).resolve().parents[2] / "app"
    violations: list[str] = []

    for file_path in app_root.rglob("*.py"):
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        rel = file_path.relative_to(app_root.parent)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in LOG_LEVEL_METHODS:
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "logger":
                continue
            if not node.args:
                continue

            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                if PERCENT_PLACEHOLDER_PATTERN.search(first_arg.value):
                    violations.append(f"{rel}:{node.lineno}: {first_arg.value!r}")

    assert not violations, (
        "Found stdlib-style logger placeholders in Loguru calls. "
        "Use '{}' placeholders instead.\n" + "\n".join(violations[:50])
    )
