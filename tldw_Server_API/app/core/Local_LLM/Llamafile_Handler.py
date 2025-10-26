# Llamafile_Handler.py
#
# Imports
import os
import platform
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
#
# Third-party imports
import asyncio
import httpx
import socket
import time
#
# Local imports
from tldw_Server_API.app.core.Local_LLM.LLM_Base_Handler import BaseLLMHandler
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions import ModelDownloadError, ServerError, \
    ModelNotFoundError, InferenceError
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Schemas import LlamafileConfig
from tldw_Server_API.app.core.Utils.Utils import download_file, verify_checksum
from tldw_Server_API.app.core.Local_LLM import http_utils


def redact_cmd_args(*args, **kwargs):
    """Proxy command redaction for easier monkeypatching in tests."""
    return http_utils.redact_cmd_args(*args, **kwargs)


def create_async_client(*args, **kwargs):
    """Proxy AsyncClient factory to respect patched targets."""
    return http_utils.create_async_client(*args, **kwargs)


async def request_json(*args, **kwargs):
    """Proxy JSON request helper."""
    return await http_utils.request_json(*args, **kwargs)


async def wait_for_http_ready(*args, **kwargs):
    """Proxy readiness poller preserving test expectations."""
    return await http_utils.wait_for_http_ready(*args, **kwargs)
# from .base_handler import BaseLLMHandler
# from .exceptions import ModelNotFoundError, ModelDownloadError, ServerError, InferenceError
# from .utils_loader import logging, project_utils # From the loader
# from .config_model import LlamafileConfig
#
########################################################################################################################
#
# Functions:


