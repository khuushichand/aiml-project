import pytest


pytestmark = pytest.mark.unit


class _SynthesisProviderStub:
    def __init__(self, response=None, *, error: Exception | None = None):
        self._response = response
        self._error = error
        self.calls: list[dict[str, object]] = []

    async def summarize(
        self,
        *,
        plan,
        source_registry,
        evidence_notes,
        collection_summary,
        config,
    ):
        self.calls.append(
            {
                "plan": plan,
                "source_registry": list(source_registry),
                "evidence_notes": list(evidence_notes),
                "collection_summary": dict(collection_summary or {}),
                "config": dict(config),
            }
        )
        if self._error is not None:
            raise self._error
        return self._response


def _plan(focus_areas: list[str]):
    from tldw_Server_API.app.core.Research.models import ResearchPlan

    return ResearchPlan(
        query="Map evidence gaps",
        focus_areas=focus_areas,
        source_policy="balanced",
        autonomy_mode="checkpointed",
        stop_criteria={"min_cited_sections": 1},
    )


def _source(source_id: str, focus_area: str):
    from tldw_Server_API.app.core.Research.models import ResearchSourceRecord

    return ResearchSourceRecord(
        source_id=source_id,
        focus_area=focus_area,
        source_type="local_document",
        provider="local_corpus",
        title=f"Source for {focus_area}",
        url=None,
        snippet=f"Snippet for {focus_area}",
        published_at=None,
        retrieved_at="2026-03-07T00:00:00+00:00",
        fingerprint=f"fp_{source_id}",
        trust_tier="internal",
        metadata={},
    )


def _note(note_id: str, source_id: str, focus_area: str, text: str):
    from tldw_Server_API.app.core.Research.models import ResearchEvidenceNote

    return ResearchEvidenceNote(
        note_id=note_id,
        source_id=source_id,
        focus_area=focus_area,
        kind="summary",
        text=text,
        citation_locator=None,
        confidence=0.8,
        metadata={},
    )


@pytest.mark.asyncio
async def test_synthesizer_groups_notes_into_sections_and_claims():
    from tldw_Server_API.app.core.Research.synthesizer import ResearchSynthesizer

    synthesizer = ResearchSynthesizer()
    result = await synthesizer.synthesize(
        plan=_plan(["background", "counterevidence"]),
        source_registry=[
            _source("src_background", "background"),
            _source("src_counter", "counterevidence"),
        ],
        evidence_notes=[
            _note("note_background", "src_background", "background", "Internal notes confirm baseline context."),
            _note("note_counter", "src_counter", "counterevidence", "Counterevidence remains limited but present."),
        ],
        collection_summary={
            "remaining_gaps": [],
        },
        provider_config={"synthesis": {"provider": None, "model": None, "temperature": 0.2}},
    )

    assert [section.focus_area for section in result.outline_sections] == ["background", "counterevidence"]
    assert result.claims[0].citations == [{"source_id": "src_background"}]
    assert result.claims[1].citations == [{"source_id": "src_counter"}]
    assert "## Background" in result.report_markdown
    assert "[Sources: src_background]" in result.report_markdown
    assert result.synthesis_summary["section_count"] == 2
    assert result.synthesis_summary["claim_count"] == 2
    assert result.synthesis_summary["coverage"]["missing_focus_areas"] == []


@pytest.mark.asyncio
async def test_synthesizer_omits_unsupported_claims_and_carries_unresolved_questions():
    from tldw_Server_API.app.core.Research.synthesizer import ResearchSynthesizer

    synthesizer = ResearchSynthesizer()
    result = await synthesizer.synthesize(
        plan=_plan(["background", "missing evidence"]),
        source_registry=[
            _source("src_background", "background"),
        ],
        evidence_notes=[
            _note("note_background", "src_background", "background", "Background evidence is grounded."),
            _note("note_unsupported", "src_unknown", "background", "Unsupported evidence should not become a claim."),
        ],
        collection_summary={
            "remaining_gaps": ["weak_external_coverage"],
        },
        provider_config={"synthesis": {"provider": None, "model": None, "temperature": 0.2}},
    )

    assert len(result.claims) == 1
    assert result.claims[0].source_ids == ["src_background"]
    assert "weak_external_coverage" in result.unresolved_questions
    assert "missing evidence" in result.synthesis_summary["coverage"]["missing_focus_areas"]
    assert any("missing evidence" in item for item in result.unresolved_questions)


