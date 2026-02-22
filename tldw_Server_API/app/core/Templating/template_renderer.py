from __future__ import annotations

import os
import re
import time
import threading
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from jinja2 import StrictUndefined, TemplateError, nodes
from jinja2.sandbox import SandboxedEnvironment
from loguru import logger

from tldw_Server_API.app.core.Metrics import increment_counter, observe_histogram
from tldw_Server_API.app.core.testing import is_truthy

try:  # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - fallback for older environments
    ZoneInfo = None  # type: ignore

_TEMPLATE_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    ImportError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    UnicodeDecodeError,
    ValueError,
    TemplateError,
)


# -----------------------------
# Dataclasses and Options
# -----------------------------


@dataclass
class TemplateEnv:
    timezone: str = "UTC"
    locale: str | None = None  # Reserved for future use (Babel)


@dataclass
class TemplateContext:
    user: Mapping[str, Any] | None = None
    chat: Mapping[str, Any] | None = None
    request_meta: Mapping[str, Any] | None = None
    env: TemplateEnv = field(default_factory=TemplateEnv)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class TemplateOptions:
    allow_random: bool = False
    allow_external_calls: bool = False
    max_output_chars: int = 2000
    timeout_ms: int = 250
    random_seed: int | None = None
    cache_max_entries: int = 256


import contextlib

from tldw_Server_API.app.core.config import load_comprehensive_config


def options_from_env() -> TemplateOptions:
    def _truthy(name: str, default: bool = False) -> bool:
        val = os.getenv(name)
        if val is None:
            return default
        return is_truthy(str(val))

    def _int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return int(str(raw))
        except (TypeError, ValueError):
            return default

    seed_env = os.getenv("TEMPLATES_RANDOM_SEED")
    seed = None
    try:
        if seed_env is not None and str(seed_env).strip() != "":
            seed = int(str(seed_env))
    except (TypeError, ValueError):
        seed = None

    # Fallback to config.txt when env not set
    cp = None
    try:
        cp = load_comprehensive_config()
    except _TEMPLATE_NONCRITICAL_EXCEPTIONS:
        cp = None

    def _cfg_bool(section: str, key: str, default: bool) -> bool:
        if cp and cp.has_section(section):
            try:
                raw = cp.get(section, key, fallback=str(default))
                return is_truthy(str(raw))
            except _TEMPLATE_NONCRITICAL_EXCEPTIONS:
                return default
        return default

    def _cfg_int(section: str, key: str, default: int) -> int:
        if cp and cp.has_section(section):
            try:
                return int(str(cp.get(section, key, fallback=str(default))))
            except _TEMPLATE_NONCRITICAL_EXCEPTIONS:
                return default
        return default

    return TemplateOptions(
        allow_random=_truthy("CHAT_DICT_TEMPLATES_ALLOW_RANDOM", _cfg_bool("Chat-Templating", "allow_random", False)),
        allow_external_calls=_truthy("TEMPLATES_ALLOW_EXTERNAL_CALLS", _cfg_bool("Chat-Templating", "allow_external_calls", False)),
        max_output_chars=_int("MAX_TEMPLATE_OUTPUT_CHARS", _cfg_int("Chat-Templating", "max_output_chars", 2000)),
        timeout_ms=_int("TEMPLATE_RENDER_TIMEOUT_MS", _cfg_int("Chat-Templating", "render_timeout_ms", 250)),
        random_seed=seed,
        cache_max_entries=_int("TEMPLATE_CACHE_MAX_ENTRIES", _cfg_int("Chat-Templating", "cache_max_entries", 256)),
    )


# -----------------------------
# Jinja Environment (Sandboxed)
# -----------------------------


def _build_env() -> SandboxedEnvironment:
    env = SandboxedEnvironment(autoescape=False, undefined=StrictUndefined)

    # Add minimal custom filter: slugify
    def _slugify(s: Any) -> str:
        t = str(s or "")
        t = t.strip().lower()
        t = re.sub(r"[^a-z0-9\-\_\s]+", "", t)
        t = re.sub(r"[\s\_]+", "-", t)
        t = re.sub(r"\-+", "-", t)
        return t.strip("-")

    env.filters["slugify"] = _slugify
    return env


_ENV = _build_env()


