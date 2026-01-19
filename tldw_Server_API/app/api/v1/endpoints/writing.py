from __future__ import annotations

import functools
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_rate_limiter_dep, rbac_rate_limit
from tldw_Server_API.app.api.v1.endpoints.llm_providers import get_configured_providers_async
from tldw_Server_API.app.api.v1.schemas.writing_schemas import (
    WritingCapabilitiesResponse,
    WritingProviderCapabilities,
    WritingRequestedCapabilities,
    WritingServerCapabilities,
    WritingSessionCloneRequest,
    WritingSessionCreate,
    WritingSessionListItem,
    WritingSessionListResponse,
    WritingSessionResponse,
    WritingSessionUpdate,
    WritingTemplateCreate,
    WritingTemplateListResponse,
    WritingTemplateResponse,
    WritingTemplateUpdate,
    WritingThemeCreate,
    WritingThemeListResponse,
    WritingThemeResponse,
    WritingThemeUpdate,
    WritingTokenCountRequest,
    WritingTokenCountResponse,
    WritingTokenizeRequest,
    WritingTokenizeResponse,
    WritingTokenizeMeta,
    WritingTokenizerSupport,
    WritingVersionResponse,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
    InputError,
)
from tldw_Server_API.app.core.LLM_Calls.capability_registry import get_allowed_fields


router = APIRouter()


class TokenizerUnavailable(Exception):
    pass


async def _enforce_rate_limit(rate_limiter: RateLimiter, user_id: int, scope: str) -> None:
    try:
        allowed, meta = await rate_limiter.check_user_rate_limit(int(user_id), scope)
    except Exception:
        allowed, meta = True, {}
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {scope}",
            headers={"Retry-After": str(meta.get("retry_after", 60))},
        )


def _handle_db_errors(exc: Exception, entity_label: str) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, InputError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        message = str(exc)
        lowered = message.lower()
        if "not found" in lowered or "soft-deleted" in lowered or "soft deleted" in lowered:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity_label} not found") from exc
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message) from exc
    if isinstance(exc, CharactersRAGDBError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while processing {entity_label}",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Unexpected error while processing {entity_label}",
    ) from exc


@functools.lru_cache(maxsize=128)
def _resolve_tiktoken_encoding(model: str):
    try:
        import tiktoken  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency missing
        raise TokenizerUnavailable("Tokenizer library unavailable") from exc
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError as exc:
        raise TokenizerUnavailable("Tokenizer not available for provider/model") from exc


def _resolve_tokenizer(provider: str, model: str) -> Tuple[Any, str]:
    if not provider or not provider.strip():
        raise TokenizerUnavailable("Provider is required")
    if not model or not model.strip():
        raise TokenizerUnavailable("Model is required")
    encoding = _resolve_tiktoken_encoding(model.strip())
    tokenizer_name = getattr(encoding, "name", "unknown")
    return encoding, f"tiktoken:{tokenizer_name}"


def _provider_features(provider: str) -> Dict[str, bool]:
    fields = get_allowed_fields(provider)
    return {
        "logprobs": "logprobs" in fields,
        "logit_bias": "logit_bias" in fields,
        "tools": "tools" in fields,
        "tool_choice": "tool_choice" in fields,
        "response_format": "response_format" in fields,
        "seed": "seed" in fields,
        "top_k": "top_k" in fields,
        "min_p": "min_p" in fields,
        "top_p": "top_p" in fields,
        "temperature": "temperature" in fields,
        "presence_penalty": "presence_penalty" in fields,
        "frequency_penalty": "frequency_penalty" in fields,
    }


def _coerce_model_name(model: Any) -> Optional[str]:
    if isinstance(model, str):
        return model.strip() or None
    if isinstance(model, dict):
        for key in ("name", "id", "model"):
            value = model.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _tokenizer_support(provider: str, model: str) -> WritingTokenizerSupport:
    try:
        _, tokenizer_name = _resolve_tokenizer(provider, model)
        return WritingTokenizerSupport(available=True, tokenizer=tokenizer_name)
    except TokenizerUnavailable as exc:
        return WritingTokenizerSupport(available=False, error=str(exc))


