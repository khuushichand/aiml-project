# vector_stores_openai.py
# OpenAI-compatible Vector Store API backed by ChromaDB

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import (
    VectorStoreConfig, VectorStoreType,
)
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.chromadb_adapter import ChromaDBAdapter
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import (
    create_embeddings_batch,
)

router = APIRouter(
    tags=["Vector Stores"],
)


# ==========================
# Schemas (OpenAI-like)
# ==========================

class VectorStoreCreate(BaseModel):
    name: Optional[str] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    embedding_model: Optional[str] = Field(default=None, description="Model id for embeddings metadata")
    dimensions: int = Field(..., gt=0)


class VectorStoreObject(BaseModel):
    id: str
    object: str = "vector_store"
    name: Optional[str] = None
    created_at: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    dimensions: int


class VectorRecord(BaseModel):
    id: Optional[str] = None
    values: Optional[List[float]] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpsertVectorsRequest(BaseModel):
    records: List[VectorRecord]


class VectorItem(BaseModel):
    id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    content: Optional[str] = None


class QueryRequest(BaseModel):
    query: Optional[str] = None
    vector: Optional[List[float]] = None
    top_k: int = Field(default=10, gt=0, le=100)
    filter: Optional[Dict[str, Any]] = None


def _adapter_for_user(user: User, embedding_dim: int) -> ChromaDBAdapter:
    cfg = VectorStoreConfig(
        store_type=VectorStoreType.CHROMADB,
        connection_params={"use_default": True},
        embedding_dim=embedding_dim,
        user_id=str(getattr(user, 'id', settings.get("SINGLE_USER_FIXED_ID", "1")))
    )
    return ChromaDBAdapter(cfg)


def _vs_id() -> str:
    return f"vs_{uuid.uuid4().hex[:24]}"


def _now_ts() -> int:
    return int(time.time())


@router.post("/vector_stores", response_model=VectorStoreObject)
async def create_vector_store(
    payload: VectorStoreCreate = Body(...),
    current_user: User = Depends(get_request_user),
):
    if payload.dimensions <= 0:
        raise HTTPException(400, detail="dimensions must be > 0")

    store_id = _vs_id()
    created = _now_ts()
    name = payload.name or store_id

    adapter = _adapter_for_user(current_user, payload.dimensions)
    await adapter.initialize()

    # Use store_id as collection name for uniqueness; keep human name in metadata
    metadata = dict(payload.metadata or {})
    metadata.update({
        "openai_id": store_id,
        "name": name,
        "created_at": created,
        "embedding_model": payload.embedding_model or "",
        "embedding_dimension": payload.dimensions,
        "owner": str(getattr(current_user, 'id', '1')),
    })
    await adapter.create_collection(store_id, metadata=metadata)

    return VectorStoreObject(
        id=store_id,
        name=name,
        created_at=created,
        metadata=metadata,
        dimensions=payload.dimensions,
    )


@router.get("/vector_stores")
async def list_vector_stores(
    current_user: User = Depends(get_request_user)
):
    # We need a dimension to init adapter; use a reasonable default
    adapter = _adapter_for_user(current_user, embedding_dim=1536)
    await adapter.initialize()
    stores = []
    for col_name in await adapter.list_collections():
        try:
            stats = await adapter.get_collection_stats(col_name)
            md = stats.get("metadata", {}) or {}
            stores.append({
                "id": md.get("openai_id", col_name),
                "object": "vector_store",
                "name": md.get("name", col_name),
                "created_at": md.get("created_at", _now_ts()),
                "metadata": md,
                "dimensions": stats.get("dimension", 1536)
            })
        except Exception:
            continue
    return {"data": stores}


@router.get("/vector_stores/{store_id}", response_model=VectorStoreObject)
async def get_vector_store(
    store_id: str = Path(...),
    current_user: User = Depends(get_request_user)
):
    adapter = _adapter_for_user(current_user, embedding_dim=1536)
    await adapter.initialize()
    stats = await adapter.get_collection_stats(store_id)
    md = stats.get("metadata", {}) or {}
    return VectorStoreObject(
        id=md.get("openai_id", store_id),
        name=md.get("name", store_id),
        created_at=md.get("created_at", _now_ts()),
        metadata=md,
        dimensions=stats.get("dimension", 1536)
    )


class VectorStoreUpdate(BaseModel):
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.patch("/vector_stores/{store_id}", response_model=VectorStoreObject)
async def update_vector_store(
    store_id: str = Path(...),
    payload: VectorStoreUpdate = Body(...),
    current_user: User = Depends(get_request_user)
):
    adapter = _adapter_for_user(current_user, embedding_dim=1536)
    await adapter.initialize()
    # Fetch current stats then write metadata
    stats = await adapter.get_collection_stats(store_id)
    md = stats.get("metadata", {}) or {}
    if payload.name:
        md["name"] = payload.name
    if payload.metadata:
        md.update(payload.metadata)

    # Use underlying manager to modify metadata
    collection = adapter.manager.get_or_create_collection(store_id)
    if hasattr(collection, "modify"):
        collection.modify(metadata=md)

    stats = await adapter.get_collection_stats(store_id)
    md = stats.get("metadata", {}) or {}
    return VectorStoreObject(
        id=md.get("openai_id", store_id),
        name=md.get("name", store_id),
        created_at=md.get("created_at", _now_ts()),
        metadata=md,
        dimensions=stats.get("dimension", 1536)
    )