class LlamafileHandler(BaseLLMHandler):
    def __init__(self, config: LlamafileConfig, global_app_config: Dict[str, Any]):
        super().__init__(config, global_app_config)
        self.config: LlamafileConfig  # For type hinting

        self.llamafile_exe_path = self.config.llamafile_dir / ("llamafile.exe" if os.name == "nt" else "llamafile")
        self.models_dir = Path(self.config.models_dir)

        self.config.llamafile_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # Corrected type hint for asyncio.subprocess.Process
        self._active_servers: Dict[int, asyncio.subprocess.Process] = {}

        # Apply environment overrides
        def _env_bool(name: str):
            v = os.getenv(name)
            if v is None:
                return None
            return str(v).strip().lower() in {"1", "true", "yes", "on"}

        def _env_int(name: str):
            v = os.getenv(name)
            if v is None:
                return None
            try:
                return int(v)
            except ValueError:
                return None

        def _env_paths(name: str):
            v = os.getenv(name)
            if not v:
                return None
            parts = [p.strip() for p in v.split(",") if p.strip()]
            return [Path(p) for p in parts]

        b = _env_bool("LOCAL_LLM_ALLOW_CLI_SECRETS")
        if b is not None:
            self.config.allow_cli_secrets = b
        b = _env_bool("LOCAL_LLM_PORT_AUTOSELECT")
        if b is not None:
            self.config.port_autoselect = b
        i = _env_int("LOCAL_LLM_PORT_PROBE_MAX")
        if i is not None:
            self.config.port_probe_max = i
        paths = _env_paths("LOCAL_LLM_ALLOWED_PATHS")
        if paths is not None:
            self.config.allowed_paths = paths

        self._setup_signal_handlers()  # For cleaning up on exit
        self.metrics = {"starts": 0, "stops": 0, "start_errors": 0, "readiness_time_sum": 0.0, "readiness_count": 0}

    def get_metrics(self) -> Dict[str, Any]:
        return dict(self.metrics)

    def _is_port_free(self, host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return True
            except OSError:
                return False

    def _pick_port(self, host: str, start_port: int) -> int:
        if not getattr(self.config, "port_autoselect", True):
            return start_port
        max_probe = int(getattr(self.config, "port_probe_max", 10) or 0)
        for i in range(max_probe + 1):
            cand = start_port + i
            if self._is_port_free(host, cand):
                return cand
        return start_port

    def _denylist_check(self, args: Dict[str, Any]):
        if not getattr(self.config, "allow_cli_secrets", False):
            bad = [k for k in args.keys() if k in {"hf_token", "token"}]
            if bad:
                raise ServerError(f"Refusing secret flags {bad}. Use env (e.g., HF_TOKEN) or enable allow_cli_secrets.")

    def _is_path_allowed(self, p: Path) -> bool:
        try: pr = p.resolve()
        except Exception: return False
        bases = [self.models_dir.resolve()]
        extra = getattr(self.config, "allowed_paths", None) or []
        try:
            bases.extend([Path(x).resolve() for x in extra])
        except Exception:
            pass
        return any(str(pr).startswith(str(base)) for base in bases)

    # --- Llamafile Executable Management ---
    async def download_latest_llamafile_executable(self, force_download: bool = False) -> Path:
        """Downloads the latest llamafile binary if not present or if force_download is True."""
        output_path = self.llamafile_exe_path
        self.logger.info(f"Checking for llamafile executable at {output_path}...")
        if output_path.exists() and not force_download:
            self.logger.debug(f"{output_path.name} already exists. Skipping download.")
            await asyncio.to_thread(os.chmod, output_path, 0o755)  # Ensure executable
            return output_path

        repo = "Mozilla-Ocho/llamafile"
        asset_name_prefix = "llamafile-"  # This needs to be accurate based on current releases
        latest_release_url = f"https://api.github.com/repos/{repo}/releases/latest"

        from tldw_Server_API.app.core.Local_LLM.http_utils import request_json, async_stream_download

        async with create_async_client(timeout=60.0) as client:  # Increased timeout for fetching release info
            try:
                self.logger.debug(f"Fetching latest release info from {latest_release_url}")
                latest_release_data = await request_json(client, "GET", latest_release_url)
                tag_name = latest_release_data['tag_name']
                self.logger.debug(f"Latest release tag: {tag_name}")

                assets = latest_release_data.get('assets', [])
                asset_url = None
                chosen_asset_name = None

                # Prioritize assets that are just "llamafile" or "llamafile-<version>"
                # As the universal executable is often simply named.
                simple_llamafile_asset = None
                for asset in assets:
                    if asset['name'] == "llamafile" or asset['name'].startswith(f"llamafile-{tag_name}") or asset[
                        'name'].startswith(f"{asset_name_prefix}{tag_name.lstrip('v')}"):
                        # Check if it's an executable type or no extension (common for Linux/macOS executables)
                        if '.' not in asset['name'].split('-')[-1] or asset['name'].endswith(
                                ('.exe', '.zip')) == False:  # Heuristic for executable
                            simple_llamafile_asset = asset
                            break

                if simple_llamafile_asset:
                    asset_url = simple_llamafile_asset['browser_download_url']
                    chosen_asset_name = simple_llamafile_asset['name']
                else:  # Fallback to previous broader search if specific one isn't found
                    preferred_assets = []
                    for asset in assets:
                        # More general check if the specific name isn't found
                        if asset['name'].startswith(asset_name_prefix) and "debug" not in asset['name'].lower():
                            preferred_assets.append(asset)

                    if not preferred_assets:
                        for asset in assets:  # Broader fallback if prefix fails
                            if tag_name in asset['name'] and 'llamafile' in asset['name'].lower() and "debug" not in \
                                    asset['name'].lower():
                                preferred_assets.append(asset)

                    if preferred_assets:
                        # Simplistic choice: take the first one. Might need refinement.
                        asset_to_download = preferred_assets[0]
                        # Prefer smaller, non-source files if multiple matches
                        preferred_assets.sort(key=lambda x: x.get('size', float('inf')))
                        for pa in preferred_assets:
                            if 'src' not in pa['name'].lower() and 'source' not in pa['name'].lower():
                                asset_to_download = pa
                                break
                        asset_url = asset_to_download['browser_download_url']
                        chosen_asset_name = asset_to_download['name']

                if not asset_url:
                    self.logger.error(
                        f"No suitable llamafile asset found in release {tag_name}. Assets: {[a['name'] for a in assets]}")
                    raise ModelDownloadError(f"No suitable llamafile asset found for tag {tag_name}.")

                self.logger.info(
                    f"Found asset: {chosen_asset_name}. Downloading Llamafile from {asset_url} to {output_path}...")

                # Ensure the target directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Streaming download with retries
                await async_stream_download(asset_url, str(output_path))
                await asyncio.to_thread(os.chmod, output_path, 0o755)
                self.logger.info(f"Downloaded {output_path.name} successfully.")
                return output_path

            except httpx.HTTPStatusError as e:
                self.logger.error(
                    f"Failed to fetch llamafile release info/download: {e.response.status_code} - {e.response.text}",
                    exc_info=True)
                raise ModelDownloadError(f"Failed to fetch/download llamafile: {e.response.status_code}")
            except Exception as e:
                self.logger.error(f"Unexpected error downloading llamafile: {e}", exc_info=True)
                if output_path.exists():
                    output_path.unlink(missing_ok=True)
                raise ModelDownloadError(f"Unexpected error downloading llamafile: {e}")

    # --- Model Management ---
    async def download_model_file(self, model_name: str, model_url: str, model_filename: Optional[str] = None,
                                  expected_hash: Optional[str] = None, force_download: bool = False) -> Path:
        """Downloads the specified LLM model file (.llamafile or .gguf)."""
        filename = model_filename or model_url.split('/')[-1].split('?')[0]
        model_path = self.models_dir / filename

        self.logger.info(f"Checking availability of model: {model_name} at {model_path}")
        if model_path.exists() and not force_download:
            if expected_hash:
                # project_utils.verify_checksum needs to be a real function
                is_valid = await asyncio.to_thread(verify_checksum, str(model_path), expected_hash)
                if not is_valid:
                    self.logger.warning(f"Checksum mismatch for existing model {model_path}. Re-downloading.")
                    model_path.unlink()
                else:
                    self.logger.debug(f"Model '{model_name}' ({filename}) already exists and checksum verified.")
                    return model_path
            else:
                self.logger.debug(
                    f"Model '{model_name}' ({filename}) already exists. Skipping download (no hash check).")
                return model_path

        self.models_dir.mkdir(parents=True, exist_ok=True)  # Ensure models dir exists
        self.logger.info(f"Downloading model: {model_name} from {model_url} to {model_path}")
        try:
            from tldw_Server_API.app.core.Local_LLM.http_utils import async_stream_download
            await async_stream_download(model_url, str(model_path))
            if expected_hash:
                is_valid = await asyncio.to_thread(verify_checksum, str(model_path), expected_hash)
                if not is_valid:
                    model_path.unlink(missing_ok=True)
                    raise ModelDownloadError("Checksum verification failed for downloaded model.")
            self.logger.info(f"Downloaded model '{model_name}' ({filename}) successfully.")
            return model_path
        except Exception as e:
            self.logger.error(f"Failed to download model {model_name}: {e}", exc_info=True)
            if model_path.exists(): model_path.unlink(missing_ok=True)
            raise ModelDownloadError(f"Failed to download model {model_name}: {e}")

    async def list_models(self) -> List[str]:
        if not self.models_dir.exists():
            return []

        def _scan_dir():
            files = []
            for ext in ("*.gguf", "*.llamafile"):
                files.extend(self.models_dir.glob(ext))
            return [f.name for f in files]

        return await asyncio.to_thread(_scan_dir)

    async def is_model_available(self, model_filename: str) -> bool:
        return (self.models_dir / model_filename).is_file()  # Check if it's a file

    # --- Server Management ---
    async def start_server(self, model_filename: str, server_args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        llamafile_exe = await self.download_latest_llamafile_executable()
        if not llamafile_exe or not llamafile_exe.exists():
            raise ServerError("Llamafile executable not found or could not be downloaded.")

        model_path = self.models_dir / model_filename
        if not model_path.exists():
            raise ModelNotFoundError(f"Model file {model_filename} not found in {self.models_dir}.")

        args = server_args or {}
        host = args.get("host", self.config.default_host)
        if not host:
            host = self.config.default_host or "127.0.0.1"
        host = str(host)
        port = self._pick_port(host, int(args.get("port", self.config.default_port)))

        # Corrected check using .returncode for asyncio.subprocess.Process
        if port in self._active_servers and self._active_servers[port].returncode is None:
            active_pid = self._active_servers[port].pid
            self.logger.warning(
                f"Llamafile server already managed on port {port} with PID {active_pid}.")
            return {"status": "already_managed", "pid": active_pid, "port": port, "host": host,
                    "model": model_filename}

        # Allowlist of supported args
        allowed_formatters: Dict[str, Any] = {
            "port": lambda v: ["--port", str(int(v))],
            "host": lambda v: ["--host", str(v)],
            "threads": lambda v: ["-t", str(int(v))],
            "threads_batch": lambda v: ["-tb", str(int(v))],
            "ctx_size": lambda v: ["-c", str(int(v))],
            "c": lambda v: ["-c", str(int(v))],
            "ngl": lambda v: ["-ngl", str(int(v))],
            "gpu_layers": lambda v: ["-ngl", str(int(v))],
            "batch_size": lambda v: ["-b", str(int(v))],
            "b": lambda v: ["-b", str(int(v))],
            "verbose": lambda v: (["-v"] if v else []),
            "api_key": lambda v: (["--api-key", str(v)] if v else []),
            # Boolean toggles
            "log_disable": lambda v: (["--log-disable"] if v else []),
            "memory_f32": lambda v: (["--memory-f32"] if v else []),
            "numa": lambda v: (["--numa"] if v else []),
            "sane_defaults": lambda v: (["--sane-defaults"] if v else []),
            # Extended safe flags commonly supported by llama.cpp-compatible CLIs
            "no_mmap": lambda v: (["--no-mmap"] if v else []),
            "mlock": lambda v: (["--mlock"] if v else []),
            "main_gpu": lambda v: ["--main-gpu", str(int(v))],
            "tensor_split": lambda v: ["--tensor-split", ",".join(map(str, v))] if isinstance(v, (list, tuple)) else ["--tensor-split", str(v)],
            "rope_freq_base": lambda v: ["--rope-freq-base", str(float(v))],
            "rope_freq_scale": lambda v: ["--rope-freq-scale", str(float(v))],
            # Parity with llama.cpp handler
            "main_kv": lambda v: ["--main-kv", str(int(v))],
            "no_kv_offload": lambda v: (["--no-kv-offload"] if v else []),
            "rope_scaling": lambda v: ["--rope-scaling", str(v)],
            "flash_attn": lambda v: (["--flash-attn"] if v else []),
            "cont_batching": lambda v: (["--cont-batching"] if v else []),
            "lora": lambda v: sum((["--lora", str(x)] for x in (v if isinstance(v, (list, tuple)) else [v])), []),
            "lora_base": lambda v: ["--lora-base", str(v)],
            "cache_type_k": lambda v: ["--cache-type-k", str(v)],
            "cache_type_v": lambda v: ["--cache-type-v", str(v)],
            "hf_token": lambda v: ["--hf-token", str(v)],
            "token": lambda v: ["--token", str(v)],
            # Paths
            "grammar_file": lambda v: ["--grammar-file", str(v)],
            "json_schema_file": lambda v: ["--json-schema-file", str(v)],
            "chat_template_file": lambda v: ["--chat-template-file", str(v)],
            "prompt_cache": lambda v: ["--prompt-cache", str(v)],
            "log_file": lambda v: ["--log-file", str(v)],
        }

        self._denylist_check(args)
        command = [str(llamafile_exe), "-m", str(model_path)]
        command += ["--port", str(port)]
        if host:
            command += ["--host", host]

        # Validate keys
        invalid = [k for k in args.keys() if k not in allowed_formatters]
        if invalid and not getattr(self.config, "allow_unvalidated_args", False):
            raise ServerError(f"Unsupported llamafile server args: {sorted(invalid)}")

        # Apply allowlisted flags (skip ones already included explicitly)
        for k, v in args.items():
            if k in ("port", "host"):
                continue
            if k in allowed_formatters:
                if k in {"grammar_file", "json_schema_file", "chat_template_file", "prompt_cache", "log_file", "lora_base"}:
                    if not self._is_path_allowed(Path(v)):
                        raise ServerError(f"File path for '{k}' must be under allowed directories.")
                if k == "lora":
                    vals = v if isinstance(v, (list, tuple)) else [v]
                    for item in vals:
                        if not self._is_path_allowed(Path(item)):
                            raise ServerError("LoRA path must be under allowed directories.")
                command += allowed_formatters[k](v)
            elif getattr(self.config, "allow_unvalidated_args", False):
                flag = f"--{k.replace('_', '-')}"
                if v is True:
                    command.append(flag)
                elif v is False or v is None:
                    pass
                else:
                    command += [flag, str(v)]

        redacted_cmd = redact_cmd_args(command)
        self.logger.info(f"Starting llamafile server for {model_filename} with command: {' '.join(redacted_cmd)}")

        try:
            # Using create_subprocess_exec for better security with list of args
            cpe_kwargs = {"stdout": asyncio.subprocess.PIPE, "stderr": asyncio.subprocess.PIPE}
            if platform.system() != "Windows":
                cpe_kwargs["preexec_fn"] = os.setsid
            else:
                cpe_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            t0 = time.perf_counter()
            process = await asyncio.create_subprocess_exec(*command, **cpe_kwargs)
            # Poll HTTP readiness instead of fixed sleep
            base_url = f"http://{host}:{port}"
            is_ready = await wait_for_http_ready(base_url, timeout_total=30.0, interval=0.5)

            if process.returncode is not None or not is_ready:
                stderr_output = ""
                if process.stderr:
                    err_bytes = await process.stderr.read()
                    stderr_output = err_bytes.decode(errors='ignore').strip()
                self.logger.error(
                    f"Llamafile server failed to start or become ready for {model_filename}. Exit code: {process.returncode}. Stderr: {stderr_output}")
                stdout_output = ""
                if process.stdout:
                    out_bytes = await process.stdout.read()
                    stdout_output = out_bytes.decode(errors='ignore').strip()
                if stdout_output: self.logger.error(f"Llamafile server stdout: {stdout_output}")
                self.metrics["start_errors"] += 1
                raise ServerError(f"Llamafile server failed to start. Stderr: {stderr_output}")

            self._active_servers[port] = process
            t1 = time.perf_counter()
            self.metrics["starts"] += 1
            self.metrics["readiness_time_sum"] += max(0.0, t1 - t0)
            self.metrics["readiness_count"] += 1
            self.logger.info(f"Llamafile server started for {model_filename} on port {port} with PID {process.pid}.")
            return {"status": "started", "pid": process.pid, "port": port, "host": host, "model": model_filename,
                    "command": ' '.join(redacted_cmd)}  # Return redacted command
        except Exception as e:
            self.logger.error(f"Exception starting llamafile server for {model_filename}: {e}", exc_info=True)
            raise ServerError(f"Exception starting llamafile: {e}")

    async def stop_server(self, port: Optional[int] = None, pid: Optional[int] = None) -> str:
        process_to_stop: Optional[asyncio.subprocess.Process] = None
        port_to_clear = None

        if pid:
            for p, proc_obj in self._active_servers.items():
                if proc_obj.pid == pid:
                    process_to_stop = proc_obj
                    port_to_clear = p
                    break
            if not process_to_stop:
                self.logger.warning(
                    f"PID {pid} not in managed servers. Attempting to terminate externally (best effort).")
                try:
                    # This part is synchronous and for unmanaged processes
                    target_pid = int(pid)
                    if platform.system() == "Windows":
                        subprocess.run(['taskkill', '/F', '/PID', str(target_pid)], check=True, capture_output=True)
                    else:
                        os.kill(target_pid, signal.SIGTERM)  # Can use os.killpg if it was started in a group
                    return f"Attempted to send SIGTERM to unmanaged llamafile server with PID {pid}."
                except ProcessLookupError:
                    return f"No process found with PID {pid}."
                except subprocess.CalledProcessError as e_taskkill:
                    self.logger.error(f"taskkill failed for PID {pid}: {e_taskkill.stderr.decode()}")
                    return f"Failed to stop unmanaged PID {pid} with taskkill."
                except Exception as e:
                    self.logger.error(f"Error stopping unmanaged PID {pid}: {e}", exc_info=True)
                    raise ServerError(f"Error stopping unmanaged PID {pid}: {e}")
        elif port:
            if port in self._active_servers:
                process_to_stop = self._active_servers[port]
                port_to_clear = port
            else:
                return f"No managed llamafile server found on port {port}."
        else:
            return "Please provide a port or PID to stop a llamafile server."

        if not process_to_stop:
            return "No server matching criteria to stop."

        current_pid = process_to_stop.pid
        self.logger.info(f"Stopping llamafile server (PID: {current_pid}, Port: {port_to_clear or 'N/A'}).")
        try:
            # Check if still running using returncode
            if process_to_stop.returncode is None:
                if platform.system() == "Windows":
                    process_to_stop.terminate()
                else:
                    try:
                        # Get process group ID (pgid) to terminate the entire group
                        pgid = await asyncio.to_thread(os.getpgid, current_pid)
                        await asyncio.to_thread(os.killpg, pgid, signal.SIGTERM)
                        self.logger.info(f"Sent SIGTERM to process group {pgid} (leader PID: {current_pid}).")
                    except ProcessLookupError:  # Process might have died just now
                        self.logger.warning(
                            f"Process {current_pid} not found during getpgid, likely already terminated.")
                        # Fallback to terminating just the PID if getpgid fails for other reasons
                        process_to_stop.terminate()
                        self.logger.info(f"Sent SIGTERM to process PID {current_pid} (fallback).")

                try:
                    await asyncio.wait_for(process_to_stop.wait(), timeout=10)
                    self.logger.info(
                        f"Llamafile server PID {current_pid} terminated gracefully (return code: {process_to_stop.returncode}).")
                except asyncio.TimeoutError:
                    self.logger.warning(
                        f"Llamafile server PID {current_pid} did not terminate gracefully after SIGTERM. Killing.")
                    if platform.system() == "Windows":
                        process_to_stop.kill()
                    else:
                        try:
                            pgid = await asyncio.to_thread(os.getpgid, current_pid)
                            await asyncio.to_thread(os.killpg, pgid, signal.SIGKILL)
                            self.logger.info(f"Sent SIGKILL to process group {pgid} (leader PID: {current_pid}).")
                        except ProcessLookupError:
                            self.logger.warning(f"Process {current_pid} not found during getpgid for SIGKILL.")
                            process_to_stop.kill()  # Fallback
                            self.logger.info(f"Sent SIGKILL to process PID {current_pid} (fallback).")

                    await process_to_stop.wait()  # Ensure it's reaped
                    self.logger.info(
                        f"Llamafile server PID {current_pid} killed (return code: {process_to_stop.returncode}).")
            else:
                self.logger.info(
                    f"Llamafile server PID {current_pid} was already stopped (return code: {process_to_stop.returncode}).")

            if port_to_clear and port_to_clear in self._active_servers:
                del self._active_servers[port_to_clear]
            return f"Llamafile server PID {current_pid} stopped."
        except Exception as e:
            self.logger.error(f"Error stopping llamafile server PID {current_pid}: {e}", exc_info=True)
            if port_to_clear and port_to_clear in self._active_servers:
                del self._active_servers[port_to_clear]
            raise ServerError(f"Error stopping llamafile server: {e}")

    async def inference(self,
                        prompt: str,
                        port: int,
                        host: Optional[str] = None,
                        system_prompt: Optional[str] = None,
                        n_predict: int = -1,
                        temperature: float = 0.8,
                        top_k: int = 40,
                        top_p: float = 0.95,
                        api_key: Optional[str] = None,
                        **kwargs) -> Dict[str, Any]:
        target_host = host or self.config.default_host
        api_url = f"http://{target_host}:{port}/v1/chat/completions"

        if port not in self._active_servers or self._active_servers[port].returncode is not None:
            self.logger.debug(
                f"Port {port} not in _active_servers or process terminated. Checking for external server responsiveness.")
            conn_made = False
            try:
                _, writer = await asyncio.open_connection(target_host, port)
                writer.close()
                await writer.wait_closed()
                conn_made = True
                self.logger.debug(f"Successfully connected to {target_host}:{port}. Assuming external server.")
            except ConnectionRefusedError:
                self.logger.error(
                    f"No managed llamafile server on port {port} (or it terminated), and connection refused to {target_host}:{port}.")
                raise ServerError(f"Llamafile server not found or not responding on {target_host}:{port}.")
            except Exception as e:
                self.logger.error(f"Error checking connection to {target_host}:{port}: {e}", exc_info=True)
                raise ServerError(f"Error connecting to Llamafile server at {target_host}:{port}: {e}")
            if not conn_made:
                raise ServerError(f"Llamafile server not found/responding on {target_host}:{port} (conn test failed).")
        else:
            self.logger.debug(f"Using managed llamafile server on port {port}.")

        headers = {"Content-Type": "application/json"}
        if api_key: headers["Authorization"] = f"Bearer {api_key}"

        messages = []
        if system_prompt: messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages, "temperature": temperature, "top_k": top_k, "top_p": top_p,
            "n_predict": n_predict, "stream": False, **kwargs
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        self.logger.debug(f"Sending llamafile inference request to {api_url} with payload: {payload}")
        async with create_async_client(timeout=kwargs.get("timeout", 120.0)) as client:
            try:
                result = await request_json(client, "POST", api_url, json=payload, headers=headers)
                self.logger.debug("Llamafile inference successful.")
                return result
            except httpx.HTTPStatusError as e:
                error_text = e.response.text
                self.logger.error("Llamafile API error ({}) from {}: {}", e.response.status_code, api_url, error_text,
                                  exc_info=True)
                raise InferenceError(f"Llamafile API error ({e.response.status_code}): {error_text}")
            except httpx.RequestError as e:
                self.logger.error("Could not connect or communicate with Llamafile server at {}: {}", api_url, e,
                                  exc_info=True)
                raise ServerError(f"Could not connect/communicate with Llamafile server at {api_url}: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error during llamafile inference to {api_url}: {e}", exc_info=True)
                raise InferenceError(f"Unexpected error during llamafile inference: {e}")

    def _cleanup_all_managed_servers_sync(self):  # Renamed to indicate it's synchronous
        """Synchronous cleanup for signal handlers or app shutdown."""
        self.logger.info("Cleaning up all managed llamafile servers (sync)...")
        ports_to_remove = list(self._active_servers.keys())
        for port in ports_to_remove:
            proc = self._active_servers.get(port)
            # Check if proc exists and if its returncode is None (meaning it might be running)
            if proc and proc.returncode is None:
                pid = proc.pid
                self.logger.info(f"Stopping server on port {port}, PID {pid}...")
                try:
                    if platform.system() == "Windows":
                        proc.terminate()
                    else:
                        # For processes started with os.setsid, kill the process group
                        try:
                            pgid = os.getpgid(pid)
                            os.killpg(pgid, signal.SIGTERM)
                            self.logger.info(f"Sent SIGTERM to process group {pgid} (leader PID {pid}).")
                        except ProcessLookupError:
                            self.logger.warning(
                                f"Process {pid} (or group) not found during SIGTERM, likely already terminated.")
                            # Fallback just in case, or if it wasn't started with setsid somehow
                            proc.terminate()

                    # proc.wait() is a coroutine, cannot be called directly in sync func
                    # For a sync cleanup, we might need to use a different approach or
                    # acknowledge that immediate reaping might not happen here.
                    # A simple approach for atexit: send terminate and hope for the best.
                    # More robust would be to launch a small async task to await termination.
                    # For now, just send terminate/kill.
                    try:
                        # Python's subprocess module Popen has a wait() method, but asyncio.Process does not have a sync one.
                        # We are in a sync function (_cleanup_all_managed_servers_sync)
                        # We can't `await proc.wait()`.
                        # The OS will eventually reap, but for cleaner shutdown logging:
                        self.logger.debug(f"Termination signal sent to PID {pid}. OS will handle reaping.")
                    except Exception as e_wait:  # Catch any error from trying to wait
                        self.logger.warning(f"Error during proc.wait() for PID {pid} in sync cleanup: {e_wait}")


                except ProcessLookupError:  # If process died between check and action
                    self.logger.warning(f"Process {pid} not found during termination, likely already exited.")
                except Exception as e:
                    self.logger.error(f"Error during cleanup of PID {pid}: {e}. Attempting kill.")
                    if proc.returncode is None:  # Check again before kill
                        if platform.system() == "Windows":
                            proc.kill()
                        else:
                            try:
                                pgid = os.getpgid(pid)
                                os.killpg(pgid, signal.SIGKILL)
                            except Exception as e_kill:
                                self.logger.debug(f"os.killpg failed for PID {pid} (pgid may be absent): error={e_kill}; falling back to proc.kill()")
                                proc.kill()  # fallback
            if port in self._active_servers:
                del self._active_servers[port]
        self.logger.info("Managed llamafile server synchronous cleanup attempt complete.")

    def _signal_handler(self, sig, frame):
        self.logger.info(f'Signal handler called with signal: {sig}')
        self._cleanup_all_managed_servers_sync()
        sys.exit(0)

    def _setup_signal_handlers(self):
        import atexit
        atexit.register(self._cleanup_all_managed_servers_sync)
        self.logger.info("Registered atexit synchronous cleanup for LlamafileHandler.")
        # Signal handling can be tricky with asyncio and web servers.
        # Relying on atexit for this synchronous cleanup part is simpler for now.
        # For FastAPI, its own startup/shutdown events are better for managing async resources.

#
# # End of Llamafile_Handler.py
#########################################################################################################################
