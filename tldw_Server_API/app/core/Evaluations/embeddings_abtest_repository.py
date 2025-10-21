from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import uuid

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    select,
    func,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker, selectinload


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso_or_none(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class EmbeddingABTest(Base):
    __tablename__ = "embedding_abtests"

    test_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    stats_json: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    arms: Mapped[List["EmbeddingABTestArm"]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="EmbeddingABTestArm.arm_index"
    )
    queries: Mapped[List["EmbeddingABTestQuery"]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="EmbeddingABTestQuery.created_at"
    )
    results: Mapped[List["EmbeddingABTestResult"]] = relationship(
        back_populates="test", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_abtests_created", created_at.desc()),
        Index("idx_abtests_status", status),
    )


class EmbeddingABTestArm(Base):
    __tablename__ = "embedding_abtest_arms"

    arm_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    test_id: Mapped[str] = mapped_column(ForeignKey("embedding_abtests.test_id"), nullable=False)
    arm_index: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    dimensions: Mapped[Optional[int]] = mapped_column(Integer)
    collection_hash: Mapped[Optional[str]] = mapped_column(String(128))
    pipeline_hash: Mapped[Optional[str]] = mapped_column(String(128))
    collection_name: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    stats_json: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)

    test: Mapped[EmbeddingABTest] = relationship(back_populates="arms")
    results: Mapped[List["EmbeddingABTestResult"]] = relationship(back_populates="arm", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_abtest_arms_test", "test_id"),
    )


