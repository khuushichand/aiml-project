import json
from pathlib import Path
from types import SimpleNamespace
from typing import List

import numpy as np
import pytest


@pytest.mark.unit
def test_load_terms_text_and_json(tmp_path, monkeypatch):
    mod = __import__(
        'tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Custom_Vocabulary',
        fromlist=['*']
    )

    # Configure module to look at our temp files
    terms_txt = tmp_path / 'terms.txt'
    terms_txt.write_text("Acme\nPhasor\nAcme\nXJ-12\n", encoding='utf-8')
    terms_json = tmp_path / 'terms.json'
    terms_json.write_text(json.dumps(["Alpha", "Beta", "Alpha"]), encoding='utf-8')

    cfg = {
        'STT-Settings': {
            'custom_vocab_terms_file': str(terms_txt),
            'custom_vocab_replacements_file': '',
        }
    }
    monkeypatch.setattr(mod, 'loaded_config_data', cfg, raising=False)

    terms = mod.load_terms()
    assert terms[:3] == ["Acme", "Phasor", "XJ-12"]
    assert len(terms) == 3  # dedup keeps order

    # Switch to JSON list format
    cfg['STT-Settings']['custom_vocab_terms_file'] = str(terms_json)
    terms2 = mod.load_terms()
    assert terms2[:2] == ["Alpha", "Beta"]


@pytest.mark.unit
def test_load_replacements_json_and_text(tmp_path, monkeypatch):
    mod = __import__(
        'tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Custom_Vocabulary',
        fromlist=['*']
    )

    rep_json = tmp_path / 'repl.json'
    rep_json.write_text(json.dumps({"mispell": "misspell", "XJ12": "XJ-12"}), encoding='utf-8')
    rep_txt = tmp_path / 'repl.txt'
    rep_txt.write_text("colour=color\nIOT,IoT\n", encoding='utf-8')

    cfg = {'STT-Settings': {'custom_vocab_replacements_file': str(rep_json)}}
    monkeypatch.setattr(mod, 'loaded_config_data', cfg, raising=False)
    r1 = mod.load_replacements()
    assert r1["mispell"] == "misspell"
    assert r1["XJ12"] == "XJ-12"

    cfg['STT-Settings']['custom_vocab_replacements_file'] = str(rep_txt)
    r2 = mod.load_replacements()
    assert r2["colour"] == "color"
    assert r2["IOT"] == "IoT"


@pytest.mark.unit
def test_build_initial_prompt_and_toggle(tmp_path, monkeypatch):
    mod = __import__(
        'tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Custom_Vocabulary',
        fromlist=['*']
    )

    terms_txt = tmp_path / 'terms.txt'
    terms_txt.write_text("Acme\nXJ-12\n", encoding='utf-8')
    cfg = {
        'STT-Settings': {
            'custom_vocab_terms_file': str(terms_txt),
            'custom_vocab_initial_prompt_enable': 'True',
            'custom_vocab_prompt_template': 'Domain terms: {terms}.',
        }
    }
    monkeypatch.setattr(mod, 'loaded_config_data', cfg, raising=False)

    prompt = mod.build_initial_prompt()
    assert prompt == 'Domain terms: Acme, XJ-12.'

    # Disable and expect None
    cfg['STT-Settings']['custom_vocab_initial_prompt_enable'] = 'False'
    prompt2 = mod.build_initial_prompt()
    assert prompt2 is None


@pytest.mark.unit
def test_apply_replacements_case_and_word_boundaries(monkeypatch):
    mod = __import__(
        'tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Custom_Vocabulary',
        fromlist=['*']
    )
    cfg = {
        'STT-Settings': {
            'custom_vocab_postprocess_enable': 'True',
            'custom_vocab_case_sensitive': 'False',
        }
    }
    monkeypatch.setattr(mod, 'loaded_config_data', cfg, raising=False)

    # Monkeypatch file loaders to avoid filesystem
    monkeypatch.setattr(mod, 'load_replacements', lambda: {"IOT": "IoT", "color": "colour"})

    text = "The new IOT device improves color accuracy."
    out = mod.apply_replacements(text)
    assert out == "The new IoT device improves colour accuracy."

    # Case-sensitive: IOT should not change
    cfg['STT-Settings']['custom_vocab_case_sensitive'] = 'True'
    out2 = mod.apply_replacements(text)
    assert out2 == "The new IOT device improves colour accuracy."


@pytest.mark.unit
def test_whisper_streaming_initial_prompt_injection(monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
        WhisperStreamingTranscriber, UnifiedStreamingConfig,
    )

    # Fake model to avoid heavy deps
    class FakeModel:
        def transcribe(self, path: str, **opts):
            return [], SimpleNamespace(language='en', language_probability=1.0)

    # Patch get_whisper_model to return fake model
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Streaming_Unified as s
    monkeypatch.setattr(s, 'get_whisper_model', lambda size, device: FakeModel())

    # Force CUDA off path
    import builtins
    try:
        import torch
        monkeypatch.setattr(torch, 'cuda', SimpleNamespace(is_available=lambda: False), raising=True)
    except Exception:
        pass

    # Initial prompt provider
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Custom_Vocabulary as cv
    monkeypatch.setattr(cv, 'initial_prompt_if_enabled', lambda: 'Domain terms: Acme, XJ-12.', raising=False)

    transcriber = WhisperStreamingTranscriber(UnifiedStreamingConfig())
    transcriber.initialize()
    assert 'initial_prompt' in transcriber.transcribe_options
    assert transcriber.transcribe_options['initial_prompt'] == 'Domain terms: Acme, XJ-12.'


@pytest.mark.unit
def test_whisper_streaming_postprocess_applied(monkeypatch):
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Streaming_Unified import (
        WhisperStreamingTranscriber, UnifiedStreamingConfig,
    )

    class FakeSeg:
        def __init__(self, text: str):
            self.text = text

    class FakeModel:
        def transcribe(self, path: str, **opts):
            segs = [FakeSeg("this is a mispell"), FakeSeg("and IOT sensor")]  # note mispell + IOT
            info = SimpleNamespace(language='en', language_probability=0.99)
            return segs, info

    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Streaming_Unified as s
    monkeypatch.setattr(s, 'get_whisper_model', lambda size, device: FakeModel())

    # Replacements
    from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio import Audio_Custom_Vocabulary as cv
    monkeypatch.setattr(cv, 'postprocess_text_if_enabled', lambda t: t.replace('mispell', 'misspell').replace('IOT', 'IoT'))

    transcriber = WhisperStreamingTranscriber(UnifiedStreamingConfig())
    transcriber.initialize()
    out = transcriber._transcribe_audio(np.zeros(1600, dtype=np.float32))
    assert 'misspell' in out
    assert 'IoT' in out
