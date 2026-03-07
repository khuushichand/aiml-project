import pytest


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_planning_job_writes_plan_and_opens_checkpoint(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Test planning",
        source_policy="balanced",
        autonomy_mode="checkpointed",
        limits_json={},
    )

    result = await handle_research_phase_job(
        {
            "id": 5,
            "payload": {
                "session_id": session.id,
                "phase": "drafting_plan",
                "checkpoint_id": None,
                "policy_version": 1,
            },
        },
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
    )

    updated = db.get_session(session.id)
    assert updated is not None
    assert updated.phase == "awaiting_plan_review"
    assert updated.latest_checkpoint_id is not None
    assert result["phase"] == "awaiting_plan_review"
    assert result["artifacts_written"] >= 1
    assert (tmp_path / "outputs" / "research" / session.id / "plan.json").exists()


@pytest.mark.asyncio
async def test_collecting_job_writes_artifacts_and_opens_source_review(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job
    from tldw_Server_API.app.core.Research.models import (
        ResearchCollectionResult,
        ResearchEvidenceNote,
        ResearchSourceRecord,
    )

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Test collecting",
        source_policy="balanced",
        autonomy_mode="checkpointed",
        limits_json={},
        phase="collecting",
        status="queued",
    )
    store = ResearchArtifactStore(base_dir=tmp_path / "outputs", db=db)
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="approved_plan.json",
        payload={
            "query": session.query,
            "focus_areas": ["evidence alignment"],
            "source_policy": session.source_policy,
            "autonomy_mode": session.autonomy_mode,
            "stop_criteria": {"min_cited_sections": 1},
        },
        phase="collecting",
        job_id=None,
    )

    class StubBroker:
        async def collect_focus_area(self, **kwargs):
            _ = kwargs
            return ResearchCollectionResult(
                sources=[
                    ResearchSourceRecord(
                        source_id="src_1",
                        focus_area="evidence alignment",
                        source_type="local_document",
                        provider="local_corpus",
                        title="Internal source",
                        url=None,
                        snippet="Internal note summary",
                        published_at=None,
                        retrieved_at="2026-03-07T00:00:00+00:00",
                        fingerprint="fp_1",
                        trust_tier="internal",
                        metadata={},
                    )
                ],
                evidence_notes=[
                    ResearchEvidenceNote(
                        note_id="note_1",
                        source_id="src_1",
                        focus_area="evidence alignment",
                        kind="summary",
                        text="Internal note summary",
                        citation_locator=None,
                        confidence=0.8,
                        metadata={},
                    )
                ],
                collection_metrics={"lane_counts": {"local": 1, "academic": 0, "web": 0}, "deduped_sources": 0},
                remaining_gaps=[],
            )

    result = await handle_research_phase_job(
        {
            "id": 6,
            "payload": {
                "session_id": session.id,
                "phase": "collecting",
                "checkpoint_id": None,
                "policy_version": 1,
            },
        },
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
        broker=StubBroker(),
    )

    updated = db.get_session(session.id)
    assert updated is not None
    assert updated.phase == "awaiting_source_review"
    assert updated.latest_checkpoint_id is not None
    assert result["phase"] == "awaiting_source_review"
    assert result["artifacts_written"] >= 3
    assert (tmp_path / "outputs" / "research" / session.id / "source_registry.json").exists()
    assert (tmp_path / "outputs" / "research" / session.id / "evidence_notes.jsonl").exists()
    assert (tmp_path / "outputs" / "research" / session.id / "collection_summary.json").exists()


@pytest.mark.asyncio
async def test_collecting_job_advances_autonomous_run_to_synthesizing(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job
    from tldw_Server_API.app.core.Research.models import ResearchCollectionResult

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Test collecting",
        source_policy="balanced",
        autonomy_mode="autonomous",
        limits_json={},
        phase="collecting",
        status="queued",
    )
    store = ResearchArtifactStore(base_dir=tmp_path / "outputs", db=db)
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="plan.json",
        payload={
            "query": session.query,
            "focus_areas": ["evidence alignment"],
            "source_policy": session.source_policy,
            "autonomy_mode": session.autonomy_mode,
            "stop_criteria": {"min_cited_sections": 1},
        },
        phase="collecting",
        job_id=None,
    )

    class StubBroker:
        async def collect_focus_area(self, **kwargs):
            _ = kwargs
            return ResearchCollectionResult(
                sources=[],
                evidence_notes=[],
                collection_metrics={"lane_counts": {"local": 0, "academic": 0, "web": 0}, "deduped_sources": 0},
                remaining_gaps=["no_sources_collected"],
            )

    result = await handle_research_phase_job(
        {
            "id": 7,
            "payload": {
                "session_id": session.id,
                "phase": "collecting",
                "checkpoint_id": None,
                "policy_version": 1,
            },
        },
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
        broker=StubBroker(),
    )

    updated = db.get_session(session.id)
    assert updated is not None
    assert updated.phase == "synthesizing"
    assert result["phase"] == "synthesizing"


