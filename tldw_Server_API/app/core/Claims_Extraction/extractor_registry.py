from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Claims_Extraction.extractor_catalog import (
    LLM_PROVIDER_MODES,
    detect_claims_language,
    get_spacy_pipeline,
    resolve_claims_extractor_mode,
    resolve_ner_model_name,
    split_claims_sentences,
)


ClaimsExtractorCallable = Callable[[str, int, str | None], list[str] | Awaitable[list[str]]]


@dataclass(frozen=True)
class ClaimsExtractionDispatch:
    mode: str
    language: str
    claim_texts: list[str]


def extract_heuristic_claims_texts(text: str, max_claims: int, language: str | None = None) -> list[str]:
    return split_claims_sentences(text, language or detect_claims_language(text), max_sentences=max_claims)


def extract_ner_claims_texts(text: str, max_claims: int, language: str | None = None) -> list[str]:
    lang = language or detect_claims_language(text)
    model_name = resolve_ner_model_name(lang)
    nlp = get_spacy_pipeline(model_name, lang)
    if nlp is None or not nlp.has_pipe("ner"):
        raise RuntimeError("spaCy NER pipeline unavailable")
    doc = nlp(text)
    out: list[str] = []
    for sent in getattr(doc, "sents", [doc]):
        has_ent = any(getattr(ent, "label_", "") for ent in getattr(sent, "ents", []))
        if not has_ent:
            continue
        sentence = sent.text.strip()
        if len(sentence) >= 12:
            out.append(sentence)
        if len(out) >= max_claims:
            break
    return out


def resolve_claims_strategy_mode(
    requested_mode: str | None,
    *,
    text: str,
    strategy_map: Mapping[str, ClaimsExtractorCallable],
    language: str | None = None,
    provider_modes: set[str] | None = None,
) -> tuple[str, str]:
    mode = (requested_mode or "heuristic").strip().lower()
    lang = (language or "").strip().lower() or detect_claims_language(text)

    if mode in {"auto", "detect"}:
        resolved_mode, resolved_lang = resolve_claims_extractor_mode(mode, text)
        mode = resolved_mode
        lang = resolved_lang or lang

    if mode == "simple":
        mode = "heuristic"

    provider_aliases = provider_modes or LLM_PROVIDER_MODES
    if mode in provider_aliases and "llm" in strategy_map:
        mode = "llm"

    if mode not in strategy_map:
        if "llm" in strategy_map and mode not in {"heuristic", "ner", "aps"}:
            mode = "llm"
        elif "heuristic" in strategy_map:
            mode = "heuristic"
        elif strategy_map:
            mode = next(iter(strategy_map.keys()))
        else:
            mode = "heuristic"

    return mode, lang


def _coerce_claim_texts(values: Any, max_claims: int) -> list[str]:
    out: list[str] = []
    if not isinstance(values, list):
        return out
    for value in values:
        if isinstance(value, str) and value.strip():
            out.append(value.strip())
        if len(out) >= max_claims:
            break
    return out


def _execute_sync_strategy(
    strategy: ClaimsExtractorCallable,
    *,
    text: str,
    max_claims: int,
    language: str | None,
) -> list[str]:
    value = strategy(text, max_claims, language)
    if inspect.isawaitable(value):
        raise RuntimeError("Async extractor strategy cannot be executed in sync mode.")
    return _coerce_claim_texts(value, max_claims)


async def _execute_async_strategy(
    strategy: ClaimsExtractorCallable,
    *,
    text: str,
    max_claims: int,
    language: str | None,
) -> list[str]:
    value = strategy(text, max_claims, language)
    if inspect.isawaitable(value):
        value = await value  # type: ignore[assignment]
    return _coerce_claim_texts(value, max_claims)


def run_sync_claims_strategy(
    *,
    requested_mode: str | None,
    text: str,
    max_claims: int,
    strategy_map: Mapping[str, ClaimsExtractorCallable],
    fallback_mode: str = "heuristic",
    language: str | None = None,
    provider_modes: set[str] | None = None,
    catch_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> ClaimsExtractionDispatch:
    mode, lang = resolve_claims_strategy_mode(
        requested_mode,
        text=text,
        strategy_map=strategy_map,
        language=language,
        provider_modes=provider_modes,
    )

    strategy = strategy_map.get(mode)
    if strategy is None:
        return ClaimsExtractionDispatch(mode=mode, language=lang, claim_texts=[])

    try:
        claim_texts = _execute_sync_strategy(strategy, text=text, max_claims=max_claims, language=lang)
        if claim_texts:
            return ClaimsExtractionDispatch(mode=mode, language=lang, claim_texts=claim_texts)
    except catch_exceptions as exc:
        logger.debug(f"Claims extractor strategy '{mode}' failed: {exc}")

    fallback = strategy_map.get(fallback_mode)
    if fallback is None or fallback_mode == mode:
        return ClaimsExtractionDispatch(mode=mode, language=lang, claim_texts=[])

    try:
        claim_texts = _execute_sync_strategy(fallback, text=text, max_claims=max_claims, language=lang)
    except catch_exceptions as exc:
        logger.debug(f"Claims fallback strategy '{fallback_mode}' failed: {exc}")
        claim_texts = []
    return ClaimsExtractionDispatch(mode=fallback_mode, language=lang, claim_texts=claim_texts)


async def run_async_claims_strategy(
    *,
    requested_mode: str | None,
    text: str,
    max_claims: int,
    strategy_map: Mapping[str, ClaimsExtractorCallable],
    fallback_mode: str = "heuristic",
    language: str | None = None,
    provider_modes: set[str] | None = None,
    catch_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> ClaimsExtractionDispatch:
    mode, lang = resolve_claims_strategy_mode(
        requested_mode,
        text=text,
        strategy_map=strategy_map,
        language=language,
        provider_modes=provider_modes,
    )

    strategy = strategy_map.get(mode)
    if strategy is None:
        return ClaimsExtractionDispatch(mode=mode, language=lang, claim_texts=[])

    try:
        claim_texts = await _execute_async_strategy(strategy, text=text, max_claims=max_claims, language=lang)
        if claim_texts:
            return ClaimsExtractionDispatch(mode=mode, language=lang, claim_texts=claim_texts)
    except catch_exceptions as exc:
        logger.debug(f"Claims extractor strategy '{mode}' failed: {exc}")

    fallback = strategy_map.get(fallback_mode)
    if fallback is None or fallback_mode == mode:
        return ClaimsExtractionDispatch(mode=mode, language=lang, claim_texts=[])

    try:
        claim_texts = await _execute_async_strategy(fallback, text=text, max_claims=max_claims, language=lang)
    except catch_exceptions as exc:
        logger.debug(f"Claims fallback strategy '{fallback_mode}' failed: {exc}")
        claim_texts = []
    return ClaimsExtractionDispatch(mode=fallback_mode, language=lang, claim_texts=claim_texts)


__all__ = [
    "ClaimsExtractionDispatch",
    "ClaimsExtractorCallable",
    "extract_heuristic_claims_texts",
    "extract_ner_claims_texts",
    "resolve_claims_strategy_mode",
    "run_async_claims_strategy",
    "run_sync_claims_strategy",
]
