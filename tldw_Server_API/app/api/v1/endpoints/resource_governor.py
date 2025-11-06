from __future__ import annotations

from typing import Any, Dict, Optional
import inspect
import os

from fastapi import APIRouter, Depends, Query, Path, Body
from fastapi.responses import JSONResponse
from loguru import logger

from tldw_Server_API.app.main import app as _app

router = APIRouter()


def _get_or_init_governor() -> Optional[Any]:
    """Return the resource governor from app state or lazily initialize it.

    Tries to create a MemoryResourceGovernor using the configured policy loader
    if no governor is currently present. Returns None if initialization fails
    or no loader is available.
    """
    gov = getattr(_app.state, "rg_governor", None)
    if gov is None:
        try:
            from tldw_Server_API.app.core.Resource_Governance import (
                MemoryResourceGovernor,
            )

            loader = getattr(_app.state, "rg_policy_loader", None)
            if loader is not None:
                gov = MemoryResourceGovernor(policy_loader=loader)
                _app.state.rg_governor = gov
        except Exception as e:
            # Keep behavior consistent with previous code path: best-effort only.
            logger.debug(f"Resource governor lazy-init skipped: {e}")
            gov = None
    return gov


@router.get("/resource-governor/policy")
async def get_resource_governor_policy(include: Optional[str] = Query(None, description="Include extra data: 'ids' or 'full'")) -> JSONResponse:
    """
    Return current Resource Governor policy snapshot metadata.

    - include=ids → include policy IDs list
    - include=full → include full policies and tenant payloads (use with caution)
    """
    try:
        loader = getattr(_app.state, "rg_policy_loader", None)
        store = getattr(_app.state, "rg_policy_store", None)
        # If loader missing or points to a different path than RG_POLICY_PATH, (re)initialize
        try:
            env_path = os.getenv("RG_POLICY_PATH")
        except Exception:
            env_path = None
        snap = None
        try:
            snap = loader.get_snapshot() if loader else None
        except Exception:
            snap = None
        needs_reload = False
        if loader is None:
            needs_reload = True
        elif env_path and snap and str(getattr(snap, "source_path", "")) != str(env_path):
            needs_reload = True
        if needs_reload:
            # Best-effort fallback to a default file-based loader using env
            try:
                from tldw_Server_API.app.core.Resource_Governance.policy_loader import PolicyLoader, PolicyReloadConfig, default_policy_loader as _rg_default_loader
                if env_path:
                    reload_enabled = (os.getenv("RG_POLICY_RELOAD_ENABLED", "true").lower() in {"1", "true", "yes"})
                    interval = int(os.getenv("RG_POLICY_RELOAD_INTERVAL_SEC", "10") or "10")
                    loader = PolicyLoader(env_path, PolicyReloadConfig(enabled=reload_enabled, interval_sec=interval))
                else:
                    loader = _rg_default_loader()
                await loader.load_once()
                _app.state.rg_policy_loader = loader
                if store is None:
                    store = "file"
                _app.state.rg_policy_store = store
                # Update snapshot metadata for health/routes that read app.state
                try:
                    snap_meta = loader.get_snapshot()
                    _app.state.rg_policy_version = int(getattr(snap_meta, "version", 0) or 0)
                    _app.state.rg_policy_count = len(getattr(snap_meta, "policies", {}) or {})
                except Exception:
                    pass
            except Exception:
                return JSONResponse({"status": "unavailable", "reason": "policy_loader_not_initialized"}, status_code=503)
        snap = loader.get_snapshot()
        body: Dict[str, Any] = {
            "status": "ok",
            "version": int(getattr(snap, "version", 0) or 0),
            "store": store,
            "policies_count": len(getattr(snap, "policies", {}) or {}),
        }
        if include == "ids":
            body["policy_ids"] = sorted(list((snap.policies or {}).keys()))
        elif include == "full":
            # Caution: large response depending on policy size
            body["policies"] = snap.policies or {}
            body["tenant"] = snap.tenant or {}
        return JSONResponse(body)
    except Exception as e:
        logger.exception("get_resource_governor_policy failed")
        return JSONResponse({"status": "error", "error": "internal server error"}, status_code=500)


# --- Admin endpoints (gated) ---
from pydantic import BaseModel, Field
from tldw_Server_API.app.core.AuthNZ.permissions import RoleChecker
from tldw_Server_API.app.core.Resource_Governance.policy_admin import AuthNZPolicyAdmin


class PolicyUpsertRequest(BaseModel):
    payload: Dict[str, Any] = Field(..., description="Policy payload JSON object")
    version: Optional[int] = Field(None, description="Optional explicit version (auto-increments if omitted)")


