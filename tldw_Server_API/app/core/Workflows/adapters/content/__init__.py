"""Content generation adapters.

This module includes adapters for content operations:
- summarize: Summarize text content
- citations: Generate citations
- bibliography_generate: Generate bibliography
- image_gen: Generate images
- image_describe: Describe images
- rerank: Rerank search results
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

from tldw_Server_API.app.core.Workflows.adapters.content.citations import (
    run_bibliography_generate_adapter,
    run_citations_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.content.generation import (
    run_diagram_generate_adapter,
    run_flashcard_generate_adapter,
    run_glossary_extract_adapter,
    run_mindmap_generate_adapter,
    run_newsletter_generate_adapter,
    run_outline_generate_adapter,
    run_quiz_generate_adapter,
    run_report_generate_adapter,
    run_slides_generate_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.content.image import (
    run_image_describe_adapter,
    run_image_gen_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.content.rerank import (
    run_rerank_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.content.summarize import (
    run_summarize_adapter,
)

__all__ = [
    "run_summarize_adapter",
    "run_citations_adapter",
    "run_bibliography_generate_adapter",
    "run_image_gen_adapter",
    "run_image_describe_adapter",
    "run_rerank_adapter",
    "run_flashcard_generate_adapter",
    "run_quiz_generate_adapter",
    "run_outline_generate_adapter",
    "run_mindmap_generate_adapter",
    "run_glossary_extract_adapter",
    "run_slides_generate_adapter",
    "run_report_generate_adapter",
    "run_newsletter_generate_adapter",
    "run_diagram_generate_adapter",
]
