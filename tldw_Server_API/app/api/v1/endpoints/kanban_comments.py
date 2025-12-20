# app/api/v1/endpoints/kanban_comments.py
"""
Kanban Comment API endpoints.

Provides CRUD operations for Kanban card comments including:
- Create, read, update, delete comments
- List comments for a card with pagination
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from tldw_Server_API.app.core.DB_Management.Kanban_DB import KanbanDB
from tldw_Server_API.app.api.v1.schemas.kanban_schemas import (
    CommentCreate,
    CommentUpdate,
    CommentResponse,
    CommentsListResponse,
    PaginationInfo,
    DetailResponse,
)
from tldw_Server_API.app.api.v1.API_Deps.kanban_deps import (
    get_kanban_db_for_user,
    handle_kanban_db_error,
)


router = APIRouter(tags=["Kanban Comments"])


# --- Helper for Exception Handling ---
def _handle_error(e: Exception) -> HTTPException:
    """Convert exceptions to appropriate HTTP responses."""
    return handle_kanban_db_error(e)


# =============================================================================
# Comment CRUD Endpoints
# =============================================================================

@router.post(
    "/cards/{card_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a comment",
    description="Create a new comment on a card."
)
async def create_comment(
    card_id: int,
    comment_in: CommentCreate,
    db: KanbanDB = Depends(get_kanban_db_for_user)
) -> CommentResponse:
    """
    Create a new comment on a card.

    - **content**: Comment content (required, 1-10000 characters, markdown supported)

    The comment author is derived from the authenticated user context.
    """
    try:
        comment = db.create_comment(
            card_id=card_id,
            content=comment_in.content
        )
        return CommentResponse(**comment)
    except Exception as e:
        raise _handle_error(e) from e


@router.get(
    "/cards/{card_id}/comments",
    response_model=CommentsListResponse,
    summary="List card comments",
    description="Get all comments for a card with pagination."
)
async def list_comments(
    card_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    include_deleted: bool = Query(False, description="Include soft-deleted comments"),
    db: KanbanDB = Depends(get_kanban_db_for_user)
) -> CommentsListResponse:
    """Get comments for a card, ordered by most recent first."""
    try:
        comments, total = db.list_comments(
            card_id=card_id,
            include_deleted=include_deleted,
            page=page,
            per_page=per_page
        )

        offset = (page - 1) * per_page
        has_more = offset + len(comments) < total

        return CommentsListResponse(
            comments=[CommentResponse(**c) for c in comments],
            pagination=PaginationInfo(
                total=total,
                limit=per_page,
                offset=offset,
                has_more=has_more
            )
        )
    except Exception as e:
        raise _handle_error(e) from e


@router.get(
    "/comments/{comment_id}",
    response_model=CommentResponse,
    summary="Get a comment",
    description="Get a comment by ID."
)
async def get_comment(
    comment_id: int,
    include_deleted: bool = Query(False, description="Include soft-deleted comment"),
    db: KanbanDB = Depends(get_kanban_db_for_user)
) -> CommentResponse:
    """Get a single comment by ID."""
    try:
        comment = db.get_comment(comment_id=comment_id, include_deleted=include_deleted)
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Comment {comment_id} not found"
            )
        return CommentResponse(**comment)
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_error(e) from e


@router.patch(
    "/comments/{comment_id}",
    response_model=CommentResponse,
    summary="Update a comment",
    description="Update an existing comment. Only the comment author can edit their comments."
)
async def update_comment(
    comment_id: int,
    comment_in: CommentUpdate,
    db: KanbanDB = Depends(get_kanban_db_for_user)
) -> CommentResponse:
    """
    Update a comment.

    - **content**: New comment content (required)

    Only the comment author can edit their own comments.
    """
    try:
        comment = db.update_comment(
            comment_id=comment_id,
            content=comment_in.content
        )
        return CommentResponse(**comment)
    except Exception as e:
        raise _handle_error(e) from e


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
    description="Soft delete a comment. The comment can be recovered within the retention period."
)
async def delete_comment(
    comment_id: int,
    hard_delete: bool = Query(False, description="Permanently delete the comment"),
    db: KanbanDB = Depends(get_kanban_db_for_user)
) -> None:
    """
    Delete a comment.

    By default, comments are soft-deleted for audit trail.
    Use hard_delete=true to permanently remove the comment.
    """
    try:
        success = db.delete_comment(comment_id=comment_id, hard_delete=hard_delete)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Comment {comment_id} not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_error(e) from e
