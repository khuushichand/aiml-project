# media_embeddings.py
# Description: Endpoints for managing embeddings for media items
#
# This module provides endpoints to:
# - Check if embeddings exist for a media item
# - Generate embeddings for uploaded media
# - Delete embeddings for a media item

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field
from loguru import logger

# Local imports
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import (
    ChromaDBManager,
    store_in_chroma
)
from tldw_Server_API.app.api.v1.API_Deps.rate_limiting import limiter
from tldw_Server_API.app.core.config import settings, load_comprehensive_config
from tldw_Server_API.app.core.Chunking.chunker import Chunker
from tldw_Server_API.app.core.Chunking.base import ChunkerConfig
import asyncio

from tldw_Server_API.app.core.Embeddings.media_embedding_jobs_db import (
    init_db as jobs_init_db,
    create_job as jobs_create,
    update_job as jobs_update,
    get_job as jobs_get,
    list_jobs as jobs_list,
)

router = APIRouter(prefix="/media", tags=["media-embeddings"])

# Default embedding settings
DEFAULT_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-4B-GGUF"
DEFAULT_EMBEDDING_PROVIDER = "huggingface"
FALLBACK_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

class GenerateEmbeddingsRequest(BaseModel):
    """Request model for generating embeddings"""
    embedding_model: Optional[str] = Field(
        None,
        description="Specific embedding model to use (defaults to Qwen3-Embedding-4B-GGUF)"
    )
    embedding_provider: Optional[str] = Field(
        None,
        description="Embedding provider (huggingface, openai, etc)"
    )
    chunk_size: int = Field(
        1000,
        description="Size of text chunks for embedding"
    )
    chunk_overlap: int = Field(
        200,
        description="Overlap between chunks"
    )
    force_regenerate: bool = Field(
        False,
        description="Force regeneration even if embeddings exist"
    )

class EmbeddingsStatusResponse(BaseModel):
    """Response model for embedding status"""
    media_id: int
    has_embeddings: bool
    embedding_count: Optional[int] = None
    embedding_model: Optional[str] = None
    last_generated: Optional[str] = None

class GenerateEmbeddingsResponse(BaseModel):
    """Response model for embedding generation"""
    media_id: int
    status: str
    message: str
    embedding_count: Optional[int] = None
    embedding_model: str
    chunks_processed: Optional[int] = None
    job_id: Optional[str] = None


async def get_media_content(media_id: int, db: MediaDatabase) -> Dict[str, Any]:
    """Retrieve media content from database"""
    try:
        # Get media item details
        media_item = db.get_media_by_id(media_id)
        if not media_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media item {media_id} not found"
            )
        
        # Get content
        content = media_item  # The get_media_by_id returns all data including content
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No content found for media item {media_id}"
            )
        
        return {
            "media_item": media_item,
            "content": content
        }
    except HTTPException:
        # Propagate explicit HTTP errors (e.g., 404 Not Found)
        raise
    except Exception as e:
        logger.error(f"Error retrieving media content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving media content: {str(e)}"
        )


def chunk_media_content(text: str, chunk_size: int = 1000, overlap: int = 200, method: str = "words") -> List[Dict[str, Any]]:
    """
    Split text into overlapping chunks using the Chunking module.
    
    Args:
        text: Text to chunk
        chunk_size: Maximum size of each chunk
        overlap: Overlap between chunks
        method: Chunking method to use (words, sentences, tokens, etc.)
    
    Returns:
        List of chunk dictionaries with text and metadata
    """
    # Initialize chunker with configuration
    config = ChunkerConfig(
        default_method=method,
        default_max_size=chunk_size,
        default_overlap=overlap,
        language="en"  # TODO: Detect language from content
    )
    
    chunker = Chunker(config=config)
    
    # Use chunk_text_with_metadata to get detailed results
    chunk_results = chunker.chunk_text_with_metadata(
        text=text,
        method=method,
        max_size=chunk_size,
        overlap=overlap
    )
    
    # Convert ChunkResult objects to our format
    chunks = []
    for i, result in enumerate(chunk_results):
        # ChunkMetadata is an object, not a dict
        chunks.append({
            "text": result.text,
            "index": i,
            "start": result.metadata.start_char if hasattr(result.metadata, 'start_char') else i * (chunk_size - overlap),
            "end": result.metadata.end_char if hasattr(result.metadata, 'end_char') else (i + 1) * chunk_size,
            "metadata": {
                "word_count": result.metadata.word_count if hasattr(result.metadata, 'word_count') else None,
                "language": result.metadata.language if hasattr(result.metadata, 'language') else "en"
            }
        })
    
    return chunks


