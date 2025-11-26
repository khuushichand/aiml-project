from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MLXLoadRequest(BaseModel):
    model_path: Optional[str] = Field(default=None, description="Local path or repo id for the MLX model")
    max_seq_len: Optional[int] = Field(default=None, description="Override max sequence length")
    max_batch_size: Optional[int] = Field(default=None, description="Override max batch size")
    device: Optional[str] = Field(default=None, description="Device selection (auto|mps|cpu)")
    dtype: Optional[str] = Field(default=None, description="dtype override (float16/bfloat16/auto)")
    quantization: Optional[str] = Field(default=None, description="Quantization hint if supported")
    compile: Optional[bool] = Field(default=None, description="Enable compile at load time")
    warmup: Optional[bool] = Field(default=None, description="Run warmup generation on load")
    prompt_template: Optional[str] = Field(default=None, description="Optional chat template override")
    revision: Optional[str] = Field(default=None, description="Model revision (when using repo ids)")
    trust_remote_code: Optional[bool] = Field(default=None, description="Allow remote code (defaults to false)")
    tokenizer: Optional[str] = Field(default=None, description="Tokenizer override")
    adapter: Optional[str] = Field(default=None, description="Adapter identifier")
    adapter_weights: Optional[str] = Field(default=None, description="Path to adapter weights")
    max_kv_cache_size: Optional[int] = Field(default=None, description="KV cache upper bound if supported")
    max_concurrent: Optional[int] = Field(default=None, description="Concurrency cap (defaults to 1)")


class MLXUnloadRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Optional reason for audit logs")

