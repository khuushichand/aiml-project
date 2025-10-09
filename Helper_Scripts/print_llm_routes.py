"""
Helper script: Print LLM Providers API routes and tags

Usage:
  python Helper_Scripts/print_llm_routes.py

This builds a minimal FastAPI app with only the LLM Providers router
and prints the HTTP methods, paths, route name, summary, and tags.
It also prints the OpenAPI tags and the subset of OpenAPI paths that
match the LLM Providers endpoints.
"""
from __future__ import annotations

import json
from typing import List

import os
os.environ.setdefault("LOGURU_LEVEL", "ERROR")  # Reduce log noise during introspection

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.openapi.utils import get_openapi


def build_app() -> FastAPI:
    from tldw_Server_API.app.api.v1.endpoints.llm_providers import (
        router as llm_router,
    )

    app = FastAPI(title="LLM Providers Routes Snapshot", version="dev")
    app.include_router(llm_router, prefix="/api/v1", tags=["llm"])
    return app


def print_routes(app: FastAPI) -> None:
    print("== LLM Providers Routes ==")
    routes: List[APIRoute] = [r for r in app.routes if isinstance(r, APIRoute)]
    for r in routes:
        if not r.path.startswith("/api/v1/llm"):
            continue
        methods = sorted({m for m in r.methods if m in {"GET", "POST", "PUT", "PATCH", "DELETE"}})
        summary = (r.summary or "").strip()
        tags = r.tags or []
        name = r.name
        print(f"{'|'.join(methods):<10} {r.path}  name={name}  tags={tags}")
        if summary:
            print(f"  summary: {summary}")


def print_openapi_subset(app: FastAPI) -> None:
    spec = get_openapi(
        title=app.title,
        version=app.version,
        description="",
        routes=app.routes,
    )
    tags = spec.get("tags", [])
    print("\n== OpenAPI Tags ==")
    print(json.dumps(tags, indent=2))

    print("\n== OpenAPI Paths (LLM subset) ==")
    llm_paths = {k: v for k, v in spec.get("paths", {}).items() if k.startswith("/api/v1/llm")}
    print(json.dumps(llm_paths, indent=2))


def main() -> None:
    try:
        app = build_app()
        print_routes(app)
        print_openapi_subset(app)
    except Exception as e:
        print(f"[ERROR] Failed to load LLM Providers routes: {e}")


if __name__ == "__main__":
    main()
