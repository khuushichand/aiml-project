#!/usr/bin/env python3
"""
Print a minimal snapshot of the Chat routes and OpenAPI info without importing
heavy DB dependencies. This script stubs modules that the chat endpoint imports
only for typing/DB access so FastAPI can build the route table.

Usage:
  python -m Helper_Scripts.print_chat_routes
"""
from __future__ import annotations

import sys
import types
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def _install_stub_modules():
    # Stub DB module used by chat endpoint
    ccdb = types.ModuleType("tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB")
    class _StubDB:  # minimal placeholder
        pass
    class CharactersRAGDBError(Exception):
        pass
    class SchemaError(Exception):
        pass
    class ConflictError(Exception):
        pass
    class InputError(Exception):
        pass
    ccdb.CharactersRAGDB = _StubDB
    ccdb.CharactersRAGDBError = CharactersRAGDBError
    ccdb.SchemaError = SchemaError
    ccdb.ConflictError = ConflictError
    ccdb.InputError = InputError
    sys.modules["tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB"] = ccdb

    # Stub async DB wrapper
    adb = types.ModuleType("tldw_Server_API.app.core.DB_Management.async_db_wrapper")
    def create_async_db(db):
        return db
    adb.create_async_db = create_async_db
    sys.modules["tldw_Server_API.app.core.DB_Management.async_db_wrapper"] = adb


def main() -> int:
    _install_stub_modules()
    from tldw_Server_API.app.api.v1.endpoints.chat import router as chat_router

    app = FastAPI()
    app.include_router(chat_router, prefix="/api/v1/chat")
    spec = get_openapi(title="chat", version="test", description="", routes=app.routes)

    print("TAGS:", [t.get("name") for t in spec.get("tags", [])])
    print("PATHS:")
    for path, methods in sorted(spec.get("paths", {}).items()):
        print(path, sorted(methods.keys()))
        for method, info in methods.items():
            print("  ", method, "|", info.get("summary"), "|", info.get("tags"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
