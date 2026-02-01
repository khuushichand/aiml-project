"""Pydantic config models for content adapters."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class SummarizeConfig(BaseAdapterConfig):
    """Config for summarization adapter."""

    text: Optional[str] = Field(None, description="Text to summarize (templated)")
    input_key: Optional[str] = Field(None, description="Context key containing text")
    style: Literal["brief", "detailed", "bullet", "academic", "executive"] = Field(
        "brief", description="Summary style"
    )
    max_length: Optional[int] = Field(None, ge=50, description="Maximum summary length in words")
    provider: Optional[str] = Field(None, description="LLM provider for summarization")
    model: Optional[str] = Field(None, description="Model for summarization")
    language: Optional[str] = Field(None, description="Output language")


class CitationsConfig(BaseAdapterConfig):
    """Config for citations generation adapter."""

    text: str = Field(..., description="Text to generate citations for (templated)")
    style: Literal["apa", "mla", "chicago", "harvard", "ieee", "bibtex"] = Field(
        "apa", description="Citation style"
    )
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="Source documents/metadata")
    inline: bool = Field(True, description="Generate inline citations")
    bibliography: bool = Field(True, description="Generate bibliography")


class BibliographyGenerateConfig(BaseAdapterConfig):
    """Config for bibliography generation adapter."""

    sources: List[Dict[str, Any]] = Field(..., description="Source documents/metadata")
    style: Literal["apa", "mla", "chicago", "harvard", "ieee", "bibtex"] = Field(
        "apa", description="Citation style"
    )
    sort_by: Literal["author", "date", "title"] = Field("author", description="Sort order")
    include_urls: bool = Field(True, description="Include URLs in bibliography")


class ImageGenConfig(BaseAdapterConfig):
    """Config for image generation adapter."""

    prompt: str = Field(..., description="Image generation prompt (templated)")
    provider: Literal["openai", "stability", "midjourney", "local"] = Field(
        "openai", description="Image generation provider"
    )
    model: Optional[str] = Field(None, description="Model to use (e.g., dall-e-3)")
    size: str = Field("1024x1024", description="Image size (e.g., '1024x1024')")
    quality: Literal["standard", "hd"] = Field("standard", description="Image quality")
    style: Optional[str] = Field(None, description="Style preset")
    negative_prompt: Optional[str] = Field(None, description="Negative prompt")
    num_images: int = Field(1, ge=1, le=4, description="Number of images to generate")


class ImageDescribeConfig(BaseAdapterConfig):
    """Config for image description adapter."""

    image_uri: str = Field(..., description="file:// or https:// path to image (required)")
    detail: Literal["brief", "detailed", "comprehensive"] = Field(
        "detailed", description="Description detail level"
    )
    include_ocr: bool = Field(False, description="Include OCR text extraction")
    provider: Optional[str] = Field(None, description="Vision model provider")
    model: Optional[str] = Field(None, description="Vision model to use")


class RerankConfig(BaseAdapterConfig):
    """Config for reranking adapter."""

    query: str = Field(..., description="Query for reranking (templated)")
    documents: List[str] = Field(..., description="Documents to rerank")
    model: Optional[str] = Field(None, description="Reranking model")
    top_k: int = Field(10, ge=1, le=100, description="Number of results to return")
    return_scores: bool = Field(True, description="Include relevance scores")


class FlashcardGenerateConfig(BaseAdapterConfig):
    """Config for flashcard generation adapter."""

    text: str = Field(..., description="Source text for flashcard generation (templated)")
    num_cards: int = Field(10, ge=1, le=50, description="Number of flashcards to generate")
    difficulty: Literal["easy", "medium", "hard", "mixed"] = Field(
        "mixed", description="Flashcard difficulty"
    )
    format: Literal["qa", "cloze", "definition"] = Field("qa", description="Flashcard format")
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="Model for generation")


class QuizGenerateConfig(BaseAdapterConfig):
    """Config for quiz generation adapter."""

    text: str = Field(..., description="Source text for quiz generation (templated)")
    num_questions: int = Field(10, ge=1, le=50, description="Number of questions")
    question_types: List[Literal["multiple_choice", "true_false", "short_answer", "fill_blank"]] = Field(
        ["multiple_choice"], description="Types of questions to generate"
    )
    difficulty: Literal["easy", "medium", "hard", "mixed"] = Field(
        "mixed", description="Quiz difficulty"
    )
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="Model for generation")


class OutlineGenerateConfig(BaseAdapterConfig):
    """Config for outline generation adapter."""

    topic: str = Field(..., description="Topic for outline (templated)")
    depth: int = Field(3, ge=1, le=5, description="Outline depth (levels)")
    style: Literal["academic", "business", "creative", "technical"] = Field(
        "academic", description="Outline style"
    )
    include_descriptions: bool = Field(False, description="Include section descriptions")
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="Model for generation")


class MindmapGenerateConfig(BaseAdapterConfig):
    """Config for mindmap generation adapter."""

    topic: str = Field(..., description="Central topic for mindmap (templated)")
    depth: int = Field(3, ge=1, le=5, description="Mindmap depth (levels)")
    format: Literal["markdown", "mermaid", "json"] = Field(
        "markdown", description="Output format"
    )
    max_branches: int = Field(5, ge=2, le=10, description="Max branches per node")
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="Model for generation")


class GlossaryExtractConfig(BaseAdapterConfig):
    """Config for glossary extraction adapter."""

    text: str = Field(..., description="Text to extract glossary from (templated)")
    domain: Optional[str] = Field(None, description="Domain hint (medical, legal, etc.)")
    include_definitions: bool = Field(True, description="Include term definitions")
    max_terms: int = Field(50, ge=1, le=200, description="Maximum terms to extract")
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="Model for extraction")


class SlidesGenerateConfig(BaseAdapterConfig):
    """Config for presentation slides generation adapter."""

    content: str = Field(..., description="Content for slides (templated)")
    num_slides: int = Field(10, ge=3, le=50, description="Number of slides")
    style: Literal["professional", "creative", "minimal", "academic"] = Field(
        "professional", description="Slide style"
    )
    format: Literal["markdown", "pptx", "html", "json"] = Field(
        "markdown", description="Output format"
    )
    include_speaker_notes: bool = Field(True, description="Include speaker notes")
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="Model for generation")


class ReportGenerateConfig(BaseAdapterConfig):
    """Config for report generation adapter."""

    topic: str = Field(..., description="Report topic (templated)")
    sections: Optional[List[str]] = Field(None, description="Report sections to include")
    style: Literal["executive", "technical", "research", "summary"] = Field(
        "executive", description="Report style"
    )
    max_length: Optional[int] = Field(None, ge=500, description="Maximum length in words")
    include_toc: bool = Field(True, description="Include table of contents")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="Source materials")
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="Model for generation")


class NewsletterGenerateConfig(BaseAdapterConfig):
    """Config for newsletter generation adapter."""

    content: str = Field(..., description="Content for newsletter (templated)")
    title: Optional[str] = Field(None, description="Newsletter title")
    style: Literal["professional", "casual", "formal", "creative"] = Field(
        "professional", description="Newsletter style"
    )
    sections: int = Field(3, ge=1, le=10, description="Number of sections")
    include_cta: bool = Field(True, description="Include call-to-action")
    format: Literal["markdown", "html", "text"] = Field("markdown", description="Output format")
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="Model for generation")


class DiagramGenerateConfig(BaseAdapterConfig):
    """Config for diagram generation adapter."""

    description: str = Field(..., description="Diagram description (templated)")
    diagram_type: Literal["flowchart", "sequence", "class", "state", "er", "gantt", "pie"] = Field(
        "flowchart", description="Type of diagram"
    )
    format: Literal["mermaid", "plantuml", "graphviz", "svg"] = Field(
        "mermaid", description="Output format"
    )
    style: Optional[str] = Field(None, description="Diagram style theme")
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="Model for generation")
