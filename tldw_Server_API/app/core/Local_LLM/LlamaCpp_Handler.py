# /tldw_Server_API/app/core/Local_LLM/LlamaCpp_Handler.py
# Description: Handler for Llama.cpp models, managing server processes and inference.
#
import asyncio
import socket
import time
import os
import platform
import signal
import subprocess  # For synchronous fallback if needed
from pathlib import Path
from typing import List, Optional, Dict, Any
#
# Third-party imports
import httpx  # For making API calls to the Llama.cpp server
# from loguru import logger # Assuming you have a global logger or pass one
#
# Local imports
from .LLM_Base_Handler import BaseLLMHandler
from .LLM_Inference_Exceptions import ModelNotFoundError, ServerError, InferenceError
from .LLM_Inference_Schemas import LlamaCppConfig
from tldw_Server_API.app.core.Local_LLM import http_utils


def create_async_client(*args, **kwargs):
    """Proxy create_async_client so tests can monkeypatch either module."""
    return http_utils.create_async_client(*args, **kwargs)


async def request_json(*args, **kwargs):
    """Proxy request_json for test monkeypatching."""
    return await http_utils.request_json(*args, **kwargs)


async def wait_for_http_ready(*args, **kwargs):
    """Proxy wait_for_http_ready preserving signature expectations."""
    return await http_utils.wait_for_http_ready(*args, **kwargs)
# from .Utils import download_file, verify_checksum # If you need model downloading later
#########################################################################################################################
#
# Functions:

