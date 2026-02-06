from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Sequence
from typing import Any

from loguru import logger

from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import DEFAULT_LLM_PROVIDER
from tldw_Server_API.app.core.Chat.Chat_Deps import ChatConfigurationError
from tldw_Server_API.app.core.Chat.chat_helpers import extract_response_content
from tldw_Server_API.app.core.Chat.chat_service import resolve_provider_api_key
from tldw_Server_API.app.core.config import load_and_log_configs
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase, get_latest_transcription
from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry
from tldw_Server_API.app.core.LLM_Calls.provider_metadata import provider_requires_api_key

DEFAULT_QUESTION_TYPES = ["multiple_choice", "true_false", "fill_blank"]
MAX_CONTENT_CHARS = 15000

QUIZ_GENERATION_PROMPT = """You are a quiz generator. Based on the following content, generate {num_questions} quiz questions.


Content:
{content}

Requirements:
- Difficulty: {difficulty}
- Question types to include: {question_types}
{focus_instruction}

Return a JSON object in this exact format:
{{
  "questions": [
    {{
      "question_type": "multiple_choice" | "true_false" | "fill_blank",
      "question_text": "The question text",
      "options": ["A", "B", "C", "D"],
      "correct_answer": 0 | 1 | 2 | 3 | "true" | "false" | "the answer",
      "explanation": "Brief explanation of why this is correct",
      "points": 1
    }}
  ]
}}

Important:
- For multiple_choice: options must be array of 4 strings, correct_answer is 0-based index (0-3)
- For true_false: correct_answer must be exactly "true" or "false"
- For fill_blank: question_text should contain ___ where answer goes, correct_answer is the word/phrase
- Vary question difficulty according to the specified level
- Make questions test understanding, not just memorization
- Return ONLY valid JSON, no other text
"""


def _resolve_model(provider: str, model: str | None, app_config: dict[str, Any]) -> str | None:
    if model:
        return model
    key = f"{provider.replace('-', '_').replace('.', '_')}_api"
    return (app_config.get(key) or {}).get("model")


def _get_adapter(provider: str):
    registry = get_registry()
    adapter = registry.get_adapter(provider)
    if adapter is None:
        raise ChatConfigurationError(provider=provider, message="LLM adapter unavailable.")
    return adapter


