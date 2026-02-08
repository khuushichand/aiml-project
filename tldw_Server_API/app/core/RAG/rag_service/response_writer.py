"""
Structured Response Writer.

Formats retrieved context as XML-tagged blocks and builds mode-specific
writer prompts that enforce inline citations, structured formatting,
and appropriate depth. Inspired by Perplexica's writer prompt pattern.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Context formatting
# ---------------------------------------------------------------------------

def format_context_xml(chunks: list[dict[str, Any]]) -> str:
    """Format retrieval results as XML-tagged context blocks.

    Each chunk dict should have: content, title (optional), url/source (optional).
    Results are auto-indexed starting from 1.

    Returns:
        XML string with <result> elements wrapped in a <context> root.
    """
    if not chunks:
        return "<context>\n  (no results)\n</context>"

    parts = ["<context>"]
    for i, chunk in enumerate(chunks, 1):
        content = str(chunk.get("content", "")).strip()
        if not content:
            continue

        title = chunk.get("title", "") or ""
        source = chunk.get("url", "") or chunk.get("source", "") or ""
        metadata = chunk.get("metadata", {}) or {}
        if not title and isinstance(metadata, dict):
            title = metadata.get("title", "")
        if not source and isinstance(metadata, dict):
            source = metadata.get("source", "") or metadata.get("url", "")

        attrs = f'index="{i}"'
        if title:
            # Escape XML special chars in attributes
            safe_title = str(title).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
            attrs += f' title="{safe_title}"'
        if source:
            safe_source = str(source).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
            attrs += f' source="{safe_source}"'

        parts.append(f"  <result {attrs}>{content}</result>")

    parts.append("</context>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Writer system prompts per mode
# ---------------------------------------------------------------------------

_WRITER_BASE_RULES = """\
You are a knowledgeable assistant generating a response based on the provided context.

## Citation Rules
- EVERY factual claim must include at least one citation using [number] notation
- Citations reference the <result index="N"> elements in the context
- Place citations at the end of the relevant sentence, before the period: "fact [1]."
- Multiple citations can be grouped: "supported by multiple studies [1][3]."
- Do NOT fabricate information not present in the context
- If the context doesn't contain sufficient information, say so explicitly

## Formatting Rules
- Use clear markdown formatting: headings, subheadings, bullet points
- Start with a direct answer to the query
- Organize information logically with appropriate section headers
- Use paragraphs for detailed explanations, bullets for lists/comparisons"""

_SPEED_WRITER_PROMPT = _WRITER_BASE_RULES + """

## Mode: Speed (Concise)
- Keep the response concise and direct (150-400 words)
- Focus on answering the core question
- Use 1-2 short paragraphs, optionally with a brief bullet list
- Skip deep analysis — prioritize clarity and speed
- Include a brief 1-sentence conclusion if appropriate"""

_BALANCED_WRITER_PROMPT = _WRITER_BASE_RULES + """

## Mode: Balanced (Comprehensive)
- Provide a well-structured, moderately detailed response (400-1200 words)
- Use 2-4 sections with descriptive headings
- Include context, explanation, and practical implications
- Synthesize information from multiple sources when possible
- End with a concise conclusion or summary paragraph
- Balance depth with readability"""

_QUALITY_WRITER_PROMPT = _WRITER_BASE_RULES + """

## Mode: Quality (Research Report)
- Generate a DEEP, DETAILED, and COMPREHENSIVE response
- Target at minimum 2000 words for complex topics
- Structure as a professional research report:
  1. **Introduction**: Brief overview and scope
  2. **Background/Context**: Relevant history and definitions
  3. **Detailed Analysis**: Multiple sections covering different aspects
  4. **Comparisons**: Compare approaches, viewpoints, or alternatives where relevant
  5. **Practical Implications**: Real-world applications, use cases, or recommendations
  6. **Limitations & Considerations**: Caveats, edge cases, or areas of debate
  7. **Conclusion**: Synthesize key findings and provide a balanced summary
- Every section should cite sources extensively
- Use tables or structured comparisons where they add clarity
- Include nuanced analysis, not just surface-level summaries
- Address potential counterarguments or alternative perspectives"""


def build_writer_system_prompt(
    mode: str = "balanced",
    system_instructions: str = "",
) -> str:
    """Build structured response generation system prompt.

    Args:
        mode: Search depth mode (speed/balanced/quality).
        system_instructions: Optional additional instructions to prepend.

    Returns:
        Complete system prompt string for the response writer.
    """
    prompt_map = {
        "speed": _SPEED_WRITER_PROMPT,
        "balanced": _BALANCED_WRITER_PROMPT,
        "quality": _QUALITY_WRITER_PROMPT,
    }
    base = prompt_map.get(mode, _BALANCED_WRITER_PROMPT)

    if system_instructions:
        return f"{system_instructions}\n\n{base}"
    return base


# ---------------------------------------------------------------------------
# Writer user prompt
# ---------------------------------------------------------------------------

def build_writer_user_prompt(
    query: str,
    context_xml: str,
) -> str:
    """Build the user prompt with XML-tagged context.

    Args:
        query: The user's query.
        context_xml: Pre-formatted XML context from format_context_xml().

    Returns:
        Complete user prompt string for the response writer.
    """
    return (
        f"Using the context below, answer the following query.\n\n"
        f"Query: {query}\n\n"
        f"{context_xml}\n\n"
        f"Provide your response with proper citations [number] referencing the results above."
    )