class LlamaCppHandler(BaseLLMHandler):
    def __init__(self, config: LlamaCppConfig, global_app_config: Dict[str, Any]):
        super().__init__(config, global_app_config)
        self.config: LlamaCppConfig  # For type hinting
        # self.logger = logger # Or use self.logger from BaseLLMHandler if already set

        self.models_dir = Path(self.config.models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        # For Llama.cpp, we usually manage one server instance that can have its model swapped.
        # If you need multiple concurrent Llama.cpp servers, this would be a Dict like in LlamafileHandler
        self._active_server_process: Optional[asyncio.subprocess.Process] = None
        self._active_server_model: Optional[str] = None
        self._active_server_port: Optional[int] = None
        self._active_server_host: Optional[str] = None
        self._active_server_log_handle = None

        # Apply environment overrides for handler config
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
        # Lightweight metrics
        self.metrics = {
            "starts": 0,
            "stops": 0,
            "start_errors": 0,
            "readiness_time_sum": 0.0,
            "readiness_count": 0,
            "inference_count": 0,
            "inference_error_count": 0,
            "inference_time_sum": 0.0,
        }

    def get_metrics(self) -> Dict[str, Any]:
        return dict(self.metrics)

    # --- Utilities ---
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
        p = int(start_port)
        for i in range(max_probe + 1):
            cand = p + i
            if self._is_port_free(host, cand):
                return cand
        return start_port  # Fallback

    def _denylist_check(self, args: Dict[str, Any]):
        deny = {"hf_token", "token", "openai_api_key", "anthropic_api_key"}
        if not getattr(self.config, "allow_cli_secrets", False):
            bad = [k for k in args.keys() if k in deny]
            if bad:
                raise ServerError(
                    f"Refusing secret flags {bad}. Set environment variables (e.g., HF_TOKEN) instead or enable allow_cli_secrets.")

    def _is_path_allowed(self, p: Path) -> bool:
        try:
            pr = p.resolve()
        except Exception:
            return False
        bases = [self.models_dir.resolve()]
        extra = getattr(self.config, "allowed_paths", None) or []
        try:
            bases.extend([Path(x).resolve() for x in extra])
        except Exception:
            pass
        return any(str(pr).startswith(str(base)) for base in bases)

    def _safe_log(self, level: str, msg: str, *args):
        """Log defensively to avoid errors when sinks are closed during atexit."""
        try:
            log_fn = getattr(self.logger, level, None)
            if callable(log_fn):
                log_fn(msg, *args)
        except Exception:
            # Swallow logging errors on interpreter shutdown / closed sinks
            pass

    async def list_models(self) -> List[str]:
        """Lists locally available GGUF models."""
        if not self.models_dir.exists():
            return []

        def _scan_dir():
            return [f.name for f in self.models_dir.glob("*.gguf")]

        return await asyncio.to_thread(_scan_dir)

    async def is_model_available(self, model_filename: str) -> bool:
        """Checks if a GGUF model file is available locally."""
        return (self.models_dir / model_filename).is_file()

    # --- Server Management (Core of the swapping logic) ---
    async def start_server(self, model_filename: str, server_args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Starts the Llama.cpp server with the specified model.
        If a server is already running managed by this handler, it will be stopped first (model swap).
        """
        if not Path(self.config.executable_path).is_file():
            raise ServerError(f"Llama.cpp server executable not found at {self.config.executable_path}")

        model_path = self.models_dir / model_filename
        if not model_path.is_file():
            raise ModelNotFoundError(f"Model file {model_filename} not found in {self.models_dir}.")

        # --- Model Swapping Logic ---
        if self._active_server_process and self._active_server_process.returncode is None:
            self.logger.info(
                f"Stopping existing Llama.cpp server (PID: {self._active_server_process.pid}) to swap model.")
            await self.stop_server()  # stop_server will clear _active_server_process etc.

        args = server_args or {}
        self._denylist_check(args)

        # Allowlist of supported args (internal key -> formatter)
        # Each formatter extends the command list with the mapped CLI args.
        allowed_formatters: Dict[str, Any] = {
            "port": lambda v: ["--port", str(int(v))],
            "host": lambda v: ["--host", str(v)],
            "threads": lambda v: ["-t", str(int(v))],
            "t": lambda v: ["-t", str(int(v))],
            "threads_batch": lambda v: ["--threads-batch", str(int(v))],
            "tb": lambda v: ["--threads-batch", str(int(v))],
            "ctx_size": lambda v: ["-c", str(int(v))],
            "c": lambda v: ["-c", str(int(v))],
            "n_gpu_layers": lambda v: ["-ngl", str(int(v))],
            "ngl": lambda v: ["-ngl", str(int(v))],
            "gpu_layers": lambda v: ["-ngl", str(int(v))],
            "batch_size": lambda v: ["-b", str(int(v))],
            "b": lambda v: ["-b", str(int(v))],
            "ubatch_size": lambda v: ["--ubatch-size", str(int(v))],
            "ub": lambda v: ["--ubatch-size", str(int(v))],
            "verbose": lambda v: (["--verbose"] if v else []),
            "log_disable": lambda v: (["--log-disable"] if v else []),
            # Extended safe flags
            "no_mmap": lambda v: (["--no-mmap"] if v else []),
            "mlock": lambda v: (["--mlock"] if v else []),
            "main_gpu": lambda v: ["--main-gpu", str(int(v))],
            "mg": lambda v: ["--main-gpu", str(int(v))],
            "split_mode": lambda v: ["--split-mode", str(v)],
            "sm": lambda v: ["--split-mode", str(v)],
            # Additional extended flags
            # Note: Some of these may be build-dependent in llama.cpp;
            # keeping them in allowlist enables safe, explicit usage when supported.
            "main_kv": lambda v: ["--main-kv", str(int(v))],
            "no_kv_offload": lambda v: (["--no-kv-offload"] if v else []),
            # Rope scaling type (e.g., "linear", "yarn", etc.)
            "rope_scaling_type": lambda v: ["--rope-scaling", str(v)],
            "rope_scaling": lambda v: ["--rope-scaling", str(v)],
            "tensor_split": lambda v: ["--tensor-split", ",".join(map(str, v))] if isinstance(v, (list, tuple)) else ["--tensor-split", str(v)],
            "rope_freq_base": lambda v: ["--rope-freq-base", str(float(v))],
            "rope_freq_scale": lambda v: ["--rope-freq-scale", str(float(v))],
            # Aliases and additional safe toggles
            "rope_scale": lambda v: ["--rope-freq-scale", str(float(v))],
            "flash_attn": lambda v: (["--flash-attn"] if v else []),
            "cont_batching": lambda v: (["--cont-batching"] if v else []),
            # LoRA support (repeatable)
            "lora": lambda v: sum((["--lora", str(x)] for x in (v if isinstance(v, (list, tuple)) else [v])), []),
            "lora_scaled": lambda v: (["--lora-scaled", str(v[0]), str(v[1])]
                                      if isinstance(v, (list, tuple)) and len(v) == 2
                                      else (["--lora-scaled", str(v)] if v is not None else [])),
            "lora_base": lambda v: ["--lora-base", str(v)],
            "control_vector": lambda v: ["--control-vector", str(v)],
            # KV cache type hints
            "cache_type_k": lambda v: ["--cache-type-k", str(v)],
            "cache_type_v": lambda v: ["--cache-type-v", str(v)],
            # Model download / HF
            "hf_repo": lambda v: ["--hf-repo", str(v)],
            "hf_file": lambda v: ["--hf-file", str(v)],
            "hf_token": lambda v: ["--hf-token", str(v)],
            "offline": lambda v: (["--offline"] if v else []),
            # Chat / conversation toggles
            "conversation": lambda v: (["--conversation"] if v else []),
            "cnv": lambda v: (["--conversation"] if v else []),
            "no_conversation": lambda v: (["--no-conversation"] if v else []),
            "no_cnv": lambda v: (["--no-conversation"] if v else []),
            "interactive": lambda v: (["--interactive"] if v else []),
            "i": lambda v: (["--interactive"] if v else []),
            "interactive_first": lambda v: (["--interactive-first"] if v else []),
            "if": lambda v: (["--interactive-first"] if v else []),
            "single_turn": lambda v: (["--single-turn"] if v else []),
            "st": lambda v: (["--single-turn"] if v else []),
            "jinja": lambda v: (["--jinja"] if v else []),
            "chat_template": lambda v: ["--chat-template", str(v)],
            "chat_template_file": lambda v: ["--chat-template-file", str(v)],
            # Input/output control
            "in_prefix": lambda v: ["--in-prefix", str(v)],
            "in_suffix": lambda v: ["--in-suffix", str(v)],
            "in_prefix_bos": lambda v: (["--in-prefix-bos"] if v else []),
            "reverse_prompt": lambda v: ["--reverse-prompt", str(v)],
            "r": lambda v: ["--reverse-prompt", str(v)],
            # Text generation controls
            "predict": lambda v: ["-n", str(int(v))],
            "n": lambda v: ["-n", str(int(v))],
            "keep": lambda v: ["--keep", str(int(v))],
            "ignore_eos": lambda v: (["--ignore-eos"] if v else []),
            "no_context_shift": lambda v: (["--no-context-shift"] if v else []),
            # Sampling controls
            "temp": lambda v: ["--temp", str(float(v))],
            "seed": lambda v: ["-s", str(int(v))],
            "dynatemp_range": lambda v: ["--dynatemp-range", str(float(v))],
            "top_k": lambda v: ["--top-k", str(int(v))],
            "top_p": lambda v: ["--top-p", str(float(v))],
            "min_p": lambda v: ["--min-p", str(float(v))],
            "typical": lambda v: ["--typical", str(float(v))],
            # Repetition controls
            "repeat_penalty": lambda v: ["--repeat-penalty", str(float(v))],
            "repeat_last_n": lambda v: ["--repeat-last-n", str(int(v))],
            "presence_penalty": lambda v: ["--presence-penalty", str(float(v))],
            "frequency_penalty": lambda v: ["--frequency-penalty", str(float(v))],
            # DRY sampling
            "dry_multiplier": lambda v: ["--dry-multiplier", str(float(v))],
            "dry_base": lambda v: ["--dry-base", str(float(v))],
            "dry_allowed_length": lambda v: ["--dry-allowed-length", str(int(v))],
            # Mirostat
            "mirostat": lambda v: ["--mirostat", str(int(v))],
            "mirostat_lr": lambda v: ["--mirostat-lr", str(float(v))],
            "mirostat_ent": lambda v: ["--mirostat-ent", str(float(v))],
            # CPU/GPU/NUMA
            "cpu_mask": lambda v: ["--cpu-mask", str(v)],
            "cpu_range": lambda v: ["--cpu-range", str(v)],
            "numa": lambda v: (["--numa", str(v)] if isinstance(v, str) else (["--numa"] if v else [])),
            # Structured generation
            "grammar": lambda v: ["--grammar", str(v)],
            "grammar_file": lambda v: ["--grammar-file", str(v)],
            "json_schema": lambda v: ["--json-schema", str(v)],
            "json_schema_file": lambda v: ["--json-schema-file", str(v)],
            "j": lambda v: ["-j", str(v)],
            # Reasoning
            "reasoning_format": lambda v: ["--reasoning-format", str(v)],
            "reasoning_budget": lambda v: ["--reasoning-budget", str(int(v))],
            # Caching
            "prompt_cache": lambda v: ["--prompt-cache", str(v)],
            "prompt_cache_all": lambda v: (["--prompt-cache-all"] if v else []),
            "prompt_cache_ro": lambda v: (["--prompt-cache-ro"] if v else []),
            # Logging
            "log_file": lambda v: ["--log-file", str(v)],
            "log_colors": lambda v: (["--log-colors"] if v else []),
            "log_timestamps": lambda v: (["--log-timestamps"] if v else []),
            "log_verbosity": lambda v: ["--log-verbosity", str(v)],
            "no_perf": lambda v: (["--no-perf"] if v else []),
            # System prompt/chat
            "system_prompt": lambda v: ["--system-prompt", str(v)],
            "sys": lambda v: ["--system-prompt", str(v)],
            # Prompt convenience
            "prompt": lambda v: ["-p", str(v)],
        }

        # Required defaults
        raw_port = int(args.get("port", self.config.default_port))
        host = str(args.get("host", self.config.default_host))
        port = self._pick_port(host, raw_port)
        n_gpu_layers = int(args.get("n_gpu_layers", args.get("ngl", self.config.default_n_gpu_layers)))
        ctx_size = int(args.get("ctx_size", args.get("c", self.config.default_ctx_size)))
        threads = args.get("threads", args.get("t", self.config.default_threads))

        command = [str(self.config.executable_path), "-m", str(model_path)]
        # Always include core args
        command += ["--host", host, "--port", str(port), "-c", str(ctx_size), "-ngl", str(n_gpu_layers)]
        if threads is not None:
            command += ["-t", str(int(threads))]

        # Validate all provided keys are allowed
        invalid = [k for k in args.keys() if k not in allowed_formatters and k not in {"port", "host", "threads", "t", "ctx_size", "c", "n_gpu_layers", "ngl", "gpu_layers"}]
        if invalid and not getattr(self.config, "allow_unvalidated_args", False):
            raise ServerError(f"Unsupported llama.cpp server args: {sorted(invalid)}")

        # Apply boolean/kv flags from allowlist (exclude ones already encoded above)
        for k, v in args.items():
            if k in ("port", "host", "threads", "t", "ctx_size", "c", "n_gpu_layers", "ngl", "gpu_layers"):
                continue
            fmt = allowed_formatters.get(k)
            if fmt:
                # Path safety for file arguments
                if k in {"grammar_file", "json_schema_file", "chat_template_file", "prompt_cache", "log_file", "lora_base", "control_vector"}:
                    p = Path(v)
                    if not self._is_path_allowed(p):
                        raise ServerError(f"File path for '{k}' must be under allowed directories.")
                if k == "lora":
                    vals = v if isinstance(v, (list, tuple)) else [v]
                    for item in vals:
                        if not self._is_path_allowed(Path(item)):
                            raise ServerError("LoRA path must be under allowed directories.")
                command += fmt(v)
            elif getattr(self.config, "allow_unvalidated_args", False):
                # Pass-through unknown args as --key value (bool True -> flag only)
                flag = f"--{k.replace('_', '-')}"
                if v is True:
                    command.append(flag)
                elif v is False or v is None:
                    pass
                else:
                    command += [flag, str(v)]

        from .http_utils import redact_cmd_args
        redacted_cmd = redact_cmd_args(command)
        self.logger.info(
            f"Starting Llama.cpp server for {model_filename} on {host}:{port} with command: {' '.join(redacted_cmd)}")

        stdout_redir = asyncio.subprocess.PIPE
        stderr_redir = asyncio.subprocess.PIPE
        log_file_handle = None

        if self.config.log_output_file:
            try:
                log_file_handle = open(self.config.log_output_file, "ab")  # Append binary
                stdout_redir = log_file_handle
                stderr_redir = log_file_handle
                self.logger.info(f"Llama.cpp server logs will be written to: {self.config.log_output_file}")
            except Exception as e:
                self.logger.error(f"Could not open log file {self.config.log_output_file}: {e}. Logging to PIPE.")

        try:
            cpe_kwargs = dict(
                stdout=stdout_redir,
                stderr=stderr_redir,
            )
            if platform.system() != "Windows":
                cpe_kwargs["preexec_fn"] = os.setsid
            else:
                # Use a fresh process group allowing CTRL_BREAK_EVENT (Windows-only)
                cpe_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            process = await asyncio.create_subprocess_exec(
                *command,
                **cpe_kwargs
            )
            # Poll HTTP health instead of fixed sleep
            base_url = f"http://{host}:{port}"
            t0 = time.perf_counter()
            is_ready = await wait_for_http_ready(base_url, timeout_total=30.0, interval=0.5)

            if process.returncode is not None or not is_ready:
                # If logging to file, error might not be in stderr pipe here.
                # Consider reading last few lines of log_output_file if it exists.
                stderr_output = ""
                if stderr_redir == asyncio.subprocess.PIPE and process.stderr:  # Check if stderr was piped
                    err_bytes = await process.stderr.read()  # This might hang if server is still writing
                    stderr_output = err_bytes.decode(errors='ignore').strip()
                self.logger.error(
                    f"Llama.cpp server failed to start or become ready for {model_filename}. Exit code: {process.returncode}. Stderr: {stderr_output}"
                )
                if log_file_handle: log_file_handle.close()
                try:
                    if process.returncode is None:
                        # Stop server if it started but not ready
                        process.terminate()
                except Exception:
                    pass
                self.metrics["start_errors"] += 1
                raise ServerError(f"Llama.cpp server failed to start. Stderr: {stderr_output}")

            self._active_server_process = process
            self._active_server_model = model_filename
            self._active_server_port = port
            self._active_server_host = host
            t1 = time.perf_counter()
            self.metrics["starts"] += 1
            self.metrics["readiness_time_sum"] += max(0.0, t1 - t0)
            self.metrics["readiness_count"] += 1
            if log_file_handle:  # Store handle to close it later
                self._active_server_log_handle = log_file_handle
            else:
                self._active_server_log_handle = None

            self.logger.info(f"Llama.cpp server started for {model_filename} on {host}:{port} with PID {process.pid}.")
            return {"status": "started", "pid": process.pid, "model": model_filename, "port": port, "host": host,
                    "command": ' '.join(redacted_cmd)}
        except Exception as e:
            if log_file_handle: log_file_handle.close()
            self.logger.error(f"Exception starting Llama.cpp server for {model_filename}: {e}", exc_info=True)
            raise ServerError(f"Exception starting Llama.cpp server: {e}")

    async def stop_server(self) -> str:
        if not self._active_server_process:
            return "No Llama.cpp server managed by this handler is currently running."

        process_to_stop = self._active_server_process
        pid = process_to_stop.pid
        model_name = self._active_server_model
        self.logger.info(f"Stopping Llama.cpp server (PID: {pid}, Model: {model_name}).")

        try:
            if process_to_stop.returncode is None:  # Still running
                if platform.system() == "Windows":
                    process_to_stop.terminate()
                else:
                    try:
                        pgid = await asyncio.to_thread(os.getpgid, pid)
                        await asyncio.to_thread(os.killpg, pgid, signal.SIGTERM)
                        self.logger.info(f"Sent SIGTERM to process group {pgid} (leader PID: {pid}).")
                    except ProcessLookupError:
                        self.logger.warning(f"Process {pid} not found for SIGTERM, likely already terminated.")
                        process_to_stop.terminate()  # Fallback
                    except Exception as e_pg:
                        self.logger.warning(
                            f"Failed to send SIGTERM to process group {pid}: {e_pg}. Falling back to PID.")
                        process_to_stop.terminate()

                try:
                    await asyncio.wait_for(process_to_stop.wait(), timeout=10)
                    self.logger.info(f"Llama.cpp server PID {pid} (Model: {model_name}) terminated gracefully.")
                except asyncio.TimeoutError:
                    self.logger.warning(
                        f"Llama.cpp server PID {pid} (Model: {model_name}) did not terminate gracefully. Killing.")
                    if platform.system() == "Windows":
                        if hasattr(process_to_stop, "send_signal"):
                            try:
                                process_to_stop.send_signal(signal.CTRL_BREAK_EVENT)
                            except Exception:
                                pass
                        if hasattr(process_to_stop, "terminate"):
                            process_to_stop.terminate()
                        if hasattr(process_to_stop, "kill"):
                            process_to_stop.kill()
                    else:
                        try:
                            pgid = await asyncio.to_thread(os.getpgid, pid)  # Re-fetch pgid in case
                            await asyncio.to_thread(os.killpg, pgid, signal.SIGKILL)
                        except (ProcessLookupError, PermissionError, OSError) as e:  # Specific exceptions for kill fallback
                            self.logger.warning(f"Failed to kill process group {pgid}: {str(e)}. Falling back to kill.")
                            process_to_stop.kill()
                    await process_to_stop.wait()
            else:
                self.logger.info(
                    f"Llama.cpp server PID {pid} (Model: {model_name}) was already stopped (return code: {process_to_stop.returncode}).")

            if self._active_server_log_handle:
                self._active_server_log_handle.close()
                self._active_server_log_handle = None

            self._active_server_process = None
            self._active_server_model = None
            self._active_server_port = None
            self._active_server_host = None
            self.metrics["stops"] += 1
            return f"Llama.cpp server PID {pid} (Model: {model_name}) stopped."

        except Exception as e:
            self.logger.error(f"Error stopping Llama.cpp server PID {pid}: {e}", exc_info=True)
            # Clear state even on error to allow trying to start a new one
            if self._active_server_log_handle:
                self._active_server_log_handle.close()
                self._active_server_log_handle = None
            self._active_server_process = None
            self._active_server_model = None
            self._active_server_port = None
            self._active_server_host = None
            raise ServerError(f"Error stopping Llama.cpp server: {e}")

    async def get_server_status(self) -> Dict[str, Any]:
        if self._active_server_process and self._active_server_process.returncode is None:
            return {
                "status": "running",
                "pid": self._active_server_process.pid,
                "model": self._active_server_model,
                "port": self._active_server_port,
                "host": self._active_server_host,
                "log_file": str(
                    self.config.log_output_file) if self.config.log_output_file and self._active_server_log_handle else None
            }
        return {"status": "stopped", "model": None, "pid": None, "port": None, "host": None}

    async def inference(self, prompt: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None,
                        api_endpoint: str = "/v1/chat/completions",  # or /completion
                        **kwargs) -> Dict[str, Any]:
        if not self._active_server_process or self._active_server_process.returncode is not None:
            raise ServerError("Llama.cpp server is not running or not managed by this handler.")

        base_url = f"http://{self._active_server_host}:{self._active_server_port}"
        # Ensure exactly one slash between base and path
        target_url = f"{base_url}/{api_endpoint.lstrip('/')}"

        # Prepare payload (OpenAI compatible)
        payload = kwargs.copy()  # n_predict, temperature, top_k, top_p, stop, etc.
        if messages:
            payload["messages"] = messages
        elif prompt:  # Convert simple prompt to messages for chat completions endpoint
            payload["messages"] = [{"role": "user", "content": prompt}]
        else:
            raise InferenceError("Either 'prompt' or 'messages' must be provided for inference.")

        if "stream" not in payload:  # Default to non-streaming for this method
            payload["stream"] = False

        self.logger.debug(f"Sending Llama.cpp inference request to {target_url} with payload: {payload}")

        t0 = time.perf_counter()
        async with create_async_client(timeout=kwargs.get("timeout", 120.0)) as client:
            try:
                result = await request_json(client, "POST", target_url, json=payload, headers={"Content-Type": "application/json"})
                t1 = time.perf_counter()
                self.metrics["inference_count"] += 1
                self.metrics["inference_time_sum"] += max(0.0, t1 - t0)
                self.logger.debug("Llama.cpp inference successful.")
                return result
            except httpx.HTTPStatusError as e:
                error_text = e.response.text
                self.logger.error("Llama.cpp API error ({}) from {}: {}", e.response.status_code, target_url, error_text,
                                  exc_info=True)
                self.metrics["inference_error_count"] += 1
                raise InferenceError(f"Llama.cpp API error ({e.response.status_code}): {error_text}")
            except httpx.RequestError as e:
                self.logger.error("Could not connect or communicate with Llama.cpp server at {}: {}", target_url, e,
                                  exc_info=True)
                self.metrics["inference_error_count"] += 1
                raise ServerError(f"Could not connect/communicate with Llama.cpp server at {target_url}: {e}")

    async def stream_inference(self, prompt: Optional[str] = None, messages: Optional[List[Dict[str, str]]] = None,
                               api_endpoint: str = "/v1/chat/completions", **kwargs):
        if not self._active_server_process or self._active_server_process.returncode is not None:
            raise ServerError("Llama.cpp server is not running or not managed by this handler.")
        base_url = f"http://{self._active_server_host}:{self._active_server_port}"
        target_url = f"{base_url}/{api_endpoint.lstrip('/')}"
        payload = kwargs.copy()
        if messages:
            payload["messages"] = messages
        elif prompt:
            payload["messages"] = [{"role": "user", "content": prompt}]
        else:
            raise InferenceError("Either 'prompt' or 'messages' must be provided for stream_inference.")
        payload["stream"] = True
        headers = {"Content-Type": "application/json"}

        from tldw_Server_API.app.core.LLM_Calls.sse import ensure_sse_line, sse_done, sse_data, openai_delta_chunk, finalize_stream
        async with create_async_client(timeout=kwargs.get("timeout", 120.0)) as client:
            try:
                async with client.stream("POST", target_url, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    done_sent = False
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        l = line.strip()
                        if not l:
                            continue
                        if l.startswith("data:"):
                            if l.strip().lower() == "data: [done]".lower():
                                done_sent = True
                            yield ensure_sse_line(l)
                        else:
                            yield openai_delta_chunk(l)
                    if not done_sent:
                        yield sse_done()
            except httpx.HTTPStatusError as e:
                msg = getattr(e.response, "text", str(e))
                yield sse_data({"error": {"message": f"HTTP error: {msg}", "type": "llamacpp_stream_error"}})
            except Exception as e:
                yield sse_data({"error": {"message": f"Stream error: {str(e)}", "type": "llamacpp_stream_error"}})

    # --- Cleanup ---
    def _cleanup_managed_server_sync(self):
        # Avoid logging here: during interpreter shutdown, logging sinks may be closed.
        if self._active_server_process and self._active_server_process.returncode is None:
            proc = self._active_server_process
            pid = proc.pid
            try:
                if platform.system() == "Windows":
                    # Use subprocess for synchronous Popen if asyncio process is tricky here
                    # Or just call terminate on the asyncio process if it works in sync context
                    if hasattr(proc, "terminate"):
                        proc.terminate()
                else:
                    try:
                        pgid = os.getpgid(pid)
                        os.killpg(pgid, signal.SIGTERM)
                    except ProcessLookupError:
                        if hasattr(proc, "terminate"):
                            proc.terminate()  # Fallback
                    except Exception:  # Broad except for pgid issues
                        if hasattr(proc, "terminate"):
                            proc.terminate()

                # Synchronous wait is tricky with asyncio.subprocess.Process.
                # For atexit, sending TERM/KILL is often the best effort.
                # If you need guaranteed wait, you might need to use `subprocess.Popen` for the server.
                # Do not log here to avoid closed sink errors.

            except Exception as e:
                # Avoid logging; best-effort kill if needed
                if proc.returncode is None:  # Check again before kill
                    if platform.system() == "Windows":
                        if hasattr(proc, "kill"):
                            proc.kill()
                    else:
                        try:
                            os.killpg(os.getpgid(pid), signal.SIGKILL)
                        except (ProcessLookupError, PermissionError, OSError) as e:
                            # Fall back to direct kill
                            if hasattr(proc, "kill"):
                                proc.kill()
            if self._active_server_log_handle:
                self._active_server_log_handle.close()

        self._active_server_process = None  # Clear state
        # Avoid logging at atexit

    def _signal_handler(self, sig, frame):
        self._cleanup_managed_server_sync()
        # Let other handlers run, don't sys.exit here unless it's the main app's job
        # sys.exit(0)

    def _setup_signal_handlers(self):
        import atexit
        # Register for process exit
        atexit.register(self._cleanup_managed_server_sync)
        self.logger.info("Registered atexit synchronous cleanup for LlamaCppHandler.")
        # Signal handling for Ctrl+C etc.
        # Note: Multiple signal handlers can be tricky. Ensure this doesn't conflict.
        # signal.signal(signal.SIGINT, self._signal_handler)
        # signal.signal(signal.SIGTERM, self._signal_handler)

#
# End of LlamaCpp_Handler.py
########################################################################################################################
