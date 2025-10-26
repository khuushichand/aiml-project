
"""Utilities to execute backend installation plans after the setup wizard."""

from __future__ import annotations

import contextlib
import shutil
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from configparser import ConfigParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from loguru import logger
from requests import exceptions as requests_exceptions

from tldw_Server_API.app.core.Setup import setup_manager
from tldw_Server_API.app.core.Setup.install_schema import DEFAULT_WHISPER_MODELS, InstallPlan
from tldw_Server_API.app.core.config import load_and_log_configs
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat

CONFIG_ROOT = setup_manager.CONFIG_RELATIVE_PATH.parent
STATUS_FILENAME = 'setup_install_status.json'


_LATEST_STATUS_DATA: Optional[Dict[str, Any]] = None
_INSTALLED_DEPENDENCIES: Set[str] = set()


def _candidate_status_dirs() -> List[Path]:
    candidates: List[Path] = []
    override = os.getenv('TLDW_INSTALL_STATE_DIR')
    if override:
        candidates.append(Path(override))
    candidates.append(CONFIG_ROOT)
    try:
        home = Path.home()
    except Exception:  # noqa: BLE001
        home = None
    if home:
        candidates.append(home / '.cache' / 'tldw_server')
    candidates.append(Path(tempfile.gettempdir()) / 'tldw_server')
    return candidates


def _resolve_status_file() -> Optional[Path]:
    """Return a writable path for persisting install status, or ``None`` if unavailable."""

    for root in _candidate_status_dirs():
        if not root:
            continue
        try:
            root.mkdir(parents=True, exist_ok=True)
            probe = root / '.write_test'
            with probe.open('w', encoding='utf-8') as handle:
                handle.write('ok')
            with contextlib.suppress(FileNotFoundError):
                probe.unlink()
            return root / STATUS_FILENAME
        except Exception:  # noqa: BLE001
            logger.debug('Install status directory %s not writable', root, exc_info=True)

    logger.warning('No writable location found for setup install status; running without persistence.')
    return None


def _install_dependencies(plan: InstallPlan, status: InstallationStatus, errors: List[str]) -> None:
    """Install required Python packages for selected backends."""

    processed_backends: Set[str] = set()

    for entry in plan.stt:
        key = f"stt:{entry.engine}"
        if key not in processed_backends:
            try:
                _install_backend_dependencies('stt', entry.engine, status, errors)
            except PipInstallBlockedError:
                pass
            processed_backends.add(key)

    for entry in plan.tts:
        key = f"tts:{entry.engine}"
        if key not in processed_backends:
            try:
                _install_backend_dependencies('tts', entry.engine, status, errors)
            except PipInstallBlockedError:
                pass
            processed_backends.add(key)

    if plan.embeddings.huggingface:
        try:
            _install_embedding_dependencies('huggingface', status, errors)
        except PipInstallBlockedError:
            pass
    if plan.embeddings.custom:
        try:
            _install_embedding_dependencies('custom', status, errors)
        except PipInstallBlockedError:
            pass
    if plan.embeddings.onnx:
        try:
            _install_embedding_dependencies('onnx', status, errors)
        except PipInstallBlockedError:
            pass


def _install_backend_dependencies(category: str, engine: str, status: InstallationStatus, errors: List[str]) -> None:
    requirements: List[PipRequirement] = []
    if category == 'stt':
        requirements = STT_DEPENDENCIES.get(engine, [])
    elif category == 'tts':
        requirements = TTS_DEPENDENCIES.get(engine, [])

    if not requirements:
        return

    step_name = f"deps:{category}:{engine}"
    status.step(step_name, 'in_progress')

    try:
        _install_requirement_list(requirements)
        status.step(step_name, 'completed')
    except PipInstallBlockedError as exc:
        status.step(step_name, 'skipped', str(exc))
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Dependency install failed for %s:%s", category, engine)
        status.step(step_name, 'failed', str(exc))
        errors.append(f"{engine} dependencies: {exc}")
        raise


