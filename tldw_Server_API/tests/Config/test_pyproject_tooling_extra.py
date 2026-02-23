from pathlib import Path

try:
    import tomllib  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


def test_pyproject_has_tooling_optional_dependency_group():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    optional = data["project"]["optional-dependencies"]
    assert "tooling" in optional
    assert any(dep.startswith("requests") for dep in optional["tooling"])