@router.delete("/vector_stores/{store_id}")
async def delete_vector_store(
    store_id: str = Path(...),
    current_user: User = Depends(get_request_user)
):
    adapter = _adapter_for_user(current_user, embedding_dim=1536)
    await adapter.initialize()
    await adapter.delete_collection(store_id)
    return {"id": store_id, "deleted": True}


@router.post("/vector_stores/{store_id}/vectors")
async def upsert_vectors(
    store_id: str = Path(...),
    payload: UpsertVectorsRequest = Body(...),
    current_user: User = Depends(get_request_user)
):
    # Determine embedding dimension from existing collection
    adapter = _adapter_for_user(current_user, embedding_dim=1536)
    await adapter.initialize()
    stats = await adapter.get_collection_stats(store_id)
    dim = stats.get("dimension", 1536)

    # Recreate adapter with correct dim
    adapter = _adapter_for_user(current_user, embedding_dim=dim)
    await adapter.initialize()

    ids: List[str] = []
    vectors: List[List[float]] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    # Support content->embed via local embedding pipeline if needed
    texts_to_embed: List[str] = []
    text_indices: List[int] = []

    for idx, rec in enumerate(payload.records):
        rid = rec.id or f"vec_{uuid.uuid4().hex[:24]}"
        ids.append(rid)
        metadatas.append(rec.metadata or {})
        if rec.values is not None:
            if len(rec.values) != dim:
                raise HTTPException(400, detail=f"Vector length {len(rec.values)} != expected {dim}")
            vectors.append(rec.values)
            documents.append(rec.content or "")
        elif rec.content:
            texts_to_embed.append(rec.content)
            text_indices.append(idx)
            # placeholder; will fill after embedding
            vectors.append([0.0] * dim)
            documents.append(rec.content)
        else:
            raise HTTPException(400, detail="Each record requires 'values' or 'content'")

    if texts_to_embed:
        # Build app config for embedding create using default settings
        embedding_settings = settings.get("EMBEDDING_CONFIG", {})
        app_config = {"embedding_config": embedding_settings}
        # Default model id
        model_id = embedding_settings.get("default_model_id") or embedding_settings.get("embedding_model") or "text-embedding-3-small"
        try:
            embedded = await adapter._loop.run_in_executor(None, create_embeddings_batch, texts_to_embed, app_config, model_id)
        except Exception as e:
            logger.error(f"Embedding generation failed for vectors upsert: {e}")
            raise HTTPException(500, detail="Failed to generate embeddings for provided content")
        # Assign back to vectors at corresponding indices
        for i, vec in zip(text_indices, embedded):
            vectors[i] = vec

    await adapter.upsert_vectors(store_id, ids=ids, vectors=vectors, documents=documents, metadatas=metadatas)
    return {"upserted": len(ids), "ids": ids}


@router.get("/vector_stores/{store_id}/vectors")
async def list_vectors(
    store_id: str = Path(...),
    limit: int = Query(100, gt=0, le=1000),
    current_user: User = Depends(get_request_user)
):
    adapter = _adapter_for_user(current_user, embedding_dim=1536)
    await adapter.initialize()
    collection = adapter.manager.get_or_create_collection(store_id)
    data = collection.get(limit=limit, include=["documents", "metadatas", "ids"])
    items: List[VectorItem] = []
    if data and data.get("ids"):
        for i, vid in enumerate(data["ids"]):
            items.append(VectorItem(
                id=vid,
                metadata=(data.get("metadatas") or [{}])[i] if data.get("metadatas") else {},
                content=(data.get("documents") or [""])[i] if data.get("documents") else ""
            ))
    return {"data": [item.dict() for item in items]}


@router.delete("/vector_stores/{store_id}/vectors/{vector_id}")
async def delete_vector(
    store_id: str = Path(...),
    vector_id: str = Path(...),
    current_user: User = Depends(get_request_user)
):
    adapter = _adapter_for_user(current_user, embedding_dim=1536)
    await adapter.initialize()
    await adapter.delete_vectors(store_id, ids=[vector_id])
    return {"id": vector_id, "deleted": True}


@router.post("/vector_stores/{store_id}/query")
async def query_vectors(
    store_id: str = Path(...),
    payload: QueryRequest = Body(...),
    current_user: User = Depends(get_request_user)
):
    adapter = _adapter_for_user(current_user, embedding_dim=1536)
    await adapter.initialize()

    # Determine the query vector
    qvec: Optional[List[float]] = None
    if payload.vector is not None:
        qvec = payload.vector
    elif payload.query:
        # Embed the text query
        embedding_settings = settings.get("EMBEDDING_CONFIG", {})
        app_config = {"embedding_config": embedding_settings}
        model_id = embedding_settings.get("default_model_id") or embedding_settings.get("embedding_model") or "text-embedding-3-small"
        try:
            embedded = await adapter._loop.run_in_executor(None, create_embeddings_batch, [payload.query], app_config, model_id)
            qvec = embedded[0]
        except Exception as e:
            logger.error(f"Embedding generation failed for query: {e}")
            raise HTTPException(500, detail="Failed to generate embedding for query")
    else:
        raise HTTPException(400, detail="Provide either 'query' text or 'vector'")

    dim = len(qvec)
    # Recreate adapter with correct dimension
    adapter = _adapter_for_user(current_user, embedding_dim=dim)
    await adapter.initialize()

    results = await adapter.search(
        collection_name=store_id,
        query_vector=qvec,
        k=payload.top_k,
        filter=payload.filter,
        include_metadata=True
    )
    return {
        "data": [
            {
                "id": r.id,
                "content": r.content,
                "metadata": r.metadata,
                "score": r.score,
            } for r in results
        ]
    }

