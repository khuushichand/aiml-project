"""Tests for the governor factory module."""
from __future__ import annotations

import importlib
import types
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_factory():
    """Import the factory module fresh."""
    from tldw_Server_API.app.core.Resource_Governance import governor_factory
    return governor_factory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateGovernorCallable:
    """Smoke test: the factory function exists and is callable."""

    def test_factory_is_callable(self):
        mod = _import_factory()
        assert callable(mod.create_governor)


class TestMemoryFallbackNoRedisUrl:
    """When no REDIS_URL is set, the factory must return a MemoryResourceGovernor."""

    def test_returns_memory_governor_when_no_url(self):
        from tldw_Server_API.app.core.Resource_Governance.governor import (
            MemoryResourceGovernor,
        )

        mod = _import_factory()
        with mock.patch.dict("os.environ", {}, clear=False):
            # Ensure REDIS_URL is absent
            env = dict(__import__("os").environ)
            env.pop("REDIS_URL", None)
            with mock.patch.dict("os.environ", env, clear=True):
                gov = mod.create_governor()

        assert isinstance(gov, MemoryResourceGovernor)

    def test_passes_policies_to_memory_governor(self):
        from tldw_Server_API.app.core.Resource_Governance.governor import (
            MemoryResourceGovernor,
        )

        mod = _import_factory()
        policies = {
            "test.policy": {"requests": {"rpm": 60, "burst": 1.0}}
        }
        with mock.patch.dict("os.environ", {}, clear=False):
            env = dict(__import__("os").environ)
            env.pop("REDIS_URL", None)
            with mock.patch.dict("os.environ", env, clear=True):
                gov = mod.create_governor(policies=policies)

        assert isinstance(gov, MemoryResourceGovernor)
        # The policy should be reachable via internal state
        assert gov._policies == policies


class TestMemoryFallbackRedisUnreachable:
    """When REDIS_URL is set but Redis is unreachable, fall back to memory."""

    def test_falls_back_on_connection_error(self):
        from tldw_Server_API.app.core.Resource_Governance.governor import (
            MemoryResourceGovernor,
        )

        mod = _import_factory()

        # Make redis.from_url(...).ping() raise ConnectionError
        fake_client = mock.MagicMock()
        fake_client.ping.side_effect = ConnectionError("refused")

        with mock.patch.dict(
            "os.environ", {"REDIS_URL": "redis://bad-host:6379"}, clear=False
        ):
            with mock.patch(
                "redis.from_url", return_value=fake_client
            ):
                gov = mod.create_governor()

        assert isinstance(gov, MemoryResourceGovernor)

    def test_falls_back_on_import_error(self):
        """If the redis package is not installed at all."""
        from tldw_Server_API.app.core.Resource_Governance.governor import (
            MemoryResourceGovernor,
        )

        mod = _import_factory()

        # Simulate ImportError when importing governor_redis
        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def _fake_import(name, *args, **kwargs):
            if "governor_redis" in name:
                raise ImportError("no redis")
            return original_import(name, *args, **kwargs)

        with mock.patch.dict(
            "os.environ", {"REDIS_URL": "redis://localhost:6379"}, clear=False
        ):
            with mock.patch("builtins.__import__", side_effect=_fake_import):
                gov = mod.create_governor()

        assert isinstance(gov, MemoryResourceGovernor)


class TestExplicitRedisUrlNone:
    """Passing redis_url=None explicitly should check env, then fall back."""

    def test_explicit_none_uses_env(self):
        from tldw_Server_API.app.core.Resource_Governance.governor import (
            MemoryResourceGovernor,
        )

        mod = _import_factory()
        env = dict(__import__("os").environ)
        env.pop("REDIS_URL", None)
        with mock.patch.dict("os.environ", env, clear=True):
            gov = mod.create_governor(redis_url=None)

        assert isinstance(gov, MemoryResourceGovernor)
