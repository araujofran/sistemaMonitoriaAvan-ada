"""SQLAlchemy 2.x mapping for deployments that use ORM migrations.

The runtime repository uses explicit SQLite transactions in database.py to remain
portable; these mappings mirror the persisted contract and are ready for Alembic.
"""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase): pass


class AnalysisBatch(Base):
    __tablename__ = "analysis_batches"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    processed_files: Mapped[int] = mapped_column(Integer, default=0)
    failed_files: Mapped[int] = mapped_column(Integer, default=0)
    skipped_files: Mapped[int] = mapped_column(Integer, default=0)


class Interaction(Base):
    __tablename__ = "interactions"
    __table_args__ = (UniqueConstraint("batch_id", "content_hash"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("analysis_batches.id"))
    filename: Mapped[str] = mapped_column(String)
    content_hash: Mapped[str] = mapped_column(String)
    analysis_status: Mapped[str] = mapped_column(String)
    score_operator: Mapped[float] = mapped_column(Float)
    score_experience: Mapped[float] = mapped_column(Float)
    analysis_json: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String, default="txt")
    source_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    source_sheet: Mapped[str | None] = mapped_column(String, nullable=True)
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    analysis_date: Mapped[str | None] = mapped_column(String, nullable=True)


class EvidenceModel(Base):
    __tablename__ = "evidences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interaction_id: Mapped[str] = mapped_column(ForeignKey("interactions.id"))
    regex_id: Mapped[str] = mapped_column(String)
    criterion_code: Mapped[str | None] = mapped_column(String, nullable=True)
    speaker: Mapped[str] = mapped_column(String)
    evidence_text: Mapped[str] = mapped_column(Text)
    is_negated: Mapped[int] = mapped_column(Integer)


class CriterionResultModel(Base):
    __tablename__ = "monitoring_criteria_results"
    __table_args__ = (UniqueConstraint("interaction_id", "code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interaction_id: Mapped[str] = mapped_column(ForeignKey("interactions.id"))
    code: Mapped[str] = mapped_column(String)
    classification: Mapped[str] = mapped_column(String)
    weight: Mapped[float] = mapped_column(Float)
    factor: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)


class InteractionMetadataModel(Base):
    __tablename__ = "interaction_metadata"
    __table_args__ = (UniqueConstraint("interaction_id", "original_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interaction_id: Mapped[str] = mapped_column(ForeignKey("interactions.id"))
    original_key: Mapped[str] = mapped_column(String)
    normalized_key: Mapped[str] = mapped_column(String)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
