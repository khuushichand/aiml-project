"""Content generation adapters.

This module includes adapters for various content generation operations:
- flashcard_generate: Generate flashcards
- quiz_generate: Generate quizzes
- outline_generate: Generate content outlines
- mindmap_generate: Generate mind maps
- glossary_extract: Extract glossary terms
- slides_generate: Generate presentation slides
- report_generate: Generate reports
- newsletter_generate: Generate newsletters
- diagram_generate: Generate diagrams
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.content._config import (
    FlashcardGenerateConfig,
    QuizGenerateConfig,
    OutlineGenerateConfig,
    MindmapGenerateConfig,
    GlossaryExtractConfig,
    SlidesGenerateConfig,
    ReportGenerateConfig,
    NewsletterGenerateConfig,
    DiagramGenerateConfig,
)


@registry.register(
    "flashcard_generate",
    category="content",
    description="Generate flashcards",
    parallelizable=True,
    tags=["content", "education"],
    config_model=FlashcardGenerateConfig,
)
async def run_flashcard_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate flashcards from text content.

    Config:
      - text: str (templated) - Source text for flashcard generation
      - provider: str - LLM provider
      - model: str - Model to use
      - count: int = 10 - Number of flashcards to generate
      - difficulty: Literal["easy", "medium", "hard"] = "medium"
    Output:
      - {"flashcards": [{"front": str, "back": str}], "count": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_flashcard_generate_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "quiz_generate",
    category="content",
    description="Generate quizzes",
    parallelizable=True,
    tags=["content", "education"],
    config_model=QuizGenerateConfig,
)
async def run_quiz_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate quiz questions from text content.

    Config:
      - text: str (templated) - Source text for quiz generation
      - provider: str - LLM provider
      - model: str - Model to use
      - count: int = 5 - Number of questions
      - question_types: list[str] = ["multiple_choice"] - Types of questions
      - difficulty: Literal["easy", "medium", "hard"] = "medium"
    Output:
      - {"questions": [dict], "count": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_quiz_generate_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "outline_generate",
    category="content",
    description="Generate content outlines",
    parallelizable=True,
    tags=["content", "generation"],
    config_model=OutlineGenerateConfig,
)
async def run_outline_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a structured outline from text or topic.

    Config:
      - text: str (templated) - Source text or topic
      - provider: str - LLM provider
      - model: str - Model to use
      - depth: int = 3 - Maximum outline depth
      - style: Literal["academic", "business", "creative"] = "academic"
    Output:
      - {"outline": dict, "sections": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_outline_generate_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "mindmap_generate",
    category="content",
    description="Generate mind maps",
    parallelizable=True,
    tags=["content", "visualization"],
    config_model=MindmapGenerateConfig,
)
async def run_mindmap_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a mind map from text content.

    Config:
      - text: str (templated) - Source text for mind map
      - provider: str - LLM provider
      - model: str - Model to use
      - format: Literal["json", "mermaid", "markdown"] = "json"
      - max_nodes: int = 20 - Maximum number of nodes
    Output:
      - {"mindmap": dict | str, "format": str, "nodes": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_mindmap_generate_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "glossary_extract",
    category="content",
    description="Extract glossary terms",
    parallelizable=True,
    tags=["content", "extraction"],
    config_model=GlossaryExtractConfig,
)
async def run_glossary_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract glossary terms and definitions from text.

    Config:
      - text: str (templated) - Source text
      - provider: str - LLM provider
      - model: str - Model to use
      - max_terms: int = 20 - Maximum number of terms
      - include_context: bool = True - Include usage context
    Output:
      - {"terms": [{"term": str, "definition": str}], "count": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_glossary_extract_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "slides_generate",
    category="content",
    description="Generate presentation slides",
    parallelizable=True,
    tags=["content", "generation"],
    config_model=SlidesGenerateConfig,
)
async def run_slides_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate presentation slides from text content.

    Config:
      - text: str (templated) - Source text for slides
      - provider: str - LLM provider
      - model: str - Model to use
      - num_slides: int = 10 - Target number of slides
      - format: Literal["json", "markdown", "marp"] = "json"
      - style: Literal["professional", "academic", "creative"] = "professional"
    Output:
      - {"slides": [dict], "count": int, "format": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_slides_generate_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "report_generate",
    category="content",
    description="Generate reports",
    parallelizable=True,
    tags=["content", "generation"],
    config_model=ReportGenerateConfig,
)
async def run_report_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a structured report from data or text.

    Config:
      - text: str (templated) - Source content
      - provider: str - LLM provider
      - model: str - Model to use
      - report_type: Literal["summary", "analysis", "research"] = "summary"
      - format: Literal["markdown", "html", "text"] = "markdown"
      - sections: list[str] (optional) - Custom section headers
    Output:
      - {"report": str, "format": str, "sections": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_report_generate_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "newsletter_generate",
    category="content",
    description="Generate newsletters",
    parallelizable=True,
    tags=["content", "generation"],
    config_model=NewsletterGenerateConfig,
)
async def run_newsletter_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate newsletter content from sources.

    Config:
      - text: str (templated) - Source content
      - provider: str - LLM provider
      - model: str - Model to use
      - format: Literal["markdown", "html", "text"] = "markdown"
      - tone: Literal["formal", "casual", "professional"] = "professional"
      - sections: list[str] (optional) - Custom sections
    Output:
      - {"newsletter": str, "format": str, "word_count": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_newsletter_generate_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "diagram_generate",
    category="content",
    description="Generate diagrams",
    parallelizable=True,
    tags=["content", "visualization"],
    config_model=DiagramGenerateConfig,
)
async def run_diagram_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate diagrams from text descriptions.

    Config:
      - text: str (templated) - Description or source text
      - provider: str - LLM provider
      - model: str - Model to use
      - diagram_type: Literal["flowchart", "sequence", "class", "er", "state"] = "flowchart"
      - format: Literal["mermaid", "plantuml", "graphviz"] = "mermaid"
    Output:
      - {"diagram": str, "format": str, "type": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_diagram_generate_adapter as _legacy
    return await _legacy(config, context)
