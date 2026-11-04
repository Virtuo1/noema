"""SQLAlchemy 2.0 relational models implementing the Noema data model."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from noema.persistence.db import Base


class AppUserModel(Base):
    __tablename__ = "app_users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)


class AISettingsModel(Base):
    __tablename__ = "ai_settings"

    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id", ondelete="CASCADE"), primary_key=True
    )
    conversation_provider: Mapped[str] = mapped_column(
        String, nullable=False, default="local_heuristic"
    )
    conversation_model: Mapped[str] = mapped_column(
        String, nullable=False, default="noema-local-chat-v1"
    )
    extraction_provider: Mapped[str] = mapped_column(
        String, nullable=False, default="local_heuristic"
    )
    extraction_model: Mapped[str] = mapped_column(
        String, nullable=False, default="noema-local-extractor-v1"
    )
    embedding_provider: Mapped[str] = mapped_column(
        String, nullable=False, default="local_heuristic"
    )
    embedding_model: Mapped[str] = mapped_column(
        String, nullable=False, default="noema-local-embed-v1"
    )
    hosted_data_consent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    local_endpoint_url: Mapped[str] = mapped_column(
        String, nullable=False, default="http://127.0.0.1:11434/v1"
    )
    context_budget_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1600)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class ConversationModel(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_owner_updated", "owner_user_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    archived_at: Mapped[str | None] = mapped_column(String, nullable=True)


class MessageModel(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence_no", name="uq_messages_conv_seq"),
        CheckConstraint("sequence_no >= 0", name="ck_messages_seq_nonneg"),
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')", name="ck_messages_role"
        ),
        Index("ix_messages_conversation_seq", "conversation_id", "sequence_no"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    reply_to_message_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")


class GenerationRunModel(Base):
    __tablename__ = "generation_runs"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id", "idempotency_key", name="uq_generation_runs_idempotency"
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_generation_runs_status",
        ),
        Index("ix_generation_runs_conversation", "conversation_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), nullable=False
    )
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    user_message_id: Mapped[str] = mapped_column(
        String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    assistant_message_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    context_mode: Mapped[str] = mapped_column(
        String, nullable=False, default="personalized"
    )
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)


class ConceptModel(Base):
    __tablename__ = "concepts"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id", "normalized_name", name="uq_concepts_owner_normalized"
        ),
        CheckConstraint(
            "merged_into_concept_id IS NULL OR merged_into_concept_id <> id",
            name="ck_concepts_no_self_merge",
        ),
        Index("ix_concepts_owner_updated", "owner_user_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), nullable=False
    )
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    merged_into_concept_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("concepts.id"), nullable=True
    )
    archived_at: Mapped[str | None] = mapped_column(String, nullable=True)


class ConceptAliasModel(Base):
    __tablename__ = "concept_aliases"
    __table_args__ = (
        CheckConstraint(
            "origin IN ('user', 'extractor', 'import')", name="ck_concept_aliases_origin"
        ),
        Index("ix_concept_aliases_normalized", "normalized_alias"),
        Index("ix_concept_aliases_concept", "concept_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String, nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String, nullable=False)
    origin: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class BackgroundJobModel(Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_background_jobs_idempotency"),
        CheckConstraint(
            "job_kind IN ('knowledge_extraction', 'embedding', 'connection_discovery')",
            name="ck_background_jobs_kind",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_background_jobs_status",
        ),
        Index("ix_background_jobs_status_avail", "status", "available_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), nullable=False
    )
    job_kind: Mapped[str] = mapped_column(String, nullable=False)
    source_generation_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("generation_runs.id", ondelete="CASCADE"), nullable=True
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String, nullable=True)
    lease_expires_at: Mapped[str | None] = mapped_column(String, nullable=True)
    available_at: Mapped[str] = mapped_column(String, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)


class ExtractionRunModel(Base):
    __tablename__ = "extraction_runs"
    __table_args__ = (
        CheckConstraint(
            "output_status IN ('running', 'succeeded', 'failed', 'repaired')",
            name="ck_extraction_runs_status",
        ),
        Index("ix_extraction_runs_job", "background_job_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    background_job_id: Mapped[str] = mapped_column(
        String, ForeignKey("background_jobs.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    output_status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)


class ConceptMentionModel(Base):
    __tablename__ = "concept_mentions"
    __table_args__ = (
        CheckConstraint(
            "(start_offset IS NULL AND end_offset IS NULL) OR (start_offset >= 0 AND end_offset > start_offset)",
            name="ck_concept_mentions_offsets",
        ),
        CheckConstraint(
            "offset_unit = 'unicode_codepoint'", name="ck_concept_mentions_offset_unit"
        ),
        CheckConstraint(
            "resolution IN ('explicit', 'resolved', 'candidate')",
            name="ck_concept_mentions_resolution",
        ),
        Index("ix_concept_mentions_concept", "concept_id"),
        Index("ix_concept_mentions_message", "message_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[str] = mapped_column(
        String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offset_unit: Mapped[str] = mapped_column(
        String, nullable=False, default="unicode_codepoint"
    )
    surface_text: Mapped[str] = mapped_column(String, nullable=False)
    resolution: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    extraction_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("extraction_runs.id", ondelete="SET NULL"), nullable=True
    )


class AnnotationModel(Base):
    __tablename__ = "annotations"
    __table_args__ = (
        CheckConstraint(
            "tag IN ('aha','confused','question','connection','hypothesis','revisit','important')",
            name="ck_annotations_tag",
        ),
        CheckConstraint(
            "offset_unit = 'unicode_codepoint'", name="ck_annotations_offset_unit"
        ),
        CheckConstraint("origin = 'user_explicit'", name="ck_annotations_origin"),
        CheckConstraint(
            "(start_offset IS NULL AND end_offset IS NULL) OR (start_offset >= 0 AND end_offset > start_offset)",
            name="ck_annotations_offsets",
        ),
        Index("ix_annotations_message", "message_id"),
        Index("ix_annotations_owner", "owner_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), nullable=False
    )
    message_id: Mapped[str] = mapped_column(
        String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    tag: Mapped[str] = mapped_column(String, nullable=False)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offset_unit: Mapped[str] = mapped_column(
        String, nullable=False, default="unicode_codepoint"
    )
    selected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin: Mapped[str] = mapped_column(String, nullable=False, default="user_explicit")
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    removed_at: Mapped[str | None] = mapped_column(String, nullable=True)


class WorldClaimModel(Base):
    __tablename__ = "world_claims"
    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('assistant_message', 'user_source', 'curated')",
            name="ck_world_claims_source_kind",
        ),
        CheckConstraint(
            "status IN ('provisional', 'supported', 'challenged', 'superseded')",
            name="ck_world_claims_status",
        ),
        CheckConstraint(
            "polarity IN ('affirmative', 'negative')",
            name="ck_world_claims_polarity",
        ),
        CheckConstraint(
            "confidence_hint IS NULL OR confidence_hint IN ('low', 'medium', 'high')",
            name="ck_world_claims_confidence_hint",
        ),
        Index("ix_world_claims_subject", "owner_user_id", "subject_concept_id"),
        Index("ix_world_claims_object", "owner_user_id", "object_concept_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), nullable=False
    )
    subject_concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    predicate: Mapped[str] = mapped_column(String, nullable=False)
    object_concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    polarity: Mapped[str] = mapped_column(
        String, nullable=False, default="affirmative"
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="provisional")
    source_kind: Mapped[str] = mapped_column(String, nullable=False)
    confidence_hint: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    valid_from: Mapped[str] = mapped_column(String, nullable=False)
    supersedes_claim_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("world_claims.id"), nullable=True
    )


class UserConceptStateModel(Base):
    __tablename__ = "user_concept_states"
    __table_args__ = (
        CheckConstraint(
            "self_assessment IN ('unknown','confused','uncertain','self_reports_understanding')",
            name="ck_user_concept_states_self_assessment",
        ),
        CheckConstraint(
            "demonstration_status IN ('none','some_evidence','repeated_evidence','contradictory_evidence')",
            name="ck_user_concept_states_demonstration",
        ),
    )

    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), primary_key=True
    )
    concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True
    )
    first_encountered_at: Mapped[str | None] = mapped_column(String, nullable=True)
    last_explored_at: Mapped[str | None] = mapped_column(String, nullable=True)
    self_assessment: Mapped[str] = mapped_column(
        String, nullable=False, default="unknown"
    )
    demonstration_status: Mapped[str] = mapped_column(
        String, nullable=False, default="none"
    )
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class KnowledgeSuggestionModel(Base):
    __tablename__ = "knowledge_suggestions"
    __table_args__ = (
        CheckConstraint(
            "suggestion_type IN ('connection')", name="ck_suggestions_type"
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'dismissed')",
            name="ck_suggestions_status",
        ),
        CheckConstraint(
            "confidence_hint IS NULL OR confidence_hint IN ('low', 'medium', 'high')",
            name="ck_suggestions_confidence",
        ),
        CheckConstraint(
            "subject_concept_id <> object_concept_id",
            name="ck_suggestions_distinct_concepts",
        ),
        Index(
            "ix_suggestions_owner_status",
            "owner_user_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), nullable=False
    )
    suggestion_type: Mapped[str] = mapped_column(
        String, nullable=False, default="connection"
    )
    subject_concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    predicate: Mapped[str] = mapped_column(String, nullable=False)
    object_concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_hint: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    extraction_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("extraction_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    resolved_at: Mapped[str | None] = mapped_column(String, nullable=True)


class UserRelationModel(Base):
    __tablename__ = "user_relations"
    __table_args__ = (
        CheckConstraint(
            "origin IN ('direct_user_assertion','accepted_suggestion','explicit_annotation')",
            name="ck_user_relations_origin",
        ),
        CheckConstraint(
            "subject_concept_id <> object_concept_id",
            name="ck_user_relations_distinct_concepts",
        ),
        Index("ix_user_relations_subject", "owner_user_id", "subject_concept_id"),
        Index("ix_user_relations_object", "owner_user_id", "object_concept_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), nullable=False
    )
    subject_concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    predicate: Mapped[str] = mapped_column(String, nullable=False)
    object_concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    origin: Mapped[str] = mapped_column(String, nullable=False)
    established_at: Mapped[str] = mapped_column(String, nullable=False)
    withdrawn_at: Mapped[str | None] = mapped_column(String, nullable=True)
    supersedes_relation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("user_relations.id"), nullable=True
    )
    source_suggestion_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("knowledge_suggestions.id", ondelete="SET NULL"), nullable=True
    )


class EvidenceModel(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "(message_id IS NOT NULL AND external_uri IS NULL) OR (message_id IS NULL AND external_uri IS NOT NULL)",
            name="ck_evidence_single_source_anchor",
        ),
        CheckConstraint(
            "source_role IN ('user', 'assistant', 'external')",
            name="ck_evidence_source_role",
        ),
        Index("ix_evidence_message", "message_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), nullable=False
    )
    message_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=True
    )
    annotation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("annotations.id", ondelete="SET NULL"), nullable=True
    )
    external_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    summary_model: Mapped[str | None] = mapped_column(String, nullable=True)
    summary_prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    summary_generated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_role: Mapped[str] = mapped_column(String, nullable=False)
    extraction_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("extraction_runs.id", ondelete="SET NULL"), nullable=True
    )
    captured_at: Mapped[str] = mapped_column(String, nullable=False)


class WorldClaimEvidenceModel(Base):
    __tablename__ = "world_claim_evidence"

    world_claim_id: Mapped[str] = mapped_column(
        String, ForeignKey("world_claims.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[str] = mapped_column(
        String, ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )


class UserStateEvidenceModel(Base):
    __tablename__ = "user_state_evidence"
    __table_args__ = (
        CheckConstraint(
            "signal_kind IN ('encounter','exploration','self_report','explanation','problem_solving','contradiction')",
            name="ck_user_state_evidence_signal",
        ),
        CheckConstraint(
            "origin IN ('explicit_annotation','user_statement','ai_inferred')",
            name="ck_user_state_evidence_origin",
        ),
        CheckConstraint(
            "review_status IN ('confirmed','candidate','dismissed')",
            name="ck_user_state_evidence_review",
        ),
    )

    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), primary_key=True
    )
    concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[str] = mapped_column(
        String, ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )
    signal_kind: Mapped[str] = mapped_column(String, nullable=False)
    origin: Mapped[str] = mapped_column(String, nullable=False)
    review_status: Mapped[str] = mapped_column(String, nullable=False)
    confidence_hint: Mapped[str | None] = mapped_column(String, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserRelationEvidenceModel(Base):
    __tablename__ = "user_relation_evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_role IN ('assertion','explanation','problem_solving','annotation')",
            name="ck_user_relation_evidence_role",
        ),
    )

    user_relation_id: Mapped[str] = mapped_column(
        String, ForeignKey("user_relations.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[str] = mapped_column(
        String, ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_role: Mapped[str] = mapped_column(String, nullable=False)


class SuggestionEvidenceModel(Base):
    __tablename__ = "suggestion_evidence"

    suggestion_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("knowledge_suggestions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    evidence_id: Mapped[str] = mapped_column(
        String, ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )


class UserHypothesisModel(Base):
    __tablename__ = "user_hypotheses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','supported','challenged','revised','withdrawn')",
            name="ck_user_hypotheses_status",
        ),
        CheckConstraint(
            "supersedes_hypothesis_id IS NULL OR supersedes_hypothesis_id <> id",
            name="ck_user_hypotheses_no_self_supersede",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), nullable=False
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    supersedes_hypothesis_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("user_hypotheses.id"), nullable=True
    )
    withdrawn_at: Mapped[str | None] = mapped_column(String, nullable=True)


class HypothesisEvidenceModel(Base):
    __tablename__ = "hypothesis_evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_role IN ('statement','support','challenge','revision')",
            name="ck_hypothesis_evidence_role",
        ),
    )

    hypothesis_id: Mapped[str] = mapped_column(
        String, ForeignKey("user_hypotheses.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[str] = mapped_column(
        String, ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_role: Mapped[str] = mapped_column(String, nullable=False)


class KnowledgeEventModel(Base):
    __tablename__ = "knowledge_events"
    __table_args__ = (
        Index("ix_knowledge_events_owner_time", "owner_user_id", "occurred_at"),
        Index("ix_knowledge_events_concept_time", "concept_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    occurred_at: Mapped[str] = mapped_column(String, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String, nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True
    )
    message_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=True
    )
    annotation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("annotations.id", ondelete="SET NULL"), nullable=True
    )
    concept_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=True
    )
    world_claim_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("world_claims.id", ondelete="CASCADE"), nullable=True
    )
    user_relation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("user_relations.id", ondelete="CASCADE"), nullable=True
    )
    suggestion_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("knowledge_suggestions.id", ondelete="CASCADE"),
        nullable=True,
    )
    hypothesis_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("user_hypotheses.id", ondelete="CASCADE"), nullable=True
    )
    extraction_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("extraction_runs.id", ondelete="SET NULL"), nullable=True
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class SearchDocumentModel(Base):
    __tablename__ = "search_documents"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('message_chunk', 'concept', 'hypothesis')",
            name="ck_search_documents_kind",
        ),
        CheckConstraint(
            "(CASE WHEN message_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN concept_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN hypothesis_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_search_documents_single_source",
        ),
        Index("ix_search_documents_owner_kind", "owner_user_id", "kind"),
        Index("ix_search_documents_message", "message_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_users.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    message_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=True
    )
    concept_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=True
    )
    hypothesis_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("user_hypotheses.id", ondelete="CASCADE"), nullable=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class DocumentEmbeddingModel(Base):
    __tablename__ = "document_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "provider",
            "model",
            "dimensions",
            name="uq_document_embeddings_doc_model",
        ),
        Index("ix_document_embeddings_doc", "document_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String, ForeignKey("search_documents.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

