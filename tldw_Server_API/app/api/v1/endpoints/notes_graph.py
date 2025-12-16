from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status, Body
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    rbac_rate_limit,
    require_token_scope,
    require_permissions,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.schemas.notes_graph import (
    NoteGraphRequest,
    NoteGraphResponse,
    NoteLinkCreate,
    GraphLimits,
)
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB, ConflictError, InputError, CharactersRAGDBError
from tldw_Server_API.app.core.AuthNZ.permissions import NOTES_GRAPH_READ, NOTES_GRAPH_WRITE


router = APIRouter()


@router.get(
    "/graph",
    summary="Fetch a graph of notes and related entities (stub)",
    description=(
        "Returns a bounded subgraph of notes, tags, and sources based on filters.\n\n"
        "- Honors enum edge_types: manual, wikilink, backlink, tag_membership, source_membership.\n"
        "- Uses BFS with deterministic ordering; see Docs/Design/Graphing-Notes-PRD.md §21 for cursor details.\n\n"
        "Example response (default format) matches the NoteGraphResponse schema.\n\n"
        "Cytoscape example (when format=cytoscape) is documented in Docs/Design/Graphing-Notes-PRD.md (§9, §14)."
    ),
    tags=["notes", "notes-graph"],
    response_model=NoteGraphResponse,
    responses={
        200: {
            "description": "Graph response (default format)",
            "content": {
                "application/json": {
                    "example": {
                        "nodes": [
                            {
                                "id": "note:123",
                                "type": "note",
                                "label": "My Note",
                                "created_at": "2025-01-01T12:00:00Z",
                                "degree": 2,
                                "tag_count": 3,
                                "primary_source_id": "source:yt:abcd",
                            },
                            {"id": "tag:ml", "type": "tag", "label": "ml"},
                            {
                                "id": "source:yt:abcd",
                                "type": "source",
                                "label": "YouTube: abcd",
                            },
                        ],
                        "edges": [
                            {
                                "id": "e:1",
                                "source": "note:123",
                                "target": "note:456",
                                "type": "manual",
                                "directed": False,
                                "weight": 1.0,
                            },
                            {
                                "id": "e:2",
                                "source": "note:123",
                                "target": "tag:ml",
                                "type": "tag_membership",
                                "directed": False,
                            },
                        ],
                        "truncated": False,
                        "truncated_by": [],
                        "has_more": False,
                        "cursor": None,
                        "limits": {
                            "max_nodes": 300,
                            "max_edges": 1200,
                            "max_degree": 40,
                        },
                    }
                }
            },
        }
    },
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "bash",
                "label": "curl",
                "source": "curl -H 'Authorization: Bearer <token>' 'http://127.0.0.1:8000/api/v1/notes/graph?center_note_id=note:123&radius=1&edge_types=manual,wikilink,tag_membership&max_nodes=200'",
            },
            {
                "lang": "python",
                "label": "httpx",
                "source": "import httpx\nresp = httpx.get('http://127.0.0.1:8000/api/v1/notes/graph', params={'center_note_id':'note:123','radius':1,'edge_types':'manual,wikilink,tag_membership'})\nprint(resp.json())",
            },
        ]
    },
)
async def get_notes_graph(
    req: NoteGraphRequest = Depends(),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("notes.graph.read")),
    __: None = Depends(require_permissions(NOTES_GRAPH_READ)),
    ___: None = Depends(require_token_scope("notes", require_if_present=True, endpoint_id="notes.graph.read")),
) -> NoteGraphResponse:
    """
    Stub response for notes graph. RBAC and token-scope dependencies are enforced.
    Returns an empty graph structure for now.
    """
    try:
        limits = GraphLimits(max_nodes=300, max_edges=1200, max_degree=40)
        return NoteGraphResponse(
            nodes=[],
            edges=[],
            truncated=False,
            truncated_by=[],
            has_more=False,
            cursor=None,
            limits=limits,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"notes.graph.read stub failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Graph fetch failed")


