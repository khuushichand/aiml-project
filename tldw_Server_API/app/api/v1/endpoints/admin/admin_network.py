from __future__ import annotations

from fastapi import APIRouter, Request

from tldw_Server_API.app.services import admin_network_service

router = APIRouter()


@router.get("/network-info")
async def network_info(request: Request):
    return admin_network_service.build_network_info(request)
