"""Local conftest for Characters tests.

Note: pytest >= 8 forbids defining `pytest_plugins` in non top-level
conftest files because it affects the entire suite.

If specific tests need fixtures from shared plugins, opt in directly in the
test module (for example via a module-level `pytest_plugins = [...]`).
"""
