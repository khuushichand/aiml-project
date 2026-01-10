from __future__ import annotations

from datetime import datetime, timezone

import os

from tldw_Server_API.app.core.Templating.template_renderer import (
    TemplateContext,
    TemplateEnv,
    TemplateOptions,
    render,
)


def test_basic_now_renders_year():


    ctx = TemplateContext(env=TemplateEnv(timezone="UTC"))
    out = render("Today is {{ now('%Y', tz='UTC') }}", ctx)
    assert str(datetime.now(timezone.utc).year) in out


def test_strict_undefined_fallbacks_to_original():


     # Unknown name should not raise; renderer returns original text
    ctx = TemplateContext()
    tpl = "Hello {{ unknown_variable }}"
    out = render(tpl, ctx)
    assert out == tpl


def test_random_gated_off_fallbacks():


     # When random is not allowed, randint is undefined and render should fallback
    ctx = TemplateContext()
    tpl = "Roll: {{ randint(1, 6) }}"
    opts = TemplateOptions(allow_random=False)
    out = render(tpl, ctx, opts)
    assert out == tpl


def test_random_allowed_is_deterministic_with_seed():


    ctx = TemplateContext()
    tpl = "Roll: {{ randint(1, 6) }}"
    opts = TemplateOptions(allow_random=True, random_seed=123)
    out1 = render(tpl, ctx, opts)
    out2 = render(tpl, ctx, opts)
    assert out1 == out2
    assert out1.startswith("Roll: ")


def test_max_output_cap_truncates():


    big = "x" * 3000
    ctx = TemplateContext(extra={"big": big})
    opts = TemplateOptions(max_output_chars=2000)
    out = render("{{ big }}", ctx, opts)
    assert len(out) == 2000
    assert out == "x" * 2000
