"""Local conftest for Characters tests.

Note: pytest >= 8 forbids defining `pytest_plugins` in non top-level
conftest files because it affects the entire suite. Plugins are now
loaded globally via `pyproject.toml` under `[tool.pytest.ini_options].plugins`.

If you need fixtures from shared plugins here, simply use them in tests;
they are already available without re-registering `pytest_plugins` locally.
"""