@pytest.mark.asyncio
async def test_synthesizing_job_writes_artifacts_and_opens_outline_review(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Test synthesizing",
        source_policy="balanced",
        autonomy_mode="checkpointed",
        limits_json={},
        phase="synthesizing",
        status="queued",
    )
    store = ResearchArtifactStore(base_dir=tmp_path / "outputs", db=db)
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="approved_plan.json",
        payload={
            "query": session.query,
            "focus_areas": ["evidence alignment"],
            "source_policy": session.source_policy,
            "autonomy_mode": session.autonomy_mode,
            "stop_criteria": {"min_cited_sections": 1},
        },
        phase="synthesizing",
        job_id=None,
    )
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="source_registry.json",
        payload={
            "sources": [
                {
                    "source_id": "src_1",
                    "focus_area": "evidence alignment",
                    "source_type": "local_document",
                    "provider": "local_corpus",
                    "title": "Internal source",
                    "url": None,
                    "snippet": "Internal note summary",
                    "published_at": None,
                    "retrieved_at": "2026-03-07T00:00:00+00:00",
                    "fingerprint": "fp_1",
                    "trust_tier": "internal",
                    "metadata": {},
                }
            ]
        },
        phase="synthesizing",
        job_id=None,
    )
    store.write_jsonl(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="evidence_notes.jsonl",
        records=[
            {
                "note_id": "note_1",
                "source_id": "src_1",
                "focus_area": "evidence alignment",
                "kind": "summary",
                "text": "Internal evidence remains aligned.",
                "citation_locator": None,
                "confidence": 0.8,
                "metadata": {},
            }
        ],
        phase="synthesizing",
        job_id=None,
    )
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="collection_summary.json",
        payload={
            "query": session.query,
            "focus_areas": ["evidence alignment"],
            "source_count": 1,
            "evidence_note_count": 1,
            "remaining_gaps": [],
            "collection_metrics": {"lane_counts": {"local": 1, "academic": 0, "web": 0}, "deduped_sources": 0},
        },
        phase="synthesizing",
        job_id=None,
    )

    result = await handle_research_phase_job(
        {
            "id": 8,
            "payload": {
                "session_id": session.id,
                "phase": "synthesizing",
                "checkpoint_id": None,
                "policy_version": 1,
            },
        },
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
    )

    updated = db.get_session(session.id)
    assert updated is not None
    assert updated.phase == "awaiting_outline_review"
    assert updated.latest_checkpoint_id is not None
    assert result["phase"] == "awaiting_outline_review"
    assert result["artifacts_written"] >= 4
    assert (tmp_path / "outputs" / "research" / session.id / "outline_v1.json").exists()
    assert (tmp_path / "outputs" / "research" / session.id / "claims.json").exists()
    assert (tmp_path / "outputs" / "research" / session.id / "report_v1.md").exists()
    assert (tmp_path / "outputs" / "research" / session.id / "synthesis_summary.json").exists()


@pytest.mark.asyncio
async def test_synthesizing_job_advances_autonomous_run_to_packaging(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Test synthesizing",
        source_policy="balanced",
        autonomy_mode="autonomous",
        limits_json={},
        phase="synthesizing",
        status="queued",
    )
    store = ResearchArtifactStore(base_dir=tmp_path / "outputs", db=db)
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="plan.json",
        payload={
            "query": session.query,
            "focus_areas": ["evidence alignment"],
            "source_policy": session.source_policy,
            "autonomy_mode": session.autonomy_mode,
            "stop_criteria": {"min_cited_sections": 1},
        },
        phase="synthesizing",
        job_id=None,
    )
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="source_registry.json",
        payload={"sources": []},
        phase="synthesizing",
        job_id=None,
    )
    store.write_jsonl(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="evidence_notes.jsonl",
        records=[],
        phase="synthesizing",
        job_id=None,
    )
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="collection_summary.json",
        payload={
            "query": session.query,
            "focus_areas": ["evidence alignment"],
            "source_count": 0,
            "evidence_note_count": 0,
            "remaining_gaps": ["no_sources_collected"],
            "collection_metrics": {"lane_counts": {"local": 0, "academic": 0, "web": 0}, "deduped_sources": 0},
        },
        phase="synthesizing",
        job_id=None,
    )

    result = await handle_research_phase_job(
        {
            "id": 9,
            "payload": {
                "session_id": session.id,
                "phase": "synthesizing",
                "checkpoint_id": None,
                "policy_version": 1,
            },
        },
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
    )

    updated = db.get_session(session.id)
    assert updated is not None
    assert updated.phase == "packaging"
    assert result["phase"] == "packaging"


