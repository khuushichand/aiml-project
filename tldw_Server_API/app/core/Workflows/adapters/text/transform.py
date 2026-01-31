"""Text transformation adapters.

This module includes adapters for text transformation operations:
- json_transform: Transform JSON data
- json_validate: Validate JSON data
- xml_transform: Transform XML data
- template_render: Render Jinja templates
- regex_extract: Extract with regex patterns
- text_clean: Clean and normalize text
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.text._config import (
    JSONTransformConfig,
    JSONValidateConfig,
    RegexExtractConfig,
    TemplateRenderConfig,
    TextCleanConfig,
    XMLTransformConfig,
)


@registry.register(
    "json_transform",
    category="text",
    description="Transform JSON data",
    parallelizable=True,
    tags=["text", "json"],
    config_model=JSONTransformConfig,
)
async def run_json_transform_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Transform JSON data using jq-like expressions or mappings.

    Config:
      - json: dict | list (templated) - JSON data to transform
      - expression: str (optional) - jq-like expression
      - mapping: dict (optional) - Field mapping rules
    Output:
      - {"result": Any, "text": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_json_transform_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "json_validate",
    category="text",
    description="Validate JSON data",
    parallelizable=True,
    tags=["text", "json"],
    config_model=JSONValidateConfig,
)
async def run_json_validate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Validate JSON data against a schema.

    Config:
      - json: Any (templated) - JSON data to validate
      - schema: dict (optional) - JSON Schema to validate against
      - strict: bool = False - Strict validation mode
    Output:
      - {"valid": bool, "errors": [str]}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_json_validate_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "xml_transform",
    category="text",
    description="Transform XML data",
    parallelizable=True,
    tags=["text", "xml"],
    config_model=XMLTransformConfig,
)
async def run_xml_transform_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Transform XML data using XPath or XSLT.

    Config:
      - xml: str (templated) - XML content to transform
      - xpath: str (optional) - XPath expression
      - xslt: str (optional) - XSLT stylesheet
      - output_format: Literal["xml", "json", "text"] = "xml"
    Output:
      - {"result": Any, "text": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_xml_transform_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "template_render",
    category="text",
    description="Render Jinja templates",
    parallelizable=True,
    tags=["text", "template"],
    config_model=TemplateRenderConfig,
)
async def run_template_render_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Render Jinja2 templates with context data.

    Config:
      - template: str (templated) - Jinja2 template string
      - variables: dict (optional) - Template variables
      - strict: bool = False - Fail on undefined variables
    Output:
      - {"rendered": str, "text": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_template_render_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "regex_extract",
    category="text",
    description="Extract with regex patterns",
    parallelizable=True,
    tags=["text", "extraction"],
    config_model=RegexExtractConfig,
)
async def run_regex_extract_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract data using regular expressions.

    Config:
      - text: str (templated) - Text to search
      - pattern: str - Regular expression pattern
      - group: int = 0 - Capture group to return
      - all_matches: bool = False - Return all matches
      - flags: str (optional) - Regex flags (i, m, s)
    Output:
      - {"matches": [str], "count": int, "text": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_regex_extract_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "text_clean",
    category="text",
    description="Clean and normalize text",
    parallelizable=True,
    tags=["text", "cleaning"],
    config_model=TextCleanConfig,
)
async def run_text_clean_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and normalize text content.

    Config:
      - text: str (templated) - Text to clean
      - lowercase: bool = False - Convert to lowercase
      - strip_html: bool = True - Remove HTML tags
      - normalize_whitespace: bool = True - Normalize whitespace
      - remove_punctuation: bool = False - Remove punctuation
      - remove_numbers: bool = False - Remove numbers
      - remove_urls: bool = False - Remove URLs
    Output:
      - {"text": str, "original_length": int, "cleaned_length": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_text_clean_adapter as _legacy
    return await _legacy(config, context)
