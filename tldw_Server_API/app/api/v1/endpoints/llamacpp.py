# llamacpp.py
# Description: This file contains the API endpoints for managing Llama.cpp server operations in tldw_Server_API.
#
# Imports
from typing import Optional, Dict, Any
#
# Thid-party Libraries
from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel, Field, ConfigDict
from typing import List
#
# Local Imports
from tldw_Server_API.app.core.Local_LLM.LLM_Inference_Exceptions import ModelNotFoundError, ServerError, InferenceError
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
#
########################################################################################################################
#
# Functions:

router = APIRouter()

#     LlamaCppConfig: Defines paths and default arguments for llama.cpp/server.
#
#     LlamaCpp_Handler:
#
#         Manages a single llama.cpp/server process (_active_server_process).
#
#         start_server(): This is your model swap function. If an existing server is running (managed by this handler), it calls stop_server() first, then starts a new server with the new model_filename and server_args.
#
#         stop_server(): Terminates the managed server process, handling process groups for robust cleanup.
#
#         inference(): Sends requests to the Llama.cpp server's OpenAI-compatible API (e.g., /v1/chat/completions).
#
#         list_models(): Scans the models_dir for .gguf files.
#
#         get_server_status(): Reports the current state of the managed server.
#
#         _cleanup_managed_server_sync(): Ensures server is stopped on application exit.
#
#         Optional logging of llama.cpp/server output to a file.
#
#     LLM_Inference_Manager Updates:
#
#         Initializes and provides access to LlamaCppHandler.
#
#         Delegates relevant calls (start_server, stop_server, run_inference, list_local_models) to the LlamaCppHandler.
#
#     API Endpoints: Provide HTTP interfaces to list models, start/swap the server with a specific model, stop it, get status, and run inference.

# Assuming 'llm_manager' is available, e.g., initialized in main.py and passed around or via Depends
# For simplicity, let's assume it's directly accessible here.
# from your_main_app_file import llm_manager_instance as llm_manager


