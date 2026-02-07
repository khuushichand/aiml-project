from __future__ import annotations

from tldw_Server_API.app.core.Chat.document_generator import DocumentGeneratorService


def get_document_generator_service() -> type[DocumentGeneratorService]:
    """Return the document generator service class for DI overrides."""
    return DocumentGeneratorService
