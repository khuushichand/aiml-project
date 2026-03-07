"""Provider adapters for deep research collection and synthesis."""

from .academic import AcademicResearchProvider
from .config import resolve_provider_config
from .local import LocalResearchProvider
from .web import WebResearchProvider

__all__ = [
    "AcademicResearchProvider",
    "LocalResearchProvider",
    "WebResearchProvider",
    "resolve_provider_config",
]
