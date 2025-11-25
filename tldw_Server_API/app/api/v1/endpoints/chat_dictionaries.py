from __future__ import annotations

import datetime
import json
import time
import warnings
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    CharactersRAGDBError,
    ConflictError,
    InputError,
)
from tldw_Server_API.app.api.v1.schemas.chat_dictionary_schemas import (
    TimedEffects,
    ChatDictionaryCreate,
    ChatDictionaryUpdate,
    ChatDictionaryResponse,
    ChatDictionaryWithEntries,
    DictionaryEntryCreate,
    DictionaryEntryUpdate,
    DictionaryEntryResponse,
    ProcessTextRequest,
    ProcessTextResponse,
    ImportDictionaryRequest,
    ImportDictionaryResponse,
    ExportDictionaryResponse,
    ImportDictionaryJSONRequest,
    ExportDictionaryJSONResponse,
    DictionaryListResponse,
    EntryListResponse,
    DictionaryStatistics,
)
from tldw_Server_API.app.core.Character_Chat.chat_dictionary import (
    ChatDictionaryService,
    TokenBudgetExceededWarning,
)

router = APIRouter()


def _coerce_datetime(value: Any) -> datetime.datetime:
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f",
        ):
            try:
                return datetime.datetime.strptime(value, fmt)
            except ValueError:
                continue
        try:
            return datetime.datetime.fromisoformat(value)
        except Exception:
            pass
    return datetime.datetime.utcnow()


def _parse_timed_effects(value: Any) -> Optional[TimedEffects]:
    if value is None:
        return None
    if isinstance(value, TimedEffects):
        return value
    if isinstance(value, dict):
        try:
            return TimedEffects(**value)
        except Exception:
            return None
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return TimedEffects(**parsed)
        except Exception:
            return None
    return None


def _entry_dict_to_response(
    entry_data: Dict[str, Any],
    fallback_dictionary_id: Optional[int] = None,
) -> DictionaryEntryResponse:
    dictionary_id = entry_data.get("dictionary_id") or fallback_dictionary_id
    if dictionary_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dictionary ID missing for entry.",
        )

    pattern = entry_data.get("pattern") or entry_data.get("key") or ""
    replacement = entry_data.get("replacement") or entry_data.get("content") or ""
    probability = entry_data.get("probability", 1.0)
    try:
        probability = float(probability)
    except (TypeError, ValueError):
        probability = 1.0

    max_replacements = entry_data.get("max_replacements", 0)
    try:
        max_replacements = int(max_replacements or 0)
    except (TypeError, ValueError):
        max_replacements = 0

    entry_type = entry_data.get("type")
    if not entry_type:
        entry_type = "regex" if bool(entry_data.get("is_regex")) else "literal"

    enabled = bool(entry_data.get("enabled", entry_data.get("is_enabled", 1)))
    case_sensitive = bool(entry_data.get("case_sensitive", entry_data.get("is_case_sensitive", 1)))

    return DictionaryEntryResponse(
        id=int(entry_data.get("id")),
        dictionary_id=int(dictionary_id),
        pattern=pattern,
        replacement=replacement,
        probability=probability,
        group=entry_data.get("group") or entry_data.get("group_name"),
        timed_effects=_parse_timed_effects(entry_data.get("timed_effects")),
        max_replacements=max_replacements,
        type=entry_type,
        enabled=enabled,
        case_sensitive=case_sensitive,
        created_at=_coerce_datetime(entry_data.get("created_at")),
        updated_at=_coerce_datetime(entry_data.get("updated_at")),
    )


