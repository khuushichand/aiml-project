# User_DB_Handling.py
# Description: Handles user authentication and identification based on application mode.
#
# Imports
import hmac
from typing import Optional, List, Dict, Any, Union
#
# 3rd-Party Libraries
from fastapi import Depends, HTTPException, status, Header, Request
from pydantic import BaseModel, ValidationError, Field
#
# Local Imports
# New unified settings
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
# New JWT service
from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.AuthNZ.exceptions import InvalidTokenError, TokenExpiredError
from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager
from tldw_Server_API.app.core.DB_Management.scope_context import set_scope
from tldw_Server_API.app.core.AuthNZ.orgs_teams import list_memberships_for_user
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.rbac_repo import AuthnzRbacRepo
from tldw_Server_API.app.core.AuthNZ.rbac import get_effective_permissions
# Utils
from loguru import logger
# API Dependencies
from tldw_Server_API.app.api.v1.API_Deps.v1_endpoint_deps import oauth2_scheme
from tldw_Server_API.app.core.config import settings as app_settings

#######################################################################################################################


_RBAC_ENRICH_REPO = AuthnzRbacRepo(client_id="authnz_user_enrichment")


def _enrich_user_with_rbac(
    user_id: Optional[int],
    user_data: dict,
    *,
    pii_redact_logs: bool = False,
) -> tuple[list[str], list[str], bool]:
    """
    Fetch roles/permissions/admin flag for a user from central RBAC tables.
    """
    roles: list[str] = []
    perms: list[str] = []
    is_admin_flag = bool(user_data.get("is_superuser") or user_data.get("is_admin"))
    if user_id is None:
        return roles, perms, is_admin_flag

    base_perms: set[str] = set()

    # Roles from centralized RBAC repository
    try:
        role_rows = _RBAC_ENRICH_REPO.get_user_roles(int(user_id))
        for row in role_rows or []:
            role_name = row.get("name") or row.get("role") or row.get("role_name")
            if role_name:
                role_str = str(role_name)
                if role_str not in roles:
                    roles.append(role_str)
        if "admin" in roles:
            is_admin_flag = True
    except Exception as rb_exc:
        if pii_redact_logs:
            logger.debug("RBAC enrichment failed for user roles (details redacted)")
        else:
            logger.debug(f"RBAC enrichment failed for user {user_id} roles: {rb_exc}")

    # Effective permissions from RBAC helper (roles + user overrides)
    try:
        base_perms = set(get_effective_permissions(int(user_id)))
    except Exception as rb_exc:
        if pii_redact_logs:
            logger.debug("RBAC enrichment failed for permissions (details redacted)")
        else:
            logger.debug(f"RBAC enrichment failed for user {user_id} permissions: {rb_exc}")

    # Fallback: honor legacy role column when user_roles entries are absent
    if not roles:
        implicit_role = user_data.get("role")
        if implicit_role:
            try:
                rname = str(implicit_role)
                roles.append(rname)
                if rname == "admin":
                    is_admin_flag = True
                try:
                    role_row_id = _RBAC_ENRICH_REPO.get_role_id_by_name(rname)
                except Exception as rb_exc_lookup:  # pragma: no cover - best-effort lookup
                    role_row_id = None
                    if pii_redact_logs:
                        logger.debug("RBAC fallback (role column) lookup failed [redacted]")
                    else:
                        logger.debug(
                            f"RBAC fallback (role column) lookup failed for role {implicit_role}: {rb_exc_lookup}"
                        )
                if role_row_id is not None:
                    try:
                        rp_rows_fallback = _RBAC_ENRICH_REPO.get_role_effective_permissions(role_row_id)
                        for pname in rp_rows_fallback.get("all_permissions", []):
                            if pname:
                                base_perms.add(str(pname))
                    except Exception as rb_exc_fallback:  # pragma: no cover - fallback best-effort
                        if pii_redact_logs:
                            logger.debug("RBAC fallback (role column) failed [redacted]")
                        else:
                            logger.debug(
                                f"RBAC fallback (role column) failed for role {implicit_role}: {rb_exc_fallback}"
                            )
            except Exception as rb_exc_outer:  # pragma: no cover - guard against unexpected shapes
                if pii_redact_logs:
                    logger.debug("RBAC fallback (role column) outer failure [redacted]")
                else:
                    logger.debug(
                        f"RBAC fallback (role column) outer failure for role {implicit_role}: {rb_exc_outer}"
                    )

    perms = sorted(base_perms)
    if is_admin_flag:
        perms = sorted(set(perms) | {"system.configure"})

    return roles, perms, is_admin_flag