@router.get(
    "/version",
    response_model=WritingVersionResponse,
    summary="Writing Playground API version",
    tags=["writing"],
)
async def get_writing_version(
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.version")),
) -> WritingVersionResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.version")
    return WritingVersionResponse(version=1)


@router.get(
    "/capabilities",
    response_model=WritingCapabilitiesResponse,
    summary="Writing Playground capabilities",
    tags=["writing"],
)
async def get_writing_capabilities(
    provider: Optional[str] = Query(None, description="Optional provider to resolve"),
    model: Optional[str] = Query(None, description="Optional model to resolve"),
    include_providers: bool = Query(True, description="Include configured providers list"),
    include_deprecated: bool = Query(False, description="Include deprecated models"),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.capabilities")),
) -> WritingCapabilitiesResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.capabilities")

    server = WritingServerCapabilities(
        sessions=True,
        templates=True,
        themes=True,
        tokenize=True,
        token_count=True,
    )

    providers_payload: Optional[List[WritingProviderCapabilities]] = None
    default_provider = None
    if include_providers:
        providers_info = await get_configured_providers_async(include_deprecated=include_deprecated)
        default_provider = providers_info.get("default_provider")
        providers_payload = []
        for provider_info in providers_info.get("providers", []):
            name = provider_info.get("name") or "unknown"
            raw_models = provider_info.get("models") or []
            models: List[str] = []
            for model in raw_models:
                model_name = _coerce_model_name(model)
                if model_name:
                    models.append(model_name)
            capabilities = provider_info.get("capabilities") or {}
            supported_fields = sorted(get_allowed_fields(name))
            tokenizers = None
            if models:
                tokenizers = {model: _tokenizer_support(name, model) for model in models}
            providers_payload.append(
                WritingProviderCapabilities(
                    name=name,
                    models=models,
                    capabilities=capabilities,
                    supported_fields=supported_fields,
                    features=_provider_features(name),
                    tokenizers=tokenizers,
                )
            )

    requested: Optional[WritingRequestedCapabilities] = None
    if provider or model:
        provider_name = (provider or "").strip()
        model_name = (model or "").strip() or None
        supported_fields = sorted(get_allowed_fields(provider_name)) if provider_name else []
        features = _provider_features(provider_name) if provider_name else {}
        tokenizer_available = False
        tokenizer_name = None
        tokenization_error = None
        if provider_name and model_name:
            try:
                _, tokenizer_name = _resolve_tokenizer(provider_name, model_name)
                tokenizer_available = True
            except TokenizerUnavailable as exc:
                tokenization_error = str(exc)
        requested = WritingRequestedCapabilities(
            provider=provider_name,
            model=model_name,
            supported_fields=supported_fields,
            features=features,
            tokenizer_available=tokenizer_available,
            tokenizer=tokenizer_name,
            tokenization_error=tokenization_error,
        )

    return WritingCapabilitiesResponse(
        version=1,
        server=server,
        default_provider=default_provider,
        providers=providers_payload,
        requested=requested,
    )


@router.get(
    "/sessions",
    response_model=WritingSessionListResponse,
    summary="List writing sessions",
    tags=["writing"],
)
async def list_writing_sessions(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.sessions.list")),
) -> WritingSessionListResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.sessions.list")
    try:
        sessions = db.list_writing_sessions(limit=limit, offset=offset)
        total = db.count_writing_sessions()
        items = [WritingSessionListItem(**item) for item in sessions]
        return WritingSessionListResponse(sessions=items, total=total)
    except Exception as exc:
        _handle_db_errors(exc, "writing sessions")


