"""Text processing adapters.

This module includes adapters for text operations:
- html_to_markdown: Convert HTML to Markdown
- markdown_to_html: Convert Markdown to HTML
- csv_to_json: Convert CSV to JSON
- json_to_csv: Convert JSON to CSV
- json_transform: Transform JSON data
- json_validate: Validate JSON data
- xml_transform: Transform XML data
- template_render: Render Jinja templates
- regex_extract: Extract with regex patterns
- text_clean: Clean and normalize text
- keyword_extract: Extract keywords
- sentiment_analyze: Analyze sentiment
- language_detect: Detect language
- topic_model: Topic modeling
- entity_extract: Extract named entities
- token_count: Count tokens
"""

from tldw_Server_API.app.core.Workflows.adapters.text.conversion import (
    run_csv_to_json_adapter,
    run_html_to_markdown_adapter,
    run_json_to_csv_adapter,
    run_markdown_to_html_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.text.nlp import (
    run_entity_extract_adapter,
    run_keyword_extract_adapter,
    run_language_detect_adapter,
    run_sentiment_analyze_adapter,
    run_token_count_adapter,
    run_topic_model_adapter,
)
from tldw_Server_API.app.core.Workflows.adapters.text.transform import (
    run_json_transform_adapter,
    run_json_validate_adapter,
    run_regex_extract_adapter,
    run_template_render_adapter,
    run_text_clean_adapter,
    run_xml_transform_adapter,
)

__all__ = [
    "run_html_to_markdown_adapter",
    "run_markdown_to_html_adapter",
    "run_csv_to_json_adapter",
    "run_json_to_csv_adapter",
    "run_json_transform_adapter",
    "run_json_validate_adapter",
    "run_xml_transform_adapter",
    "run_template_render_adapter",
    "run_regex_extract_adapter",
    "run_text_clean_adapter",
    "run_keyword_extract_adapter",
    "run_sentiment_analyze_adapter",
    "run_language_detect_adapter",
    "run_topic_model_adapter",
    "run_entity_extract_adapter",
    "run_token_count_adapter",
]