def _install_embedding_dependencies(target: str, status: InstallationStatus, errors: List[str]) -> None:
    requirements = EMBEDDING_DEPENDENCIES.get(target)
    if not requirements:
        return

    step_name = f"deps:embeddings:{target}"
    status.step(step_name, 'in_progress')

    try:
        _install_requirement_list(requirements)
        status.step(step_name, 'completed')
    except PipInstallBlockedError as exc:
        status.step(step_name, 'skipped', str(exc))
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Dependency install failed for embeddings:%s", target)
        status.step(step_name, 'failed', str(exc))
        errors.append(f"embeddings:{target} deps: {exc}")
        raise


def _install_requirement_list(requirements: Iterable[PipRequirement]) -> None:
    for requirement in requirements:
        _ensure_requirement(requirement)


def _ensure_requirement(requirement: PipRequirement) -> None:
    package_name = _select_package(requirement)
    if not package_name:
        return

    platforms = requirement.platforms
    if platforms and sys.platform not in platforms:
        logger.info('Skipping %s due to platform restriction', package_name)
        return

    if package_name in _INSTALLED_DEPENDENCIES:
        logger.debug('Requirement %s already processed this session', package_name)
        return

    import_name = requirement.import_name
    if import_name and importlib.util.find_spec(import_name) is not None:
        logger.info('Dependency %s already available (import %s)', package_name, import_name)
        _INSTALLED_DEPENDENCIES.add(package_name)
        return

    if not _pip_allowed():
        raise PipInstallBlockedError('Package installs disabled via TLDW_SETUP_SKIP_PIP')

    logger.info('Installing dependency %s', package_name)
    # Prefer python -m pip when available; fall back to `uv pip` if pip isn't available
    def _pip_available() -> bool:
        try:
            probe = subprocess.run(
                [sys.executable, '-m', 'pip', '--version'],
                check=False,
                capture_output=True,
                text=True,
            )
            return probe.returncode == 0
        except Exception:
            return False

    def _pip_cmd(pkg: str) -> list[str]:
        cmd = [sys.executable, '-m', 'pip', 'install', '--upgrade', '--no-input', pkg]
        idx = os.getenv('TLDW_SETUP_PIP_INDEX_URL')
        if idx:
            cmd.extend(['--index-url', idx])
        return cmd

    def _uv_pip_cmd(pkg: str) -> list[str] | None:
        uv = shutil.which('uv')
        if not uv:
            return None
        cmd = [uv, 'pip', 'install', '--upgrade', pkg]
        idx = os.getenv('TLDW_SETUP_PIP_INDEX_URL')
        if idx:
            cmd.extend(['--index-url', idx])
        return cmd

    tried_commands: list[list[str]] = []
    if _pip_available():
        tried_commands.append(_pip_cmd(package_name))
        uv_cmd = _uv_pip_cmd(package_name)
        if uv_cmd:
            tried_commands.append(uv_cmd)
    else:
        uv_cmd = _uv_pip_cmd(package_name)
        if uv_cmd:
            tried_commands.append(uv_cmd)
        tried_commands.append(_pip_cmd(package_name))

    last_err: Exception | None = None
    for cmd in tried_commands:
        try:
            logger.info('Attempting installer: %s', ' '.join(cmd[:3]))
            _run_subprocess(cmd)
            last_err = None
            break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.warning('Installer command failed: %s', exc)
    if last_err is not None:
        raise last_err
    _INSTALLED_DEPENDENCIES.add(package_name)


def _select_package(requirement: PipRequirement) -> Optional[str]:
    package = requirement.package
    if requirement.gpu_package or requirement.cpu_package:
        if _cuda_available() and requirement.gpu_package:
            package = requirement.gpu_package
        elif requirement.cpu_package:
            package = requirement.cpu_package
    return package


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False