# -----------------------------
# Safe Helpers
# -----------------------------


def _tzinfo(tz_name: str | None) -> Any:
    if not tz_name:
        return timezone.utc
    if ZoneInfo is None:
        # Fallback: naive UTC when zoneinfo not available
        return timezone.utc
    try:
        return ZoneInfo(tz_name)
    except _TEMPLATE_NONCRITICAL_EXCEPTIONS:
        return timezone.utc


def _fn_now(fmt: str = "%Y-%m-%d", tz: str | None = None) -> str:
    tzinfo = _tzinfo(tz)
    return datetime.now(tz=tzinfo).strftime(fmt)


def _fn_today(fmt: str = "%Y-%m-%d") -> str:
    return date.today().strftime(fmt)


def _fn_iso_now(tz: str | None = None) -> str:
    tzinfo = _tzinfo(tz)
    return datetime.now(tz=tzinfo).isoformat()


def _sanitize_user(user_raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if not user_raw:
        return {}
    return {
        "id": user_raw.get("id"),
        "display_name": user_raw.get("display_name") or user_raw.get("name"),
    }


class _RandomFacade:
    def __init__(self, seed: int | None = None):
        import random as _random  # local import to avoid global state surprises

        self._random = _random.Random()
        if seed is not None:
            with contextlib.suppress(_TEMPLATE_NONCRITICAL_EXCEPTIONS):
                self._random.seed(seed)

    def randint(self, a: int, b: int) -> int:
        return self._random.randint(a, b)

    def choice(self, seq: Any) -> Any:
        # Convert Mapping/Set to list for determinism
        if isinstance(seq, dict):
            seq = list(seq.values())
        elif isinstance(seq, set):
            seq = list(seq)
        return self._random.choice(list(seq))


# -----------------------------
# AST Validation (Expression-only)
# -----------------------------


_DISALLOWED_NODE_TYPES = {
    nodes.For,
    nodes.If,
    nodes.Macro,
    nodes.Block,
    nodes.Import,
    nodes.FromImport,
    nodes.Include,
    nodes.Assign,
    nodes.AssignBlock,
    nodes.CallBlock,
    nodes.FilterBlock,
    nodes.Extends,
    nodes.With,
    nodes.ScopedEvalContextModifier,
}

_COMPILED_TEMPLATE_CACHE: OrderedDict[str, Any] = OrderedDict()
_COMPILED_TEMPLATE_CACHE_LOCK = threading.Lock()


def _get_compiled_template(template_src: str, max_entries: int) -> Any:
    """Return a compiled template using a bounded LRU cache keyed by source text."""
    if max_entries <= 0:
        return _ENV.from_string(template_src)

    with _COMPILED_TEMPLATE_CACHE_LOCK:
        cached = _COMPILED_TEMPLATE_CACHE.get(template_src)
        if cached is not None:
            _COMPILED_TEMPLATE_CACHE.move_to_end(template_src)
            return cached

    compiled = _ENV.from_string(template_src)
    with _COMPILED_TEMPLATE_CACHE_LOCK:
        _COMPILED_TEMPLATE_CACHE[template_src] = compiled
        _COMPILED_TEMPLATE_CACHE.move_to_end(template_src)
        while len(_COMPILED_TEMPLATE_CACHE) > max_entries:
            _COMPILED_TEMPLATE_CACHE.popitem(last=False)
    return compiled


def _clear_template_cache() -> None:
    """Test helper to clear compiled template cache."""
    with _COMPILED_TEMPLATE_CACHE_LOCK:
        _COMPILED_TEMPLATE_CACHE.clear()


def _validate_expression_only(template_src: str) -> None:
    # Block statements/tags are intentionally unsupported for this feature.
    if "{%" in template_src:
        raise ValueError("Forbidden construct in template: BlockTag")

    ast = _ENV.parse(template_src)

    def _walk(n: nodes.Node) -> None:
        if isinstance(n, tuple(_DISALLOWED_NODE_TYPES)):
            raise ValueError(f"Forbidden construct in template: {type(n).__name__}")
        for child in n.iter_child_nodes():
            _walk(child)

    _walk(ast)


# -----------------------------
# Render Entry Point
# -----------------------------


class TemplateRenderError(Exception):
    pass


def render(text: str, ctx: TemplateContext, options: TemplateOptions | None = None) -> str:
    """Render `text` with a sandboxed environment and strict guards.

    On any error or guard violation, logs and returns the original `text`.
    """
    if not isinstance(text, str) or text == "":
        return text

    opts = options or options_from_env()

    # Determine metrics source
    metrics_source = "unknown"
    try:
        metrics_source = str((ctx.extra or {}).get("_metrics_source", "unknown"))
    except _TEMPLATE_NONCRITICAL_EXCEPTIONS:
        metrics_source = "unknown"

    # Validate expression-only template
    try:
        _validate_expression_only(text)
    except _TEMPLATE_NONCRITICAL_EXCEPTIONS as e:
        logger.debug(f"template_parse_error/expression_only: {e}")
        with contextlib.suppress(_TEMPLATE_NONCRITICAL_EXCEPTIONS):
            increment_counter("template_render_failure_total", labels={"source": metrics_source, "reason": "parse"})
        return text

    # Build helper functions and variables exposed to the template
    # Functions are provided via the render context so they can be gated per-call.
    helpers: dict[str, Any] = {
        "now": _fn_now,
        "today": _fn_today,
        "iso_now": _fn_iso_now,
        "now_tz": lambda fmt="%Y-%m-%d", tz="UTC": _fn_now(fmt=fmt, tz=tz),
        # Built-in string helpers also exist as Jinja filters, but provide callables too
        "upper": lambda s: str(s).upper(),
        "lower": lambda s: str(s).lower(),
        "title": lambda s: str(s).title(),
    }

    # Random helpers gated
    if opts.allow_random:
        rnd = _RandomFacade(seed=opts.random_seed)
        helpers.update({
            "randint": rnd.randint,
            "choice": rnd.choice,
        })

    # Optional user() callable returns a sanitized view
    safe_user = _sanitize_user(ctx.user)
    helpers["user"] = (lambda _u=safe_user: lambda: dict(_u))()

    # Collect variables for rendering
    render_vars: dict[str, Any] = {}
    render_vars.update(helpers)

    # Provide a minimal env block
    render_vars["env"] = {"timezone": ctx.env.timezone, "locale": ctx.env.locale}

    # Expose extra variables directly
    if ctx.extra:
        for k, v in ctx.extra.items():
            # Avoid clobbering helper names
            if k not in render_vars:
                render_vars[k] = v

    # Perform render with guardrails
    start = time.monotonic()
    try:
        tmpl = _get_compiled_template(text, int(opts.cache_max_entries))
        output = tmpl.render(render_vars)
    except _TEMPLATE_NONCRITICAL_EXCEPTIONS as e:
        logger.debug(f"template_render_failure: {e}")
        with contextlib.suppress(_TEMPLATE_NONCRITICAL_EXCEPTIONS):
            increment_counter("template_render_failure_total", labels={"source": metrics_source, "reason": "exception"})
        return text
    finally:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if elapsed_ms > opts.timeout_ms:
            logger.debug(
                f"template_render_timeout: elapsed_ms={elapsed_ms} > timeout_ms={opts.timeout_ms}"
            )
            with contextlib.suppress(_TEMPLATE_NONCRITICAL_EXCEPTIONS):
                increment_counter("template_render_timeout_total", labels={"source": metrics_source})
        with contextlib.suppress(_TEMPLATE_NONCRITICAL_EXCEPTIONS):
            observe_histogram("template_render_duration_seconds", value=float(elapsed_ms) / 1000.0, labels={"source": metrics_source})

    if not isinstance(output, str):
        try:
            output = str(output)
        except _TEMPLATE_NONCRITICAL_EXCEPTIONS:
            return text

    if len(output) > opts.max_output_chars:
        logger.debug(
            f"template_output_too_large: size={len(output)} cap={opts.max_output_chars}"
        )
        with contextlib.suppress(_TEMPLATE_NONCRITICAL_EXCEPTIONS):
            increment_counter("template_output_truncated_total", labels={"source": metrics_source})
        return output[: opts.max_output_chars]

    with contextlib.suppress(_TEMPLATE_NONCRITICAL_EXCEPTIONS):
        increment_counter("template_render_success_total", labels={"source": metrics_source})
    return output