# --- User Model ---
# Standardized User object, used even for the dummy single user.
class User(BaseModel):
    # Accept either integer DB ids or string tenant-style ids in tests
    id: Union[int, str]
    username: str
    email: Optional[str] = None
    is_active: bool = True
    # Optional tenant field for multi-tenant-aware endpoints/tests
    tenant_id: Optional[str] = None
    # RBAC/claims exposure
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    is_admin: bool = False

    # Convenience properties for downstream code that expects int ids
    @property
    def id_int(self) -> Optional[int]:
        try:
            return int(self.id)  # type: ignore[arg-type]
        except Exception:
            return None

    @property
    def id_str(self) -> str:
        try:
            return str(self.id)
        except Exception:
            return ""

# --- Single User "Dummy" Object ---
# Created when in single-user mode using values from the settings
_single_user_instance: Optional[User] = None

def get_single_user_instance() -> User:
    """Get or create the single user instance"""
    global _single_user_instance
    settings = get_settings()
    desired_id = settings.SINGLE_USER_FIXED_ID

    if (
        _single_user_instance is None
        or getattr(_single_user_instance, "id", None) != desired_id
    ):
        _single_user_instance = User(
            id=desired_id,
            username="single_user",
            is_active=True
        )
    return _single_user_instance

# Eagerly initialize for environments/tests that mutate the module-level reference directly.
try:
    _single_user_instance = get_single_user_instance()
except Exception:
    _single_user_instance = None

#######################################################################################################################

# --- Verification Dependencies ---