class InstallationStatus:
    """Persist installation progress to a status file."""

    def __init__(self, plan: InstallPlan) -> None:
        self.path = _resolve_status_file()
        self._persist_failed = False
        self.data: Dict[str, Any] = {
            'plan': model_dump_compat(plan),
            'status': 'in_progress',
            'started_at': _utc_now(),
            'completed_at': None,
            'steps': [],
            'errors': [],
        }
        self._save()

    def step(self, name: str, status: str, detail: Optional[str] = None) -> None:
        entry = {
            'name': name,
            'status': status,
            'detail': detail,
            'timestamp': _utc_now(),
        }
        self.data.setdefault('steps', []).append(entry)
        if status == 'failed' and detail:
            self.data.setdefault('errors', []).append(detail)
        self._save()

    def complete(self) -> None:
        self.data['status'] = 'completed'
        self.data['completed_at'] = _utc_now()
        self._save()

    def fail(self, message: str) -> None:
        self.data['status'] = 'failed'
        self.data['completed_at'] = _utc_now()
        self.data.setdefault('errors', []).append(message)
        self._save()

    def _save(self) -> None:
        if not self.path:
            return

        try:
            self.path.write_text(json.dumps(self.data, indent=2), encoding='utf-8')
        except Exception:  # noqa: BLE001
            if not self._persist_failed:
                logger.warning(
                    'Failed to persist setup install status to %s; continuing in-memory.',
                    self.path,
                    exc_info=True,
                )
            self._persist_failed = True
            self.path = None
        _record_latest_status(self.data)


class DownloadBlockedError(RuntimeError):
    """Raised when installer downloads are disabled or unavailable."""


def _downloads_allowed() -> bool:
    flag = os.getenv('TLDW_SETUP_SKIP_DOWNLOADS')
    if not flag:
        return True
    return flag.strip().lower() not in {'1', 'true', 'yes', 'y', 'on'}


def _ensure_downloads_allowed(target: str) -> None:
    if _downloads_allowed():
        return
    raise DownloadBlockedError(
        f'Downloads disabled via TLDW_SETUP_SKIP_DOWNLOADS; skipped {target}.',
    )


class PipInstallBlockedError(RuntimeError):
    """Raised when pip installation is disabled for the setup installer."""


def _pip_allowed() -> bool:
    flag = os.getenv('TLDW_SETUP_SKIP_PIP')
    if not flag:
        return True
    return flag.strip().lower() not in {'1', 'true', 'yes', 'y', 'on'}


def _record_latest_status(data: Dict[str, Any]) -> None:
    global _LATEST_STATUS_DATA
    _LATEST_STATUS_DATA = json.loads(json.dumps(data))


# --- HTTPX network error detection -------------------------------------------
def _is_httpx_network_error(exc: Exception) -> bool:
    """Return True if the exception is an httpx HTTP/network error.

    We import httpx lazily to avoid hard dependency at module import time
    (the package is typically installed via huggingface_hub).
    """
    try:
        import httpx  # type: ignore
    except Exception:  # noqa: BLE001
        return False
    return isinstance(exc, httpx.HTTPError)


def get_install_status_snapshot() -> Optional[Dict[str, Any]]:
    """Return the most recent install status if available."""

    for root in _candidate_status_dirs():
        path = root / STATUS_FILENAME if root else None
        if not path or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            _record_latest_status(data)
            return json.loads(json.dumps(data))
        except Exception:  # noqa: BLE001
            logger.exception('Failed to read install status from %s', path)

    if _LATEST_STATUS_DATA is not None:
        return json.loads(json.dumps(_LATEST_STATUS_DATA))

    return None

def _utc_now() -> str:
    return datetime.utcnow().isoformat() + 'Z'

