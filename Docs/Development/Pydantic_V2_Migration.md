Pydantic v2 Migration Plan
==========================

Goal
- Eliminate deprecation warnings and align all models with Pydantic v2 APIs.

Why
- Cleaner runtime logs, forward compatibility, and better performance.

Scope
- Replace v1 `@root_validator`/`@validator` with v2 `@model_validator`/`@field_validator`.
- Replace class-based `Config` with `model_config = ConfigDict(...)`.
- Review and update any type coercions and strict modes.

Quick Reference
- Root validator (v1) → Model validator (v2)

```python
from pydantic import BaseModel, model_validator

class SubmitAudioJobRequest(BaseModel):
    url: str | None = None
    local_path: str | None = None

    @model_validator(mode='after')
    def check_inputs(self) -> 'SubmitAudioJobRequest':
        if not (self.url or self.local_path):
            raise ValueError("Either url or local_path must be provided")
        if self.url and self.local_path:
            raise ValueError("Provide only one of url or local_path")
        return self
```

- Field validator (v1) → Field validator (v2)

```python
from pydantic import field_validator

class M(BaseModel):
    name: str

    @field_validator('name')
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('empty name')
        return v
```

- Class Config (v1) → ConfigDict (v2)

```python
from pydantic import BaseModel, ConfigDict

class M(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)
```

Staging Plan
1) Wave 1 (Low risk, high noise):
   - Convert simple `@root_validator` patterns to `@model_validator(mode='after')`.
   - Replace class Config with `ConfigDict` in leaf models.
2) Wave 2 (Complex models):
   - Convert nested and `pre=True` validators; review any custom parsing code.
   - Add unit tests for edge cases.
3) Wave 3 (Final polish):
   - Turn on stricter `extra='forbid'` where safe.
   - Audit any dynamic defaults; prefer `Field(default_factory=...)`.

Targets (initial)
- app/api/v1/endpoints/audio_jobs.py (converted as example)
- app/api/v1/schemas/rag_schemas_unified.py (multiple root validators)
- app/api/v1/schemas/rag_schemas_unified.py: replace class Config

Testing
- Run `pytest -q` and ensure no regressions.
- Watch logs for residual deprecation warnings.

Tips
- Use `rg -n "root_validator\(|class\s+Config\s*:\s*"` to find candidates.
- Prefer `mode='after'` for validators that need post-coercion instances; use `mode='before'` only when you must preprocess raw input.
