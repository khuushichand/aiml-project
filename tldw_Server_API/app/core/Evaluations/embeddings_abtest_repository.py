from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

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
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker, selectinload


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @classmethod
    def from_config(cls, config: RepositoryConfig) -> "EmbeddingABTestRepository":
        engine = create_engine(config.db_url, echo=config.echo, future=True)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        return cls(factory)

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
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EmbeddingABTestArm:
        with self.session_scope() as session:
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
                metadata_json=json.dumps(metadata, sort_keys=True) if metadata else None,
            )
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
                for arm in result.arms:
                    session.expunge(arm)
                for query in result.queries:
                    session.expunge(query)
                for item in result.results:
                    session.expunge(item)
            return result