@router.get(
    "/{note_id}/neighbors",
    summary="Fetch neighbors for a note (stub)",
    description=(
        "Returns a radius=1 ego network for the given note. Uses the same filters, limits, and ordering as /graph.\n"
        "See Docs/Design/Graphing-Notes-PRD.md (§9, §10, §21)."
    ),
    tags=["notes", "notes-graph"],
    response_model=NoteGraphResponse,
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "bash",
                "label": "curl",
                "source": "curl -H 'Authorization: Bearer <token>' 'http://127.0.0.1:8000/api/v1/notes/note:123/neighbors?edge_types=manual,backlink'",
            }
        ]
    },
)
async def get_note_neighbors(
    note_id: str,
    req: NoteGraphRequest = Depends(),
    current_user: User = Depends(get_request_user),
    _: None = Depends(rbac_rate_limit("notes.graph.read")),
    __: None = Depends(require_permissions(NOTES_GRAPH_READ)),
    ___: None = Depends(require_token_scope("notes", require_if_present=True, endpoint_id="notes.graph.read")),
) -> NoteGraphResponse:
    """
    Stub neighbors endpoint; enforces RBAC and token scope.
    """
    limits = GraphLimits(max_nodes=300, max_edges=1200, max_degree=40)
    return NoteGraphResponse(
        nodes=[],
        edges=[],
        truncated=False,
        truncated_by=[],
        has_more=False,
        cursor=None,
        limits=limits,
    )


@router.post(
    "/{note_id}/links",
    summary="Create a manual link between notes (stub)",
    description=(
        "Creates a manual link from the given note to another note. Undirected by default (directed=false).\n"
        "See Docs/Design/Graphing-Notes-PRD.md (§8, §9, §10)."
    ),
    tags=["notes", "notes-graph"],
    responses={
        200: {
            "description": "Creation result (stub)",
            "content": {
                "application/json": {
                    "example": {
                        "status": "stub",
                        "edge": None,
                        "from": "note:123",
                        "to": "note:456",
                    }
                }
            },
        }
    },
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "bash",
                "label": "curl",
                "source": "curl -X POST -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' \\\n+  -d '{\"to_note_id\":\"note:456\",\"directed\":false,\"weight\":1.0}' \\\n+  'http://127.0.0.1:8000/api/v1/notes/note:123/links'",
            }
        ]
    },
)
async def create_manual_link(
    note_id: str,
    link: NoteLinkCreate = Body(
        ..., example={"to_note_id": "note:456", "directed": False, "weight": 1.0}
    ),
    current_user: User = Depends(get_request_user),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("notes.graph.write")),
    __: None = Depends(require_permissions(NOTES_GRAPH_WRITE)),
    ___: None = Depends(require_token_scope("notes", require_if_present=True, endpoint_id="notes.graph.write")),
) -> Dict[str, Any]:
    """
    Create a manual link in the user's ChaChaNotes DB. Populates created_by.
    """
    to_note_id = link.to_note_id
    if not to_note_id:
        raise HTTPException(status_code=400, detail="to_note_id is required")

    try:
        principal = f"user:{current_user.id_str}"
        edge = db.create_manual_note_edge(
            user_id=str(current_user.id_str),
            from_note_id=note_id,
            to_note_id=to_note_id,
            directed=bool(link.directed),
            weight=link.weight if link.weight is not None else 1.0,
            metadata=link.metadata,
            created_by=principal,
        )
        return {"status": "created", "edge": edge}
    except ConflictError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="duplicate manual link")
    except InputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CharactersRAGDBError as e:
        logger.error(f"Failed to create manual note link: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Link creation failed")


@router.delete(
    "/links/{edge_id}",
    summary="Delete a manual link (stub)",
    description=(
        "Deletes a manual link by id. Stub returns a placeholder payload.\n"
        "See Docs/Design/Graphing-Notes-PRD.md (§9)."
    ),
    tags=["notes", "notes-graph"],
    responses={
        200: {
            "description": "Deletion result (stub)",
            "content": {
                "application/json": {
                    "example": {"deleted": False, "edge_id": "e:1", "status": "stub"}
                }
            },
        }
    },
    openapi_extra={
        "x-codeSamples": [
            {
                "lang": "bash",
                "label": "curl",
                "source": "curl -X DELETE -H 'Authorization: Bearer <token>' 'http://127.0.0.1:8000/api/v1/notes/links/e:1'",
            }
        ]
    },
)
async def delete_manual_link(
    edge_id: str,
    current_user: User = Depends(get_request_user),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    _: None = Depends(rbac_rate_limit("notes.graph.write")),
    __: None = Depends(require_permissions(NOTES_GRAPH_WRITE)),
    ___: None = Depends(require_token_scope("notes", require_if_present=True, endpoint_id="notes.graph.write")),
) -> Dict[str, Any]:
    """
    Delete a manual link by id for the current user.
    """
    try:
        deleted = db.delete_manual_note_edge(user_id=str(current_user.id_str), edge_id=edge_id)
        return {"deleted": bool(deleted), "edge_id": edge_id}
    except InputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CharactersRAGDBError as e:
        logger.error(f"Failed to delete manual note link: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Link deletion failed")