async def generate_embeddings_for_media(
    media_id: int,
    media_content: Dict[str, Any],
    embedding_model: str,
    embedding_provider: str,
    chunk_size: int,
    chunk_overlap: int,
    user_id: str = "1"
) -> Dict[str, Any]:
    """Generate embeddings for media content"""
    try:
        from tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced import (
            create_embeddings_batch_async
        )
        
        # Extract text content
        content_text = media_content["content"].get("content", "")
        if not content_text:
            return {
                "status": "error",
                "message": "No text content to generate embeddings from",
                "embedding_count": 0
            }
        
        # Chunk the text using the Chunking module
        chunks = chunk_media_content(content_text, chunk_size, chunk_overlap)
        logger.info(f"Created {len(chunks)} chunks for media {media_id}")
        
        # Extract chunk texts for embedding
        chunk_texts = [chunk["text"] for chunk in chunks]
        
        # Generate embeddings
        try:
            embeddings = await create_embeddings_batch_async(
                texts=chunk_texts,
                provider=embedding_provider,
                model_id=embedding_model
            )
            
            # Store in ChromaDB using per-user collections
            collection_name = f"user_{user_id}_media_embeddings"
            
            # Prepare metadata for each chunk
            metadatas = []
            for i, chunk in enumerate(chunks):
                metadata = {
                    "media_id": str(media_id),
                    "chunk_index": chunk["index"],
                    "chunk_start": chunk["start"],
                    "chunk_end": chunk["end"],
                    "title": media_content["media_item"].get("title", ""),
                    "author": media_content["media_item"].get("author", ""),
                    "embedding_model": embedding_model,
                    "embedding_provider": embedding_provider
                }
                metadatas.append(metadata)
            
            # Store embeddings
            ids = [f"chunk_{i}" for i in range(len(chunks))]
            
            # Convert embeddings to list format if they're numpy arrays
            logger.info(f"Embeddings type: {type(embeddings)}, first item type: {type(embeddings[0]) if embeddings else 'None'}")
            if embeddings and hasattr(embeddings[0], 'tolist'):
                embeddings_list = [emb.tolist() for emb in embeddings]
            else:
                embeddings_list = embeddings
            
            logger.info(f"After conversion - embeddings_list type: {type(embeddings_list)}, first item type: {type(embeddings_list[0]) if embeddings_list else 'None'}")
            logger.info(f"First embedding length: {len(embeddings_list[0]) if embeddings_list and embeddings_list[0] else 0}")
            
            store_in_chroma(
                texts=chunk_texts,
                embeddings=embeddings_list,
                ids=ids,
                metadatas=metadatas,
                collection_name=collection_name
            )
            
            return {
                "status": "success",
                "message": f"Successfully generated {len(embeddings)} embeddings",
                "embedding_count": len(embeddings),
                "chunks_processed": len(chunks)
            }
            
        except Exception as e:
            # Try fallback model if primary fails
            if embedding_model != FALLBACK_EMBEDDING_MODEL:
                logger.warning(f"Failed with {embedding_model}, trying fallback {FALLBACK_EMBEDDING_MODEL}")
                embeddings = await create_embeddings_batch_async(
                    texts=chunk_texts,
                    provider="huggingface",
                    model_id=FALLBACK_EMBEDDING_MODEL
                )
                
                # Store with fallback model info in per-user collection
                collection_name = f"user_{user_id}_media_embeddings"
                
                metadatas = []
                for i, chunk in enumerate(chunks):
                    metadata = {
                        "media_id": str(media_id),
                        "chunk_index": chunk["index"],
                        "chunk_start": chunk["start"],
                        "chunk_end": chunk["end"],
                        "title": media_content["media_item"].get("title", ""),
                        "author": media_content["media_item"].get("author", ""),
                        "embedding_model": FALLBACK_EMBEDDING_MODEL,
                        "embedding_provider": "huggingface"
                    }
                    metadatas.append(metadata)
                
                ids = [f"chunk_{i}" for i in range(len(chunks))]
                
                # Convert embeddings to list format if they're numpy arrays
                if embeddings and hasattr(embeddings[0], 'tolist'):
                    embeddings_list = [emb.tolist() for emb in embeddings]
                else:
                    embeddings_list = embeddings
                
                store_in_chroma(
                    texts=chunk_texts,
                    embeddings=embeddings_list,
                    ids=ids,
                    metadatas=metadatas,
                    collection_name=collection_name
                )
                
                return {
                    "status": "success",
                    "message": f"Generated embeddings using fallback model {FALLBACK_EMBEDDING_MODEL}",
                    "embedding_count": len(embeddings),
                    "chunks_processed": len(chunks)
                }
            else:
                raise e
                
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        return {
            "status": "error",
            "message": f"Failed to generate embeddings: {str(e)}",
            "embedding_count": 0
        }


