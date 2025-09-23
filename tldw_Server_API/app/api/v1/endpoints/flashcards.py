# flashcards.py
# REST endpoints for Flashcards/Decks backed by ChaChaNotes DB (schema v5)

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
)
from tldw_Server_API.app.api.v1.schemas.flashcards import (
    DeckCreate,
    Deck,
    FlashcardCreate,
    Flashcard,
    FlashcardListResponse,
    FlashcardReviewRequest,
    FlashcardReviewResponse,
    FlashcardQuery,
    FlashcardUpdate,
    FlashcardTagsUpdate,
    FlashcardsImportRequest,
)
import json

from tldw_Server_API.app.core.Flashcards.apkg_exporter import export_apkg_from_rows

router = APIRouter(prefix="/flashcards", tags=["flashcards (Experimental)"])


@router.post("/decks", response_model=Deck)
def create_deck(payload: DeckCreate, db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    try:
        deck_id = db.add_deck(payload.name, payload.description)
        # Return deck row
        decks = db.list_decks(limit=1, offset=0, include_deleted=True)
        # If there are many decks, fetch the one by id directly
        deck = next((d for d in decks if d.get("id") == deck_id), None)
        if not deck:
            # fallback: refetch
            deck = {
                "id": deck_id,
                "name": payload.name,
                "description": payload.description,
                "created_at": None,
                "last_modified": None,
                "deleted": False,
                "client_id": "",
                "version": 1,
            }
        return deck
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except CharactersRAGDBError as e:
        logger.error(f"Failed to create deck: {e}")
        raise HTTPException(status_code=500, detail="Failed to create deck")


@router.get("/decks", response_model=List[Deck])
def list_decks(db: CharactersRAGDB = Depends(get_chacha_db_for_user), include_deleted: bool = False,
               limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    try:
        return db.list_decks(limit=limit, offset=offset, include_deleted=include_deleted)
    except CharactersRAGDBError as e:
        logger.error(f"Failed to list decks: {e}")
        raise HTTPException(status_code=500, detail="Failed to list decks")


@router.post("", response_model=Flashcard)
def create_flashcard(payload: FlashcardCreate, db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    try:
        data = payload.model_dump()
        # Convert tags list to tags_json string
        tags = data.pop("tags", None)
        if tags is not None:
            data["tags_json"] = json.dumps(tags)
        card_uuid = db.add_flashcard(data)
        # Return the created flashcard
        items = db.list_flashcards(q=None, deck_id=data.get("deck_id"), limit=1, offset=0)
        card = next((it for it in items if it.get("uuid") == card_uuid), None)
        if not card:
            # fallback minimal
            card = {
                "uuid": card_uuid,
                "deck_id": data.get("deck_id"),
                "deck_name": None,
                "front": data.get("front"),
                "back": data.get("back"),
                "notes": data.get("notes"),
                "is_cloze": bool(data.get("is_cloze")),
                "tags_json": data.get("tags_json"),
                "ef": 2.5,
                "interval_days": 0,
                "repetitions": 0,
                "lapses": 0,
                "due_at": None,
                "last_reviewed_at": None,
                "created_at": None,
                "last_modified": None,
                "deleted": False,
                "client_id": "",
                "version": 1,
            }
        return card
    except CharactersRAGDBError as e:
        logger.error(f"Failed to create flashcard: {e}")
        raise HTTPException(status_code=500, detail="Failed to create flashcard")


@router.post("/bulk", response_model=FlashcardListResponse)
def create_flashcards_bulk(payload: List[FlashcardCreate], db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    try:
        card_dicts = []
        raw_list = []
        for item in payload:
            data = item.model_dump()
            tags = data.pop("tags", None)
            if tags is not None:
                data["tags_json"] = json.dumps(tags)
            raw_list.append(data)
        uuids = db.add_flashcards_bulk(raw_list)
        # Fetch created cards
        items = db.list_flashcards(limit=len(uuids))
        index = {c["uuid"]: c for c in items}
        for u in uuids:
            if u in index:
                card_dicts.append(index[u])
        return {"items": card_dicts, "count": len(card_dicts)}
    except CharactersRAGDBError as e:
        logger.error(f"Failed bulk create flashcards: {e}")
        raise HTTPException(status_code=500, detail="Failed to create flashcards")


@router.get("", response_model=FlashcardListResponse)
def list_flashcards(
    deck_id: Optional[int] = None,
    tag: Optional[str] = None,
    due_status: Optional[str] = Query('all', pattern="^(new|learning|due|all)$"),
    q: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    order_by: Optional[str] = Query('due_at', pattern="^(due_at|created_at)$"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    try:
        items = db.list_flashcards(deck_id=deck_id, tag=tag, due_status=due_status or 'all', q=q,
                                   include_deleted=False, limit=limit, offset=offset, order_by=order_by or 'due_at')
        return {"items": items, "count": len(items)}
    except CharactersRAGDBError as e:
        logger.error(f"Failed to list flashcards: {e}")
        raise HTTPException(status_code=500, detail="Failed to list flashcards")

@router.get("/{card_uuid}", response_model=Flashcard)
def get_flashcard(card_uuid: str, db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    try:
        card = db.get_flashcard(card_uuid)
        if not card:
            raise HTTPException(status_code=404, detail="Flashcard not found")
        return card
    except CharactersRAGDBError as e:
        logger.error(f"Failed to get flashcard: {e}")
        raise HTTPException(status_code=500, detail="Failed to get flashcard")


@router.patch("/{card_uuid}")
def update_flashcard(card_uuid: str, payload: FlashcardUpdate, db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    try:
        data = payload.model_dump()
        expected_version = data.pop("expected_version", None)
        tags = data.pop("tags", None)
        # Convert tags list to tags_json if provided; also sync to keywords via set_flashcard_tags
        if tags is not None:
            db.set_flashcard_tags(card_uuid, tags)
            data["tags_json"] = json.dumps(tags)
        ok = db.update_flashcard(card_uuid, data, expected_version)
        if not ok:
            raise HTTPException(status_code=404, detail="Flashcard not found or not updated")
        card = db.get_flashcard(card_uuid)
        return card
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except CharactersRAGDBError as e:
        logger.error(f"Failed to update flashcard: {e}")
        raise HTTPException(status_code=500, detail="Failed to update flashcard")


@router.delete("/{card_uuid}")
def delete_flashcard(card_uuid: str, expected_version: int = Query(..., ge=1), db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    try:
        ok = db.soft_delete_flashcard(card_uuid, expected_version)
        if not ok:
            raise HTTPException(status_code=404, detail="Flashcard not found or already deleted")
        return {"deleted": True}
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except CharactersRAGDBError as e:
        logger.error(f"Failed to delete flashcard: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete flashcard")


@router.put("/{card_uuid}/tags")
def set_flashcard_tags(card_uuid: str, payload: FlashcardTagsUpdate, db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    try:
        db.set_flashcard_tags(card_uuid, payload.tags)
        card = db.get_flashcard(card_uuid)
        return card
    except CharactersRAGDBError as e:
        logger.error(f"Failed to set flashcard tags: {e}")
        raise HTTPException(status_code=500, detail="Failed to set flashcard tags")


@router.get("/{card_uuid}/tags")
def get_flashcard_tags(card_uuid: str, db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    try:
        kws = db.get_keywords_for_flashcard(card_uuid)
        return {"items": kws, "count": len(kws)}
    except CharactersRAGDBError as e:
        logger.error(f"Failed to get flashcard tags: {e}")
        raise HTTPException(status_code=500, detail="Failed to get flashcard tags")


@router.post("/import")
def import_flashcards(payload: FlashcardsImportRequest, db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    try:
        delimiter = payload.delimiter or '\t'
        raw_lines = [ln for ln in (payload.content or '').splitlines()]
        header_map: dict[str, int] = {}
        lines = raw_lines
        if payload.has_header and raw_lines:
            header = raw_lines[0]
            lines = raw_lines[1:]
            cols = [c.strip() for c in header.split(delimiter)]
            # Build header map (lower-cased keys)
            for idx, name in enumerate(cols):
                lname = name.strip().lower()
                header_map[lname] = idx
        # Build or cache decks by name
        decks_cache: dict[str, int] = {}
        # Preload existing decks once
        existing_decks = {d.get('name'): d.get('id') for d in db.list_decks(limit=10000, offset=0, include_deleted=False)}
        created: list[dict] = []
        for raw in lines:
            if not raw.strip():
                continue
            parts = raw.split(delimiter)
            # Default mapping: Deck, Front, Back, Tags, Notes
            deck_name = front = back = tags_s = notes = extra = model_type = deck_desc = None
            reverse_flag = None
            is_cloze_flag = None
            def get_col(*names: str) -> Optional[str]:
                for nm in names:
                    idx = header_map.get(nm)
                    if idx is not None and idx < len(parts):
                        return parts[idx].strip()
                return None

            if header_map:
                deck_name = get_col('deck', 'deckname', 'deck_name') or ''
                deck_desc = get_col('deckdescription', 'deck_description', 'deckdesc', 'deck desc')
                front = get_col('front', 'question') or ''
                back = get_col('back', 'answer') or ''
                tags_s = get_col('tags') or ''
                notes = get_col('notes', 'note') or ''
                extra = get_col('extra', 'back extra', 'back_extra') or None
                model_type = (get_col('model_type', 'model', 'type') or '').lower() or None
                rev_val = (get_col('reverse', 'reversed') or '').lower()
                if rev_val in ('1', 'true', 'yes', 'y', 'on'):
                    reverse_flag = True
                elif rev_val in ('0', 'false', 'no', 'n', 'off'):
                    reverse_flag = False
                ic_val = (get_col('iscloze', 'is_cloze') or '').lower()
                if ic_val in ('1', 'true', 'yes', 'y', 'on'):
                    is_cloze_flag = True
                elif ic_val in ('0', 'false', 'no', 'n', 'off'):
                    is_cloze_flag = False
            else:
                # Expect 5 columns: Deck, Front, Back, Tags, Notes
                if len(parts) < 5:
                    parts = parts + [''] * (5 - len(parts))
                deck_name, front, back, tags_s, notes = [p.strip() for p in parts[:5]]
                extra = None
                model_type = None
                reverse_flag = None
                deck_desc = None
                is_cloze_flag = None
            # Resolve deck
            deck_id = None
            if deck_name:
                if deck_name in decks_cache:
                    deck_id = decks_cache[deck_name]
                else:
                    if deck_name in existing_decks:
                        deck_id = existing_decks[deck_name]
                    else:
                        deck_id = db.add_deck(deck_name, description=deck_desc)
                        existing_decks[deck_name] = deck_id
                    decks_cache[deck_name] = deck_id
            # Parse tags from space-delimited
            tags_list = [t for t in (tags_s or '').replace(',', ' ').split() if t]
            # Create card
            data: dict = {
                'deck_id': deck_id,
                'front': front,
                'back': back,
                'notes': notes,
                'tags_json': json.dumps(tags_list) if tags_list else None,
                'model_type': model_type or 'basic',
                'reverse': bool(reverse_flag) if reverse_flag is not None else False,
            }
            if extra:
                data['extra'] = extra
            # If model_type indicates cloze, set is_cloze
            if (model_type or '').lower() == 'cloze' or is_cloze_flag:
                data['is_cloze'] = True
            uuid = db.add_flashcard(data)
            created.append({'uuid': uuid, 'deck_id': deck_id})
            # Also ensure keyword links reflect tags
            if tags_list:
                db.set_flashcard_tags(uuid, tags_list)
        return {'imported': len(created), 'items': created}
    except CharactersRAGDBError as e:
        logger.error(f"Failed to import flashcards TSV: {e}")
        raise HTTPException(status_code=500, detail="Failed to import flashcards")


@router.post("/review", response_model=FlashcardReviewResponse)
def review_flashcard(payload: FlashcardReviewRequest, db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    try:
        updated = db.review_flashcard(payload.card_uuid, payload.rating, payload.answer_time_ms)
        return updated
    except CharactersRAGDBError as e:
        logger.error(f"Failed to review flashcard: {e}")
        raise HTTPException(status_code=500, detail="Failed to review flashcard")


@router.get("/export")
def export_flashcards(
    deck_id: Optional[int] = None,
    tag: Optional[str] = None,
    q: Optional[str] = None,
    format: Optional[str] = Query("csv", pattern="^(csv|apkg)$"),
    include_reverse: Optional[bool] = False,
    delimiter: Optional[str] = Query('\t', description="CSV/TSV delimiter; default tab"),
    include_header: Optional[bool] = Query(False, description="Include header row for CSV/TSV"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    try:
        items = db.list_flashcards(deck_id=deck_id, tag=tag, q=q, due_status='all', include_deleted=False, limit=100000, offset=0)
        if format == 'apkg':
            apkg = export_apkg_from_rows(items, include_reverse=include_reverse)
            return StreamingResponse(iter([apkg]), media_type="application/apkg",
                                     headers={"Content-Disposition": "attachment; filename=flashcards.apkg"})
        # default csv/tsv
        dlm = delimiter or '\t'
        data = db.export_flashcards_csv(deck_id=deck_id, tag=tag, q=q, delimiter=dlm, include_header=bool(include_header))
        media_type = "text/tab-separated-values; charset=utf-8" if dlm == '\t' else "text/csv; charset=utf-8"
        filename = "flashcards.tsv" if dlm == '\t' else "flashcards.csv"
        return StreamingResponse(iter([data]), media_type=media_type,
                                 headers={"Content-Disposition": f"attachment; filename={filename}"})
    except CharactersRAGDBError as e:
        logger.error(f"Failed to export flashcards: {e}")
        raise HTTPException(status_code=500, detail="Failed to export flashcards")