@router.post(
    "/sessions",
    response_model=WritingSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a writing session",
    tags=["writing"],
)
async def create_writing_session(
    payload: WritingSessionCreate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.sessions.create")),
) -> WritingSessionResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.sessions.create")
    try:
        session_id = db.add_writing_session(
            name=payload.name,
            payload=payload.payload,
            schema_version=payload.schema_version,
            session_id=payload.id,
            version_parent_id=payload.version_parent_id,
        )
        session = db.get_writing_session(session_id)
        if not session:
            raise CharactersRAGDBError("Session created but could not be retrieved")
        session["payload"] = session.get("payload") or {}
        return WritingSessionResponse(**session)
    except Exception as exc:
        _handle_db_errors(exc, "writing session")


@router.get(
    "/sessions/{session_id}",
    response_model=WritingSessionResponse,
    summary="Get a writing session",
    tags=["writing"],
)
async def get_writing_session(
    session_id: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.sessions.get")),
) -> WritingSessionResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.sessions.get")
    try:
        session = db.get_writing_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        session["payload"] = session.get("payload") or {}
        return WritingSessionResponse(**session)
    except Exception as exc:
        _handle_db_errors(exc, "writing session")


@router.patch(
    "/sessions/{session_id}",
    response_model=WritingSessionResponse,
    summary="Update a writing session",
    tags=["writing"],
)
async def update_writing_session(
    session_id: str,
    payload: WritingSessionUpdate,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.sessions.update")),
) -> WritingSessionResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.sessions.update")
    update_data: Dict[str, Any] = {}
    if payload.name is not None:
        update_data["name"] = payload.name.strip()
        if not update_data["name"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session name cannot be empty")
    if payload.payload is not None:
        update_data["payload_json"] = db._serialize_writing_payload(payload.payload, "Session")
    if payload.schema_version is not None:
        update_data["schema_version"] = payload.schema_version
    if payload.version_parent_id is not None:
        update_data["version_parent_id"] = payload.version_parent_id
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")
    try:
        db.update_writing_session(session_id, update_data, expected_version)
        session = db.get_writing_session(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        session["payload"] = session.get("payload") or {}
        return WritingSessionResponse(**session)
    except Exception as exc:
        _handle_db_errors(exc, "writing session")


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a writing session",
    tags=["writing"],
)
async def delete_writing_session(
    session_id: str,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.sessions.delete")),
) -> None:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.sessions.delete")
    try:
        db.soft_delete_writing_session(session_id, expected_version)
        return None
    except Exception as exc:
        _handle_db_errors(exc, "writing session")


@router.post(
    "/sessions/{session_id}/clone",
    response_model=WritingSessionResponse,
    summary="Clone a writing session",
    tags=["writing"],
)
async def clone_writing_session(
    session_id: str,
    payload: WritingSessionCloneRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.sessions.clone")),
) -> WritingSessionResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.sessions.clone")
    try:
        cloned = db.clone_writing_session(session_id, name=payload.name)
        cloned["payload"] = cloned.get("payload") or {}
        return WritingSessionResponse(**cloned)
    except Exception as exc:
        _handle_db_errors(exc, "writing session")


@router.get(
    "/templates",
    response_model=WritingTemplateListResponse,
    summary="List writing templates",
    tags=["writing"],
)
async def list_writing_templates(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.templates.list")),
) -> WritingTemplateListResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.templates.list")
    try:
        templates = db.list_writing_templates(limit=limit, offset=offset)
        total = db.count_writing_templates()
        for tmpl in templates:
            tmpl["payload"] = tmpl.get("payload") or {}
        return WritingTemplateListResponse(
            templates=[WritingTemplateResponse(**tmpl) for tmpl in templates],
            total=total,
        )
    except Exception as exc:
        _handle_db_errors(exc, "writing templates")


@router.post(
    "/templates",
    response_model=WritingTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a writing template",
    tags=["writing"],
)
async def create_writing_template(
    payload: WritingTemplateCreate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.templates.create")),
) -> WritingTemplateResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.templates.create")
    try:
        db.add_writing_template(
            name=payload.name,
            payload=payload.payload,
            schema_version=payload.schema_version,
            version_parent_id=payload.version_parent_id,
            is_default=payload.is_default,
        )
        template = db.get_writing_template_by_name(payload.name)
        if not template:
            raise CharactersRAGDBError("Template created but could not be retrieved")
        template["payload"] = template.get("payload") or {}
        return WritingTemplateResponse(**template)
    except Exception as exc:
        _handle_db_errors(exc, "writing template")


@router.get(
    "/templates/{name}",
    response_model=WritingTemplateResponse,
    summary="Get a writing template",
    tags=["writing"],
)
async def get_writing_template(
    name: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.templates.get")),
) -> WritingTemplateResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.templates.get")
    try:
        template = db.get_writing_template_by_name(name)
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        template["payload"] = template.get("payload") or {}
        return WritingTemplateResponse(**template)
    except Exception as exc:
        _handle_db_errors(exc, "writing template")


@router.patch(
    "/templates/{name}",
    response_model=WritingTemplateResponse,
    summary="Update a writing template",
    tags=["writing"],
)
async def update_writing_template(
    name: str,
    payload: WritingTemplateUpdate,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.templates.update")),
) -> WritingTemplateResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.templates.update")
    update_data: Dict[str, Any] = {}
    if payload.name is not None:
        update_data["name"] = payload.name.strip()
        if not update_data["name"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template name cannot be empty")
    if payload.payload is not None:
        update_data["payload_json"] = db._serialize_writing_payload(payload.payload, "Template")
    if payload.schema_version is not None:
        update_data["schema_version"] = payload.schema_version
    if payload.version_parent_id is not None:
        update_data["version_parent_id"] = payload.version_parent_id
    if payload.is_default is not None:
        update_data["is_default"] = payload.is_default
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")
    try:
        db.update_writing_template(name, update_data, expected_version)
        template_name = update_data.get("name", name)
        template = db.get_writing_template_by_name(template_name)
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        template["payload"] = template.get("payload") or {}
        return WritingTemplateResponse(**template)
    except Exception as exc:
        _handle_db_errors(exc, "writing template")


@router.delete(
    "/templates/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a writing template",
    tags=["writing"],
)
async def delete_writing_template(
    name: str,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.templates.delete")),
) -> None:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.templates.delete")
    try:
        db.soft_delete_writing_template(name, expected_version)
        return None
    except Exception as exc:
        _handle_db_errors(exc, "writing template")


@router.get(
    "/themes",
    response_model=WritingThemeListResponse,
    summary="List writing themes",
    tags=["writing"],
)
async def list_writing_themes(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.themes.list")),
) -> WritingThemeListResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.themes.list")
    try:
        themes = db.list_writing_themes(limit=limit, offset=offset)
        total = db.count_writing_themes()
        for theme in themes:
            theme["order"] = theme.pop("order_index", 0)
        return WritingThemeListResponse(
            themes=[WritingThemeResponse(**theme) for theme in themes],
            total=total,
        )
    except Exception as exc:
        _handle_db_errors(exc, "writing themes")


@router.post(
    "/themes",
    response_model=WritingThemeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a writing theme",
    tags=["writing"],
)
async def create_writing_theme(
    payload: WritingThemeCreate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.themes.create")),
) -> WritingThemeResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.themes.create")
    try:
        db.add_writing_theme(
            name=payload.name,
            class_name=payload.class_name,
            css=payload.css,
            schema_version=payload.schema_version,
            version_parent_id=payload.version_parent_id,
            is_default=payload.is_default,
            order_index=payload.order,
        )
        theme = db.get_writing_theme_by_name(payload.name)
        if not theme:
            raise CharactersRAGDBError("Theme created but could not be retrieved")
        theme["order"] = theme.pop("order_index", 0)
        return WritingThemeResponse(**theme)
    except Exception as exc:
        _handle_db_errors(exc, "writing theme")


@router.get(
    "/themes/{name}",
    response_model=WritingThemeResponse,
    summary="Get a writing theme",
    tags=["writing"],
)
async def get_writing_theme(
    name: str,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.themes.get")),
) -> WritingThemeResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.themes.get")
    try:
        theme = db.get_writing_theme_by_name(name)
        if not theme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found")
        theme["order"] = theme.pop("order_index", 0)
        return WritingThemeResponse(**theme)
    except Exception as exc:
        _handle_db_errors(exc, "writing theme")


@router.patch(
    "/themes/{name}",
    response_model=WritingThemeResponse,
    summary="Update a writing theme",
    tags=["writing"],
)
async def update_writing_theme(
    name: str,
    payload: WritingThemeUpdate,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.themes.update")),
) -> WritingThemeResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.themes.update")
    update_data: Dict[str, Any] = {}
    if payload.name is not None:
        update_data["name"] = payload.name.strip()
        if not update_data["name"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Theme name cannot be empty")
    if payload.class_name is not None:
        update_data["class_name"] = payload.class_name
    if payload.css is not None:
        update_data["css"] = payload.css
    if payload.schema_version is not None:
        update_data["schema_version"] = payload.schema_version
    if payload.version_parent_id is not None:
        update_data["version_parent_id"] = payload.version_parent_id
    if payload.is_default is not None:
        update_data["is_default"] = payload.is_default
    if payload.order is not None:
        update_data["order_index"] = payload.order
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")
    try:
        db.update_writing_theme(name, update_data, expected_version)
        theme_name = update_data.get("name", name)
        theme = db.get_writing_theme_by_name(theme_name)
        if not theme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found")
        theme["order"] = theme.pop("order_index", 0)
        return WritingThemeResponse(**theme)
    except Exception as exc:
        _handle_db_errors(exc, "writing theme")


@router.delete(
    "/themes/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a writing theme",
    tags=["writing"],
)
async def delete_writing_theme(
    name: str,
    expected_version: int = Header(..., description="Expected version for optimistic locking"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.themes.delete")),
) -> None:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.themes.delete")
    try:
        db.soft_delete_writing_theme(name, expected_version)
        return None
    except Exception as exc:
        _handle_db_errors(exc, "writing theme")


@router.post(
    "/tokenize",
    response_model=WritingTokenizeResponse,
    summary="Tokenize text for a provider/model",
    tags=["writing"],
)
async def tokenize_writing_text(
    payload: WritingTokenizeRequest,
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.tokenize")),
) -> WritingTokenizeResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.tokenize")
    include_strings = True
    if payload.options is not None:
        include_strings = bool(payload.options.include_strings)
    try:
        encoding, tokenizer_name = _resolve_tokenizer(payload.provider, payload.model)
    except TokenizerUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    token_ids = encoding.encode(payload.text, disallowed_special=())
    token_strings = None
    if include_strings:
        token_strings = [encoding.decode([token_id]) for token_id in token_ids]
    meta = WritingTokenizeMeta(
        provider=payload.provider,
        model=payload.model,
        tokenizer=tokenizer_name,
        input_chars=len(payload.text),
        token_count=len(token_ids),
        warnings=[],
    )
    return WritingTokenizeResponse(ids=token_ids, strings=token_strings, meta=meta)


@router.post(
    "/token-count",
    response_model=WritingTokenCountResponse,
    summary="Count tokens for a provider/model",
    tags=["writing"],
)
async def count_writing_tokens(
    payload: WritingTokenCountRequest,
    rate_limiter: RateLimiter = Depends(get_rate_limiter_dep),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("writing.token_count")),
) -> WritingTokenCountResponse:
    await _enforce_rate_limit(rate_limiter, int(current_user.id), "writing.token_count")
    try:
        encoding, tokenizer_name = _resolve_tokenizer(payload.provider, payload.model)
    except TokenizerUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    token_ids = encoding.encode(payload.text, disallowed_special=())
    meta = WritingTokenizeMeta(
        provider=payload.provider,
        model=payload.model,
        tokenizer=tokenizer_name,
        input_chars=len(payload.text),
        token_count=len(token_ids),
        warnings=[],
    )
    return WritingTokenCountResponse(count=len(token_ids), meta=meta)