@pytest.mark.asyncio
async def test_synthesizer_uses_provider_payload_when_references_are_valid():
    from tldw_Server_API.app.core.Research.synthesizer import ResearchSynthesizer

    provider = _SynthesisProviderStub(
        {
            "outline_sections": [
                {
                    "title": "Background",
                    "focus_area": "background",
                    "source_ids": ["src_background"],
                    "note_ids": ["note_background"],
                }
            ],
            "claims": [
                {
                    "text": "Supported claim",
                    "focus_area": "background",
                    "source_ids": ["src_background"],
                    "citations": [{"source_id": "src_background"}],
                    "confidence": 0.81,
                }
            ],
            "report_sections": [
                {
                    "title": "Background",
                    "markdown": "Evidence-backed section text.",
                }
            ],
            "unresolved_questions": [],
            "summary": {"mode": "llm_backed"},
        }
    )

    synthesizer = ResearchSynthesizer(synthesis_provider=provider)
    result = await synthesizer.synthesize(
        plan=_plan(["background"]),
        source_registry=[_source("src_background", "background")],
        evidence_notes=[_note("note_background", "src_background", "background", "Grounded evidence.")],
        collection_summary={"remaining_gaps": []},
        provider_config={"synthesis": {"provider": "openai", "model": "gpt-4.1-mini", "temperature": 0.2}},
    )

    assert provider.calls[0]["config"] == {"provider": "openai", "model": "gpt-4.1-mini", "temperature": 0.2}
    assert [section.title for section in result.outline_sections] == ["Background"]
    assert result.claims[0].text == "Supported claim"
    assert result.report_markdown == "# Research Report\n\n## Background\n\nEvidence-backed section text."
    assert result.synthesis_summary["mode"] == "llm_backed"


@pytest.mark.asyncio
async def test_synthesizer_falls_back_when_provider_references_unknown_ids():
    from tldw_Server_API.app.core.Research.synthesizer import ResearchSynthesizer

    provider = _SynthesisProviderStub(
        {
            "outline_sections": [
                {
                    "title": "Background",
                    "focus_area": "background",
                    "source_ids": ["src_missing"],
                    "note_ids": ["note_missing"],
                }
            ],
            "claims": [
                {
                    "text": "Unsupported claim",
                    "focus_area": "background",
                    "source_ids": ["src_missing"],
                    "citations": [{"source_id": "src_missing"}],
                    "confidence": 0.2,
                }
            ],
            "report_sections": [
                {
                    "title": "Background",
                    "markdown": "Invalid references should trigger fallback.",
                }
            ],
            "unresolved_questions": [],
            "summary": {"mode": "llm_backed"},
        }
    )

    synthesizer = ResearchSynthesizer(synthesis_provider=provider)
    result = await synthesizer.synthesize(
        plan=_plan(["background"]),
        source_registry=[_source("src_background", "background")],
        evidence_notes=[_note("note_background", "src_background", "background", "Grounded evidence.")],
        collection_summary={"remaining_gaps": []},
        provider_config={"synthesis": {"provider": "openai", "model": "gpt-4.1-mini", "temperature": 0.2}},
    )

    assert result.synthesis_summary["mode"] == "deterministic_fallback"
    assert "unknown source_id" in result.synthesis_summary["fallback_reason"]
    assert "unknown note_id" in result.synthesis_summary["fallback_reason"]
    assert result.claims[0].source_ids == ["src_background"]


@pytest.mark.asyncio
async def test_synthesizer_falls_back_when_provider_raises():
    from tldw_Server_API.app.core.Research.synthesizer import ResearchSynthesizer

    provider = _SynthesisProviderStub(error=RuntimeError("provider unavailable"))
    synthesizer = ResearchSynthesizer(synthesis_provider=provider)
    result = await synthesizer.synthesize(
        plan=_plan(["background"]),
        source_registry=[_source("src_background", "background")],
        evidence_notes=[_note("note_background", "src_background", "background", "Grounded evidence.")],
        collection_summary={"remaining_gaps": []},
        provider_config={"synthesis": {"provider": "openai", "model": "gpt-4.1-mini", "temperature": 0.2}},
    )

    assert result.synthesis_summary["mode"] == "deterministic_fallback"
    assert "provider unavailable" in result.synthesis_summary["fallback_reason"]


@pytest.mark.asyncio
async def test_synthesizer_uses_locked_outline_seed_order_and_titles():
    from tldw_Server_API.app.core.Research.synthesizer import ResearchSynthesizer

    synthesizer = ResearchSynthesizer()
    result = await synthesizer.synthesize(
        plan=_plan(["background", "counterevidence"]),
        source_registry=[
            _source("src_background", "background"),
            _source("src_counter", "counterevidence"),
        ],
        evidence_notes=[
            _note("note_background", "src_background", "background", "Background evidence."),
            _note("note_counter", "src_counter", "counterevidence", "Counterevidence."),
        ],
        collection_summary={"remaining_gaps": []},
        provider_config={"synthesis": {"provider": "openai", "model": "gpt-4.1-mini", "temperature": 0.2}},
        outline_seed=[
            {"title": "Counterevidence First", "focus_area": "counterevidence"},
            {"title": "Background Context", "focus_area": "background"},
        ],
        approved_outline_locked=True,
    )

    assert [section.title for section in result.outline_sections] == [
        "Counterevidence First",
        "Background Context",
    ]
    assert [section.focus_area for section in result.outline_sections] == [
        "counterevidence",
        "background",
    ]
    assert "## Counterevidence First" in result.report_markdown
    assert "## Background Context" in result.report_markdown
    assert result.synthesis_summary["mode"] == "deterministic_outline_locked"
