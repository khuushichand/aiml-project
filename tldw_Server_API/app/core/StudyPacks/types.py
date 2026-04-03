from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_locator(locator: Mapping[str, Any] | None) -> dict[str, Any]:
    if locator is None:
        return {}
    return dict(locator)


@dataclass(slots=True, frozen=True)
class StudySourceSelection:
    source_type: str
    source_id: str
    locator: dict[str, Any] = field(default_factory=dict)
    excerpt_text: str | None = None
    label: str | None = None

    def __post_init__(self) -> None:
        source_type = _clean_text(self.source_type)
        source_id = _clean_text(self.source_id)
        excerpt_text = _clean_text(self.excerpt_text) or None
        label = _clean_text(self.label) or None
        if not source_type:
            raise ValueError("source_type must not be blank")
        if not source_id:
            raise ValueError("source_id must not be blank")
        if not isinstance(self.locator, Mapping):
            raise ValueError("locator must be a mapping")
        object.__setattr__(self, "source_type", source_type)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "locator", _normalize_locator(self.locator))
        object.__setattr__(self, "excerpt_text", excerpt_text)
        object.__setattr__(self, "label", label)


@dataclass(slots=True, frozen=True)
class StudySourceBundleItem:
    source_type: str
    source_id: str
    label: str
    evidence_text: str
    locator: dict[str, Any]

    def __post_init__(self) -> None:
        source_type = _clean_text(self.source_type)
        source_id = _clean_text(self.source_id)
        label = _clean_text(self.label)
        evidence_text = _clean_text(self.evidence_text)
        if not source_type:
            raise ValueError("source_type must not be blank")
        if not source_id:
            raise ValueError("source_id must not be blank")
        if not label:
            raise ValueError("label must not be blank")
        if not evidence_text:
            raise ValueError("evidence_text must not be blank")
        if not isinstance(self.locator, Mapping) or not self.locator:
            raise ValueError("locator must not be empty")
        object.__setattr__(self, "source_type", source_type)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "evidence_text", evidence_text)
        object.__setattr__(self, "locator", _normalize_locator(self.locator))


@dataclass(slots=True, frozen=True)
class StudySourceBundle:
    items: list[StudySourceBundleItem]

    def __post_init__(self) -> None:
        normalized_items = list(self.items)
        for item in normalized_items:
            if not isinstance(item, StudySourceBundleItem):
                raise ValueError("StudySourceBundle items must be StudySourceBundleItem instances")
        object.__setattr__(self, "items", normalized_items)


@dataclass(slots=True, frozen=True)
class StudyCitationDraft:
    source_type: str
    source_id: str
    citation_text: str
    locator: dict[str, Any]

    def __post_init__(self) -> None:
        source_type = _clean_text(self.source_type)
        source_id = _clean_text(self.source_id)
        citation_text = _clean_text(self.citation_text)
        if not source_type:
            raise ValueError("source_type must not be blank")
        if not source_id:
            raise ValueError("source_id must not be blank")
        if not citation_text:
            raise ValueError("citation_text must not be blank")
        if not isinstance(self.locator, Mapping) or not self.locator:
            raise ValueError("locator must not be empty")
        object.__setattr__(self, "source_type", source_type)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "citation_text", citation_text)
        object.__setattr__(self, "locator", _normalize_locator(self.locator))