async def verify_single_user_api_key(
    _request: Request,
    api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> bool:
    """
    Dependency to verify that the provided credentials correspond to the
    bootstrapped single-user admin principal.

    This helper no longer branches on AUTH_MODE. Instead, it:
    - Extracts the candidate API key from headers (X-API-KEY or Bearer).
    - Uses the standard API-key authentication flow to resolve a User.
    - Asserts that the resolved user id matches SINGLE_USER_FIXED_ID.
    """
    settings = get_settings()
    expected_user_id = getattr(settings, "SINGLE_USER_FIXED_ID", 1)

    # Derive the presented API key from headers
    provided = api_key or ""
    if not provided and authorization:
        try:
            scheme, _, credential = authorization.partition(" ")
            if scheme.lower() == "bearer":
                provided = credential.strip()
        except Exception:
            provided = ""

    if not provided:
        if settings.PII_REDACT_LOGS:
            logger.warning("Invalid or missing API Key for single-user verification (no credentials)")
        else:
            logger.warning("Invalid or missing API Key for single-user verification: '<missing>'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )

    # Use the shared API-key authentication path so that verification is
    # driven by AuthNZ tables and RBAC rather than inline comparisons.
    user = await authenticate_api_key_user(_request, provided)

    try:
        user_id_val = getattr(user, "id_int", None)
        if user_id_val is None:
            user_id_val = int(getattr(user, "id"))
    except Exception:
        user_id_val = None

    if user_id_val != expected_user_id:
        if settings.PII_REDACT_LOGS:
            logger.warning("API Key resolved to non-single-user principal during single-user verification")
        else:
            logger.warning(
                f"API Key resolved to user_id={user_id_val} during single-user verification; "
                f"expected {expected_user_id}"
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )

    logger.debug("Single-user API Key verified successfully via AuthNZ store.")
    return True


async def verify_jwt_and_fetch_user(request: Request, token: str = Depends(oauth2_scheme)) -> User:
    """
    Dependency to verify JWT and fetch user details.

    Uses the new JWT service for token validation and is agnostic to
    AUTH_MODE; callers decide whether JWTs are appropriate for their
    deployment via configuration and routing, not via this helper.
    """

    # Import Users_DB here to avoid import errors in single-user mode
    try:
        from tldw_Server_API.app.core.DB_Management.Users_DB import (
            get_user_by_id,
            get_user_by_uuid,
            get_user_by_username,
            UserNotFoundError,
        )
    except ImportError:
        logger.error("Multi-user mode requires Users_DB module, but it's not available.")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Multi-user mode requires Users_DB implementation."
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    pii_redact_logs = get_settings().PII_REDACT_LOGS

    # Use new JWT service to decode token
    jwt_service = get_jwt_service()
    try:
        payload = jwt_service.decode_access_token(token)
        raw_subject = payload.get("user_id") or payload.get("sub")  # Handle both formats
        if raw_subject is None:
            logger.warning("Token payload missing user_id/sub claim")
            raise credentials_exception

        user_id_int: Optional[int] = None
        if isinstance(raw_subject, int):
            user_id_int = raw_subject
        elif isinstance(raw_subject, str):
            try:
                user_id_int = int(raw_subject)
            except ValueError:
                user_id_int = None
        else:
            # Leave as-is; downstream lookups will attempt to resolve
            user_id_int = None
    except (InvalidTokenError, TokenExpiredError) as e:
        logger.warning(f"Token validation failed: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Unexpected error decoding token: {e}")
        raise credentials_exception

    if pii_redact_logs:
        logger.debug("Token decoded successfully for authenticated subject (redacted)")
    else:
        logger.debug(f"Token decoded successfully for subject: {raw_subject}")

    # Enforce blacklist revocation (fail-closed)
    try:
        session_manager = await get_session_manager()
        if await session_manager.is_token_blacklisted(token, payload.get("jti")):
            logger.warning("Token has been revoked according to blacklist/session state")
            raise credentials_exception
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error checking token blacklist: {exc}")
        raise credentials_exception

    # --- Fetch and Validate User Data ---
    subject_identifier = user_id_int if user_id_int is not None else raw_subject
    user_data: Optional[dict] = None
    try:
        if user_id_int is not None:
            user_data = await get_user_by_id(user_id_int)
        else:
            identifier_str = str(raw_subject)
            user_data = await get_user_by_uuid(identifier_str)
            if not user_data and payload.get("username"):
                # Fallback to username claim when UUID lookup misses
                user_data = await get_user_by_username(str(payload["username"]))

        if not user_data:
            if pii_redact_logs:
                logger.warning("User record for authenticated subject not found.")
            else:
                logger.warning(f"User record for subject '{subject_identifier}' not found.")
            raise credentials_exception

        if not isinstance(user_data, dict):
            data_type = type(user_data)
            if pii_redact_logs:
                logger.error(f"Data retrieved for authenticated subject is not a dictionary (type: {data_type}).")
            else:
                logger.error(f"Data retrieved for subject {subject_identifier} is not a dictionary (type: {data_type}).")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error retrieving user data format."
            )

    except UserNotFoundError:
        if pii_redact_logs:
            logger.warning("User referenced by token not found in Users_DB (UserNotFoundError).")
        else:
            logger.warning(f"User with ID {subject_identifier} from token not found in Users_DB (UserNotFoundError).")
        raise credentials_exception
    except HTTPException:
        raise
    except Exception as e:
        if pii_redact_logs:
            logger.error("Error fetching user (details redacted) from Users_DB", exc_info=True)
        else:
            logger.error(f"Error fetching user {subject_identifier} from Users_DB: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user information."
        )

    # Prepare numeric ID (if available) for downstream lookups
    subject_db_id_raw = user_data.get("id")
    try:
        subject_db_id_int = int(subject_db_id_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        subject_db_id_int = None

    # --- Enrich with roles/permissions from central AuthNZ RBAC tables ---
    roles, perms, is_admin = _enrich_user_with_rbac(
        subject_db_id_int, user_data, pii_redact_logs=pii_redact_logs
    )

    # --- Create and validate the User Pydantic model ---
    try:
        user = User(**{**user_data, "roles": roles, "permissions": perms, "is_admin": is_admin})
    except ValidationError as e:  # Catch Pydantic validation errors specifically
        if pii_redact_logs:
            logger.error("Failed to validate user data for authenticated user into User model (details redacted)", exc_info=True)
        else:
            logger.error(f"Failed to validate user data for user {subject_identifier} into User model: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing user data: Invalid format - {e}"
        )
    except Exception as e:  # Catch other potential errors during model creation
        if pii_redact_logs:
            logger.error("Unexpected error creating User model for authenticated user (details redacted)", exc_info=True)
        else:
            logger.error(f"Unexpected error creating User model for user {subject_identifier}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error processing user data."
        )

    # --- Final User Status Check ---
    if not user.is_active:
        if pii_redact_logs:
            logger.warning("Authentication attempt by inactive user (details redacted)")
        else:
            logger.warning(f"Authentication attempt by inactive user: {user.username} (ID: {user.id})")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    # Attach user id for downstream context (usage logging, RBAC rate limits)
    try:
        request.state.user_id = user.id
    except Exception:
        pass

    team_ids: List[int] = []
    org_ids: List[int] = []
    try:
        membership_lookup_id = user.id_int
        if membership_lookup_id is None:
            raise ValueError("User ID is non-numeric; skipping membership lookup.")
        memberships = await list_memberships_for_user(membership_lookup_id)
        team_ids = [m.get("team_id") for m in memberships if m.get("team_id") is not None]
        org_ids = sorted({m.get("org_id") for m in memberships if m.get("org_id") is not None})
        try:
            request.state.team_ids = team_ids
            request.state.org_ids = org_ids
        except Exception:
            pass
    except Exception:
        try:
            request.state.team_ids = []
            request.state.org_ids = []
        except Exception:
            pass

    try:
        set_scope(
            user_id=user.id_int,
            org_ids=org_ids,
            team_ids=team_ids,
            is_admin=bool(user.is_admin),
        )
    except Exception as scope_exc:
        if pii_redact_logs:
            logger.debug(f"Failed to set scope context for authenticated user (redacted): {scope_exc}")
        else:
            logger.debug(f"Failed to set scope context for user {user.id}: {scope_exc}")

    # Populate AuthContext for compatibility with the new principal model
    try:
        principal = AuthPrincipal(
            kind="user",
            user_id=user.id_int,
            api_key_id=None,
            subject=None,
            token_type="access",
            jti=None,
            roles=list(user.roles or []),
            permissions=list(user.permissions or []),
            is_admin=bool(user.is_admin),
            org_ids=org_ids,
            team_ids=team_ids,
        )
        ip = request.client.host if getattr(request, "client", None) else None
        user_agent = request.headers.get("User-Agent") if getattr(request, "headers", None) else None
        request_id = (
            request.headers.get("X-Request-ID") if getattr(request, "headers", None) else None
        ) or getattr(request.state, "request_id", None)
        request.state.auth = AuthContext(
            principal=principal,
            ip=ip,
            user_agent=user_agent,
            request_id=request_id,
        )
    except Exception:
        logger.exception("Unable to populate AuthContext in verify_jwt_and_fetch_user")

    if pii_redact_logs:
        logger.info("Authenticated active user (details redacted)")
    else:
        logger.info(f"Authenticated active user: {user.username} (ID: {user.id})")
    return user


# --- Combined Primary Authentication Dependency ---


async def authenticate_api_key_user(request: Request, api_key: str) -> User:
    """
    Validate an API key in multi-user mode and return the associated User.

    This helper centralizes API-key authentication so that both legacy
    dependencies (get_request_user) and the AuthPrincipal resolver can
    share the same behavior and context population.
    """
    settings = get_settings()

    try:
        api_mgr = await get_api_key_manager()
        client_ip = None
        try:
            client = getattr(request, "client", None)
            if client is not None:
                client_ip = getattr(client, "host", None)
        except Exception:
            client_ip = None

        key_info = await api_mgr.validate_api_key(api_key=api_key, ip_address=client_ip)
        if not key_info:
            logger.warning("Multi-User Mode: Invalid X-API-KEY presented.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

        user_id = key_info.get("user_id")
        if not isinstance(user_id, int):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

        from tldw_Server_API.app.core.DB_Management.Users_DB import (
            get_user_by_id as _get_user,
        )

        user_data = await _get_user(user_id)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        # Normalize active flag
        is_active_value = user_data.get("is_active", True)
        is_active_normalized = bool(is_active_value)
        user_data["is_active"] = is_active_normalized
        if not is_active_normalized:
            if settings.PII_REDACT_LOGS:
                logger.warning("Authentication attempt by inactive user (API key)")
            else:
                logger.warning(
                    f"Authentication attempt by inactive user (API key): {user_data.get('username', user_id)}"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user",
            )

        if user_data.get("is_superuser"):
            user_data.setdefault("is_admin", True)

        roles, perms, is_admin_flag = _enrich_user_with_rbac(
            user_id, user_data, pii_redact_logs=getattr(settings, "PII_REDACT_LOGS", False)
        )

        user_data["roles"] = roles
        user_data["permissions"] = perms
        user_data["is_admin"] = bool(is_admin_flag)

        # Attach context for downstream consumers
        try:
            request.state.user_id = user_id
            request.state.api_key_id = key_info.get("id")
            # Attach org/team context if present (virtual keys)
            try:
                if key_info.get("org_id") is not None:
                    request.state.org_id = key_info.get("org_id")
                if key_info.get("team_id") is not None:
                    request.state.team_id = key_info.get("team_id")
            except Exception as e:
                logger.debug(f"Unable to attach org/team context: {e}")
        except Exception as ctx_state_exc:
            logger.debug(f"Unable to attach user/api_key context to request.state: {ctx_state_exc}")

        user_obj = User(**user_data)

        team_ids: List[int] = []
        org_ids: List[int] = []
        try:
            memberships = await list_memberships_for_user(int(user_id))
            team_ids = [
                m.get("team_id")
                for m in memberships
                if m.get("team_id") is not None
            ]
            org_ids = sorted(
                {m.get("org_id") for m in memberships if m.get("org_id") is not None}
            )
            try:
                request.state.team_ids = team_ids
                request.state.org_ids = org_ids
            except Exception as team_ctx_exc:
                logger.debug(f"Unable to attach team/org ids to request.state: {team_ctx_exc}")
        except Exception as memberships_exc:
            logger.debug(f"Membership lookup failed for user {user_id}: {memberships_exc}")
            try:
                request.state.team_ids = []
                request.state.org_ids = []
            except Exception as empty_ctx_exc:
                logger.debug(f"Unable to set empty team/org ids on request.state: {empty_ctx_exc}")

        try:
            set_scope(
                user_id=user_obj.id_int,
                org_ids=org_ids,
                team_ids=team_ids,
                is_admin=bool(user_obj.is_admin),
            )
        except Exception as scope_exc:
            logger.debug(
                f"Scope context setup failed for API key user {user_id}: {scope_exc}"
            )

        # Populate AuthContext for API-key-based principals
        try:
            api_key_id_val = None
            raw_key_id = key_info.get("id")
            if raw_key_id is not None:
                try:
                    api_key_id_val = int(raw_key_id)
                except Exception:
                    api_key_id_val = None

            subject_val: Optional[str] = None
            try:
                single_id = getattr(settings, "SINGLE_USER_FIXED_ID", None)
                if single_id is not None and user_obj.id_int == int(single_id):
                    subject_val = "single_user"
            except Exception:
                subject_val = None

            principal = AuthPrincipal(
                kind="api_key",
                user_id=user_obj.id_int,
                api_key_id=api_key_id_val,
                subject=subject_val,
                token_type="api_key",
                jti=None,
                roles=list(user_obj.roles or []),
                permissions=list(user_obj.permissions or []),
                is_admin=bool(user_obj.is_admin),
                org_ids=org_ids,
                team_ids=team_ids,
            )
            ip = request.client.host if getattr(request, "client", None) else None
            user_agent = (
                request.headers.get("User-Agent")
                if getattr(request, "headers", None)
                else None
            )
            request_id = (
                request.headers.get("X-Request-ID")
                if getattr(request, "headers", None)
                else None
            ) or getattr(request.state, "request_id", None)

            request.state.auth = AuthContext(
                principal=principal,
                ip=ip,
                user_agent=user_agent,
                request_id=request_id,
            )
            # Cache the resolved user for downstream adapters
            try:
                request.state._auth_user = user_obj
            except Exception as cache_exc:
                logger.debug(f"Failed to cache _auth_user on request.state: {cache_exc}")
        except Exception as ctx_exc:
            logger.debug(
                f"Unable to populate AuthContext in authenticate_api_key_user: {ctx_exc}"
            )

        return user_obj
    except HTTPException:
        raise
    except Exception as e:
        # Avoid logging exception messages directly to prevent leaking secrets
        # from API key validation paths; log only the exception type.
        logger.error(
            "Error validating API key in multi-user mode (type={})",
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed due to internal error",
        ) from e

async def get_request_user(
    request: Request,
    api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    token: Optional[str] = Depends(oauth2_scheme),  # Bearer from Authorization
    legacy_token_header: Optional[str] = Header(None, alias="Token"),  # Back-compat for chat endpoint tests
) -> User:
    """
    Unified authentication dependency for endpoints that require a User.

    Behavior:
    - Uses the shared JWT/API-key helpers (verify_jwt_and_fetch_user,
      authenticate_api_key_user) for all deployments.
    - Does not branch on AUTH_MODE; single-user deployments authenticate
      via the same AuthNZ tables and RBAC as multi-user, with the
      bootstrapped admin treated as a normal user with roles/permissions.
    """
    # Test-mode bypasses are disabled in production for safety
    try:
        import os as _os
        _prod = _os.getenv("tldw_production", "false").lower() in {"1", "true", "yes", "on", "y"}
        # Test-mode bypass for evaluations when admin gating is explicitly disabled
        if (
            not _prod
            and _os.getenv("TESTING", "").lower() in {"1", "true", "yes", "on"}
            and _os.getenv("EVALS_HEAVY_ADMIN_ONLY", "true").lower() not in {"1", "true", "yes", "on"}
        ):
            logger.info(
                "TESTING with EVALS_HEAVY_ADMIN_ONLY disabled: "
                "bypassing auth, returning single-user test instance"
            )
            return get_single_user_instance()
    except Exception as env_exc:
        logger.debug(
            f"get_request_user: test-mode bypass env detection failed; continuing with normal auth: {env_exc}"
        )

    # Warn if test flags are present in production deployments
    try:
        import os as _os
        _prod = _os.getenv("tldw_production", "false").lower() in {"1", "true", "yes", "on", "y"}
        if _prod and (
            _os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes", "on"}
            or _os.getenv("TESTING", "").lower() in {"1", "true", "yes", "on"}
        ):
            if not getattr(get_request_user, "_warned_testflags_prod", False):
                logger.warning(
                    "TEST flags detected while tldw_production=true; "
                    "test-only auth bypasses are disabled."
                )
                setattr(get_request_user, "_warned_testflags_prod", True)
    except Exception as warn_exc:
        logger.debug(
            f"get_request_user: production test-flag warning emission failed; continuing without warning: {warn_exc}"
        )

    # Fast-path: if an AuthPrincipal has already been resolved, reuse the cached
    # _auth_user instead of re-running authentication logic.
    try:
        existing_ctx = getattr(request.state, "auth", None)
        cached_user = getattr(request.state, "_auth_user", None)
        if isinstance(existing_ctx, AuthContext) and isinstance(cached_user, User):
            logger.debug("get_request_user: Reusing cached AuthPrincipal/_auth_user from request.state.")
            return cached_user
    except Exception as fastpath_exc:
        # Fall through to normal auth paths on any issues, but make failures observable.
        logger.debug(
            f"get_request_user fast-path reuse failed; falling back to normal auth: {fastpath_exc}"
        )

    # Backwards-compatibility: treat a legacy "Token: Bearer <API_KEY>" header as an
    # API key when X-API-KEY is absent.
    if api_key is None and legacy_token_header and isinstance(legacy_token_header, str):
        extracted = None
        try:
            legacy_token_header = legacy_token_header.strip()
            if legacy_token_header.lower().startswith("bearer "):
                extracted = legacy_token_header[len("Bearer ") :].strip()
        except Exception:
            extracted = None
        if extracted:
            api_key = extracted

    # Prefer Bearer JWT when present; otherwise fall back to API key.
    if token:
        logger.debug("get_request_user: Attempting JWT-based authentication.")
        user = await verify_jwt_and_fetch_user(request, token)
        # verify_jwt_and_fetch_user already sets request.state.auth; cache user for fast-path reuse.
        try:
            request.state._auth_user = user
        except Exception as cache_exc:
            logger.debug(f"Failed to cache _auth_user on request.state: {cache_exc}")
        return user

    if api_key:
        logger.debug("get_request_user: Attempting API-key-based authentication.")
        return await authenticate_api_key_user(request, api_key)

    # Neither Bearer token nor API key provided
    logger.warning(
        "get_request_user: No credentials provided (missing Bearer token or X-API-KEY)."
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated (provide Bearer token or X-API-KEY)",
        headers={"WWW-Authenticate": "Bearer"},
    )



#
# End of User_DB_Handling.py
#######################################################################################################################