def execute_install_plan(plan_payload: Dict[str, Any]) -> None:
    """Background entry point to execute an installation plan."""
    try:
        validate = getattr(InstallPlan, 'model_validate', None) or getattr(InstallPlan, 'parse_obj', None)
        if not validate:
            raise TypeError('No compatible Pydantic validation method found on InstallPlan')
        plan = validate(plan_payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Received invalid install plan")
        return

    if plan.is_empty():
        logger.info("Install plan empty; nothing to install.")
        return

    status = InstallationStatus(plan)
    errors: List[str] = []

    try:
        _install_dependencies(plan, status, errors)
        _install_stt(plan, status, errors)
        _install_tts(plan, status, errors)
        _install_embeddings(plan, status, errors)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Install plan execution failed")
        errors.append(str(exc))

    if errors:
        status.fail('; '.join(errors))
    else:
        status.complete()

def _install_stt(plan: InstallPlan, status: InstallationStatus, errors: List[str]) -> None:
    for entry in plan.stt:
        step_name = f"stt:{entry.engine}"
        status.step(step_name, 'in_progress')
        try:
            if entry.engine == 'faster_whisper':
                _install_faster_whisper(entry.models)
            elif entry.engine == 'qwen2_audio':
                _install_qwen2_audio()
            elif entry.engine == 'nemo_parakeet_standard':
                _install_nemo_parakeet('standard')
            elif entry.engine == 'nemo_parakeet_onnx':
                _install_nemo_parakeet('onnx')
            elif entry.engine == 'nemo_parakeet_mlx':
                _install_nemo_parakeet('mlx')
            elif entry.engine == 'nemo_canary':
                _install_nemo_canary()
            status.step(step_name, 'completed')
        except DownloadBlockedError as exc:
            logger.info('Skipping STT install %s: %s', entry.engine, exc)
            status.step(step_name, 'skipped', str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("STT install failed for %s", entry.engine)
            status.step(step_name, 'failed', str(exc))
            errors.append(f"{entry.engine}: {exc}")

def _install_tts(plan: InstallPlan, status: InstallationStatus, errors: List[str]) -> None:
    for entry in plan.tts:
        step_name = f"tts:{entry.engine}"
        status.step(step_name, 'in_progress')
        try:
            if entry.engine == 'kokoro':
                _install_kokoro(entry.variants)
            elif entry.engine == 'dia':
                _install_dia()
            elif entry.engine == 'higgs':
                _install_higgs()
            elif entry.engine == 'vibevoice':
                _install_vibevoice(entry.variants)
            status.step(step_name, 'completed')
        except DownloadBlockedError as exc:
            logger.info('Skipping TTS install %s: %s', entry.engine, exc)
            status.step(step_name, 'skipped', str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("TTS install failed for %s", entry.engine)
            status.step(step_name, 'failed', str(exc))
            errors.append(f"{entry.engine}: {exc}")

def _install_embeddings(plan: InstallPlan, status: InstallationStatus, errors: List[str]) -> None:
    if plan.embeddings.huggingface:
        step_name = 'embeddings:huggingface'
        status.step(step_name, 'in_progress')
        try:
            _download_huggingface_models(plan.embeddings.huggingface)
            status.step(step_name, 'completed')
        except DownloadBlockedError as exc:
            logger.info('Skipping Hugging Face embeddings download: %s', exc)
            status.step(step_name, 'skipped', str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to download huggingface embeddings")
            status.step(step_name, 'failed', str(exc))
            errors.append(f"embeddings:huggingface: {exc}")
    if plan.embeddings.custom:
        step_name = 'embeddings:custom'
        status.step(step_name, 'in_progress')
        try:
            _download_huggingface_models(plan.embeddings.custom)
            _append_trusted_embeddings(plan.embeddings.custom)
            status.step(step_name, 'completed')
        except DownloadBlockedError as exc:
            logger.info('Skipping custom embedding downloads: %s', exc)
            status.step(step_name, 'skipped', str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to process custom embedding models")
            status.step(step_name, 'failed', str(exc))
            errors.append(f"embeddings:custom: {exc}")

# --- Individual installers -------------------------------------------------

def _install_faster_whisper(models: List[str]) -> None:
    _ensure_downloads_allowed('faster-whisper checkpoints')
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib import WhisperModel
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError('faster-whisper not available. Ensure dependency is installed.') from exc

    for model_name in models or DEFAULT_WHISPER_MODELS:
        logger.info("Downloading faster-whisper checkpoint %s", model_name)
        try:
            instance = WhisperModel(model_name, device='cpu')
            del instance
        except Exception as exc:  # noqa: BLE001
            if _is_httpx_network_error(exc):
                raise DownloadBlockedError(f'Network unavailable while downloading {model_name}.') from exc
            raise


def _install_qwen2_audio() -> None:
    _ensure_downloads_allowed('Qwen2Audio model assets')
    try:
        import torch
        from transformers import AutoProcessor, Qwen2AudioForConditionalGeneration
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError('transformers (with Qwen2Audio) is required for Qwen installs.') from exc

    repo = 'Qwen/Qwen2-Audio-7B-Instruct'
    logger.info("Fetching Qwen2Audio assets from %s", repo)
    try:
        AutoProcessor.from_pretrained(repo)
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        Qwen2AudioForConditionalGeneration.from_pretrained(repo, torch_dtype=dtype, device_map='cpu')
    except Exception as exc:  # noqa: BLE001
        if _is_httpx_network_error(exc):
            raise DownloadBlockedError(f'Network unavailable while downloading {repo}.') from exc
        raise


def _install_nemo_parakeet(variant: str) -> None:
    _ensure_downloads_allowed(f'NeMo Parakeet {variant} weights')
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import load_parakeet_model
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError('nemo_toolkit is required for NeMo installations.') from exc

    logger.info("Loading NeMo Parakeet variant %s to trigger download", variant)
    model = load_parakeet_model(variant)
    if model is None:
        raise RuntimeError(f'Failed to load Parakeet variant {variant}; check nemo dependencies.')


def _install_nemo_canary() -> None:
    _ensure_downloads_allowed('NeMo Canary model')
    try:
        from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Nemo import load_canary_model
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError('nemo_toolkit is required for NeMo installations.') from exc

    logger.info('Loading NeMo Canary to trigger download')
    model = load_canary_model()
    if model is None:
        raise RuntimeError('Failed to load NeMo Canary model; verify nemo_toolkit installation.')


def _install_kokoro(variants: List[str]) -> None:
    targets = set(variants or ['onnx'])
    config = _load_config()
    model_path = Path(config.get('TTS-Settings', {}).get('kokoro_model_path', 'models/kokoro/kokoro-v0_19.onnx'))
    if model_path.is_dir():
        model_path = model_path / 'kokoro-v0_19.onnx'
    voices_path = Path(config.get('TTS-Settings', {}).get('kokoro_voices_json', model_path.with_name('voices.json')))

    if 'onnx' in targets:
        _download_hf_file('kokoro-82m', 'kokoro-v0_19.onnx', model_path)
    if 'voices' in targets:
        _download_hf_file('kokoro-82m', 'voices.json', voices_path)


def _install_dia() -> None:
    logger.info('Downloading Dia dialogue TTS model (nari-labs/dia)')
    _snapshot_repo('nari-labs/dia')


def _install_higgs() -> None:
    logger.info('Downloading Higgs Audio V2 model')
    _snapshot_repo('bosonai/higgs-audio-v2-generation-3B-base')
    _snapshot_repo('bosonai/higgs-audio-v2-tokenizer')


def _install_vibevoice(variants: List[str]) -> None:
    _ensure_downloads_allowed('VibeVoice assets')
    selected = set(variants or ['1.5B'])
    if '1.5B' in selected:
        _snapshot_repo('microsoft/VibeVoice-1.5B')
    if '7B' in selected:
        _snapshot_repo('WestZhang/VibeVoice-Large-pt')


def _download_huggingface_models(models: List[str]) -> None:
    for model_id in models:
        logger.info('Downloading embedding model %s', model_id)
        _snapshot_repo(model_id)


def _append_trusted_embeddings(models: List[str]) -> None:
    if not models:
        return

    parser = ConfigParser()
    config_path = setup_manager.get_config_file_path()
    parser.read(config_path)
    section = 'Embeddings'
    current = []
    if parser.has_option(section, 'trusted_hf_remote_code_models'):
        current = [value.strip() for value in parser.get(section, 'trusted_hf_remote_code_models').split(',') if value.strip()]
    merged = sorted(set(current + models), key=str.lower)
    setup_manager.update_config({section: {'trusted_hf_remote_code_models': ', '.join(merged)}})


def _load_config() -> Dict[str, Dict[str, Any]]:
    try:
        configs = load_and_log_configs()
        if isinstance(configs, dict):
            return configs
    except Exception:
        logger.debug('Falling back to empty config snapshot for installer metadata')
    return {}


def _download_hf_file(repo_id: str, filename: str, destination: Path) -> None:
    _ensure_downloads_allowed(f'{repo_id}/{filename}')
    try:
        from huggingface_hub import hf_hub_download
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError('huggingface_hub package is required for model downloads.') from exc

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(destination.parent),
            local_dir_use_symlinks=False,
        )
    except requests_exceptions.RequestException as exc:  # noqa: PERF203
        raise DownloadBlockedError(f'Network unavailable while downloading {repo_id}/{filename}.') from exc
    except Exception as exc:  # noqa: BLE001
        if _is_httpx_network_error(exc):
            raise DownloadBlockedError(f'Network unavailable while downloading {repo_id}/{filename}.') from exc
        raise


def _snapshot_repo(repo_id: str) -> None:
    _ensure_downloads_allowed(f'{repo_id} snapshot')
    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError('huggingface_hub package is required for model downloads.') from exc

    try:
        snapshot_download(repo_id=repo_id, local_dir_use_symlinks=False)
    except requests_exceptions.RequestException as exc:  # noqa: PERF203
        raise DownloadBlockedError(f'Network unavailable while downloading {repo_id}.') from exc
    except Exception as exc:  # noqa: BLE001
        if _is_httpx_network_error(exc):
            raise DownloadBlockedError(f'Network unavailable while downloading {repo_id}.') from exc
        raise


def _run_subprocess(command: List[str]) -> None:
    logger.info('Running command: %s', ' '.join(command))
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f'Command failed with exit code {result.returncode}')
    if result.stdout:
        logger.debug(result.stdout)
@dataclass(frozen=True)
class PipRequirement:
    package: str
    import_name: Optional[str] = None
    gpu_package: Optional[str] = None
    cpu_package: Optional[str] = None
    platforms: Optional[Set[str]] = None


# Dependency manifests keyed by backend type
STT_DEPENDENCIES: Dict[str, List[PipRequirement]] = {
    'faster_whisper': [
        PipRequirement(package='faster-whisper>=1.0.0', import_name='faster_whisper', cpu_package='faster-whisper>=1.0.0'),
    ],
    'qwen2_audio': [
        PipRequirement(package='torch>=2.2.0', import_name='torch'),
        PipRequirement(package='transformers>=4.41.0', import_name='transformers'),
        PipRequirement(package='accelerate>=0.28.0', import_name='accelerate'),
        PipRequirement(package='soundfile>=0.12.1', import_name='soundfile'),
        PipRequirement(package='sentencepiece>=0.1.99', import_name='sentencepiece'),
    ],
    'nemo_parakeet_standard': [
        PipRequirement(package='nemo_toolkit[asr]>=1.23.0', import_name='nemo'),
    ],
    'nemo_parakeet_onnx': [
        PipRequirement(package='onnxruntime>=1.16.0', gpu_package='onnxruntime-gpu>=1.16.0', import_name='onnxruntime'),
        PipRequirement(package='huggingface_hub>=0.23.0', import_name='huggingface_hub'),
        PipRequirement(package='soundfile>=0.12.1', import_name='soundfile'),
        PipRequirement(package='librosa>=0.10.0', import_name='librosa'),
        PipRequirement(package='numpy>=1.24.0', import_name='numpy'),
    ],
    'nemo_parakeet_mlx': [
        PipRequirement(package='mlx>=0.9.0', import_name='mlx', platforms={'darwin'}),
        PipRequirement(package='mlx-lm>=0.1.0', import_name='mlx_lm', platforms={'darwin'}),
    ],
    'nemo_canary': [
        PipRequirement(package='nemo_toolkit[asr]>=1.23.0', import_name='nemo'),
    ],
}

TTS_DEPENDENCIES: Dict[str, List[PipRequirement]] = {
    'kokoro': [
        PipRequirement(package='kokoro-onnx>=0.3.0', import_name='kokoro_onnx'),
        PipRequirement(package='onnxruntime>=1.16.0', gpu_package='onnxruntime-gpu>=1.16.0', import_name='onnxruntime'),
        PipRequirement(package='phonemizer>=3.2.1', import_name='phonemizer'),
        PipRequirement(package='espeak-phonemizer>=1.0.1', import_name='espeak_phonemizer'),
        PipRequirement(package='huggingface_hub>=0.23.0', import_name='huggingface_hub'),
    ],
    'dia': [
        PipRequirement(package='torch>=2.2.0', import_name='torch'),
        PipRequirement(package='transformers>=4.41.0', import_name='transformers'),
        PipRequirement(package='accelerate>=0.28.0', import_name='accelerate'),
        PipRequirement(package='safetensors>=0.4.0', import_name='safetensors'),
        PipRequirement(package='sentencepiece>=0.1.99', import_name='sentencepiece'),
        PipRequirement(package='soundfile>=0.12.1', import_name='soundfile'),
        PipRequirement(package='huggingface_hub>=0.23.0', import_name='huggingface_hub'),
    ],
    'higgs': [
        PipRequirement(package='git+https://github.com/boson-ai/higgs-audio.git', import_name='boson_multimodal'),
        PipRequirement(package='torch>=2.2.0', import_name='torch'),
        PipRequirement(package='torchaudio>=2.2.0', import_name='torchaudio'),
        PipRequirement(package='soundfile>=0.12.1', import_name='soundfile'),
        PipRequirement(package='huggingface_hub>=0.23.0', import_name='huggingface_hub'),
    ],
    'vibevoice': [
        PipRequirement(package='git+https://github.com/vibevoice-community/VibeVoice.git', import_name='vibevoice'),
        PipRequirement(package='torch>=2.2.0', import_name='torch'),
        PipRequirement(package='torchaudio>=2.2.0', import_name='torchaudio'),
        PipRequirement(package='sentencepiece>=0.1.99', import_name='sentencepiece'),
        PipRequirement(package='soundfile>=0.12.1', import_name='soundfile'),
        PipRequirement(package='huggingface_hub>=0.23.0', import_name='huggingface_hub'),
    ],
}

EMBEDDING_DEPENDENCIES: Dict[str, List[PipRequirement]] = {
    'huggingface': [
        PipRequirement(package='sentence-transformers>=2.6.0', import_name='sentence_transformers'),
        PipRequirement(package='torch>=2.2.0', import_name='torch'),
    ],
    'custom': [
        PipRequirement(package='sentence-transformers>=2.6.0', import_name='sentence_transformers'),
        PipRequirement(package='torch>=2.2.0', import_name='torch'),
    ],
    'onnx': [
        PipRequirement(package='onnxruntime>=1.16.0', gpu_package='onnxruntime-gpu>=1.16.0', import_name='onnxruntime'),
        PipRequirement(package='numpy>=1.24.0', import_name='numpy'),
    ],
}
