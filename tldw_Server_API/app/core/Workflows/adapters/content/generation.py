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

import json
import re
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string
from tldw_Server_API.app.core.Workflows.adapters._common import extract_openai_content
from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.content._config import (
    DiagramGenerateConfig,
    FlashcardGenerateConfig,
    GlossaryExtractConfig,
    MindmapGenerateConfig,
    NewsletterGenerateConfig,
    OutlineGenerateConfig,
    QuizGenerateConfig,
    ReportGenerateConfig,
    SlidesGenerateConfig,
)


@registry.register(
    "flashcard_generate",
    category="content",
    description="Generate flashcards",
    parallelizable=True,
    tags=["content", "education"],
    config_model=FlashcardGenerateConfig,
)
async def run_flashcard_generate_adapter(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Generate flashcards from content using LLM."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = apply_template_to_string(text, context) or text
    text = str(text).strip()

    if not text:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            text = prev.get("text") or prev.get("content") or prev.get("transcript") or ""
        text = str(text).strip()

    if not text:
        return {"error": "missing_text", "flashcards": [], "count": 0}

    num_cards = int(config.get("num_cards", 10))
    card_type = str(config.get("card_type", "basic")).lower()
    difficulty = str(config.get("difficulty", "medium")).lower()
    focus_topics = config.get("focus_topics")
    provider = config.get("provider")
    model = config.get("model")

    type_instructions = {
        "basic": "Create standard question/answer flashcards.",
        "cloze": "Create cloze deletion cards.",
        "basic_reverse": "Create bidirectional cards."
    }
    difficulty_hints = {
        "easy": "Focus on basic concepts.",
        "medium": "Include intermediate concepts.",
        "hard": "Focus on complex details."
    }
    topics_hint = f"\nFocus on: {', '.join(focus_topics)}" if focus_topics else ""

    system_prompt = (
        f"Generate {num_cards} flashcards.\n"
        f"{type_instructions.get(card_type, type_instructions['basic'])}\n"
        f"{difficulty_hints.get(difficulty, difficulty_hints['medium'])}{topics_hint}\n"
        'Return JSON array: [{"front": "Q", "back": "A", "tags": []}]'
    )

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async
        messages = [{"role": "user", "content": f"Generate flashcards from:\n\n{text[:8000]}"}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=provider,
            model=model,
            system_message=system_prompt,
            max_tokens=4000,
            temperature=0.7
        )
        response_text = extract_openai_content(response) or "[]"
        try:
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            flashcards = json.loads(json_match.group()) if json_match else []
        except json.JSONDecodeError:
            flashcards = []
        for card in flashcards:
            card["model_type"] = card_type
        return {"flashcards": flashcards, "count": len(flashcards)}
    except Exception as e:
        logger.exception(f"Flashcard generate adapter error: {e}")
        return {"error": f"flashcard_generate_error:{e}", "flashcards": [], "count": 0}


@registry.register(
    "quiz_generate",
    category="content",
    description="Generate quizzes",
    parallelizable=True,
    tags=["content", "education"],
    config_model=QuizGenerateConfig,
)
async def run_quiz_generate_adapter(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Generate quiz questions from content using LLM."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = apply_template_to_string(text, context) or text
    text = str(text).strip()

    if not text:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            text = prev.get("text") or prev.get("content") or prev.get("transcript") or ""
        text = str(text).strip()

    if not text:
        return {"error": "missing_text", "questions": [], "count": 0}

    num_questions = int(config.get("num_questions", 10))
    question_types = config.get("question_types", ["multiple_choice"])
    if isinstance(question_types, str):
        question_types = [question_types]
    difficulty = str(config.get("difficulty", "medium")).lower()
    provider = config.get("provider")
    model = config.get("model")

    system_prompt = (
        f"Generate {num_questions} quiz questions. Types: {', '.join(question_types)}. "
        f"Difficulty: {difficulty}.\n"
        'Return JSON: [{"question_type": "multiple_choice", "question_text": "Q", '
        '"options": ["A","B","C","D"], "correct_answer": 0, "explanation": "Why", "points": 1}]'
    )

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async
        messages = [{"role": "user", "content": f"Generate quiz from:\n\n{text[:8000]}"}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=provider,
            model=model,
            system_message=system_prompt,
            max_tokens=4000,
            temperature=0.7
        )
        response_text = extract_openai_content(response) or "[]"
        try:
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            questions = json.loads(json_match.group()) if json_match else []
        except json.JSONDecodeError:
            questions = []
        return {"questions": questions, "count": len(questions)}
    except Exception as e:
        logger.exception(f"Quiz generate adapter error: {e}")
        return {"error": f"quiz_generate_error:{e}", "questions": [], "count": 0}


@registry.register(
    "outline_generate",
    category="content",
    description="Generate content outlines",
    parallelizable=True,
    tags=["content", "generation"],
    config_model=OutlineGenerateConfig,
)
async def run_outline_generate_adapter(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Generate a hierarchical outline from content."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = apply_template_to_string(text, context) or text
    text = str(text).strip()
    if not text:
        prev = context.get("prev") or context.get("last") or {}
        text = str(prev.get("text") or prev.get("content") or "") if isinstance(prev, dict) else ""

    if not text:
        return {"error": "missing_text", "outline": {}, "outline_text": ""}

    max_depth = int(config.get("max_depth", 3))
    provider, model = config.get("provider"), config.get("model")
    system_prompt = (
        f"Create outline. Max depth: {max_depth}. "
        'Return JSON: {"sections": [{"title": "Section", "level": 1, "subsections": []}]}'
    )

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async
        response = await perform_chat_api_call_async(
            messages=[{"role": "user", "content": f"Outline:\n\n{text[:8000]}"}],
            api_provider=provider,
            model=model,
            system_message=system_prompt,
            max_tokens=2000,
            temperature=0.5
        )
        response_text = extract_openai_content(response) or ""
        outline = {}
        try:
            json_match = re.search(r'\{[\s\S]*"sections"[\s\S]*\}', response_text)
            outline = json.loads(json_match.group()) if json_match else {}
        except json.JSONDecodeError:
            pass
        return {"outline": outline, "outline_text": response_text, "sections": len(outline.get("sections", []))}
    except Exception as e:
        logger.exception(f"Outline generate error: {e}")
        return {"error": str(e), "outline": {}, "outline_text": ""}


@registry.register(
    "glossary_extract",
    category="content",
    description="Extract glossary terms",
    parallelizable=True,
    tags=["content", "extraction"],
    config_model=GlossaryExtractConfig,
)
async def run_glossary_extract_adapter(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Extract key terms and definitions from content."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = apply_template_to_string(text, context) or text
    text = str(text).strip()
    if not text:
        prev = context.get("prev") or context.get("last") or {}
        text = str(prev.get("text") or prev.get("content") or "") if isinstance(prev, dict) else ""

    if not text:
        return {"error": "missing_text", "glossary": [], "count": 0}

    max_terms = int(config.get("max_terms", 20))
    provider, model = config.get("provider"), config.get("model")
    system_prompt = f'Extract up to {max_terms} key terms. Return JSON: [{{"term": "Name", "definition": "Def"}}]'

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async
        response = await perform_chat_api_call_async(
            messages=[{"role": "user", "content": f"Extract glossary:\n\n{text[:8000]}"}],
            api_provider=provider,
            model=model,
            system_message=system_prompt,
            max_tokens=3000,
            temperature=0.5
        )
        response_text = extract_openai_content(response) or "[]"
        try:
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            glossary = json.loads(json_match.group()) if json_match else []
        except json.JSONDecodeError:
            glossary = []
        return {"glossary": glossary, "count": len(glossary)}
    except Exception as e:
        logger.exception(f"Glossary extract error: {e}")
        return {"error": str(e), "glossary": [], "count": 0}


@registry.register(
    "mindmap_generate",
    category="content",
    description="Generate mind maps",
    parallelizable=True,
    tags=["content", "visualization"],
    config_model=MindmapGenerateConfig,
)
async def run_mindmap_generate_adapter(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Generate a mindmap structure from content."""
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    text = config.get("text") or ""
    if isinstance(text, str):
        text = apply_template_to_string(text, context) or text
    text = str(text).strip()
    if not text:
        prev = context.get("prev") or context.get("last") or {}
        text = str(prev.get("text") or prev.get("content") or "") if isinstance(prev, dict) else ""

    if not text:
        return {"error": "missing_text", "mindmap": {}, "mermaid": ""}

    max_branches = int(config.get("max_branches", 6))
    provider, model = config.get("provider"), config.get("model")
    system_prompt = (
        f"Create mindmap. Max {max_branches} branches. "
        'Return JSON: {"central": "Topic", "branches": [{"topic": "Branch", "children": []}]}'
    )

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async
        response = await perform_chat_api_call_async(
            messages=[{"role": "user", "content": f"Mindmap:\n\n{text[:8000]}"}],
            api_provider=provider,
            model=model,
            system_message=system_prompt,
            max_tokens=2000,
            temperature=0.6
        )
        response_text = extract_openai_content(response) or ""
        mindmap = {}
        try:
            json_match = re.search(r'\{[\s\S]*"central"[\s\S]*\}', response_text)
            mindmap = json.loads(json_match.group()) if json_match else {}
        except json.JSONDecodeError:
            pass
        return {"mindmap": mindmap, "mermaid": "", "node_count": 0}
    except Exception as e:
        logger.exception(f"Mindmap generate error: {e}")
        return {"error": str(e), "mindmap": {}, "mermaid": ""}


@registry.register(
    "slides_generate",
    category="content",
    description="Generate presentation slides",
    parallelizable=True,
    tags=["content", "generation"],
    config_model=SlidesGenerateConfig,
)
async def run_slides_generate_adapter(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Generate slide deck structure.

    Config:
      - content: str - Content to create slides from
      - title: str - Presentation title
      - num_slides: int - Target number of slides (default: 10)
      - style: str - "professional", "educational", "casual" (default: "professional")
      - provider: str - LLM provider
      - model: str - Model to use
    Output:
      - slides: list[dict] - Slide content with title, bullets, notes
    """
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    content = config.get("content") or ""
    if isinstance(content, str):
        content = apply_template_to_string(content, context) or content

    if not content:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            content = prev.get("text") or prev.get("content") or ""

    if not content:
        return {"slides": [], "error": "missing_content"}

    title = config.get("title", "Presentation")
    num_slides = int(config.get("num_slides", 10))
    style = config.get("style", "professional")

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        prompt = f"""Create a {num_slides}-slide presentation outline titled "{title}".
Style: {style}

Return as JSON array with this format:
[{{"slide_number": 1, "title": "Slide Title", "bullets": ["Point 1", "Point 2"], "speaker_notes": "Notes for presenter"}}]

Content:
{content[:5000]}"""

        messages = [{"role": "user", "content": prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            system_message="Generate presentation slides as JSON.",
            max_tokens=3000,
            temperature=0.5,
        )

        result_text = extract_openai_content(response) or ""
        try:
            start = result_text.find("[")
            end = result_text.rfind("]") + 1
            if start >= 0 and end > start:
                slides = json.loads(result_text[start:end])
                return {"slides": slides, "title": title, "slide_count": len(slides)}
        except json.JSONDecodeError:
            pass

        return {"slides": [], "raw_text": result_text, "error": "json_parse_failed"}

    except Exception as e:
        logger.exception(f"Slides generate error: {e}")
        return {"slides": [], "error": str(e)}


@registry.register(
    "report_generate",
    category="content",
    description="Generate reports",
    parallelizable=True,
    tags=["content", "generation"],
    config_model=ReportGenerateConfig,
)
async def run_report_generate_adapter(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Generate a structured report from content.

    Config:
      - content: str - Content to generate report from
      - title: str - Report title
      - sections: list[str] - Section headings (default: auto-generated)
      - format: str - "markdown", "html", or "plain" (default: "markdown")
      - provider: str - LLM provider
      - model: str - Model to use
    Output:
      - report: str
      - title: str
      - sections: list[str]
    """
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    content = config.get("content") or ""
    if isinstance(content, str):
        content = apply_template_to_string(content, context) or content

    if not content:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            content = prev.get("text") or prev.get("content") or ""

    if not content:
        return {"report": "", "error": "missing_content"}

    title = config.get("title", "Report")
    if isinstance(title, str):
        title = apply_template_to_string(title, context) or title

    sections = config.get("sections")
    output_format = config.get("format", "markdown")

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        sections_str = ""
        if sections:
            sections_str = f"\n\nInclude these sections: {', '.join(sections)}"

        prompt = f"""Generate a structured report titled "{title}" from this content.
Format: {output_format}{sections_str}

Content:
{content[:6000]}"""

        messages = [{"role": "user", "content": prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            system_message="Generate well-structured reports with clear sections.",
            max_tokens=3000,
            temperature=0.5,
        )

        report = extract_openai_content(response) or ""
        return {"report": report, "text": report, "title": title, "format": output_format}

    except Exception as e:
        logger.exception(f"Report generate error: {e}")
        return {"report": "", "error": str(e)}


@registry.register(
    "newsletter_generate",
    category="content",
    description="Generate newsletters",
    parallelizable=True,
    tags=["content", "generation"],
    config_model=NewsletterGenerateConfig,
)
async def run_newsletter_generate_adapter(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Generate newsletter from content/items.

    Config:
      - items: list[dict] - Items to include (title, summary, url)
      - content: str - Alternative: raw content to summarize
      - title: str - Newsletter title
      - intro: str - Introduction text
      - format: str - "markdown" or "html" (default: "markdown")
      - provider: str - LLM provider
      - model: str - Model to use
    Output:
      - newsletter: str
    """
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    items = config.get("items") or []
    content = config.get("content") or ""

    if not items and not content:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            items = prev.get("items") or []
            content = prev.get("text") or prev.get("content") or ""

    if not items and not content:
        return {"newsletter": "", "error": "missing_items_or_content"}

    title = config.get("title", "Newsletter")
    if isinstance(title, str):
        title = apply_template_to_string(title, context) or title

    intro = config.get("intro", "")
    if isinstance(intro, str):
        intro = apply_template_to_string(intro, context) or intro

    output_format = config.get("format", "markdown")

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        items_text = ""
        if items:
            for i, item in enumerate(items[:20]):
                item_title = item.get("title", f"Item {i + 1}")
                item_summary = item.get("summary", "")
                item_url = item.get("url", "")
                items_text += f"\n- {item_title}: {item_summary}"
                if item_url:
                    items_text += f" ({item_url})"

        content_block = f"Content:\n{content[:5000]}"
        prompt = f"""Generate a newsletter titled "{title}".
Format: {output_format}

{f'Introduction: {intro}' if intro else ''}
{f'Items:{items_text}' if items_text else content_block}

Include a header, brief intro, main content sections, and a closing."""

        messages = [{"role": "user", "content": prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            system_message="Generate engaging newsletters with clear sections.",
            max_tokens=2500,
            temperature=0.6,
        )

        newsletter = extract_openai_content(response) or ""
        return {"newsletter": newsletter, "text": newsletter, "title": title}

    except Exception as e:
        logger.exception(f"Newsletter generate error: {e}")
        return {"newsletter": "", "error": str(e)}


@registry.register(
    "diagram_generate",
    category="content",
    description="Generate diagrams",
    parallelizable=True,
    tags=["content", "visualization"],
    config_model=DiagramGenerateConfig,
)
async def run_diagram_generate_adapter(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Generate diagram code (mermaid/graphviz).

    Config:
      - content: str - Content to visualize
      - diagram_type: str - "flowchart", "sequence", "class", "er", "mindmap" (default: "flowchart")
      - format: str - "mermaid" or "graphviz" (default: "mermaid")
      - provider: str - LLM provider
      - model: str - Model to use
    Output:
      - diagram: str - Diagram code
      - format: str
    """
    if callable(context.get("is_cancelled")) and context["is_cancelled"]():
        return {"__status__": "cancelled"}

    content = config.get("content") or ""
    if isinstance(content, str):
        content = apply_template_to_string(content, context) or content

    if not content:
        prev = context.get("prev") or context.get("last") or {}
        if isinstance(prev, dict):
            content = prev.get("text") or prev.get("content") or ""

    if not content:
        return {"diagram": "", "error": "missing_content"}

    diagram_type = config.get("diagram_type", "flowchart")
    output_format = config.get("format", "mermaid")

    try:
        from tldw_Server_API.app.core.Chat.chat_service import perform_chat_api_call_async

        format_examples = {
            "mermaid": "```mermaid\nflowchart TD\n    A --> B\n```",
            "graphviz": "digraph G {\n    A -> B;\n}",
        }

        prompt = f"""Create a {diagram_type} diagram from this content using {output_format} syntax.

Example format:
{format_examples.get(output_format, format_examples['mermaid'])}

Return ONLY the diagram code, no explanations.

Content:
{content[:4000]}"""

        messages = [{"role": "user", "content": prompt}]
        response = await perform_chat_api_call_async(
            messages=messages,
            api_provider=config.get("provider"),
            model=config.get("model"),
            system_message=f"Generate {output_format} diagrams. Return only diagram code.",
            max_tokens=1500,
            temperature=0.3,
        )

        diagram = extract_openai_content(response) or ""
        # Clean up code blocks
        if "```" in diagram:
            lines = diagram.split("\n")
            cleaned = []
            in_code = False
            for line in lines:
                if line.startswith("```"):
                    in_code = not in_code
                    continue
                if in_code or not line.startswith("```"):
                    cleaned.append(line)
            diagram = "\n".join(cleaned)

        return {"diagram": diagram.strip(), "format": output_format, "diagram_type": diagram_type}

    except Exception as e:
        logger.exception(f"Diagram generate error: {e}")
        return {"diagram": "", "error": str(e)}
