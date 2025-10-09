#!/usr/bin/env python3
"""
Print a minimal snapshot of the unified Evaluations API routes and their tags.

This builds a tiny FastAPI app that only mounts the evaluations_unified router
under /api/v1 and then prints the paths, methods, and primary tags so docs can
be reconciled without running the full server.
"""
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def build_app() -> FastAPI:
    app = FastAPI(title="tldw eval routes snapshot", version="test")
    # Import inside to avoid side effects on module import
    from tldw_Server_API.app.api.v1.endpoints.evaluations_unified import router as eval_router

    # Mount unified router under /api/v1
    app.include_router(eval_router, prefix="/api/v1")
    return app


def main() -> None:
    app = build_app()
    spec = get_openapi(
        title=app.title,
        version=app.version,
        description="",
        routes=app.routes,
    )
    # Print summary: PATH  METHODS  TAGS
    paths = spec.get("paths", {})
    for path in sorted(paths.keys()):
        methods = sorted(m.upper() for m in paths[path].keys())
        # Find tags from first method (all should be the same)
        first_method = next(iter(paths[path].values()))
        tags = first_method.get("tags", [])
        print(f"{path}  |  {','.join(methods)}  |  {','.join(tags)}")


if __name__ == "__main__":
    main()