@router.get("/{media_id}/embeddings/status", response_model=EmbeddingsStatusResponse)
async def get_embeddings_status(
    media_id: int,
    db: MediaDatabase = Depends(get_media_db_for_user),
    current_user: User = Depends(get_request_user)
) -> EmbeddingsStatusResponse:
    """Check if embeddings exist for a media item"""
    try:
        # Check if media exists
        media_item = db.get_media_by_id(media_id)
        if not media_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media item {media_id} not found"
            )
        
        # Check if embeddings exist by querying the per-user collection in ChromaDB
        user_id = str(getattr(current_user, 'id', '1'))
        from tldw_Server_API.app.core.config import settings as app_settings
        embedding_config = app_settings.get("EMBEDDING_CONFIG", {}).copy()
        embedding_config["USER_DB_BASE_DIR"] = app_settings.get("USER_DB_BASE_DIR")
        manager = ChromaDBManager(user_id=user_id, user_embedding_config=embedding_config)
        collection_name = f"user_{user_id}_media_embeddings"

        has_embeddings = False
        embedding_count: Optional[int] = None
        embedding_model: Optional[str] = None
        last_generated: Optional[str] = None

        try:
            collection = manager.get_or_create_collection(collection_name)
            # Try a filtered get to see if any vectors exist for this media_id
            data = collection.get(where={"media_id": str(media_id)}, include=["metadatas"], limit=100000)
            ids = (data or {}).get("ids") or []
            has_embeddings = len(ids) > 0
            if has_embeddings:
                embedding_count = len(ids)
                # Try to infer embedding model from first metadata
                md_list = (data or {}).get("metadatas") or []
                if md_list:
                    first_md = md_list[0]
                    embedding_model = first_md.get("embedding_model") if isinstance(first_md, dict) else None
        except Exception as e:
            logger.warning(f"ChromaDB status check failed for media {media_id}: {e}")

        return EmbeddingsStatusResponse(
            media_id=media_id,
            has_embeddings=has_embeddings,
            embedding_count=embedding_count,
            embedding_model=embedding_model,
            last_generated=last_generated,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking embeddings status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking embeddings status: {str(e)}"
        )


