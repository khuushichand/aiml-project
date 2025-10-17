# flashcards.py
# REST endpoints for Flashcards/Decks backed by ChaChaNotes DB (schema v5)

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from loguru import logger
import re
import os

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced import require_admin
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

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


@router.post("/decks", response_model=Deck)
def create_deck(payload: DeckCreate, db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    try:
        deck_id = db.add_deck(payload.name, payload.description)
        # Return the exact deck row by id
        deck = db.get_deck(deck_id)
        if deck:
            return deck
        # Fallback: minimal shape if retrieval failed (should not happen)
        return {
            "id": deck_id,
            "name": payload.name,
            "description": payload.description,
            "created_at": None,
            "last_modified": None,
            "deleted": False,
            "client_id": "",
            "version": 1,
        }
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
        # Validate deck_id if provided
        deck_id = data.get("deck_id")
        if deck_id is not None:
            deck = db.get_deck(int(deck_id))
            if not deck or bool(deck.get("deleted")):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Deck not found",
                        "invalid_deck_ids": [int(deck_id)],
                        "message": "Fix or remove invalid deck_id and retry",
                    },
                )
        # Cloze validation if requested
        eff_is_cloze = (str(data.get("model_type") or "").lower() == "cloze") or bool(data.get("is_cloze"))
        if eff_is_cloze:
            if not re.search(r"\{\{c\d+::", data.get("front") or ""):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Invalid cloze",
                        "invalid_fields": ["front"],
                        "message": "Front must contain one or more {{cN::...}} patterns",
                    },
                )
        card_uuid = db.add_flashcard(data)
        # Link keyword tags if provided
        if tags:
            try:
                db.set_flashcard_tags(card_uuid, tags)
            except Exception as _e:
                logger.warning(f"Failed to link tags->keywords on create: {_e}")
        # Return the created flashcard via direct fetch
        card = db.get_flashcard(card_uuid)
        if not card:
            raise HTTPException(status_code=500, detail="Failed to fetch created flashcard")
        return card
    except CharactersRAGDBError as e:
        logger.error(f"Failed to create flashcard: {e}")
        raise HTTPException(status_code=500, detail="Failed to create flashcard")


@router.post("/bulk", response_model=FlashcardListResponse)
def create_flashcards_bulk(payload: List[FlashcardCreate], db: CharactersRAGDB = Depends(get_chacha_db_for_user)):
    try:
        card_dicts = []
        raw_list = []
        tag_lists: List[Optional[List[str]]] = []
        deck_ids_to_validate: set[int] = set()
        for item in payload:
            data = item.model_dump()
            tags = data.pop("tags", None)
            if tags is not None:
                data["tags_json"] = json.dumps(tags)
            tag_lists.append(tags)
            if data.get("deck_id") is not None:
                try:
                    deck_ids_to_validate.add(int(data.get("deck_id")))
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid deck_id type")
            raw_list.append(data)
        # Validate all referenced deck IDs before inserting; collect all invalids
        invalid_deck_ids: List[int] = []
        for did in deck_ids_to_validate:
            d = db.get_deck(did)
            if not d or bool(d.get("deleted")):
                invalid_deck_ids.append(did)
        if invalid_deck_ids:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "One or more decks not found",
                    "invalid_deck_ids": sorted(invalid_deck_ids),
                    "message": "Fix or remove invalid deck_id values and retry",
                },
            )
        uuids = db.add_flashcards_bulk(raw_list)
        # Link keyword tags for each created card
        for u, tags in zip(uuids, tag_lists):
            if tags:
                try:
                    db.set_flashcard_tags(u, tags)
                except Exception as _e:
                    logger.warning(f"Failed to link tags for {u}: {_e}")
        # Fetch created cards precisely by uuid (order-preserving)
        try:
            items = db.get_flashcards_by_uuids(uuids)
            index = {c["uuid"]: c for c in items}
            for u in uuids:
                if u in index:
                    card_dicts.append(index[u])
        except Exception:
            for u in uuids:
                c = db.get_flashcard(u)
                if c:
                    card_dicts.append(c)
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
        total = db.count_flashcards(deck_id=deck_id, tag=tag, due_status=due_status or 'all', q=q, include_deleted=False)
        return {"items": items, "count": len(items), "total": int(total)}
    except CharactersRAGDBError as e:
        logger.error(f"Failed to list flashcards: {e}")
        raise HTTPException(status_code=500, detail="Failed to list flashcards")

