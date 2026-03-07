import pytest


pytestmark = pytest.mark.unit


class _ProviderStub:
    def __init__(self, records=None, *, error: Exception | None = None):
        self._records = list(records or [])
        self._error = error
        self.calls: list[dict[str, object]] = []

    async def search(self, *, focus_area: str, query: str, owner_user_id: str, config: dict[str, object]):
        self.calls.append(
            {
                "focus_area": focus_area,
                "query": query,
                "owner_user_id": owner_user_id,
                "config": dict(config),
            }
        )
        if self._error is not None:
            raise self._error
        return list(self._records)


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
async def test_collecting_job_parks_paused_before_phase_start(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Pause before collecting",
        source_policy="balanced",
        autonomy_mode="autonomous",
        limits_json={},
        phase="collecting",
        status="queued",
    )
    db.update_control_state(session.id, control_state="pause_requested")
    store = ResearchArtifactStore(base_dir=tmp_path / "outputs", db=db)
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="plan.json",
        payload={
            "query": session.query,
            "focus_areas": ["background"],
            "source_policy": session.source_policy,
            "autonomy_mode": session.autonomy_mode,
            "stop_criteria": {"min_cited_sections": 1},
        },
        phase="collecting",
        job_id=None,
    )

    class StubBroker:
        async def collect_focus_area(self, **kwargs):
            raise AssertionError(f"phase should have paused before broker call: {kwargs}")

    await handle_research_phase_job(
        {
            "id": 700,
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
    assert updated.control_state == "paused"
    assert updated.phase == "collecting"
    assert updated.active_job_id is None
    assert updated.progress_percent is None
    assert updated.progress_message is None


@pytest.mark.asyncio
async def test_collecting_job_advances_phase_and_parks_paused_when_pause_requested_during_work(tmp_path):
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
        query="Pause after collecting work",
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
            "focus_areas": ["background"],
            "source_policy": session.source_policy,
            "autonomy_mode": session.autonomy_mode,
            "stop_criteria": {"min_cited_sections": 1},
        },
        phase="collecting",
        job_id=None,
    )

    class StubBroker:
        async def collect_focus_area(self, **kwargs):
            db.update_control_state(session.id, control_state="pause_requested")
            return ResearchCollectionResult(
                sources=[
                    ResearchSourceRecord(
                        source_id="src_pause",
                        focus_area="background",
                        source_type="local_document",
                        provider="local_corpus",
                        title="Internal source",
                        url=None,
                        snippet="Internal summary",
                        published_at=None,
                        retrieved_at="2026-03-07T00:00:00+00:00",
                        fingerprint="fp_pause",
                        trust_tier="internal",
                        metadata={},
                    )
                ],
                evidence_notes=[
                    ResearchEvidenceNote(
                        note_id="note_pause",
                        source_id="src_pause",
                        focus_area="background",
                        kind="summary",
                        text="Internal summary",
                        citation_locator=None,
                        confidence=0.9,
                        metadata={},
                    )
                ],
                collection_metrics={"lane_counts": {"local": 1, "academic": 0, "web": 0}, "deduped_sources": 0},
                remaining_gaps=[],
            )

    await handle_research_phase_job(
        {
            "id": 701,
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
    assert updated.status == "queued"
    assert updated.control_state == "paused"
    assert updated.active_job_id is None
    assert updated.progress_percent == 45.0
    assert updated.progress_message == "collecting sources"


@pytest.mark.asyncio
async def test_collecting_job_reads_provider_config_and_passes_lane_settings(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore
    from tldw_Server_API.app.core.Research.broker import ResearchBroker
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Test collecting config",
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
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="provider_config.json",
        payload={
            "local": {"top_k": 4, "sources": ["media_db"]},
            "academic": {"providers": ["arxiv"], "max_results": 2},
            "web": {"engine": "kagi", "result_count": 3},
            "synthesis": {"provider": None, "model": None, "temperature": 0.2},
        },
        phase="collecting",
        job_id=None,
    )

    local_provider = _ProviderStub(
        [{"id": "doc-1", "title": "Internal source", "content": "Internal note summary", "provider": "local_corpus"}]
    )
    academic_provider = _ProviderStub(
        [{"doi": "10.1000/example", "title": "Academic source", "summary": "paper", "provider": "arxiv"}]
    )
    web_provider = _ProviderStub(
        [{"url": "https://example.com/report", "title": "Web source", "snippet": "report", "provider": "kagi"}]
    )

    result = await handle_research_phase_job(
        {
            "id": 70,
            "payload": {
                "session_id": session.id,
                "phase": "collecting",
                "checkpoint_id": None,
                "policy_version": 1,
            },
        },
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
        broker=ResearchBroker(
            local_provider=local_provider,
            academic_provider=academic_provider,
            web_provider=web_provider,
        ),
    )

    assert result["phase"] == "synthesizing"
    assert local_provider.calls[0]["config"] == {"top_k": 4, "sources": ["media_db"]}
    assert academic_provider.calls[0]["config"] == {"providers": ["arxiv"], "max_results": 2}
    assert web_provider.calls[0]["config"] == {"engine": "kagi", "result_count": 3}


@pytest.mark.asyncio
async def test_collecting_job_records_lane_errors_and_still_advances_when_one_lane_succeeds(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore
    from tldw_Server_API.app.core.Research.broker import ResearchBroker
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Test collecting lane errors",
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
    store.write_json(
        owner_user_id="1",
        session_id=session.id,
        artifact_name="provider_config.json",
        payload={
            "local": {"top_k": 5, "sources": ["media_db"]},
            "academic": {"providers": ["arxiv"], "max_results": 2},
            "web": {"engine": "duckduckgo", "result_count": 3},
            "synthesis": {"provider": None, "model": None, "temperature": 0.2},
        },
        phase="collecting",
        job_id=None,
    )

    broker = ResearchBroker(
        local_provider=_ProviderStub(
            [{"id": "doc-1", "title": "Internal source", "content": "Internal note summary", "provider": "local_corpus"}]
        ),
        academic_provider=_ProviderStub([]),
        web_provider=_ProviderStub(error=RuntimeError("web search failed")),
    )

    result = await handle_research_phase_job(
        {
            "id": 71,
            "payload": {
                "session_id": session.id,
                "phase": "collecting",
                "checkpoint_id": None,
                "policy_version": 1,
            },
        },
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
        broker=broker,
    )

    collection_summary = store.read_json(session_id=session.id, artifact_name="collection_summary.json")

    assert result["phase"] == "synthesizing"
    assert collection_summary is not None
    assert collection_summary["lane_errors"] == [
        {
            "focus_area": "evidence alignment",
            "lane": "web",
            "message": "web search failed",
        }
    ]


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
async def test_synthesizing_job_uses_provider_config_and_writes_llm_backed_summary(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job
    from tldw_Server_API.app.core.Research.synthesizer import ResearchSynthesizer

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Provider-backed synthesizing",
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
            "focus_areas": ["background"],
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
        artifact_name="provider_config.json",
        payload={
            "local": {"top_k": 5, "sources": ["media_db"]},
            "academic": {"providers": ["arxiv"], "max_results": 2},
            "web": {"engine": "duckduckgo", "result_count": 3},
            "synthesis": {"provider": "openai", "model": "gpt-4.1-mini", "temperature": 0.2},
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
                    "focus_area": "background",
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
                "focus_area": "background",
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
            "focus_areas": ["background"],
            "source_count": 1,
            "evidence_note_count": 1,
            "remaining_gaps": [],
            "collection_metrics": {"lane_counts": {"local": 1, "academic": 0, "web": 0}, "deduped_sources": 0},
        },
        phase="synthesizing",
        job_id=None,
    )

    provider = _SynthesisProviderStub(
        {
            "outline_sections": [
                {
                    "title": "Background",
                    "focus_area": "background",
                    "source_ids": ["src_1"],
                    "note_ids": ["note_1"],
                }
            ],
            "claims": [
                {
                    "text": "Supported claim",
                    "focus_area": "background",
                    "source_ids": ["src_1"],
                    "citations": [{"source_id": "src_1"}],
                    "confidence": 0.81,
                }
            ],
            "report_sections": [
                {"title": "Background", "markdown": "Evidence-backed section text."}
            ],
            "unresolved_questions": [],
            "summary": {"mode": "llm_backed"},
        }
    )

    result = await handle_research_phase_job(
        {
            "id": 81,
            "payload": {
                "session_id": session.id,
                "phase": "synthesizing",
                "checkpoint_id": None,
                "policy_version": 1,
            },
        },
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
        synthesizer=ResearchSynthesizer(synthesis_provider=provider),
    )

    summary = store.read_json(session_id=session.id, artifact_name="synthesis_summary.json")

    assert result["phase"] == "packaging"
    assert provider.calls[0]["config"] == {"provider": "openai", "model": "gpt-4.1-mini", "temperature": 0.2}
    assert summary is not None
    assert summary["mode"] == "llm_backed"


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
    assert updated.progress_percent == 100.0
    assert updated.progress_message == "packaging results"
    assert result["phase"] == "completed"
    assert result["artifacts_written"] >= 1

    bundle = store.read_json(session_id=session.id, artifact_name="bundle.json")
    assert bundle is not None
    assert bundle["question"] == session.query
    assert bundle["claims"][0]["citations"][0]["source_id"] == "src_1"


@pytest.mark.asyncio
async def test_synthesizing_job_cancels_before_phase_start(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
    from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job

    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Cancel before synthesizing",
        source_policy="balanced",
        autonomy_mode="autonomous",
        limits_json={},
        phase="synthesizing",
        status="queued",
    )
    db.update_control_state(session.id, control_state="cancel_requested")

    await handle_research_phase_job(
        {
            "id": 702,
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
    assert updated.status == "cancelled"
    assert updated.control_state == "cancelled"
    assert updated.active_job_id is None
    assert updated.phase == "synthesizing"


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
