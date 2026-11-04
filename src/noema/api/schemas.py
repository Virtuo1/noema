"""Pydantic DTOs for the /api/v1 HTTP boundary."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from noema.domain.vocabulary import (
    AnnotationTag,
    DemonstrationStatus,
    HypothesisStatus,
    ReviewStatus,
    SelfAssessment,
    SignalKind,
    SignalOrigin,
    SuggestionStatus,
    UserRelationOrigin,
    WorldClaimSourceKind,
    WorldClaimStatus,
)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class SpanDTO(BaseModel):
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    offset_unit: Literal["unicode_codepoint"] = "unicode_codepoint"


class CreateConversationRequest(BaseModel):
    title: str = ""


class UpdateConversationRequest(BaseModel):
    title: str | None = None
    archived: bool | None = None


class ConversationDTO(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    archived_at: str | None = None
    latest_turn_status: str | None = None
    extraction_status: str | None = None


class ConversationListResponse(BaseModel):
    items: list[ConversationDTO]
    next_cursor: str | None = None


class SourceReferenceDTO(BaseModel):
    source_id: str
    kind: Literal["message", "concept", "relation", "hypothesis"] = "message"
    message_id: str | None = None
    conversation_id: str | None = None
    concept_id: str | None = None
    role: str | None = None
    excerpt: str
    created_at: str | None = None
    reason: str | None = None


class AnnotationCreateRequest(BaseModel):
    tag: AnnotationTag
    span: SpanDTO | None = None


class AnnotationDTO(BaseModel):
    id: str
    message_id: str
    tag: AnnotationTag
    origin: Literal["user_explicit"] = "user_explicit"
    span: SpanDTO | None = None
    selected_text: str | None = None
    created_at: str
    affected_concept_ids: list[str] = Field(default_factory=list)
    ambiguous_concept_mapping: bool = False


class InferredAnnotationSignalDTO(BaseModel):
    evidence_id: str
    concept_id: str
    concept_name: str
    signal_kind: SignalKind
    origin: SignalOrigin
    review_status: ReviewStatus
    confidence_hint: str | None = None
    quote: str
    rationale: str | None = None


class MessageAnnotationsResponse(BaseModel):
    explicit: list[AnnotationDTO]
    inferred_candidates: list[InferredAnnotationSignalDTO]


class ConceptMentionBriefDTO(BaseModel):
    id: str
    concept_id: str
    canonical_name: str
    surface_text: str
    start_offset: int | None = None
    end_offset: int | None = None
    resolution: str


class MessageDTO(BaseModel):
    id: str
    conversation_id: str
    sequence_no: int
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: str
    reply_to_message_id: str | None = None
    provider: str | None = None
    model: str | None = None
    annotations: list[AnnotationDTO] = Field(default_factory=list)
    mentions: list[ConceptMentionBriefDTO] = Field(default_factory=list)
    sources: list[SourceReferenceDTO] = Field(default_factory=list)


class MessageListResponse(BaseModel):
    items: list[MessageDTO]
    next_cursor: str | None = None


class CreateTurnRequest(BaseModel):
    content: str = Field(min_length=1)
    context_mode: Literal["personalized", "conversation_only"] = "personalized"
    focus_concept_id: str | None = None
    client_message_id: str | None = None


class TurnAcceptedResponse(BaseModel):
    turn_id: str
    status: str
    user_message: MessageDTO
    assistant_message: MessageDTO | None = None
    assistant_message_id: str | None = None
    stream_url: str
    extraction_status: str = "queued"
    error_message: str | None = None
    applied_annotations: list[AnnotationDTO] = Field(default_factory=list)
    targeted_message_id: str | None = None


class TurnStatusResponse(BaseModel):
    turn_id: str
    conversation_id: str
    status: str
    user_message_id: str
    assistant_message_id: str | None = None
    provider: str
    model: str
    prompt_version: str
    error_code: str | None = None
    error_message: str | None = None
    sources: list[SourceReferenceDTO] = Field(default_factory=list)
    extraction_status: str = "queued"
    extraction_error_code: str | None = None
    created_at: str
    finished_at: str | None = None


class ConceptSignalsDTO(BaseModel):
    encountered: bool
    explored: bool
    first_encountered_at: str | None = None
    last_explored_at: str | None = None
    self_assessment: SelfAssessment = SelfAssessment.UNKNOWN
    demonstration_status: DemonstrationStatus = DemonstrationStatus.NONE


class GraphNodeDTO(BaseModel):
    id: str
    kind: Literal["concept"] = "concept"
    label: str
    description: str = ""
    category: str = "General"
    hierarchy_level: int = 2
    importance: float = 1.0
    tags: list[str] = Field(default_factory=list)
    top_quote: str = ""
    source_conversation_id: str | None = None
    source_conversation_title: str = ""
    signals: ConceptSignalsDTO
    mention_count: int = 0
    open_question_count: int = 0


class RelatedConversationDTO(BaseModel):
    id: str
    conversation_id: str = ""
    title: str
    updated_at: str
    shared_concepts: list[str] = Field(default_factory=list)
    snippet: str = ""
    score: float = 0.0


class RelatedConversationListResponse(BaseModel):
    items: list[RelatedConversationDTO] = Field(default_factory=list)


class GraphEdgeDTO(BaseModel):
    id: str
    source: str
    target: str
    predicate: str
    predicate_label: str
    layer: Literal["user_established", "world", "suggested"]
    status: str
    origin: str | None = None
    explanation: str = ""
    evidence_count: int = 0
    suggestion_id: str | None = None
    relation_id: str | None = None
    world_claim_id: str | None = None
    is_hierarchy: bool = False
    created_at: str | None = None


class GraphCountsDTO(BaseModel):
    nodes: int
    edges: int
    omitted_nodes: int = 0
    omitted_edges: int = 0


class GraphProjectionResponse(BaseModel):
    as_of: str
    focus_concept_id: str | None = None
    nodes: list[GraphNodeDTO]
    edges: list[GraphEdgeDTO]
    truncated: bool = False
    counts: GraphCountsDTO


class ConceptDetailDTO(BaseModel):
    id: str
    canonical_name: str
    normalized_name: str
    description: str
    aliases: list[str]
    signals: ConceptSignalsDTO
    mention_count: int
    user_relation_count: int
    world_claim_count: int
    pending_suggestion_count: int
    open_questions: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    merged_into_concept_id: str | None = None


class EvidenceItemDTO(BaseModel):
    id: str
    message_id: str | None = None
    conversation_id: str | None = None
    annotation_id: str | None = None
    annotation_tag: str | None = None
    quote: str
    summary: str | None = None
    summary_provider: str | None = None
    summary_model: str | None = None
    summary_prompt_version: str | None = None
    summary_generated_at: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    source_role: str
    captured_at: str
    extraction_provider: str | None = None
    extraction_model: str | None = None
    extraction_prompt_version: str | None = None


class WorldClaimDTO(BaseModel):
    id: str
    subject_concept_id: str
    subject_name: str
    predicate: str
    predicate_label: str
    object_concept_id: str
    object_name: str
    claim_text: str
    polarity: str
    status: WorldClaimStatus
    source_kind: WorldClaimSourceKind
    confidence_hint: str | None = None
    created_at: str
    evidence: list[EvidenceItemDTO] = Field(default_factory=list)


class UserRelationDTO(BaseModel):
    id: str
    subject_concept_id: str
    subject_name: str
    predicate: str
    predicate_label: str
    object_concept_id: str
    object_name: str
    explanation: str = ""
    origin: UserRelationOrigin
    established_at: str
    withdrawn_at: str | None = None
    source_suggestion_id: str | None = None
    evidence: list[EvidenceItemDTO] = Field(default_factory=list)


class SuggestionDTO(BaseModel):
    id: str
    suggestion_type: str
    subject_concept_id: str
    subject_name: str
    predicate: str
    predicate_label: str
    object_concept_id: str
    object_name: str
    explanation: str
    confidence_hint: str | None = None
    status: SuggestionStatus
    extraction_run_id: str | None = None
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    created_at: str
    resolved_at: str | None = None
    evidence: list[EvidenceItemDTO] = Field(default_factory=list)


class SuggestionListResponse(BaseModel):
    items: list[SuggestionDTO]
    next_cursor: str | None = None


class SuggestionAcceptRequest(BaseModel):
    predicate: str | None = None
    explanation: str | None = None


class SuggestionRejectRequest(BaseModel):
    reason: str | None = None


class CreateUserRelationRequest(BaseModel):
    target_concept_id: str
    predicate: str
    explanation: str = ""
    message_id: str | None = None


class MergeConceptRequest(BaseModel):
    target_concept_id: str


class ConceptEvidenceResponse(BaseModel):
    concept_id: str
    mentions: list[EvidenceItemDTO]
    saved_notes: list[EvidenceItemDTO] = Field(default_factory=list)
    annotations: list[AnnotationDTO]
    state_signals: list[InferredAnnotationSignalDTO]
    world_claims: list[WorldClaimDTO]
    user_relations: list[UserRelationDTO]
    suggestions: list[SuggestionDTO]


class RelatedConceptDTO(BaseModel):
    concept_id: str
    canonical_name: str
    predicate: str
    predicate_label: str
    direction: Literal["outgoing", "incoming"]
    layer: Literal["user_established", "world", "suggested"]
    status: str
    origin: str | None = None
    evidence_count: int = 0
    relation_id: str | None = None
    suggestion_id: str | None = None
    world_claim_id: str | None = None


class RelatedConceptListResponse(BaseModel):
    items: list[RelatedConceptDTO]


class KnowledgeEventDTO(BaseModel):
    id: str
    event_type: str
    payload_version: int
    occurred_at: str
    recorded_at: str
    conversation_id: str | None = None
    message_id: str | None = None
    annotation_id: str | None = None
    concept_id: str | None = None
    concept_name: str | None = None
    world_claim_id: str | None = None
    user_relation_id: str | None = None
    suggestion_id: str | None = None
    hypothesis_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class EventListResponse(BaseModel):
    items: list[KnowledgeEventDTO]
    next_cursor: str | None = None


class CreateHypothesisRequest(BaseModel):
    statement: str = Field(min_length=1)
    span: SpanDTO | None = None


class ReviseHypothesisRequest(BaseModel):
    statement: str = Field(min_length=1)
    message_id: str | None = None


class AttachHypothesisEvidenceRequest(BaseModel):
    message_id: str
    evidence_role: Literal["support", "challenge"]
    quote: str | None = None


class HypothesisDTO(BaseModel):
    id: str
    statement: str
    status: HypothesisStatus
    created_at: str
    updated_at: str
    supersedes_hypothesis_id: str | None = None
    withdrawn_at: str | None = None
    evidence: list[EvidenceItemDTO] = Field(default_factory=list)


class HypothesisListResponse(BaseModel):
    items: list[HypothesisDTO]
    next_cursor: str | None = None


class SearchResultDTO(BaseModel):
    document_id: str
    kind: Literal["message_chunk", "concept", "hypothesis"]
    excerpt: str
    score: float
    channels: list[str]
    message_id: str | None = None
    conversation_id: str | None = None
    concept_id: str | None = None
    hypothesis_id: str | None = None
    created_at: str | None = None


class SearchResponse(BaseModel):
    query: str
    items: list[SearchResultDTO]


class ProviderCapabilityDTO(BaseModel):
    provider: str
    display_name: str
    is_remote: bool
    supports_streaming: bool
    supports_structured_output: bool
    supports_embeddings: bool
    context_window: int
    has_configured_secret: bool
    masked_secret_hint: str | None = None
    recommended_chat_models: list[str] = Field(default_factory=list)
    recommended_small_models: list[str] = Field(default_factory=list)


class AISettingsDTO(BaseModel):
    conversation_provider: str
    conversation_model: str
    extraction_provider: str
    extraction_model: str
    embedding_provider: str
    embedding_model: str
    hosted_data_consent: bool
    local_endpoint_url: str
    context_budget_tokens: int
    remote_transfer_active: bool
    providers: list[ProviderCapabilityDTO]


class UpdateAISettingsRequest(BaseModel):
    conversation_provider: str | None = None
    conversation_model: str | None = None
    extraction_provider: str | None = None
    extraction_model: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    hosted_data_consent: bool | None = None
    local_endpoint_url: str | None = None
    context_budget_tokens: int | None = Field(default=None, ge=256, le=32000)
    api_keys: dict[str, str] | None = None


class ValidateAISettingsRequest(BaseModel):
    provider: str
    model: str | None = None
    local_endpoint_url: str | None = None
    api_key: str | None = None


class ValidateAISettingsResponse(BaseModel):
    valid: bool
    provider: str
    is_remote: bool
    message: str


class ExportResultResponse(BaseModel):
    export_id: str
    status: Literal["completed"]
    created_at: str
    file_path: str
    counts: dict[str, int]
    bundle: dict[str, Any]

