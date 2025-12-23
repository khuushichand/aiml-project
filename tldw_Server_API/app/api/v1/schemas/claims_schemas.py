from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class ClaimsSettingsResponse(BaseModel):
    """Current claims-related configuration values."""

    model_config = ConfigDict(extra="forbid")

    enable_ingestion_claims: bool = Field(..., description="Enable ingestion-time claim extraction.")
    claim_extractor_mode: str = Field(..., description="Default extractor mode for ingestion-time claims.")
    claims_max_per_chunk: int = Field(..., description="Maximum claims per chunk during ingestion.")
    claims_embed: bool = Field(..., description="Enable embedding of extracted claims.")
    claims_embed_model_id: str = Field(..., description="Model id for claim embeddings.")
    claims_llm_provider: str = Field(..., description="LLM provider for claim extraction.")
    claims_llm_temperature: float = Field(..., description="LLM temperature for claim extraction.")
    claims_llm_model: str = Field(..., description="LLM model for claim extraction.")
    claims_rebuild_enabled: bool = Field(..., description="Enable periodic claims rebuild worker.")
    claims_rebuild_interval_sec: int = Field(..., description="Claims rebuild loop interval in seconds.")
    claims_rebuild_policy: str = Field(..., description="Claims rebuild policy.")
    claims_stale_days: int = Field(..., description="Stale threshold for claims rebuild policy.")


class ClaimsSettingsUpdate(BaseModel):
    """Update payload for claims settings."""

    model_config = ConfigDict(extra="forbid")

    enable_ingestion_claims: Optional[bool] = Field(default=None)
    claim_extractor_mode: Optional[str] = Field(default=None)
    claims_max_per_chunk: Optional[int] = Field(default=None, ge=1, le=100)
    claims_embed: Optional[bool] = Field(default=None)
    claims_embed_model_id: Optional[str] = Field(default=None)
    claims_llm_provider: Optional[str] = Field(default=None)
    claims_llm_temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    claims_llm_model: Optional[str] = Field(default=None)
    claims_rebuild_enabled: Optional[bool] = Field(default=None)
    claims_rebuild_interval_sec: Optional[int] = Field(default=None, ge=60, le=604800)
    claims_rebuild_policy: Optional[str] = Field(default=None)
    claims_stale_days: Optional[int] = Field(default=None, ge=1, le=3650)
    persist: Optional[bool] = Field(default=None, description="Persist updates to config.txt.")


class ClaimUpdateRequest(BaseModel):
    """Update fields for a claim entry."""

    model_config = ConfigDict(extra="forbid")

    claim_text: Optional[str] = Field(default=None)
    span_start: Optional[int] = Field(default=None, ge=0)
    span_end: Optional[int] = Field(default=None, ge=0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    extractor: Optional[str] = Field(default=None)
    extractor_version: Optional[str] = Field(default=None)
    deleted: Optional[bool] = Field(default=None)