# --- Llama.cpp Specific Endpoints ---
@router.post("/llamacpp/start_server", summary="Start or Swap Llama.cpp Server Model")
async def start_llamacpp_server_endpoint(
        model_filename: str = Body(..., embed=True,
                                   description="Filename of the GGUF model to load (e.g., 'mistral-7b-v0.1.Q4_K_M.gguf')"),
        server_args: Optional[Dict[str, Any]] = Body({}, embed=True,
                                                     description="Optional Llama.cpp server arguments (e.g., port, n_gpu_layers)")
):
    """
    Starts the Llama.cpp server with the specified model.
    If a server is already running, it will be stopped and restarted with the new model (model swap).
    """
    try:
        if not llm_manager.llamacpp:  # Or llm_manager.get_handler("llamacpp") and catch error
            raise HTTPException(status_code=400, detail="Llama.cpp backend is not enabled or configured.")
        result = await llm_manager.start_server(backend="llamacpp", model_name=model_filename, server_args=server_args)
        return result
    except (ModelNotFoundError, ServerError, InferenceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        llm_manager.logger.error(f"Unexpected error starting Llama.cpp server: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.post("/llamacpp/stop_server", summary="Stop Llama.cpp Server")
async def stop_llamacpp_server_endpoint():
    try:
        if not llm_manager.llamacpp:
            raise HTTPException(status_code=400, detail="Llama.cpp backend is not enabled or configured.")
        result = await llm_manager.stop_server(backend="llamacpp")
        return {"message": result}
    except (ServerError, InferenceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        llm_manager.logger.error(f"Unexpected error stopping Llama.cpp server: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.get("/llamacpp/status", summary="Get Llama.cpp Server Status")
async def get_llamacpp_status_endpoint():
    try:
        if not llm_manager.llamacpp:
            raise HTTPException(status_code=400, detail="Llama.cpp backend is not enabled or configured.")
        # status = await llm_manager.llamacpp.get_server_status() # Direct access
        status = await llm_manager.get_server_status(backend="llamacpp")  # Via manager
        return status
    except Exception as e:
        llm_manager.logger.error(f"Unexpected error getting Llama.cpp server status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.get("/llamacpp/metrics", summary="Get Llama.cpp Metrics")
async def get_llamacpp_metrics_endpoint():
    try:
        if not llm_manager.llamacpp:
            raise HTTPException(status_code=400, detail="Llama.cpp backend is not enabled or configured.")
        handler = llm_manager.llamacpp
        if hasattr(handler, "get_metrics"):
            return handler.get_metrics()  # type: ignore[attr-defined]
        return {"message": "metrics not available"}
    except Exception as e:
        llm_manager.logger.error(f"Unexpected error getting Llama.cpp metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.get("/llamafile/metrics", summary="Get Llamafile Metrics")
async def get_llamafile_metrics_endpoint():
    try:
        if not getattr(llm_manager, "llamafile", None):
            raise HTTPException(status_code=400, detail="Llamafile backend is not enabled or configured.")
        handler = llm_manager.llamafile
        if hasattr(handler, "get_metrics"):
            return handler.get_metrics()  # type: ignore[attr-defined]
        return {"message": "metrics not available"}
    except Exception as e:
        llm_manager.logger.error(f"Unexpected error getting Llamafile metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.get("/llamacpp/models", summary="List available Llama.cpp models")
async def list_llamacpp_models_endpoint():
    try:
        if not llm_manager.llamacpp:
            raise HTTPException(status_code=400, detail="Llama.cpp backend is not enabled or configured.")
        models = await llm_manager.list_local_models(backend="llamacpp")
        return {"available_models": models}
    except Exception as e:
        llm_manager.logger.error(f"Unexpected error listing Llama.cpp models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@router.post("/llamacpp/inference", summary="Run inference with Llama.cpp")
async def run_llamacpp_inference_endpoint(
        payload: Dict[str, Any] = Body(..., description="OpenAI compatible payload (messages, temperature, etc.)")
):
    """
    Runs inference using the currently loaded Llama.cpp model.
    Payload should be OpenAI compatible (e.g., include 'messages' list).
    Example: {"messages": [{"role": "user", "content": "Hello!"}], "temperature": 0.7}
    """
    try:
        if not llm_manager.llamacpp:
            raise HTTPException(status_code=400, detail="Llama.cpp backend is not enabled or configured.")

        # The 'model_name_or_path' for manager.run_inference is for context,
        # LlamaCppHandler uses its internally known active model.
        # We can get it from status or just pass a placeholder.
        status = await llm_manager.get_server_status(backend="llamacpp")
        current_model = status.get("model", "unknown_active_model")

        result = await llm_manager.run_inference(
            backend="llamacpp",
            model_name_or_path=current_model,  # Contextual
            prompt=None,  # Assuming payload contains 'messages'
            **payload  # Pass the entire payload dict as kwargs
        )
        return result
    except (ServerError, InferenceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        llm_manager.logger.error(f"Unexpected error during Llama.cpp inference: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

# --- Llama.cpp Reranker (GGUF embeddings) ---

class LlamaCppRerankItem(BaseModel):
    id: Optional[str] = Field(default=None, description="Optional identifier for the passage")
    text: str = Field(..., min_length=1, description="Passage text to score")


class LlamaCppRerankRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Query to rank against passages")
    passages: List[LlamaCppRerankItem] = Field(..., min_length=1, description="Candidate passages to rerank")
    top_k: Optional[int] = Field(default=None, ge=1, le=100, description="Top-K results to return (defaults to len(passages))")
    # Optional overrides for llama.cpp and model selection
    model: Optional[str] = Field(default=None, description="GGUF model path (overrides config)")
    binary: Optional[str] = Field(default=None, description="llama-embedding binary name or path")
    ngl: Optional[int] = Field(default=None, ge=0, description="n_gpu_layers (-ngl)")
    separator: Optional[str] = Field(default=None, description="Text separator between query and passages")
    output_format: Optional[str] = Field(default=None, description="Embedding output format (e.g., json+)")
    pooling: Optional[str] = Field(default=None, description="Embedding pooling method (e.g., last)")
    normalize: Optional[int] = Field(default=None, description="Embedding normalize flag (-1, 0, 1)")
    max_doc_chars: Optional[int] = Field(default=None, ge=0, description="Max chars per passage (truncation)")
    # OpenAPI example
    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {
                "query": "What do llamas eat?",
                "passages": [
                    {"id": "a", "text": "Llamas eat bananas"},
                    {"id": "b", "text": "Llamas in pyjamas"},
                    {"id": "c", "text": "A bowl of fruit salad"}
                ],
                "top_k": 2,
                "model": "/models/Qwen3-Embedding-0.6B_f16.gguf",
                "ngl": 99,
                "separator": "<#sep#>",
                "output_format": "json+",
                "pooling": "last",
                "normalize": -1
            }
        ]
    })


class LlamaCppRerankResult(BaseModel):
    id: Optional[str] = Field(default=None)
    index: int = Field(..., description="Index of the passage in input list")
    score: float = Field(..., ge=0.0, le=1.0)
    text: Optional[str] = Field(default=None, description="Original passage text (truncated)")


class LlamaCppRerankResponse(BaseModel):
    results: List[LlamaCppRerankResult]


@router.post("/llamacpp/reranking", summary="Rerank passages with llama.cpp embeddings (GGUF)", response_model=LlamaCppRerankResponse, dependencies=[Depends(check_rate_limit)])
@router.post("/llamacpp/rerank", summary="Rerank passages with llama.cpp embeddings (GGUF)", response_model=LlamaCppRerankResponse, dependencies=[Depends(check_rate_limit)])
async def llamacpp_reranker_endpoint(payload: LlamaCppRerankRequest, current_user: User = Depends(get_request_user)):
    """
    Rerank passages using the llama.cpp embeddings binary (llama-embedding) with a GGUF embedding model
    such as Qwen3-Embedding-0.6B. Scores are cosine(query, passage) normalized to [0,1].
    """
    try:
        # Lazy imports to avoid extra startup cost
        from tldw_Server_API.app.core.RAG.rag_service.advanced_reranking import (
            RerankingConfig, RerankingStrategy, create_reranker
        )
        from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reranking modules unavailable: {e}")

    # Build documents from passages
    documents: List[Document] = []
    for i, item in enumerate(payload.passages):
        documents.append(Document(
            id=item.id or str(i),
            content=item.text,
            metadata={"source": "llamacpp_reranker"},
            source=DataSource.MEDIA_DB,
            score=0.0,
        ))

    # Config and overrides
    cfg = RerankingConfig(
        strategy=RerankingStrategy.LLAMA_CPP,
        top_k=min(payload.top_k or len(documents), len(documents)) if documents else 0,
        model_name=payload.model,
    )
    if payload.binary is not None:
        cfg.llama_binary = payload.binary
    if payload.ngl is not None:
        cfg.llama_ngl = payload.ngl
    if payload.separator is not None:
        cfg.llama_embd_separator = payload.separator
    if payload.output_format is not None:
        cfg.llama_embd_output_format = payload.output_format
    if payload.pooling is not None:
        cfg.llama_pooling = payload.pooling
    if payload.normalize is not None:
        cfg.llama_normalize = payload.normalize
    if payload.max_doc_chars is not None:
        cfg.llama_max_doc_chars = payload.max_doc_chars

    reranker = create_reranker(RerankingStrategy.LLAMA_CPP, cfg)

    # Execute reranking
    try:
        # Support both async and sync reranker implementations
        rerank_fn = getattr(reranker, "rerank", None)
        if rerank_fn is None:
            raise RuntimeError("Invalid reranker: missing rerank() method")
        scored = rerank_fn(payload.query, documents)
        if hasattr(scored, "__await__"):
            scored = await scored
        # Enforce top_k even if underlying reranker returns more
        if isinstance(scored, list) and cfg.top_k:
            scored = scored[: cfg.top_k]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reranking failed: {e}")

    # Convert results
    # Map back to original order indices
    id_to_index = { (p.id or str(i)): i for i, p in enumerate(payload.passages) }
    results: List[LlamaCppRerankResult] = []
    for sd in scored:
        pid = getattr(sd.document, 'id', None)
        idx = id_to_index.get(pid, 0)
        results.append(LlamaCppRerankResult(
            id=pid,
            index=idx,
            score=float(getattr(sd, 'rerank_score', 0.0)),
            text=getattr(sd.document, 'content', None)
        ))

    return LlamaCppRerankResponse(results=results)


# Public aliases matching common reranker API shapes
public_router = APIRouter()


class PublicRerankRequest(BaseModel):
    model: Optional[str] = Field(default=None, description="Reranker model id/path (GGUF for llama.cpp or HF id for transformers)")
    query: str = Field(..., min_length=1)
    documents: List[str] = Field(..., min_length=1, description="Documents (plain text) to rank")
    top_n: Optional[int] = Field(default=None, ge=1, le=100)
    backend: Optional[str] = Field(default="auto", description="Reranker backend: auto|llamacpp|transformers")
    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {
                "model": "/models/Qwen3-Embedding-0.6B_f16.gguf",
                "query": "What is panda?",
                "top_n": 3,
                "documents": [
                    "hi",
                    "it is a bear",
                    "The giant panda (Ailuropoda melanoleuca), sometimes called a panda bear ..."
                ]
            }
        ]
    })


class PublicRerankResponse(BaseModel):
    results: List[LlamaCppRerankResult]


async def _run_public_rerank(query: str, docs: List[str], model_override: Optional[str], top_k: Optional[int], backend: str) -> List[LlamaCppRerankResult]:
    from tldw_Server_API.app.core.RAG.rag_service.advanced_reranking import (
        RerankingConfig, RerankingStrategy, create_reranker
    )
    from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource

    documents: List[Document] = [
        Document(id=str(i), content=txt, metadata={"source": "public_reranking"}, source=DataSource.MEDIA_DB)
        for i, txt in enumerate(docs)
    ]

    # Select backend
    strategy = RerankingStrategy.FLASHRANK
    model_name = model_override
    b = (backend or "auto").lower()
    is_gguf = bool(model_override and model_override.strip().lower().endswith(".gguf"))
    looks_hf_id = bool(model_override and "/" in model_override and not is_gguf)
    if b == "llamacpp" or is_gguf:
        strategy = RerankingStrategy.LLAMA_CPP
    elif b == "transformers" or looks_hf_id:
        strategy = RerankingStrategy.CROSS_ENCODER
    else:
        # Auto fallback: prefer transformers if it looks like HF id, else llama if gguf
        strategy = RerankingStrategy.LLAMA_CPP if is_gguf else (RerankingStrategy.CROSS_ENCODER if looks_hf_id else RerankingStrategy.FLASHRANK)

    cfg = RerankingConfig(
        strategy=strategy,
        top_k=min(top_k or len(documents), len(documents)) if documents else 0,
        model_name=model_name,
    )
    reranker = create_reranker(strategy, cfg)
    # Support both async and sync reranker implementations
    rerank_fn = getattr(reranker, "rerank", None)
    if rerank_fn is None:
        raise HTTPException(status_code=500, detail="Invalid reranker: missing rerank() method")
    scored = rerank_fn(query, documents)
    if hasattr(scored, "__await__"):
        scored = await scored
    # Enforce top_k even if underlying reranker returns more
    if isinstance(scored, list) and cfg.top_k:
        scored = scored[: cfg.top_k]
    out: List[LlamaCppRerankResult] = []
    for sd in scored:
        idx = int(getattr(sd.document, 'id', '0')) if str(getattr(sd.document, 'id', '0')).isdigit() else 0
        out.append(LlamaCppRerankResult(
            id=getattr(sd.document, 'id', None),
            index=idx,
            score=float(getattr(sd, 'rerank_score', 0.0)),
            text=getattr(sd.document, 'content', None),
        ))
    return out


@public_router.post("/v1/reranking", summary="Rerank documents according to a query", response_model=PublicRerankResponse, dependencies=[Depends(check_rate_limit)])
@public_router.post("/v1/rerank", summary="Rerank documents according to a query", response_model=PublicRerankResponse, dependencies=[Depends(check_rate_limit)])
async def public_reranking_endpoint(payload: PublicRerankRequest, current_user: User = Depends(get_request_user)):
    try:
        results = await _run_public_rerank(
            query=payload.query,
            docs=payload.documents,
            model_override=payload.model,
            top_k=payload.top_n,
            backend=(payload.backend or "auto"),
        )
        return PublicRerankResponse(results=results)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Public reranking failed: {e}")

#
# End of llamacpp.py
##########################################################################################################################
