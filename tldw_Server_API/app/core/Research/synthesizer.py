"""Deterministic synthesis for deep research artifacts."""

from __future__ import annotations

import hashlib
from collections import defaultdict

from .models import (
    ResearchEvidenceNote,
    ResearchOutlineSection,
    ResearchPlan,
    ResearchSourceRecord,
    ResearchSynthesizedClaim,
    ResearchSynthesisResult,
)


def _stable_digest(*parts: str) -> str:
    joined = "::".join(part.strip().lower() for part in parts if part and part.strip())
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _title_for_focus_area(focus_area: str) -> str:
    return focus_area.replace("_", " ").strip().title()


class ResearchSynthesizer:
    """Build deterministic synthesis artifacts from normalized research evidence."""

    def synthesize(
        self,
        *,
        plan: ResearchPlan,
        source_registry: list[ResearchSourceRecord],
        evidence_notes: list[ResearchEvidenceNote],
        collection_summary: dict[str, object] | None = None,
    ) -> ResearchSynthesisResult:
        source_index = {source.source_id: source for source in source_registry}
        notes_by_focus_area: dict[str, list[ResearchEvidenceNote]] = defaultdict(list)
        for note in evidence_notes:
            if note.source_id in source_index:
                notes_by_focus_area[note.focus_area].append(note)

        outline_sections: list[ResearchOutlineSection] = []
        claims: list[ResearchSynthesizedClaim] = []
        report_sections: list[str] = []
        unresolved_questions: list[str] = []
        covered_focus_areas: list[str] = []
        missing_focus_areas: list[str] = []

        initial_gaps = collection_summary.get("remaining_gaps", []) if isinstance(collection_summary, dict) else []
        for gap in initial_gaps:
            gap_text = str(gap).strip()
            if gap_text and gap_text not in unresolved_questions:
                unresolved_questions.append(gap_text)

        for focus_area in plan.focus_areas:
            notes = notes_by_focus_area.get(focus_area, [])
            if not notes:
                missing_focus_areas.append(focus_area)
                unresolved = f"missing evidence for focus area: {focus_area}"
                if unresolved not in unresolved_questions:
                    unresolved_questions.append(unresolved)
                continue

            covered_focus_areas.append(focus_area)
            source_ids = list(dict.fromkeys(note.source_id for note in notes))
            note_ids = [note.note_id for note in notes]
            section = ResearchOutlineSection(
                title=_title_for_focus_area(focus_area),
                focus_area=focus_area,
                source_ids=source_ids,
                note_ids=note_ids,
            )
            outline_sections.append(section)

            report_lines = [f"## {section.title}", ""]
            for note in notes:
                claim_id = f"clm_{_stable_digest(note.note_id, note.source_id)[:12]}"
                claims.append(
                    ResearchSynthesizedClaim(
                        claim_id=claim_id,
                        text=note.text,
                        focus_area=focus_area,
                        source_ids=[note.source_id],
                        citations=[{"source_id": note.source_id}],
                        confidence=float(note.confidence),
                    )
                )
                report_lines.append(f"- {note.text} [Sources: {note.source_id}]")
            report_sections.append("\n".join(report_lines))

        report_markdown = "\n\n".join(
            ["# Research Report", f"Question: {plan.query}"] + report_sections
        ).strip()

        synthesis_summary = {
            "query": plan.query,
            "focus_areas": list(plan.focus_areas),
            "section_count": len(outline_sections),
            "claim_count": len(claims),
            "source_count": len(source_registry),
            "unresolved_questions": list(unresolved_questions),
            "coverage": {
                "covered_focus_areas": covered_focus_areas,
                "missing_focus_areas": missing_focus_areas,
            },
        }

        return ResearchSynthesisResult(
            outline_sections=outline_sections,
            claims=claims,
            report_markdown=report_markdown,
            unresolved_questions=unresolved_questions,
            synthesis_summary=synthesis_summary,
        )


__all__ = ["ResearchSynthesizer"]
