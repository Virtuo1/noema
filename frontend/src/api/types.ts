/** TypeScript contracts matching /api/v1 DTOs. */

export type AnnotationTag =
  | "aha"
  | "confused"
  | "question"
  | "connection"
  | "hypothesis"
  | "revisit"
  | "important";

export type SelfAssessment =
  "unknown" | "confused" | "uncertain" | "self_reports_understanding";

export type DemonstrationStatus =
  "none" | "some_evidence" | "repeated_evidence" | "contradictory_evidence";

export interface SpanDTO {
  start_offset: number;
  end_offset: number;
  offset_unit: "unicode_codepoint";
}

export interface ConversationDTO {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  latest_turn_status: string | null;
  extraction_status: string | null;
}

export interface RelatedConversationDTO {
  conversation_id: string;
  title: string;
  updated_at: string;
  shared_concepts: string[];
  score: number;
  snippet: string;
}

export interface SourceReferenceDTO {
  source_id: string;
  kind: "message" | "concept" | "relation" | "hypothesis";
  message_id: string | null;
  conversation_id: string | null;
  concept_id: string | null;
  role: string | null;
  excerpt: string;
  created_at: string | null;
  reason: string | null;
}

export interface AnnotationDTO {
  id: string;
  message_id: string;
  tag: AnnotationTag;
  origin: "user_explicit";
  span: SpanDTO | null;
  selected_text: string | null;
  created_at: string;
  affected_concept_ids: string[];
  ambiguous_concept_mapping: boolean;
}

export interface ConceptMentionBriefDTO {
  id: string;
  concept_id: string;
  canonical_name: str;
  surface_text: string;
  start_offset: number | null;
  end_offset: number | null;
  resolution: string;
}

type str = string;

export interface MessageDTO {
  id: string;
  conversation_id: string;
  sequence_no: number;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  reply_to_message_id: string | null;
  provider: string | null;
  model: string | null;
  annotations: AnnotationDTO[];
  mentions: ConceptMentionBriefDTO[];
  sources: SourceReferenceDTO[];
}

export interface TurnAcceptedResponse {
  turn_id: string;
  status: string;
  user_message: MessageDTO;
  assistant_message: MessageDTO | null;
  assistant_message_id: string | null;
  stream_url: string;
  extraction_status: string;
  error_message?: string | null;
  applied_annotations: AnnotationDTO[];
  targeted_message_id: string | null;
}