@pytest.mark.asyncio
async def test_packaging_job_writes_bundle_and_completes_session(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Test packaging",
        source_policy="balanced",
        autonomy_mode="autonomous",
        limits_json={},
        phase="packaging",
        status="queued",
    )
    store = ResearchArtifactStore(base_dir=tmp_path / "outputs", db=db)
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="plan.json",
        payload={
            "query": session.query,
            "focus_areas": ["evidence alignment"],
            "source_policy": session.source_policy,
            "autonomy_mode": session.autonomy_mode,
            "stop_criteria": {"min_cited_sections": 1},
        },
        phase="packaging",
        job_id=None,
    )
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="outline_v1.json",
        payload={
            "query": session.query,
            "sections": [
                {
                    "title": "Evidence Alignment",
                    "focus_area": "evidence alignment",
                    "source_ids": ["src_1"],
                    "note_ids": ["note_1"],
                }
            ],
            "unresolved_questions": [],
        },
        phase="packaging",
        job_id=None,
    )
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="claims.json",
        payload={
            "claims": [
                {
                    "claim_id": "clm_1",
                    "text": "Evidence is aligned.",
                    "focus_area": "evidence alignment",
                    "source_ids": ["src_1"],
                    "citations": [{"source_id": "src_1"}],
                    "confidence": 0.8,
                }
            ]
        },
        phase="packaging",
        job_id=None,
    )
    store.write_text(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="report_v1.md",
        content="# Research Report\n\n## Evidence Alignment\n\n- Evidence is aligned. [Sources: src_1]",
        phase="packaging",
        job_id=None,
        content_type="text/markdown",
    )
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="source_registry.json",
        payload={
            "sources": [
                {
                    "source_id": "src_1",
                    "focus_area": "evidence alignment",
                    "source_type": "local_document",
                    "provider": "local_corpus",
                    "title": "Internal source",
                    "url": None,
                    "snippet": "Internal note summary",
                    "published_at": None,
                    "retrieved_at": "2026-03-07T00:00:00+00:00",
                    "fingerprint": "fp_1",
                    "trust_tier": "internal",
                    "metadata": {},
                }
            ]
        },
        phase="packaging",
        job_id=None,
    )
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="synthesis_summary.json",
        payload={
            "query": session.query,
            "focus_areas": ["evidence alignment"],
            "section_count": 1,
            "claim_count": 1,
            "source_count": 1,
            "unresolved_questions": [],
            "coverage": {"covered_focus_areas": ["evidence alignment"], "missing_focus_areas": []},
        },
        phase="packaging",
        job_id=None,
    )

    result = await handle_research_phase_job(
        {
            "id": 10,
            "payload": {
                "session_id": session.id,
                "phase": "packaging",
                "checkpoint_id": None,
                "policy_version": 1,
            },
        },
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
    )

    updated = db.get_session(session.id)
    assert updated is not None
    assert updated.phase == "completed"
    assert updated.status == "completed"
    assert updated.completed_at is not None
    assert result["phase"] == "completed"
    assert result["artifacts_written"] >= 1

    bundle = store.read_json(session_id=session.id, artifact_name="bundle.json")
    assert bundle is not None
    assert bundle["question"] == session.query
    assert bundle["claims"][0]["citations"][0]["source_id"] == "src_1"


@pytest.mark.asyncio
async def test_packaging_job_rejects_uncited_claims(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Test packaging",
        source_policy="balanced",
        autonomy_mode="autonomous",
        limits_json={},
        phase="packaging",
        status="queued",
    )
    store = ResearchArtifactStore(base_dir=tmp_path / "outputs", db=db)
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="plan.json",
        payload={
            "query": session.query,
            "focus_areas": ["evidence alignment"],
            "source_policy": session.source_policy,
            "autonomy_mode": session.autonomy_mode,
            "stop_criteria": {"min_cited_sections": 1},
        },
        phase="packaging",
        job_id=None,
    )
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="outline_v1.json",
        payload={"query": session.query, "sections": [], "unresolved_questions": []},
        phase="packaging",
        job_id=None,
    )
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="claims.json",
        payload={
            "claims": [
                {
                    "claim_id": "clm_1",
                    "text": "Evidence is aligned.",
                    "focus_area": "evidence alignment",
                    "source_ids": ["src_1"],
                    "citations": [],
                    "confidence": 0.8,
                }
            ]
        },
        phase="packaging",
        job_id=None,
    )
    store.write_text(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="report_v1.md",
        content="# Research Report",
        phase="packaging",
        job_id=None,
        content_type="text/markdown",
    )
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="source_registry.json",
        payload={"sources": []},
        phase="packaging",
        job_id=None,
    )
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="synthesis_summary.json",
        payload={
            "query": session.query,
            "focus_areas": ["evidence alignment"],
            "section_count": 0,
            "claim_count": 1,
            "source_count": 0,
            "unresolved_questions": [],
            "coverage": {"covered_focus_areas": [], "missing_focus_areas": ["evidence alignment"]},
        },
        phase="packaging",
        job_id=None,
    )

    with pytest.raises(ValueError, match="claim_missing_citations"):
        await handle_research_phase_job(
            {
                "id": 11,
                "payload": {
                    "session_id": session.id,
                    "phase": "packaging",
                    "checkpoint_id": None,
                    "policy_version": 1,
                },
            },
            research_db_path=tmp_path / "research.db",
            outputs_dir=tmp_path / "outputs",
        )