class EmbeddingABTestQuery(Base):
    __tablename__ = "embedding_abtest_queries"

    query_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    test_id: Mapped[str] = mapped_column(ForeignKey("embedding_abtests.test_id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    ground_truth_ids: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    test: Mapped[EmbeddingABTest] = relationship(back_populates="queries")
    results: Mapped[List["EmbeddingABTestResult"]] = relationship(back_populates="query", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_abtest_queries_test", "test_id"),
    )


class EmbeddingABTestResult(Base):
    __tablename__ = "embedding_abtest_results"

    result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    test_id: Mapped[str] = mapped_column(ForeignKey("embedding_abtests.test_id"), nullable=False)
    arm_id: Mapped[str] = mapped_column(ForeignKey("embedding_abtest_arms.arm_id"), nullable=False)
    query_id: Mapped[str] = mapped_column(ForeignKey("embedding_abtest_queries.query_id"), nullable=False)
    ranked_ids: Mapped[str] = mapped_column(Text, nullable=False)
    scores: Mapped[Optional[str]] = mapped_column(Text)
    metrics_json: Mapped[Optional[str]] = mapped_column(Text)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float)
    ranked_distances: Mapped[Optional[str]] = mapped_column(Text)
    ranked_metadatas: Mapped[Optional[str]] = mapped_column(Text)
    ranked_documents: Mapped[Optional[str]] = mapped_column(Text)
    rerank_scores: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    test: Mapped[EmbeddingABTest] = relationship(back_populates="results")
    arm: Mapped[EmbeddingABTestArm] = relationship(back_populates="results")
    query: Mapped[EmbeddingABTestQuery] = relationship(back_populates="results")

    __table_args__ = (
        Index("idx_abtest_results_test", "test_id"),
        Index("idx_abtest_results_arm", "arm_id"),
        Index("idx_abtest_results_query", "query_id"),
    )


@dataclass
class RepositoryConfig:
    db_url: str
    echo: bool = False


class EmbeddingABTestRepository:
    """SQLAlchemy-backed repository for embeddings A/B tests."""

    def __init__(self, engine: Engine, session_factory: sessionmaker[Session]) -> None:
        self._engine = engine
        self._session_factory = session_factory

    @classmethod
    def from_config(cls, config: RepositoryConfig) -> "EmbeddingABTestRepository":
        engine = create_engine(config.db_url, echo=config.echo, future=True)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        return cls(engine, factory)

    @contextmanager
    def session_scope(self) -> Iterable[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_test(
        self,
        *,
        test_id: str,
        name: str,
        created_by: Optional[str],
        config: Dict[str, Any],
        status: str = "pending",
        notes: Optional[str] = None,
    ) -> EmbeddingABTest:
        with self.session_scope() as session:
            entity = EmbeddingABTest(
                test_id=test_id,
                name=name,
                created_by=created_by,
                status=status,
                notes=notes,
                config_json=json.dumps(config, separators=(",", ":"), sort_keys=True),
            )
            session.add(entity)
            session.flush()
            session.refresh(entity)
            if entity.created_at.tzinfo is None:
                entity.created_at = entity.created_at.replace(tzinfo=timezone.utc)
            return entity

    def add_arm(
        self,
        *,
        arm_id: str,
        test_id: str,
        arm_index: int,
        provider: str,
        model_id: str,
        dimensions: Optional[int] = None,
        collection_hash: Optional[str] = None,
        pipeline_hash: Optional[str] = None,
        collection_name: Optional[str] = None,
        status: str = "pending",
        stats: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EmbeddingABTestArm:
        with self.session_scope() as session:
            arm = session.get(EmbeddingABTestArm, arm_id)
            payload_stats = json.dumps(stats, sort_keys=True) if stats else None
            payload_meta = json.dumps(metadata, sort_keys=True) if metadata else None
            if arm is None:
                arm = EmbeddingABTestArm(
                    arm_id=arm_id,
                    test_id=test_id,
                    arm_index=arm_index,
                    provider=provider,
                    model_id=model_id,
                    dimensions=dimensions,
                    collection_hash=collection_hash,
                    pipeline_hash=pipeline_hash,
                    collection_name=collection_name,
                    status=status,
                    stats_json=payload_stats,
                    metadata_json=payload_meta,
                )
            else:
                arm.arm_index = arm_index
                arm.provider = provider
                arm.model_id = model_id
                arm.dimensions = dimensions
                arm.collection_hash = collection_hash
                arm.pipeline_hash = pipeline_hash
                arm.collection_name = collection_name
                arm.status = status
                if stats is not None:
                    arm.stats_json = payload_stats
                arm.metadata_json = payload_meta
            session.add(arm)
            session.flush()
            session.refresh(arm)
            return arm

    def add_query(
        self,
        *,
        query_id: str,
        test_id: str,
        text: str,
        ground_truth_ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EmbeddingABTestQuery:
        with self.session_scope() as session:
            query = EmbeddingABTestQuery(
                query_id=query_id,
                test_id=test_id,
                text=text,
                ground_truth_ids=json.dumps(ground_truth_ids) if ground_truth_ids else None,
                metadata_json=json.dumps(metadata, sort_keys=True) if metadata else None,
            )
            session.add(query)
            session.flush()
            session.refresh(query)
            return query

    def record_result(
        self,
        *,
        result_id: str,
        test_id: str,
        arm_id: str,
        query_id: str,
        ranked_ids: List[str],
        scores: Optional[List[float]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[float] = None,
        ranked_distances: Optional[List[float]] = None,
        ranked_metadatas: Optional[List[Dict[str, Any]]] = None,
        ranked_documents: Optional[List[str]] = None,
        rerank_scores: Optional[List[float]] = None,
    ) -> EmbeddingABTestResult:
        with self.session_scope() as session:
            result = EmbeddingABTestResult(
                result_id=result_id,
                test_id=test_id,
                arm_id=arm_id,
                query_id=query_id,
                ranked_ids=json.dumps(ranked_ids),
                scores=json.dumps(scores) if scores is not None else None,
                metrics_json=json.dumps(metrics, sort_keys=True) if metrics else None,
                latency_ms=latency_ms,
                ranked_distances=json.dumps(ranked_distances) if ranked_distances else None,
                ranked_metadatas=json.dumps(ranked_metadatas, sort_keys=True) if ranked_metadatas else None,
                ranked_documents=json.dumps(ranked_documents) if ranked_documents else None,
                rerank_scores=json.dumps(rerank_scores) if rerank_scores else None,
            )
            session.add(result)
            session.flush()
            session.refresh(result)
            return result

    def update_test_status(
        self,
        *,
        test_id: str,
        status: str,
        stats: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self.session_scope() as session:
            stmt = select(EmbeddingABTest).where(EmbeddingABTest.test_id == test_id)
            entity = session.execute(stmt).scalar_one_or_none()
            if not entity:
                raise ValueError(f"Embedding A/B test {test_id} not found")
            entity.status = status
            if stats is not None:
                entity.stats_json = json.dumps(stats, sort_keys=True)
            session.add(entity)

    def get_test_with_children(self, test_id: str) -> Optional[EmbeddingABTest]:
        with self._session_factory() as session:
            stmt = (
                select(EmbeddingABTest)
                .where(EmbeddingABTest.test_id == test_id)
                .options(
                    selectinload(EmbeddingABTest.arms),
                    selectinload(EmbeddingABTest.queries),
                    selectinload(EmbeddingABTest.results),
                )
            )
            result = session.execute(stmt).scalar_one_or_none()
            if result:
                session.expunge(result)
            return result

    def get_test(self, test_id: str) -> Optional[EmbeddingABTest]:
        with self._session_factory() as session:
            stmt = select(EmbeddingABTest).where(EmbeddingABTest.test_id == test_id)
            result = session.execute(stmt).scalar_one_or_none()
            if result:
                session.expunge(result)
            return result

    def list_arms(self, test_id: str) -> List[EmbeddingABTestArm]:
        with self._session_factory() as session:
            stmt = (
                select(EmbeddingABTestArm)
                .where(EmbeddingABTestArm.test_id == test_id)
                .order_by(EmbeddingABTestArm.arm_index.asc())
            )
            rows = session.execute(stmt).scalars().all()
            for row in rows:
                session.expunge(row)
            return rows

    def list_queries(self, test_id: str) -> List[EmbeddingABTestQuery]:
        with self._session_factory() as session:
            stmt = select(EmbeddingABTestQuery).where(EmbeddingABTestQuery.test_id == test_id)
            rows = session.execute(stmt).scalars().all()
            for row in rows:
                session.expunge(row)
            return rows

    def list_results(self, test_id: str, limit: int, offset: int) -> Tuple[List[EmbeddingABTestResult], int]:
        with self._session_factory() as session:
            count_stmt = (
                select(func.count())
                .select_from(EmbeddingABTestResult)
                .where(EmbeddingABTestResult.test_id == test_id)
            )
            total = int(session.execute(count_stmt).scalar_one() or 0)
            stmt = (
                select(EmbeddingABTestResult)
                .where(EmbeddingABTestResult.test_id == test_id)
                .order_by(EmbeddingABTestResult.created_at.asc())
                .limit(limit)
                .offset(offset)
            )
            rows = session.execute(stmt).scalars().all()
            for row in rows:
                session.expunge(row)
            return rows, total


def serialize_test(entity: EmbeddingABTest) -> Dict[str, Any]:
    return {
        "test_id": entity.test_id,
        "name": entity.name,
        "created_by": entity.created_by,
        "created_at": _iso_or_none(entity.created_at),
        "status": entity.status,
        "config_json": entity.config_json,
        "stats_json": entity.stats_json,
        "notes": entity.notes,
    }


def serialize_arm(entity: EmbeddingABTestArm) -> Dict[str, Any]:
    return {
        "arm_id": entity.arm_id,
        "test_id": entity.test_id,
        "arm_index": entity.arm_index,
        "provider": entity.provider,
        "model_id": entity.model_id,
        "dimensions": entity.dimensions,
        "collection_hash": entity.collection_hash,
        "pipeline_hash": entity.pipeline_hash,
        "collection_name": entity.collection_name,
        "status": entity.status,
        "stats_json": entity.stats_json,
        "metadata_json": entity.metadata_json,
    }


def serialize_query(entity: EmbeddingABTestQuery) -> Dict[str, Any]:
    return {
        "query_id": entity.query_id,
        "test_id": entity.test_id,
        "text": entity.text,
        "ground_truth_ids": entity.ground_truth_ids,
        "metadata_json": entity.metadata_json,
        "created_at": _iso_or_none(entity.created_at),
    }


def serialize_result(entity: EmbeddingABTestResult) -> Dict[str, Any]:
    return {
        "result_id": entity.result_id,
        "test_id": entity.test_id,
        "arm_id": entity.arm_id,
        "query_id": entity.query_id,
        "ranked_ids": entity.ranked_ids,
        "scores": entity.scores,
        "metrics_json": entity.metrics_json,
        "latency_ms": entity.latency_ms,
        "ranked_distances": entity.ranked_distances,
        "ranked_metadatas": entity.ranked_metadatas,
        "ranked_documents": entity.ranked_documents,
        "rerank_scores": entity.rerank_scores,
        "created_at": _iso_or_none(entity.created_at),
    }


class EmbeddingsABTestStore:
    """Compatibility adapter that mirrors EvaluationsDatabase A/B test APIs."""

    def __init__(self, repository: EmbeddingABTestRepository) -> None:
        self._repo = repository

    def create_abtest(self, name: str, config: Dict[str, Any], created_by: Optional[str] = None) -> str:
        test_id = f"abtest_{uuid.uuid4().hex[:12]}"
        self._repo.create_test(
            test_id=test_id,
            name=name,
            created_by=created_by,
            config=config,
        )
        return test_id

    def upsert_abtest_arm(
        self,
        *,
        test_id: str,
        arm_index: int,
        provider: str,
        model_id: str,
        dimensions: Optional[int] = None,
        collection_hash: Optional[str] = None,
        pipeline_hash: Optional[str] = None,
        collection_name: Optional[str] = None,
        status: str = "pending",
        stats_json: Optional[Dict[str, Any]] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> str:
        arm_id = f"arm_{test_id}_{arm_index}"
        self._repo.add_arm(
            arm_id=arm_id,
            test_id=test_id,
            arm_index=arm_index,
            provider=provider,
            model_id=model_id,
            dimensions=dimensions,
            collection_hash=collection_hash,
            pipeline_hash=pipeline_hash,
            collection_name=collection_name,
            status=status,
            stats=stats_json,
            metadata=metadata_json,
        )
        return arm_id

    def insert_abtest_queries(self, test_id: str, queries: List[Dict[str, Any]]) -> List[str]:
        ids: List[str] = []
        for payload in queries:
            qid = f"q_{uuid.uuid4().hex[:10]}"
            ids.append(qid)
            ground_truth = payload.get("expected_ids") or payload.get("ground_truth_ids")
            metadata = payload.get("metadata")
            text = payload.get("text") or ""
            self._repo.add_query(
                query_id=qid,
                test_id=test_id,
                text=text,
                ground_truth_ids=list(ground_truth) if isinstance(ground_truth, (list, tuple)) else ground_truth,
                metadata=metadata if isinstance(metadata, dict) else None,
            )
        return ids

    def set_abtest_status(self, test_id: str, status: str, stats_json: Optional[Dict[str, Any]] = None) -> None:
        self._repo.update_test_status(test_id=test_id, status=status, stats=stats_json)

    def insert_abtest_result(
        self,
        test_id: str,
        arm_id: str,
        query_id: str,
        ranked_ids: List[str],
        scores: Optional[List[float]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[float] = None,
        ranked_distances: Optional[List[float]] = None,
        ranked_metadatas: Optional[List[Dict[str, Any]]] = None,
        ranked_documents: Optional[List[str]] = None,
        rerank_scores: Optional[List[float]] = None,
    ) -> str:
        rid = f"res_{uuid.uuid4().hex[:12]}"
        self._repo.record_result(
            result_id=rid,
            test_id=test_id,
            arm_id=arm_id,
            query_id=query_id,
            ranked_ids=ranked_ids,
            scores=scores,
            metrics=metrics,
            latency_ms=latency_ms,
            ranked_distances=ranked_distances,
            ranked_metadatas=ranked_metadatas,
            ranked_documents=ranked_documents,
            rerank_scores=rerank_scores,
        )
        return rid

    def get_abtest(self, test_id: str) -> Optional[Dict[str, Any]]:
        entity = self._repo.get_test(test_id)
        if not entity:
            return None
        return serialize_test(entity)

    def get_abtest_arms(self, test_id: str) -> List[Dict[str, Any]]:
        return [serialize_arm(arm) for arm in self._repo.list_arms(test_id)]

    def get_abtest_queries(self, test_id: str) -> List[Dict[str, Any]]:
        return [serialize_query(q) for q in self._repo.list_queries(test_id)]

    def list_abtest_results(self, test_id: str, limit: int, offset: int) -> Tuple[List[Dict[str, Any]], int]:
        rows, total = self._repo.list_results(test_id, limit, offset)
        return [serialize_result(r) for r in rows], total


def _sqlite_url_from_path(path: str) -> str:
    location = Path(path).expanduser().resolve()
    return f"sqlite:///{location}"


@lru_cache(maxsize=8)
def get_embeddings_abtest_store(db_path: str) -> EmbeddingsABTestStore:
    config = RepositoryConfig(db_url=_sqlite_url_from_path(db_path))
    repo = EmbeddingABTestRepository.from_config(config)
    return EmbeddingsABTestStore(repo)