@router.post("/{media_id}/embeddings", response_model=GenerateEmbeddingsResponse)
async def generate_embeddings(
    media_id: int,
    background_tasks: BackgroundTasks,
    request: GenerateEmbeddingsRequest = GenerateEmbeddingsRequest(),
    db: MediaDatabase = Depends(get_media_db_for_user),
    current_user = Depends(get_request_user)
) -> GenerateEmbeddingsResponse:
    """Generate embeddings for a media item"""
    
    # Use provided model or defaults
    embedding_model = request.embedding_model or settings.get("embedding_model", DEFAULT_EMBEDDING_MODEL)
    embedding_provider = request.embedding_provider or settings.get("embedding_provider", DEFAULT_EMBEDDING_PROVIDER)
    
    try:
        # Generate embeddings in per-user collection
        user_id = str(current_user.id)
        collection_name = f"user_{user_id}_media_embeddings"
        
        # Get media content
        media_content = await get_media_content(media_id, db)
        
        # Persist a job record and run generation in the background
        jobs_init_db(user_id)
        import uuid
        job_id = f"mej_{uuid.uuid4().hex[:20]}"
        try:
            jobs_create(job_id=job_id, media_id=media_id, user_id=user_id, embedding_model=embedding_model)
        except Exception as e:
            logger.warning(f"Failed to persist media embedding job: {e}")

        async def _run_job():
            try:
                result = await generate_embeddings_for_media(
                    media_id=media_id,
                    media_content=media_content,
                    embedding_model=embedding_model,
                    embedding_provider=embedding_provider,
                    chunk_size=request.chunk_size,
                    chunk_overlap=request.chunk_overlap,
                    user_id=user_id
                )
                try:
                    jobs_update(job_id=job_id, user_id=user_id, status='completed',
                                embedding_count=result.get('embedding_count'),
                                chunks_processed=result.get('chunks_processed'))
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Background embeddings generation failed for media {media_id}: {e}")
                try:
                    jobs_update(job_id=job_id, user_id=user_id, status='failed', error=str(e))
                except Exception:
                    pass

        # Schedule the job on the current event loop; avoid creating tasks from non-async background thread
        asyncio.create_task(_run_job())

        # Return accepted response with job id
        return GenerateEmbeddingsResponse(
            media_id=media_id,
            status="accepted",
            message="Embedding generation started",
            embedding_count=None,
            embedding_model=embedding_model,
            chunks_processed=None,
            job_id=job_id
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating embeddings: {str(e)}"
        )


@router.delete("/{media_id}/embeddings")
async def delete_embeddings(
    media_id: int,
    db: MediaDatabase = Depends(get_media_db_for_user),
    current_user: User = Depends(get_request_user)
) -> Dict[str, Any]:
    """Delete embeddings for a media item"""
    try:
        # Check if media exists
        media_item = db.get_media_by_id(media_id)
        if not media_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media item {media_id} not found"
            )
        
        # Delete embeddings from per-user collection using a where filter
        user_id = str(getattr(current_user, 'id', '1'))
        from tldw_Server_API.app.core.config import settings as app_settings
        embedding_config = app_settings.get("EMBEDDING_CONFIG", {}).copy()
        embedding_config["USER_DB_BASE_DIR"] = app_settings.get("USER_DB_BASE_DIR")
        manager = ChromaDBManager(user_id=user_id, user_embedding_config=embedding_config)
        collection_name = f"user_{user_id}_media_embeddings"
        collection = manager.get_or_create_collection(collection_name)
        try:
            # Use where-based delete if supported
            collection.delete(where={"media_id": str(media_id)})
        except Exception as e:
            # Fall back to fetching IDs then deleting by ids
            logger.warning(f"Where-delete failed, falling back to id-based delete: {e}")
            data = collection.get(where={"media_id": str(media_id)}, include=["metadatas"], limit=100000)
            ids = (data or {}).get("ids") or []
            if ids:
                collection.delete(ids=ids)

        return {
            "status": "success",
            "message": f"Embeddings deleted for media item {media_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting embeddings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting embeddings: {str(e)}"
        )


@router.get("/embeddings/jobs/{job_id}")
async def get_media_embedding_job(
    job_id: str,
    current_user: User = Depends(get_request_user)
):
    uid = str(getattr(current_user, 'id', '1'))
    rec = jobs_get(job_id, uid)
    if not rec:
        raise HTTPException(status_code=404, detail="Job not found")
    return rec


@router.get("/embeddings/jobs")
async def list_media_embedding_jobs(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_request_user)
):
    uid = str(getattr(current_user, 'id', '1'))
    rows = jobs_list(user_id=uid, status=status, limit=limit, offset=offset)
    return {"data": rows, "pagination": {"limit": limit, "offset": offset, "count": len(rows)}}