@router.post(
    "/dictionaries",
    response_model=ChatDictionaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat dictionary",
    description="Create a dictionary used for pattern-based text replacements in chat messages.",
    tags=["chat-dictionaries"],
)
async def create_chat_dictionary(
    dictionary: ChatDictionaryCreate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> ChatDictionaryResponse:
    """
    Create a new chat dictionary for pattern-based text replacements.
    """
    try:
        service = ChatDictionaryService(db)
        dict_id = service.create_dictionary(dictionary.name, dictionary.description)

        dict_data = service.get_dictionary(dict_id)
        if not dict_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Dictionary created but could not be retrieved",
            )

        entries = service.get_entries(dictionary_id=dict_id)
        dict_data["entry_count"] = len(entries)

        return ChatDictionaryResponse(**dict_data)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating dictionary: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/dictionaries",
    response_model=DictionaryListResponse,
    summary="List all chat dictionaries",
    description="List dictionaries for the current user. Use include_inactive to show inactive ones.",
    tags=["chat-dictionaries"],
)
async def list_chat_dictionaries(
    include_inactive: bool = Query(False, description="Include inactive dictionaries"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> DictionaryListResponse:
    """List all chat dictionaries for the current user."""
    try:
        service = ChatDictionaryService(db)
        dictionaries = service.list_dictionaries(include_inactive=include_inactive)

        for dict_data in dictionaries:
            entries = service.get_entries(dictionary_id=dict_data["id"], active_only=False)
            dict_data["entry_count"] = len(entries)

        active_count = sum(1 for d in dictionaries if d.get("is_active", True))
        inactive_count = len(dictionaries) - active_count

        dict_responses = [ChatDictionaryResponse(**d) for d in dictionaries]

        return DictionaryListResponse(
            dictionaries=dict_responses,
            total=len(dictionaries),
            active_count=active_count,
            inactive_count=inactive_count,
        )
    except Exception as e:
        logger.error(f"Error listing dictionaries: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/dictionaries/{dictionary_id}",
    response_model=ChatDictionaryWithEntries,
    summary="Get dictionary with entries",
    description="Retrieve a dictionary and all its entries by ID.",
    tags=["chat-dictionaries"],
)
async def get_chat_dictionary(
    dictionary_id: int,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> ChatDictionaryWithEntries:
    """Get a specific dictionary with all its entries."""
    try:
        service = ChatDictionaryService(db)

        dict_data = service.get_dictionary(dictionary_id)
        if not dict_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dictionary not found")

        entries = service.get_entries(dictionary_id=dictionary_id, active_only=False)
        dict_data["entry_count"] = len(entries)

        entry_responses = [
            _entry_dict_to_response(entry_dict, fallback_dictionary_id=dictionary_id) for entry_dict in entries
        ]

        return ChatDictionaryWithEntries(
            **dict_data,
            entries=entry_responses,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dictionary: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put(
    "/dictionaries/{dictionary_id}",
    response_model=ChatDictionaryResponse,
    summary="Update a dictionary",
    description="Update dictionary metadata such as name, description, and active status.",
    tags=["chat-dictionaries"],
)
async def update_chat_dictionary(
    dictionary_id: int,
    update: ChatDictionaryUpdate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> ChatDictionaryResponse:
    """Update a dictionary's metadata."""
    try:
        service = ChatDictionaryService(db)

        success = service.update_dictionary(
            dictionary_id,
            name=update.name,
            description=update.description,
            is_active=update.is_active,
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dictionary not found")

        dict_data = service.get_dictionary(dictionary_id)
        entries = service.get_entries(dictionary_id=dictionary_id)
        dict_data["entry_count"] = len(entries)

        return ChatDictionaryResponse(**dict_data)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating dictionary: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete(
    "/dictionaries/{dictionary_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a dictionary",
    description="Delete a dictionary and its entries.",
    tags=["chat-dictionaries"],
)
async def delete_chat_dictionary(
    dictionary_id: int,
    hard_delete: bool = Query(False, description="Permanently delete instead of soft delete"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> None:
    """Delete a dictionary (soft delete by default)."""
    try:
        service = ChatDictionaryService(db)
        success = service.delete_dictionary(dictionary_id, hard_delete=hard_delete)

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dictionary not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting dictionary: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/dictionaries/{dictionary_id}/entries",
    response_model=DictionaryEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add entry to dictionary",
    description="Add a pattern/replacement entry to a dictionary.",
    tags=["chat-dictionaries"],
)
async def add_dictionary_entry(
    dictionary_id: int,
    entry: DictionaryEntryCreate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> DictionaryEntryResponse:
    """
    Add a new entry to a dictionary.
    """
    try:
        service = ChatDictionaryService(db)

        dict_data = service.get_dictionary(dictionary_id)
        if not dict_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dictionary not found")

        timed_effects_dict = entry.timed_effects.model_dump() if entry.timed_effects else None

        entry_id = service.add_entry(
            dictionary_id,
            pattern=entry.pattern,
            replacement=entry.replacement,
            probability=entry.probability,
            group=entry.group,
            timed_effects=timed_effects_dict,
            max_replacements=entry.max_replacements,
            type=entry.type,
            enabled=entry.enabled,
            case_sensitive=entry.case_sensitive,
        )

        created_entries = service.get_entries(dictionary_id=dictionary_id, active_only=False)
        entry_data = next((item for item in created_entries if item.get("id") == entry_id), None)
        if not entry_data:
            entry_data = {
                "id": entry_id,
                "dictionary_id": dictionary_id,
                "pattern": entry.pattern,
                "replacement": entry.replacement,
                "probability": entry.probability,
                "group": entry.group,
                "timed_effects": entry.timed_effects.model_dump() if entry.timed_effects else None,
                "max_replacements": entry.max_replacements,
                "type": entry.type,
                "enabled": entry.enabled,
                "case_sensitive": entry.case_sensitive,
                "created_at": datetime.datetime.utcnow(),
                "updated_at": datetime.datetime.utcnow(),
            }

        return _entry_dict_to_response(entry_data, fallback_dictionary_id=dictionary_id)
    except InputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding dictionary entry: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/dictionaries/{dictionary_id}/entries",
    response_model=EntryListResponse,
    summary="List dictionary entries",
    description="List entries for a dictionary.",
    tags=["chat-dictionaries"],
)
async def list_dictionary_entries(
    dictionary_id: int,
    group: Optional[str] = Query(None, description="Filter by group"),
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> EntryListResponse:
    """List all entries in a dictionary, optionally filtered by group."""
    try:
        service = ChatDictionaryService(db)

        dict_data = service.get_dictionary(dictionary_id)
        if not dict_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dictionary not found")

        entries = service.get_entries(dictionary_id=dictionary_id, group=group, active_only=False)

        entry_responses = [
            _entry_dict_to_response(entry_dict, fallback_dictionary_id=dictionary_id) for entry_dict in entries
        ]

        return EntryListResponse(
            entries=entry_responses,
            total=len(entries),
            dictionary_id=dictionary_id,
            group=group,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing dictionary entries: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put(
    "/dictionaries/entries/{entry_id}",
    response_model=DictionaryEntryResponse,
    summary="Update dictionary entry",
    description="Update entry fields such as replacement, enabled, group, case sensitivity, and probability.",
    tags=["chat-dictionaries"],
)
async def update_dictionary_entry(
    entry_id: int,
    update: DictionaryEntryUpdate,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> DictionaryEntryResponse:
    """Update a dictionary entry."""
    try:
        service = ChatDictionaryService(db)

        timed_effects_dict = update.timed_effects.model_dump() if update.timed_effects else None

        success = service.update_entry(
            entry_id,
            pattern=update.pattern,
            replacement=update.replacement,
            probability=update.probability,
            group=update.group,
            timed_effects=timed_effects_dict,
            max_replacements=update.max_replacements,
            type=update.type,
            enabled=update.enabled,
            case_sensitive=update.case_sensitive,
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

        dictionary_id_for_entry = service._get_entry_dict_id(entry_id)
        if dictionary_id_for_entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

        refreshed_entries = service.get_entries(dictionary_id=dictionary_id_for_entry, active_only=False)
        updated_entry = next((item for item in refreshed_entries if item.get("id") == entry_id), None)
        if not updated_entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

        return _entry_dict_to_response(updated_entry, fallback_dictionary_id=dictionary_id_for_entry)
    except InputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating dictionary entry: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete(
    "/dictionaries/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete dictionary entry",
    description="Delete a single dictionary entry by ID.",
    tags=["chat-dictionaries"],
)
async def delete_dictionary_entry(
    entry_id: int,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> None:
    """Delete a dictionary entry."""
    try:
        service = ChatDictionaryService(db)
        success = service.delete_entry(entry_id)

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting dictionary entry: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/dictionaries/process",
    response_model=ProcessTextResponse,
    summary="Process text through dictionaries",
    description="Apply active dictionaries to the provided text and return transformed text and statistics.",
    tags=["chat-dictionaries"],
)
async def process_text_with_dictionaries(
    request: ProcessTextRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> ProcessTextResponse:
    """
    Process text through active dictionaries to apply replacements.
    """
    try:
        service = ChatDictionaryService(db)

        start_time = time.time()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")

            processed_text, stats = service.process_text(
                request.text,
                dictionary_id=request.dictionary_id,
                group=request.group,
                max_iterations=request.max_iterations,
                token_budget=request.token_budget,
                return_stats=True,
            )

            token_budget_exceeded = any(
                issubclass(warning.category, TokenBudgetExceededWarning) for warning in caught
            )
            if token_budget_exceeded:
                stats["token_budget_exceeded"] = True

        processing_time_ms = (time.time() - start_time) * 1000

        return ProcessTextResponse(
            original_text=request.text,
            processed_text=(
                processed_text
                if isinstance(processed_text, str)
                else processed_text.get("processed_text", request.text)
            ),
            replacements=stats.get("replacements", 0),
            iterations=stats.get("iterations", 0),
            entries_used=stats.get("entries_used", []),
            token_budget_exceeded=stats.get("token_budget_exceeded", False),
            processing_time_ms=processing_time_ms,
        )
    except Exception as e:
        logger.error(f"Error processing text: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/dictionaries/import",
    response_model=ImportDictionaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import dictionary from markdown",
    description="Create a dictionary and entries from a markdown representation.",
    tags=["chat-dictionaries"],
)
async def import_dictionary(
    import_request: ImportDictionaryRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> ImportDictionaryResponse:
    """
    Import a dictionary from markdown format.
    """
    try:
        service = ChatDictionaryService(db)

        dict_id = service.import_from_markdown(import_request.content, import_request.name)

        entries = service.get_entries(dictionary_id=dict_id, active_only=False)
        groups = list({e.get("group") for e in entries if e.get("group")})

        if import_request.activate:
            service.update_dictionary(dict_id, is_active=True)

        return ImportDictionaryResponse(
            dictionary_id=dict_id,
            name=import_request.name,
            entries_imported=len(entries),
            groups_created=groups,
        )
    except InputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Error importing dictionary: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/dictionaries/{dictionary_id}/export",
    response_model=ExportDictionaryResponse,
    summary="Export dictionary to markdown",
    description="Export a dictionary and entries to a markdown representation.",
    tags=["chat-dictionaries"],
)
async def export_dictionary(
    dictionary_id: int,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> ExportDictionaryResponse:
    """Export a dictionary to markdown format."""
    try:
        service = ChatDictionaryService(db)

        dict_data = service.get_dictionary(dictionary_id)
        if not dict_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dictionary not found")

        content = service.export_to_markdown(dictionary_id)

        entries = service.get_entries(dictionary_id=dictionary_id, active_only=False)
        groups = list({e.get("group") for e in entries if e.get("group")})

        return ExportDictionaryResponse(
            name=dict_data["name"],
            content=content if isinstance(content, str) else str(content),
            entry_count=len(entries),
            group_count=len(groups),
        )
    except InputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting dictionary: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/dictionaries/{dictionary_id}/export/json",
    response_model=ExportDictionaryJSONResponse,
    summary="Export dictionary to JSON",
    description="Export a dictionary and entries to a JSON representation.",
    tags=["chat-dictionaries"],
)
async def export_dictionary_json(
    dictionary_id: int,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> ExportDictionaryJSONResponse:
    """Export a dictionary to JSON."""
    try:
        service = ChatDictionaryService(db)
        data = service.export_to_json(dictionary_id)
        return ExportDictionaryJSONResponse(**data)
    except InputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting dictionary JSON: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/dictionaries/import/json",
    response_model=ImportDictionaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import dictionary from JSON",
    description="Create a dictionary and entries from a JSON payload.",
    tags=["chat-dictionaries"],
)
async def import_dictionary_json(
    import_request: ImportDictionaryJSONRequest,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> ImportDictionaryResponse:
    """Import a dictionary and entries from JSON."""
    try:
        service = ChatDictionaryService(db)
        dict_id = service.import_from_json(import_request.data)
        entries = service.get_entries(dictionary_id=dict_id, active_only=False)
        if import_request.activate:
            service.update_dictionary(dict_id, is_active=True)
        name = import_request.data.get("name") or service.get_dictionary(dict_id).get("name", "Imported")
        return ImportDictionaryResponse(
            dictionary_id=dict_id,
            name=name,
            entries_imported=len(entries),
            groups_created=list({e.get("group") for e in entries if e.get("group")}),
        )
    except InputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Error importing dictionary JSON: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/dictionaries/{dictionary_id}/statistics",
    response_model=DictionaryStatistics,
    summary="Get dictionary statistics",
    description="Return counts, groups, usage metrics, and averages for the specified dictionary.",
    tags=["chat-dictionaries"],
)
async def get_dictionary_statistics(
    dictionary_id: int,
    db: CharactersRAGDB = Depends(get_chacha_db_for_user),
) -> DictionaryStatistics:
    """Get statistics for a dictionary."""
    try:
        service = ChatDictionaryService(db)

        dict_data = service.get_dictionary(dictionary_id)
        if not dict_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dictionary not found")

        stats = service.get_statistics(dictionary_id)
        entries = service.get_entries(dictionary_id=dictionary_id, active_only=False)
        regex_count = int(stats.get("regex_entries", 0))
        total_entries = int(stats.get("total_entries", len(entries)))
        literal_count = int(stats.get("literal_entries", total_entries - regex_count))
        groups = list({e.get("group") for e in entries if e.get("group")})
        avg_probability = (
            sum(float(e.get("probability", 1.0)) for e in entries) / len(entries) if entries else 0.0
        )

        return DictionaryStatistics(
            dictionary_id=dictionary_id,
            name=dict_data["name"],
            total_entries=total_entries,
            regex_entries=regex_count,
            literal_entries=literal_count,
            groups=groups,
            average_probability=avg_probability,
            total_usage_count=service.get_usage_statistics(dictionary_id).get("times_used"),
            last_used=None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dictionary statistics: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

