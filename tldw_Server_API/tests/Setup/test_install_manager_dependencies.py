import importlib.util
import json
import os
import tempfile

import pytest

from tldw_Server_API.app.core.Setup import install_manager


@pytest.fixture(autouse=True)
def reset_dependency_cache():
    install_manager._INSTALLED_DEPENDENCIES.clear()  # noqa: SLF001
    yield
    install_manager._INSTALLED_DEPENDENCIES.clear()  # noqa: SLF001


def _read_status(path: str):
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def test_dependencies_skipped_when_pip_disabled(monkeypatch):
    plan = {
        'stt': [{'engine': 'faster_whisper', 'models': ['small']}],
        'tts': [],
        'embeddings': {'huggingface': [], 'custom': [], 'onnx': []},
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv('TLDW_INSTALL_STATE_DIR', tmpdir)
        monkeypatch.setenv('TLDW_SETUP_SKIP_PIP', '1')
        monkeypatch.setenv('TLDW_SETUP_SKIP_DOWNLOADS', '1')

        executed = []

        def fake_subprocess(cmd, check=False, capture_output=True, text=True):  # noqa: ARG001
            executed.append(cmd)
            return

        monkeypatch.setattr(install_manager, '_run_subprocess', fake_subprocess)

        install_manager.execute_install_plan(plan)

        status_path = os.path.join(tmpdir, install_manager.STATUS_FILENAME)
        payload = _read_status(status_path)
        step_names = {entry['name']: entry['status'] for entry in payload['steps']}

        assert step_names.get('deps:stt:faster_whisper') in {'skipped', 'completed'}
        assert not executed, "Subprocess should not run when pip is disabled"


def test_dependencies_trigger_pip_install(monkeypatch):
    plan = {
        'stt': [{'engine': 'faster_whisper', 'models': ['small']}],
        'tts': [],
        'embeddings': {'huggingface': [], 'custom': [], 'onnx': []},
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv('TLDW_INSTALL_STATE_DIR', tmpdir)
        monkeypatch.delenv('TLDW_SETUP_SKIP_PIP', raising=False)
        monkeypatch.setenv('TLDW_SETUP_SKIP_DOWNLOADS', '1')

        commands = []

        original_find_spec = importlib.util.find_spec

        def fake_find_spec(name):
            if name == 'faster_whisper':
                return None
            return original_find_spec(name)

        monkeypatch.setattr(importlib.util, 'find_spec', fake_find_spec)

        def fake_subprocess(cmd, check=False, capture_output=True, text=True):  # noqa: ARG001
            commands.append(cmd)
            return

        monkeypatch.setattr(install_manager, '_run_subprocess', fake_subprocess)

        install_manager.execute_install_plan(plan)

        assert commands, "Expected pip install command to execute"
        pip_cmd = commands[0]
        assert pip_cmd[:4] == [install_manager.sys.executable, '-m', 'pip', 'install']
        assert any('faster-whisper' in part for part in pip_cmd)