## (export endpoint moved earlier)

## Note: /export endpoint is defined above to avoid path shadowing by /{card_uuid}

@router.get("/id/{card_uuid}", response_model=Flashcard)
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
        # Validate cloze if model_type/is_cloze implies cloze
        current = db.get_flashcard(card_uuid)
        if not current:
            raise HTTPException(status_code=404, detail="Flashcard not found")
        incoming_model = data.get("model_type")
        incoming_is_cloze = data.get("is_cloze")
        # derive effective model type
        effective_is_cloze = False
        if incoming_model is not None:
            effective_is_cloze = (str(incoming_model).lower() == "cloze")
        elif incoming_is_cloze is not None:
            effective_is_cloze = bool(incoming_is_cloze)
        else:
            effective_is_cloze = (current.get("model_type") == "cloze") or bool(current.get("is_cloze"))
        if effective_is_cloze:
            front_text = data.get("front") if data.get("front") is not None else (current.get("front") or "")
            if not re.search(r"\{\{c\d+::", front_text):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Invalid cloze",
                        "invalid_fields": ["front"],
                        "message": "Front must contain one or more {{cN::...}} patterns",
                    },
                )
        # If tags provided, update keyword links and avoid duplicating tags_json update here
        if tags is not None:
            db.set_flashcard_tags(card_uuid, tags)
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
def import_flashcards(
    payload: FlashcardsImportRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    max_lines: Optional[int] = Query(None, ge=1, description="Admin override: max lines to import (cannot exceed env cap)"),
    max_line_length: Optional[int] = Query(None, ge=1, description="Admin override: max line length in bytes (cannot exceed env cap)"),
    max_field_length: Optional[int] = Query(None, ge=1, description="Admin override: max field length in bytes (cannot exceed env cap)"),
    current_user: User = Depends(get_request_user)
):
    try:
        delimiter = payload.delimiter or '\t'
        raw_lines = [ln for ln in (payload.content or '').splitlines()]
        header_map: dict[str, int] = {}
        lines = raw_lines
        errors: list[dict] = []
        # Abuse caps
        # Configurable caps via environment
        def _int_env(name: str, default: int) -> int:
            try:
                v = int(os.getenv(name, str(default)))
                return max(1, v)
            except Exception:
                return default
        ENV_MAX_LINES = _int_env('FLASHCARDS_IMPORT_MAX_LINES', 10000)
        ENV_MAX_LINE_LENGTH = _int_env('FLASHCARDS_IMPORT_MAX_LINE_LENGTH', 32768)
        ENV_MAX_FIELD_LENGTH = _int_env('FLASHCARDS_IMPORT_MAX_FIELD_LENGTH', 8192)
        # Effective caps: query param can only lower the env caps, and requires admin to use
        if any(p is not None for p in (max_lines, max_line_length, max_field_length)):
            require_admin(current_user)
        MAX_LINES = min(ENV_MAX_LINES, max_lines) if max_lines else ENV_MAX_LINES
        MAX_LINE_LENGTH = min(ENV_MAX_LINE_LENGTH, max_line_length) if max_line_length else ENV_MAX_LINE_LENGTH
        MAX_FIELD_LENGTH = min(ENV_MAX_FIELD_LENGTH, max_field_length) if max_field_length else ENV_MAX_FIELD_LENGTH
        if payload.has_header and raw_lines:
            header = raw_lines[0]
            lines = raw_lines[1:]
            cols = [c.strip() for c in header.split(delimiter)]
            # Build header map (lower-cased keys)
            for idx, name in enumerate(cols):
                lname = name.strip().lower()
                header_map[lname] = idx
                # Also support variants without underscores (e.g., ModelType -> modeltype)
                header_map[lname.replace('_', '')] = idx
        # Build or cache decks by name
        decks_cache: dict[str, int] = {}
        # Preload existing decks once
        existing_decks = {d.get('name'): d.get('id') for d in db.list_decks(limit=10000, offset=0, include_deleted=False)}
        default_deck_name = 'Default'
        # Ensure default deck exists in cache
        if default_deck_name not in existing_decks:
            did = db.add_deck(default_deck_name, description=None)
            existing_decks[default_deck_name] = did
        decks_cache.update(existing_decks)
        created: list[dict] = []
        processed = 0
        for i, raw in enumerate(lines, start=1):
            if processed >= MAX_LINES:
                errors.append({'line': None, 'error': f'Maximum import line limit reached ({MAX_LINES})'})
                break
            if not raw.strip():
                continue
            # Enforce line length in bytes
            if len(raw.encode('utf-8')) > MAX_LINE_LENGTH:
                errors.append({'line': (i + 1 if payload.has_header else i), 'error': f'Line too long (>{MAX_LINE_LENGTH} bytes)'})
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
                model_type = (get_col('model_type', 'modeltype', 'model', 'type') or '').lower() or None
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

            # Basic validation: require front text (don't import empty rows)
            if not (front and front.strip()):
                errors.append({
                    'line': (i + 1 if payload.has_header else i),
                    'error': 'Missing required field: Front'
                })
                continue
            # Field length caps
            field_lengths = {
                'Deck': deck_name or '',
                'Front': front or '',
                'Back': back or '',
                'Tags': tags_s or '',
                'Notes': notes or '',
                'Extra': extra or '',
                'DeckDescription': deck_desc or '',
            }
            # Enforce field caps using UTF-8 byte length
            too_long = next(((k, v) for k, v in field_lengths.items() if len(v.encode('utf-8')) > MAX_FIELD_LENGTH), None)
            if too_long:
                errors.append({
                    'line': (i + 1 if payload.has_header else i),
                    'error': f'Field too long: {too_long[0]} (> {MAX_FIELD_LENGTH} bytes)'
                })
                continue

            # If header explicitly contains a deck column, enforce non-empty deck
            deck_keys = {'deck', 'deckname', 'deck_name'}
            if header_map and any(k in header_map for k in deck_keys) and not deck_name:
                errors.append({
                    'line': (i + 1 if payload.has_header else i),
                    'error': 'Missing required field: Deck'
                })
                continue

            # Stricter cloze rule: if cloze model or flag, require cN pattern in front
            effective_is_cloze = ((model_type or '') == 'cloze') or (is_cloze_flag is True)
            if effective_is_cloze and not re.search(r"\{\{c\d+::", front):
                errors.append({
                    'line': (i + 1 if payload.has_header else i),
                    'error': 'Invalid cloze: Front must contain one or more {{cN::...}} patterns'
                })
                continue
            # Resolve deck; default to 'Default' when none provided
            deck_id = None
            eff_deck_name = deck_name or default_deck_name
            if eff_deck_name in decks_cache:
                deck_id = decks_cache[eff_deck_name]
            else:
                if eff_deck_name in existing_decks:
                    deck_id = existing_decks[eff_deck_name]
                else:
                    deck_id = db.add_deck(eff_deck_name, description=deck_desc)
                    existing_decks[eff_deck_name] = deck_id
                decks_cache[eff_deck_name] = deck_id
            # Parse tags from space-delimited
            tags_list = [t for t in (tags_s or '').replace(',', ' ').split() if t]
            # Determine effective model type
            if ((model_type or '').lower() == 'cloze') or (is_cloze_flag is True):
                eff_model_type = 'cloze'
            elif (model_type or '') in ('basic', 'basic_reverse'):
                eff_model_type = model_type  # type: ignore[assignment]
            elif reverse_flag is True:
                eff_model_type = 'basic_reverse'
            else:
                eff_model_type = 'basic'

            # Create card
            data: dict = {
                'deck_id': deck_id,
                'front': front,
                'back': back,
                'notes': notes,
                'tags_json': json.dumps(tags_list) if tags_list else None,
                'model_type': eff_model_type,
                'reverse': True if eff_model_type == 'basic_reverse' else False,
            }
            if extra:
                data['extra'] = extra
            if eff_model_type == 'cloze':
                data['is_cloze'] = True
            uuid = db.add_flashcard(data)
            created.append({'uuid': uuid, 'deck_id': deck_id})
            # Also ensure keyword links reflect tags
            if tags_list:
                db.set_flashcard_tags(uuid, tags_list)
            processed += 1
        return {'imported': len(created), 'items': created, 'errors': errors}
    except HTTPException:
        raise
    except CharactersRAGDBError as e:
        logger.error(f"Failed to import flashcards: {e}")
        raise HTTPException(status_code=500, detail="Failed to import flashcards")
    except Exception as e:
        logger.error(f"TSV import failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to import TSV flashcards")