@router.put("/resource-governor/policy/{policy_id}")
async def upsert_policy(
    policy_id: str = Path(..., description="Policy identifier, e.g., 'chat.default'"),
    body: PolicyUpsertRequest = Body(...),
    user=Depends(RoleChecker("admin")),
):
    try:
        admin = AuthNZPolicyAdmin()
        await admin.upsert_policy(policy_id, body.payload, version=body.version)
        # Best-effort loader refresh when using DB store
        try:
            if getattr(_app.state, "rg_policy_store", None) == "db":
                loader = getattr(_app.state, "rg_policy_loader", None)
                if loader is not None:
                    await loader.load_once()
        except Exception as _ref_e:
            logger.debug(f"Policy upsert refresh skipped: {_ref_e}")
        return JSONResponse({"status": "ok", "policy_id": policy_id})
    except Exception as e:
        logger.exception("upsert_policy failed")
        return JSONResponse({"status": "error", "error": "internal server error"}, status_code=500)


@router.delete("/resource-governor/policy/{policy_id}")
async def delete_policy(
    policy_id: str = Path(..., description="Policy identifier"),
    user=Depends(RoleChecker("admin")),
):
    try:
        admin = AuthNZPolicyAdmin()
        deleted = await admin.delete_policy(policy_id)
        # Best-effort loader refresh when using DB store
        try:
            if getattr(_app.state, "rg_policy_store", None) == "db":
                loader = getattr(_app.state, "rg_policy_loader", None)
                if loader is not None:
                    await loader.load_once()
        except Exception as _ref_e:
            logger.debug(f"Policy delete refresh skipped: {_ref_e}")
        return JSONResponse({"status": "ok", "deleted": int(deleted)})
    except Exception as e:
        logger.exception("delete_policy failed")
        return JSONResponse({"status": "error", "error": "internal server error"}, status_code=500)


@router.get("/resource-governor/policies")
async def list_policies(user=Depends(RoleChecker("admin"))):
    try:
        admin = AuthNZPolicyAdmin()
        rows = await admin.list_policies()
        return JSONResponse({"status": "ok", "items": rows, "count": len(rows)})
    except Exception as e:
        logger.exception("list_policies failed")
        return JSONResponse({"status": "error", "error": "internal server error"}, status_code=500)


@router.get("/resource-governor/policy/{policy_id}")
async def get_policy(policy_id: str = Path(..., description="Policy identifier"), user=Depends(RoleChecker("admin"))):
    try:
        admin = AuthNZPolicyAdmin()
        rec = await admin.get_policy_record(policy_id)
        if not rec:
            return JSONResponse({"status": "not_found", "policy_id": policy_id}, status_code=404)
        return JSONResponse({"status": "ok", **rec})
    except Exception as e:
        logger.exception("get_policy failed")
        return JSONResponse({"status": "error", "error": "internal server error"}, status_code=500)


# --- Diagnostics (admin) ---
@router.get("/resource-governor/diag/peek")
async def rg_diag_peek(
    entity: str = Query(..., description="Entity key, e.g., 'user:123'"),
    categories: str = Query(..., description="Comma-separated categories, e.g., 'requests,tokens'"),
    user=Depends(RoleChecker("admin")),
):
    try:
        gov = _get_or_init_governor()
        if gov is None:
            return JSONResponse({"status": "unavailable", "reason": "governor_not_initialized"}, status_code=503)
        cats = [c.strip() for c in categories.split(",") if c.strip()]
        data = gov.peek(entity, cats)
        if inspect.isawaitable(data):
            data = await data
        return JSONResponse({"status": "ok", "entity": entity, "data": data})
    except Exception as e:
        logger.exception("rg_diag_peek failed")
        return JSONResponse({"status": "error", "error": "internal server error"}, status_code=500)


@router.get("/resource-governor/diag/query")
async def rg_diag_query(
    entity: str = Query(..., description="Entity key, e.g., 'user:123'"),
    category: str = Query(..., description="Category name, e.g., 'requests'"),
    user=Depends(RoleChecker("admin")),
):
    try:
        gov = _get_or_init_governor()
        if gov is None:
            return JSONResponse({"status": "unavailable", "reason": "governor_not_initialized"}, status_code=503)
        data = gov.query(entity, category)
        if inspect.isawaitable(data):
            data = await data
        return JSONResponse({"status": "ok", "entity": entity, "category": category, "data": data})
    except Exception as e:
        logger.exception("rg_diag_query failed")
        return JSONResponse({"status": "error", "error": "internal server error"}, status_code=500)


@router.get("/resource-governor/diag/capabilities")
async def rg_diag_capabilities(user=Depends(RoleChecker("admin"))):
    """Tiny capability probe to report whether Lua or fallback paths are in use."""
    try:
        gov = _get_or_init_governor()
        if gov is None:
            return JSONResponse({"status": "unavailable", "reason": "governor_not_initialized"}, status_code=503)
        caps_fn = getattr(gov, "capabilities", None)
        if callable(caps_fn):
            caps = caps_fn()
            if inspect.isawaitable(caps):
                caps = await caps
        else:
            caps = {"backend": "unknown"}
        return JSONResponse({"status": "ok", "capabilities": caps})
    except Exception as e:
        logger.exception("rg_diag_capabilities failed")
        return JSONResponse({"status": "error", "error": "internal server error"}, status_code=500)
