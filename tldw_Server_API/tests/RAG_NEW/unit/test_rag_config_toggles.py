import configparser
import os

import pytest

import tldw_Server_API.app.core.config as cfg


def _make_cfg(**rag):
    cp = configparser.ConfigParser()
    cp.add_section('RAG')
    for k, v in rag.items():
        cp.set('RAG', k, str(v))
    return cp


def test_env_overrides_config(monkeypatch):
    # Env should win over config.txt
    monkeypatch.delenv('RAG_ENABLE_STRUCTURE_INDEX', raising=False)
    monkeypatch.setenv('RAG_ENABLE_STRUCTURE_INDEX', '0')
    monkeypatch.setattr(cfg, 'load_comprehensive_config', lambda: _make_cfg(enable_structure_index='true'))
    assert cfg.rag_enable_structure_index(default=True) is False


def test_config_used_when_env_missing(monkeypatch):
    # No env -> use config value
    monkeypatch.delenv('RAG_STRICT_EXTRACTIVE', raising=False)
    monkeypatch.setattr(cfg, 'load_comprehensive_config', lambda: _make_cfg(strict_extractive='true'))
    assert cfg.rag_strict_extractive(default=False) is True


def test_low_confidence_behavior(monkeypatch):
    monkeypatch.delenv('RAG_LOW_CONFIDENCE_BEHAVIOR', raising=False)
    monkeypatch.setattr(cfg, 'load_comprehensive_config', lambda: _make_cfg(low_confidence_behavior='ask'))
    assert cfg.rag_low_confidence_behavior() == 'ask'
    # Invalid falls back
    monkeypatch.setattr(cfg, 'load_comprehensive_config', lambda: _make_cfg(low_confidence_behavior='weird'))
    assert cfg.rag_low_confidence_behavior() == 'continue'


def test_agentic_cache_backend_and_ttl(monkeypatch):
    monkeypatch.delenv('RAG_AGENTIC_CACHE_BACKEND', raising=False)
    monkeypatch.delenv('RAG_AGENTIC_CACHE_TTL_SEC', raising=False)
    monkeypatch.setattr(
        cfg,
        'load_comprehensive_config',
        lambda: _make_cfg(agentic_cache_backend='sqlite', agentic_cache_ttl_sec='123'),
    )
    assert cfg.rag_agentic_cache_backend() == 'sqlite'
    assert cfg.rag_agentic_cache_ttl_sec() == 123
    # Bad TTL returns default
    monkeypatch.setattr(cfg, 'load_comprehensive_config', lambda: _make_cfg(agentic_cache_ttl_sec='nan'))
    assert cfg.rag_agentic_cache_ttl_sec(default=42) == 42
