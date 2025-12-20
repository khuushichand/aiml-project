from __future__ import annotations

from typing import Type

from tldw_Server_API.app.core.Chat.document_generator import DocumentGeneratorService


def get_document_generator_service() -> Type[DocumentGeneratorService]:
    """Return the document generator service class for DI overrides."""
    return DocumentGeneratorService
