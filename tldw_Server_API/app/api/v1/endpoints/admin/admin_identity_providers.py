"""Admin endpoints for enterprise identity provider management."""

from __future__ import annotations

from typing import Annotated, Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, status

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    check_rate_limit,
    get_auth_principal,
)
from tldw_Server_API.app.api.v1.API_Deps.federation_deps import (
    get_federation_provisioning_service_dep,
    get_identity_provider_repo_dep,
    get_oidc_federation_service_dep,
    require_enterprise_federation,
)
from tldw_Server_API.app.api.v1.schemas.identity_provider_schemas import (
    IdentityProviderDryRunRequest,
    IdentityProviderDryRunResponse,
    IdentityProviderGrantSyncPreview,
    IdentityProviderListResponse,
    IdentityProviderMappingResult,
    IdentityProviderMappingPreviewRequest,
    IdentityProviderMappingPreviewResponse,
    IdentityProviderResponse,
    IdentityProviderTestRequest,
    IdentityProviderTestResponse,
    IdentityProviderUpsertRequest,
)
from tldw_Server_API.app.core.AuthNZ.federation.claim_mapping import preview_claim_mapping
from tldw_Server_API.app.core.AuthNZ.federation.oidc_service import OIDCFederationService
from tldw_Server_API.app.core.AuthNZ.federation.provisioning_service import (
    FederationProvisioningService,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.identity_provider_repo import (
    IdentityProviderRepo,
)


router = APIRouter()


async def _validate_provider_for_enablement(
    payload: IdentityProviderUpsertRequest,
    oidc_service: OIDCFederationService,
) -> None:
    """Reject enablement when the provider runtime configuration is invalid."""
    if not payload.enabled:
        return
    try:
        await oidc_service.inspect_provider_configuration(
            provider=payload.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _get_ensure_sqlite_authnz_ready_if_test_mode() -> Callable[[], Awaitable[None]]:
    """Return the shared SQLite AuthNZ bootstrap helper used in tests."""
    from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod

    return admin_mod._ensure_sqlite_authnz_ready_if_test_mode


async def _get_provider_or_404(
    provider_id: int,
    repo: IdentityProviderRepo,
) -> dict[str, object]:
    """Load an identity provider row or raise a 404 error."""
    provider = await repo.get_provider(provider_id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Identity provider not found",
        )
    return provider


@router.post(
    "/identity/providers",
    response_model=IdentityProviderResponse,
    dependencies=[Depends(get_auth_principal), Depends(check_rate_limit)],
)
async def admin_create_identity_provider(
    payload: IdentityProviderUpsertRequest,
    principal: Annotated[AuthPrincipal, Depends(get_auth_principal)],
    repo: Annotated[IdentityProviderRepo, Depends(get_identity_provider_repo_dep)],
    oidc_service: Annotated[OIDCFederationService, Depends(get_oidc_federation_service_dep)],
) -> IdentityProviderResponse:
    """Create a new enterprise identity provider definition."""
    await _get_ensure_sqlite_authnz_ready_if_test_mode()()
    require_enterprise_federation()
    await _validate_provider_for_enablement(payload, oidc_service)
    return await repo.create_provider(
        slug=payload.slug,
        provider_type=payload.provider_type,
        owner_scope_type=payload.owner_scope_type,
        owner_scope_id=payload.owner_scope_id,
        enabled=payload.enabled,
        display_name=payload.display_name,
        issuer=payload.issuer,
        discovery_url=payload.discovery_url,
        authorization_url=payload.authorization_url,
        token_url=payload.token_url,
        jwks_url=payload.jwks_url,
        client_id=payload.client_id,
        client_secret_ref=payload.client_secret_ref,
        claim_mapping=payload.claim_mapping,
        provisioning_policy=payload.provisioning_policy,
        created_by=principal.user_id,
        updated_by=principal.user_id,
    )


@router.get(
    "/identity/providers",
    response_model=IdentityProviderListResponse,
    dependencies=[Depends(get_auth_principal), Depends(check_rate_limit)],
)
async def admin_list_identity_providers(
    repo: Annotated[IdentityProviderRepo, Depends(get_identity_provider_repo_dep)],
    owner_scope_type: str | None = Query(None),
    owner_scope_id: int | None = Query(None, ge=1),
    enabled: bool | None = Query(None),
) -> IdentityProviderListResponse:
    """List identity providers filtered by scope and enabled state."""
    await _get_ensure_sqlite_authnz_ready_if_test_mode()()
    require_enterprise_federation()
    providers = await repo.list_providers(
        owner_scope_type=owner_scope_type,
        owner_scope_id=owner_scope_id,
        enabled=enabled,
    )
    return IdentityProviderListResponse(providers=providers)


@router.post(
    "/identity/providers/test",
    response_model=IdentityProviderTestResponse,
    dependencies=[Depends(get_auth_principal), Depends(check_rate_limit)],
)
async def admin_test_identity_provider(
    payload: IdentityProviderTestRequest,
    oidc_service: Annotated[OIDCFederationService, Depends(get_oidc_federation_service_dep)],
) -> IdentityProviderTestResponse:
    """Validate an unsaved provider configuration and resolve runtime metadata."""
    await _get_ensure_sqlite_authnz_ready_if_test_mode()()
    require_enterprise_federation()
    try:
        result = await oidc_service.inspect_provider_configuration(
            provider=payload.provider.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return IdentityProviderTestResponse.model_validate(result)


@router.post(
    "/identity/providers/dry-run",
    response_model=IdentityProviderDryRunResponse,
    dependencies=[Depends(get_auth_principal), Depends(check_rate_limit)],
)
async def admin_dry_run_identity_provider(
    payload: IdentityProviderDryRunRequest,
    repo: Annotated[IdentityProviderRepo, Depends(get_identity_provider_repo_dep)],
    oidc_service: Annotated[OIDCFederationService, Depends(get_oidc_federation_service_dep)],
    provisioning_service: Annotated[
        FederationProvisioningService,
        Depends(get_federation_provisioning_service_dep),
    ],
) -> IdentityProviderDryRunResponse:
    """Preview provider mapping and provisioning behavior without persisting changes."""
    await _get_ensure_sqlite_authnz_ready_if_test_mode()()
    require_enterprise_federation()

    provider_payload = payload.provider.model_dump()
    if payload.provider_id is not None:
        await _get_provider_or_404(payload.provider_id, repo)
        provider_payload["id"] = int(payload.provider_id)
    try:
        provider_result = await oidc_service.inspect_provider_configuration(
            provider=provider_payload,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    mapping_preview = preview_claim_mapping(
        provider_payload.get("claim_mapping"),
        payload.claims,
    )
    resolution = await provisioning_service.dry_run_login_resolution(
        provider=provider_payload,
        mapped_claims=mapping_preview,
    )
    grant_sync_preview = None
    if resolution["provisioning_action"] in {
        "subject_already_linked",
        "link_existing_user",
        "create_new_user",
    }:
        grant_sync_preview = await provisioning_service.preview_mapped_grants(
            provider=provider_payload,
            user_id=resolution.get("matched_user_id"),
            mapped_claims=mapping_preview,
        )
    combined_warnings = list(
        dict.fromkeys(
            [
                *provider_result.get("warnings", []),
                *mapping_preview.get("warnings", []),
                *resolution.get("warnings", []),
                *(grant_sync_preview.get("warnings", []) if grant_sync_preview else []),
            ]
        )
    )
    return IdentityProviderDryRunResponse(
        provider=IdentityProviderTestResponse.model_validate(provider_result),
        mapping=IdentityProviderMappingResult.model_validate(mapping_preview),
        provisioning_action=resolution["provisioning_action"],
        matched_user_id=resolution.get("matched_user_id"),
        identity_link_found=bool(resolution.get("identity_link_found")),
        email_match_found=bool(resolution.get("email_match_found")),
        grant_sync=(
            IdentityProviderGrantSyncPreview.model_validate(grant_sync_preview)
            if grant_sync_preview is not None
            else None
        ),
        warnings=combined_warnings,
    )


@router.get(
    "/identity/providers/{provider_id}",
    response_model=IdentityProviderResponse,
    dependencies=[Depends(get_auth_principal), Depends(check_rate_limit)],
)
async def admin_get_identity_provider(
    provider_id: int,
    repo: Annotated[IdentityProviderRepo, Depends(get_identity_provider_repo_dep)],
) -> IdentityProviderResponse:
    """Return a single identity provider definition."""
    await _get_ensure_sqlite_authnz_ready_if_test_mode()()
    require_enterprise_federation()
    return await _get_provider_or_404(provider_id, repo)


@router.put(
    "/identity/providers/{provider_id}",
    response_model=IdentityProviderResponse,
    dependencies=[Depends(get_auth_principal), Depends(check_rate_limit)],
)
async def admin_update_identity_provider(
    provider_id: int,
    payload: IdentityProviderUpsertRequest,
    principal: Annotated[AuthPrincipal, Depends(get_auth_principal)],
    repo: Annotated[IdentityProviderRepo, Depends(get_identity_provider_repo_dep)],
    oidc_service: Annotated[OIDCFederationService, Depends(get_oidc_federation_service_dep)],
) -> IdentityProviderResponse:
    """Update an existing enterprise identity provider definition."""
    await _get_ensure_sqlite_authnz_ready_if_test_mode()()
    require_enterprise_federation()
    await _validate_provider_for_enablement(payload, oidc_service)
    updated = await repo.update_provider(
        provider_id,
        slug=payload.slug,
        provider_type=payload.provider_type,
        owner_scope_type=payload.owner_scope_type,
        owner_scope_id=payload.owner_scope_id,
        enabled=payload.enabled,
        display_name=payload.display_name,
        issuer=payload.issuer,
        discovery_url=payload.discovery_url,
        authorization_url=payload.authorization_url,
        token_url=payload.token_url,
        jwks_url=payload.jwks_url,
        client_id=payload.client_id,
        client_secret_ref=payload.client_secret_ref,
        claim_mapping=payload.claim_mapping,
        provisioning_policy=payload.provisioning_policy,
        updated_by=principal.user_id,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Identity provider not found",
        )
    return updated


@router.post(
    "/identity/providers/{provider_id}/mappings/preview",
    response_model=IdentityProviderMappingPreviewResponse,
    dependencies=[Depends(get_auth_principal), Depends(check_rate_limit)],
)
async def admin_preview_identity_provider_mapping(
    provider_id: int,
    payload: IdentityProviderMappingPreviewRequest,
    repo: Annotated[IdentityProviderRepo, Depends(get_identity_provider_repo_dep)],
) -> IdentityProviderMappingPreviewResponse:
    """Preview claim mapping output for a stored provider definition."""
    await _get_ensure_sqlite_authnz_ready_if_test_mode()()
    require_enterprise_federation()
    provider = await _get_provider_or_404(provider_id, repo)
    preview = preview_claim_mapping(
        provider.get("claim_mapping"),
        payload.claims,
    )
    return IdentityProviderMappingPreviewResponse(
        provider_id=provider_id,
        **preview,
    )
