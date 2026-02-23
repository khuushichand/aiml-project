from __future__ import annotations

from pydantic import BaseModel, Field


class MLXLoadRequest(BaseModel):
    model_id: str | None = Field(default=None, description="Relative model id under MLX_MODEL_DIR")
    model_path: str | None = Field(default=None, description="Local path or repo id for the MLX model")
    max_seq_len: int | None = Field(default=None, description="Override max sequence length")
    max_batch_size: int | None = Field(default=None, description="Override max batch size")
    device: str | None = Field(default=None, description="Device selection (auto|mps|cpu)")
    dtype: str | None = Field(default=None, description="dtype override (float16/bfloat16/auto)")
    quantization: str | None = Field(default=None, description="Quantization hint if supported")
    compile: bool | None = Field(default=None, description="Enable compile at load time")
    warmup: bool | None = Field(default=None, description="Run warmup generation on load")
    prompt_template: str | None = Field(default=None, description="Optional chat template override")
    revision: str | None = Field(default=None, description="Model revision (when using repo ids)")
    trust_remote_code: bool | None = Field(default=None, description="Allow remote code (defaults to false)")
    tokenizer: str | None = Field(default=None, description="Tokenizer override")
    adapter: str | None = Field(default=None, description="Adapter identifier")
    adapter_weights: str | None = Field(default=None, description="Path to adapter weights")
    max_kv_cache_size: int | None = Field(default=None, description="KV cache upper bound if supported")
    max_concurrent: int | None = Field(default=None, description="Concurrency cap (defaults to 1)")


class MLXUnloadRequest(BaseModel):
    reason: str | None = Field(default=None, description="Optional reason for audit logs")