@router.post("/import/json")
async def import_flashcards_json(
    file: UploadFile = File(...),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
    max_items: Optional[int] = Query(None, ge=1, description="Admin override: max JSON items to import (cannot exceed env cap)"),
    max_field_length: Optional[int] = Query(None, ge=1, description="Admin override: max field length in bytes (cannot exceed env cap)"),
    current_user: User = Depends(get_request_user)
):
    try:
        raw = await file.read()
        # Caps via env
        def _int_env(name: str, default: int) -> int:
            try:
                return max(1, int(os.getenv(name, str(default))))
            except Exception:
                return default
        ENV_MAX_ITEMS = _int_env('FLASHCARDS_IMPORT_MAX_LINES', 10000)
        ENV_MAX_FIELD_LENGTH = _int_env('FLASHCARDS_IMPORT_MAX_FIELD_LENGTH', 8192)
        if any(p is not None for p in (max_items, max_field_length)):
            require_admin(current_user)
        MAX_ITEMS = min(ENV_MAX_ITEMS, max_items) if max_items else ENV_MAX_ITEMS
        MAX_FIELD_LENGTH = min(ENV_MAX_FIELD_LENGTH, max_field_length) if max_field_length else ENV_MAX_FIELD_LENGTH

        # Parse JSON: accept array or object with 'items' key
        import json as _json
        text = raw.decode('utf-8')
        try:
            data = _json.loads(text)
        except Exception:
            # Try JSON Lines: one JSON object per line
            items = []
            for ln in text.splitlines():
                if not ln.strip():
                    continue
                try:
                    items.append(_json.loads(ln))
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid JSON/JSONL upload: failed to parse a line")
            data = {'items': items}

        if isinstance(data, dict) and 'items' in data:
            items = data.get('items')
        else:
            items = data
        if not isinstance(items, list):
            raise HTTPException(status_code=400, detail="JSON content must be a list of objects or {'items': [...]} ")

        # Deck cache
        existing_decks = {d.get('name'): d.get('id') for d in db.list_decks(limit=10000, offset=0, include_deleted=False)}
        decks_cache: dict[str, int] = dict(existing_decks)
        default_deck_name = 'Default'
        if default_deck_name not in decks_cache:
            did = db.add_deck(default_deck_name, description=None)
            decks_cache[default_deck_name] = did
            existing_decks[default_deck_name] = did

        errors: list[dict] = []
        created: list[dict] = []
        processed = 0
        for idx, obj in enumerate(items, start=1):
            if processed >= MAX_ITEMS:
                errors.append({'index': idx, 'error': f'Maximum import item limit reached ({MAX_ITEMS})'})
                break
            if not isinstance(obj, dict):
                errors.append({'index': idx, 'error': 'Item must be a JSON object'})
                continue
            deck_name = (obj.get('deck') or obj.get('deck_name') or '').strip()
            deck_desc = (obj.get('deck_description') or obj.get('deckdesc') or obj.get('deckDescription') or None)
            front = (obj.get('front') or obj.get('question') or '').strip()
            back = (obj.get('back') or obj.get('answer') or '').strip()
            notes = (obj.get('notes') or obj.get('note') or '')
            extra = obj.get('extra')
            model_type = (obj.get('model_type') or obj.get('model') or obj.get('type') or '').lower() or None
            reverse_flag = obj.get('reverse')
            is_cloze_flag = obj.get('is_cloze')
            tags_val = obj.get('tags')
            if isinstance(tags_val, list):
                tags_list = [str(t) for t in tags_val]
            elif isinstance(tags_val, str):
                tags_list = [t for t in tags_val.replace(',', ' ').split() if t]
            else:
                tags_list = []

            # Validation
            if not front:
                errors.append({'index': idx, 'error': 'Missing required field: Front'})
                continue
            if deck_name == '':
                eff_deck = default_deck_name
            else:
                eff_deck = deck_name
            # Field caps
            fields = {
                'Deck': eff_deck,
                'Front': front,
                'Back': back,
                'Notes': notes or '',
                'Extra': extra or '',
                'DeckDescription': deck_desc or ''
            }
            too_long = next(((k, v) for k, v in fields.items() if len((v or '').encode('utf-8')) > MAX_FIELD_LENGTH), None)
            if too_long:
                errors.append({'index': idx, 'error': f'Field too long: {too_long[0]} (> {MAX_FIELD_LENGTH} bytes)'} )
                continue
            # Cloze validation
            effective_is_cloze = ((model_type or '') == 'cloze') or (is_cloze_flag is True)
            if effective_is_cloze and not re.search(r"\{\{c\d+::", front):
                errors.append({'index': idx, 'error': 'Invalid cloze: Front must contain one or more {{cN::...}} patterns'})
                continue

            # Resolve/create deck
            if eff_deck in decks_cache:
                deck_id = decks_cache[eff_deck]
            else:
                deck_id = db.add_deck(eff_deck, description=deck_desc)
                decks_cache[eff_deck] = deck_id
                existing_decks[eff_deck] = deck_id

            # Determine effective model type
            if effective_is_cloze:
                eff_model_type = 'cloze'
            elif (model_type or '') in ('basic', 'basic_reverse', 'cloze'):
                eff_model_type = model_type  # type: ignore[assignment]
            elif reverse_flag is True:
                eff_model_type = 'basic_reverse'
            else:
                eff_model_type = 'basic'

            # Build card
            data: dict = {
                'deck_id': deck_id,
                'front': front,
                'back': back,
                'notes': notes,
                'tags_json': _json.dumps(tags_list) if tags_list else None,
                'model_type': eff_model_type,
                'reverse': True if eff_model_type == 'basic_reverse' else False,
            }
            if extra:
                data['extra'] = extra
            if effective_is_cloze:
                data['is_cloze'] = True

            uuid = db.add_flashcard(data)
            created.append({'uuid': uuid, 'deck_id': deck_id})
            if tags_list:
                db.set_flashcard_tags(uuid, tags_list)
            processed += 1

        return {'imported': len(created), 'items': created, 'errors': errors}
    except HTTPException:
        raise
    except CharactersRAGDBError as e:
        logger.error(f"Failed to import JSON flashcards: {e}")
        raise HTTPException(status_code=500, detail="Failed to import flashcards")
    except Exception as e:
        logger.error(f"JSON import failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to import JSON flashcards")


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
    extended_header: Optional[bool] = Query(False, description="Include Extra and Reverse columns"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user)
):
    try:
        items = db.list_flashcards(deck_id=deck_id, tag=tag, q=q, due_status='all', include_deleted=False, limit=100000, offset=0)
        if format == 'apkg':
            # Normalize rows: when include_reverse is False and both basic + basic_reverse exist,
            # demote basic_reverse to basic to match integration expectations.
            has_basic = any((it.get('model_type') == 'basic') for it in items)
            has_basic_rev = any((it.get('model_type') == 'basic_reverse') for it in items)
            rows = []
            for r in items:
                r2 = dict(r)
                if not include_reverse and has_basic and has_basic_rev and (r2.get('model_type') == 'basic_reverse'):
                    r2['model_type'] = 'basic'
                    r2['reverse'] = False
                rows.append(r2)
            apkg = export_apkg_from_rows(rows, include_reverse=include_reverse)
            return StreamingResponse(iter([apkg]), media_type="application/apkg",
                                     headers={"Content-Disposition": "attachment; filename=flashcards.apkg"})
        # default csv/tsv
        dlm = delimiter or '\t'
        data = db.export_flashcards_csv(deck_id=deck_id, tag=tag, q=q, delimiter=dlm, include_header=bool(include_header), extended_header=bool(extended_header))
        media_type = "text/tab-separated-values; charset=utf-8" if dlm == '\t' else "text/csv; charset=utf-8"
        filename = "flashcards.tsv" if dlm == '\t' else "flashcards.csv"
        return StreamingResponse(iter([data]), media_type=media_type,
                                 headers={"Content-Disposition": f"attachment; filename={filename}"})
    except CharactersRAGDBError as e:
        logger.error(f"Failed to export flashcards: {e}")
        raise HTTPException(status_code=500, detail="Failed to export flashcards")