def _normalize_question_type(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    aliases = {
        "multiple choice": "multiple_choice",
        "multiple-choice": "multiple_choice",
        "true/false": "true_false",
        "true-false": "true_false",
        "fill in the blank": "fill_blank",
        "fill-in-the-blank": "fill_blank",
    }
    return aliases.get(text, text)


def _coerce_question_types(question_types: Sequence[Any] | None) -> list[str]:
    if not question_types:
        return list(DEFAULT_QUESTION_TYPES)
    normalized: list[str] = []
    for item in question_types:
        raw = getattr(item, "value", item)
        q_type = _normalize_question_type(raw)
        if q_type in DEFAULT_QUESTION_TYPES and q_type not in normalized:
            normalized.append(q_type)
    return normalized or list(DEFAULT_QUESTION_TYPES)


def _coerce_options(raw: Any) -> list[str]:
    if isinstance(raw, list):
        options = [str(opt).strip() for opt in raw if str(opt).strip()]
    elif isinstance(raw, str):
        if "\n" in raw:
            options = [part.strip() for part in raw.splitlines() if part.strip()]
        elif "|" in raw:
            options = [part.strip() for part in raw.split("|") if part.strip()]
        elif ";" in raw:
            options = [part.strip() for part in raw.split(";") if part.strip()]
        else:
            options = []
    else:
        options = []
    if len(options) > 4:
        options = options[:4]
    return options


def _normalize_mc_answer(raw: Any, options: list[str]) -> int:
    if raw is None:
        return 0
    if isinstance(raw, (int, float)):
        idx = int(raw)
        if 0 <= idx < len(options):
            return idx
        return 0
    text = str(raw).strip()
    if text.isdigit():
        idx = int(text)
        if 0 <= idx < len(options):
            return idx
        return 0
    if len(text) == 1 and text.upper() in {"A", "B", "C", "D"}:
        idx = ord(text.upper()) - ord("A")
        if 0 <= idx < len(options):
            return idx
        return 0
    if options:
        for idx, option in enumerate(options):
            if option.strip().lower() == text.lower():
                return idx
    return 0


def _normalize_tf_answer(raw: Any) -> str:
    text = str(raw).strip().lower()
    return "true" if text in {"true", "1", "yes", "y"} else "false"


def _extract_json_payload(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if raw is None:
        raise ValueError("LLM response was empty")
    text = str(raw).strip()
    if not text:
        raise ValueError("LLM response was empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for open_char, close_char in (("{", "}"), ("[", "]")):
        start_idx = text.find(open_char)
        end_idx = text.rfind(close_char)
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            continue
        snippet = text[start_idx:end_idx + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            continue
    raise ValueError("Failed to parse quiz JSON from LLM response")


def _normalize_questions(raw_questions: Sequence[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in raw_questions:
        if not isinstance(raw, dict):
            continue
        q_type = _normalize_question_type(raw.get("question_type"))
        if q_type not in DEFAULT_QUESTION_TYPES:
            continue
        question_text = str(raw.get("question_text") or raw.get("question") or "").strip()
        if not question_text:
            continue
        points = raw.get("points", 1)
        try:
            points_val = int(points)
        except (TypeError, ValueError):
            points_val = 1

        options: list[str] | None = None
        correct_answer: int | str
        if q_type == "multiple_choice":
            options = _coerce_options(raw.get("options"))
            correct_answer = _normalize_mc_answer(raw.get("correct_answer"), options)
        elif q_type == "true_false":
            correct_answer = _normalize_tf_answer(raw.get("correct_answer"))
        else:
            correct_answer = str(raw.get("correct_answer") or "").strip()

        normalized.append(
            {
                "question_type": q_type,
                "question_text": question_text,
                "options": options,
                "correct_answer": correct_answer,
                "explanation": str(raw.get("explanation") or "").strip() or None,
                "points": points_val if points_val >= 0 else 1,
            }
        )
    return normalized


async def generate_quiz_from_media(
    *,
    db: CharactersRAGDB,
    media_db: MediaDatabase,
    media_id: int,
    num_questions: int = 10,
    question_types: list[Any] | None = None,
    difficulty: str = "mixed",
    focus_topics: list[str] | None = None,
    model: str | None = None,
    workspace_tag: str | None = None,
) -> dict[str, Any]:
    """
    Generate a quiz from media content using an LLM.

    1. Fetch media content
    2. Build prompt
    3. Call LLM
    4. Parse response
    5. Create quiz + questions in database
    6. Return created quiz + questions
    """
    media = media_db.get_media_by_id(media_id, include_deleted=False, include_trash=False)
    if not media:
        raise ValueError(f"Media {media_id} not found")

    content = str(media.get("content") or "").strip()
    if not content:
        content = (get_latest_transcription(media_db, media_id) or "").strip()
    if not content:
        raise ValueError(f"Media {media_id} has no content to generate quiz from")
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "..."

    normalized_types = _coerce_question_types(question_types)
    focus_instruction = ""
    if focus_topics:
        focus_instruction = f"- Focus on these topics: {', '.join(t for t in focus_topics if t)}"

    prompt = QUIZ_GENERATION_PROMPT.format(
        num_questions=num_questions,
        content=content,
        difficulty=difficulty,
        question_types=", ".join(normalized_types),
        focus_instruction=focus_instruction,
    )

    provider = (DEFAULT_LLM_PROVIDER or "openai").strip().lower()
    api_key, _debug = resolve_provider_api_key(provider, prefer_module_keys_in_tests=True)
    if provider_requires_api_key(provider) and not api_key:
        raise ValueError(f"Provider '{provider}' requires an API key.")

    messages_payload = [{"role": "user", "content": prompt}]
    response_format = {"type": "json_object"}

    def _call_llm():
        adapter = _get_adapter(provider)
        app_config = load_and_log_configs() or {}
        model_to_use = _resolve_model(provider, model, app_config)
        if model_to_use is None:
            raise ChatConfigurationError(provider=provider, message="Model is required for provider.")
        return adapter.chat(
            {
                "messages": messages_payload,
                "api_key": api_key,
                "model": model_to_use,
                "temperature": 0.3,
                "max_tokens": 2000,
                "response_format": response_format,
                "app_config": app_config,
            }
        )

    start = time.time()
    raw_response = await asyncio.get_running_loop().run_in_executor(None, _call_llm)
    logger.info("Quiz generation LLM call completed in {:.1f}ms", (time.time() - start) * 1000.0)

    content_text = extract_response_content(raw_response)
    payload = _extract_json_payload(content_text if content_text is not None else raw_response)
    raw_questions = payload.get("questions") if isinstance(payload, dict) else payload
    if not isinstance(raw_questions, list):
        raise ValueError("LLM response did not include a questions list")

    questions = _normalize_questions(raw_questions)
    if num_questions and len(questions) > num_questions:
        questions = questions[:num_questions]
    if not questions:
        raise ValueError("No valid questions generated")

    quiz_title = str(media.get("title") or f"Media #{media_id}").strip()
    quiz_id = db.create_quiz(
        name=f"Quiz: {quiz_title}" if quiz_title else f"Quiz: Media #{media_id}",
        description="Auto-generated quiz from media content",
        workspace_tag=workspace_tag,
        media_id=media_id,
    )
    for idx, question in enumerate(questions):
        db.create_question(
            quiz_id=quiz_id,
            question_type=question["question_type"],
            question_text=question["question_text"],
            correct_answer=question["correct_answer"],
            options=question.get("options"),
            explanation=question.get("explanation"),
            points=question.get("points", 1),
            order_index=idx,
        )

    quiz = db.get_quiz(quiz_id)
    if not quiz:
        raise ValueError("Failed to load generated quiz")
    questions_payload = db.list_questions(quiz_id, include_answers=True, limit=None, offset=0)
    return {
        "quiz": quiz,
        "questions": questions_payload.get("items", []),
    }
