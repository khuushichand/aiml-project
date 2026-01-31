"""Natural language processing adapters.

This module includes adapters for NLP operations:
- keyword_extract: Extract keywords
- sentiment_analyze: Analyze sentiment
- language_detect: Detect language
- topic_model: Topic modeling
- entity_extract: Extract named entities
- token_count: Count tokens
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.text._config import (
    EntityExtractConfig,
    KeywordExtractConfig,
    LanguageDetectConfig,
    SentimentAnalyzeConfig,
    TokenCountConfig,
    TopicModelConfig,
)


@registry.register(
    "keyword_extract",
    category="text",
    description="Extract keywords",
    parallelizable=True,
    tags=["text", "nlp"],
    config_model=KeywordExtractConfig,
)
async def run_keyword_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract keywords from text content.

    Config:
      - text: str (templated) - Text to extract keywords from
      - method: Literal["tfidf", "rake", "yake", "llm"] = "rake"
      - max_keywords: int = 10 - Maximum keywords to return
      - provider: str (optional) - LLM provider for llm method
      - model: str (optional) - Model for llm method
    Output:
      - {"keywords": [str], "scores": [float], "count": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_keyword_extract_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "sentiment_analyze",
    category="text",
    description="Analyze sentiment",
    parallelizable=True,
    tags=["text", "nlp"],
    config_model=SentimentAnalyzeConfig,
)
async def run_sentiment_analyze_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze sentiment of text content.

    Config:
      - text: str (templated) - Text to analyze
      - method: Literal["vader", "textblob", "llm"] = "vader"
      - provider: str (optional) - LLM provider for llm method
      - model: str (optional) - Model for llm method
    Output:
      - {"sentiment": str, "score": float, "confidence": float}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_sentiment_analyze_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "language_detect",
    category="text",
    description="Detect language",
    parallelizable=True,
    tags=["text", "nlp"],
    config_model=LanguageDetectConfig,
)
async def run_language_detect_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Detect the language of text content.

    Config:
      - text: str (templated) - Text to analyze
      - method: Literal["langdetect", "fasttext", "llm"] = "langdetect"
      - return_all: bool = False - Return all detected languages
    Output:
      - {"language": str, "code": str, "confidence": float}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_language_detect_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "topic_model",
    category="text",
    description="Topic modeling",
    parallelizable=True,
    tags=["text", "nlp"],
    config_model=TopicModelConfig,
)
async def run_topic_model_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract topics from text content.

    Config:
      - text: str (templated) - Text to analyze
      - method: Literal["lda", "nmf", "llm"] = "llm"
      - num_topics: int = 5 - Number of topics to extract
      - provider: str (optional) - LLM provider for llm method
      - model: str (optional) - Model for llm method
    Output:
      - {"topics": [{"name": str, "keywords": [str]}], "count": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_topic_model_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "entity_extract",
    category="text",
    description="Extract named entities",
    parallelizable=True,
    tags=["text", "nlp"],
    config_model=EntityExtractConfig,
)
async def run_entity_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract named entities from text content.

    Config:
      - text: str (templated) - Text to analyze
      - method: Literal["spacy", "flair", "llm"] = "spacy"
      - entity_types: list[str] (optional) - Entity types to extract
      - provider: str (optional) - LLM provider for llm method
      - model: str (optional) - Model for llm method
    Output:
      - {"entities": [{"text": str, "type": str, "start": int, "end": int}], "count": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_entity_extract_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "token_count",
    category="text",
    description="Count tokens",
    parallelizable=True,
    tags=["text", "utility"],
    config_model=TokenCountConfig,
)
async def run_token_count_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Count tokens in text using various tokenizers.

    Config:
      - text: str (templated) - Text to count tokens in
      - tokenizer: str = "cl100k_base" - Tokenizer to use
      - model: str (optional) - Model to use for tokenization
    Output:
      - {"tokens": int, "characters": int, "words": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_token_count_adapter as _legacy
    return await _legacy(config, context)