export interface TurnStatusResponse {
  turn_id: string;
  conversation_id: string;
  status: string;
  user_message_id: string;
  assistant_message_id: string | null;
  provider: string;
  model: string;
  prompt_version: string;
  error_code: string | null;
  error_message: string | null;
  sources: SourceReferenceDTO[];
  extraction_status: string;
  extraction_error_code: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface ConceptSignalsDTO {
  encountered: boolean;
  explored: boolean;
  first_encountered_at: string | null;
  last_explored_at: string | null;
  self_assessment: SelfAssessment;
  demonstration_status: DemonstrationStatus;
}

export interface GraphNodeDTO {
  id: string;
  kind: "concept";
  label: string;
  description: string;
  category?: string;
  hierarchy_level?: number;
  importance?: number;
  tags?: string[];
  top_quote?: string;
  source_conversation_id?: string | null;
  source_conversation_title?: string;
  signals: ConceptSignalsDTO;
  mention_count: number;
  open_question_count: number;
}

export interface GraphEdgeDTO {
  id: string;
  source: string;
  target: string;
  predicate: string;
  predicate_label: string;
  layer: "user_established" | "world" | "suggested";
  status: string;
  origin: string | null;
  explanation: string;
  evidence_count: number;
  suggestion_id: string | null;
  relation_id: string | null;
  world_claim_id: string | null;
  is_hierarchy: boolean;
  created_at: string | null;
}

export interface GraphProjectionResponse {
  as_of: string;
  focus_concept_id: string | null;
  nodes: GraphNodeDTO[];
  edges: GraphEdgeDTO[];
  truncated: boolean;
  counts: {
    nodes: number;
    edges: number;
    omitted_nodes: number;
    omitted_edges: number;
  };
}

export interface ConceptDetailDTO {
  id: string;
  canonical_name: string;
  normalized_name: string;
  description: string;
  aliases: string[];
  signals: ConceptSignalsDTO;
  mention_count: number;
  user_relation_count: number;
  world_claim_count: number;
  pending_suggestion_count: number;
  open_questions: string[];
  created_at: string;
  updated_at: string;
  merged_into_concept_id: string | null;
}

export interface EvidenceItemDTO {
  id: string;
  message_id: string | null;
  conversation_id: string | null;
  annotation_id: string | null;
  annotation_tag: string | null;
  quote: string;
  start_offset: number | null;
  end_offset: number | null;
  source_role: string;
  captured_at: string;
  extraction_provider: string | null;
  extraction_model: string | null;
  extraction_prompt_version: string | null;
}

export interface InferredAnnotationSignalDTO {
  evidence_id: string;
  concept_id: string;
  concept_name: string;
  signal_kind: string;
  origin: string;
  review_status: "confirmed" | "candidate" | "dismissed";
  confidence_hint: string | null;
  quote: string;
  rationale: string | null;
}

export interface WorldClaimDTO {
  id: string;
  subject_concept_id: string;
  subject_name: string;
  predicate: string;
  predicate_label: string;
  object_concept_id: string;
  object_name: string;
  claim_text: string;
  polarity: string;
  status: string;
  source_kind: string;
  confidence_hint: string | null;
  created_at: string;
  evidence: EvidenceItemDTO[];
}

export interface UserRelationDTO {
  id: string;
  subject_concept_id: string;
  subject_name: string;
  predicate: string;
  predicate_label: string;
  object_concept_id: string;
  object_name: string;
  explanation: string;
  origin: string;
  established_at: string;
  withdrawn_at: string | null;
  source_suggestion_id: string | null;
  evidence: EvidenceItemDTO[];
}

export interface SuggestionDTO {
  id: string;
  suggestion_type: string;
  subject_concept_id: string;
  subject_name: string;
  predicate: string;
  predicate_label: string;
  object_concept_id: string;
  object_name: string;
  explanation: string;
  confidence_hint: string | null;
  status: "pending" | "accepted" | "rejected" | "dismissed";
  extraction_run_id: string | null;
  provider: string | null;
  model: string | null;
  prompt_version: string | null;
  created_at: string;
  resolved_at: string | null;
  evidence: EvidenceItemDTO[];
}

export interface ConceptEvidenceResponse {
  concept_id: string;
  mentions: EvidenceItemDTO[];
  annotations: AnnotationDTO[];
  state_signals: InferredAnnotationSignalDTO[];
  world_claims: WorldClaimDTO[];
  user_relations: UserRelationDTO[];
  suggestions: SuggestionDTO[];
}

export interface KnowledgeEventDTO {
  id: string;
  event_type: string;
  payload_version: number;
  occurred_at: string;
  recorded_at: string;
  conversation_id: string | null;
  message_id: string | null;
  annotation_id: string | null;
  concept_id: string | null;
  concept_name: string | null;
  world_claim_id: string | null;
  user_relation_id: string | null;
  suggestion_id: string | null;
  hypothesis_id: string | null;
  payload: Record<string, unknown>;
}

export interface SearchResultDTO {
  document_id: string;
  kind: "message_chunk" | "concept" | "hypothesis";
  excerpt: string;
  score: number;
  channels: string[];
  message_id: string | null;
  conversation_id: string | null;
  concept_id: string | null;
  hypothesis_id: string | null;
  created_at: string | null;
}

export interface ProviderCapabilityDTO {
  provider: string;
  display_name: string;
  is_remote: boolean;
  supports_streaming: boolean;
  supports_structured_output: boolean;
  supports_embeddings: boolean;
  context_window: number;
  has_configured_secret: boolean;
  masked_secret_hint?: string | null;
  recommended_chat_models: string[];
  recommended_small_models: string[];
}

export interface AISettingsDTO {
  conversation_provider: string;
  conversation_model: string;
  extraction_provider: string;
  extraction_model: string;
  embedding_provider: string;
  embedding_model: string;
  hosted_data_consent: boolean;
  local_endpoint_url: string;
  context_budget_tokens: number;
  remote_transfer_active: boolean;
  providers: ProviderCapabilityDTO[];
}

export interface UpdateAISettingsPayload extends Partial<AISettingsDTO> {
  api_keys?: Record<string, string>;
}

export interface ExportResultResponse {
  export_id: string;
  status: "completed";
  created_at: string;
  file_path: string;
  counts: Record<string, number>;
  bundle: Record<string, unknown>;
}
