"""Provider configuration, privacy boundaries, and full workspace data export."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from noema.ai.gateway import (
    PROVIDER_CAPABILITIES,
    SecretStore,
    check_provider_connectivity,
    validate_local_endpoint_url,
)
from noema.api.schemas import (
    AISettingsDTO,
    ExportResultResponse,
    ProviderCapabilityDTO,
    UpdateAISettingsRequest,
    ValidateAISettingsRequest,
    ValidateAISettingsResponse,
)
from noema.config import DEFAULT_OWNER_USER_ID, get_settings
from noema.persistence.db import new_id, utc_now_iso
from noema.persistence.models import (
    AISettingsModel,
    AnnotationModel,
    ConceptAliasModel,
    ConceptMentionModel,
    ConceptModel,
    ConversationModel,
    EvidenceModel,
    KnowledgeEventModel,
    KnowledgeSuggestionModel,
    MessageModel,
    UserConceptStateModel,
    UserHypothesisModel,
    UserRelationModel,
    WorldClaimModel,
)


def get_ai_settings_dto(
    session: Session,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> AISettingsDTO:
    cfg = session.get(AISettingsModel, owner_user_id)
    if cfg is None:
        now = utc_now_iso()
        cfg = AISettingsModel(
            owner_user_id=owner_user_id,
            conversation_provider="local_heuristic",
            conversation_model="noema-local-chat-v1",
            extraction_provider="local_heuristic",
            extraction_model="noema-local-extractor-v1",
            embedding_provider="local_heuristic",
            embedding_model="noema-local-embed-v1",
            hosted_data_consent=0,
            local_endpoint_url="http://127.0.0.1:11434/v1",
            context_budget_tokens=1600,
            updated_at=now,
        )
        session.add(cfg)
        session.flush()

    secret_store = SecretStore()
    providers: list[ProviderCapabilityDTO] = []
    for cap in PROVIDER_CAPABILITIES.values():
        providers.append(
            ProviderCapabilityDTO(
                provider=cap.provider,
                display_name=cap.display_name,
                is_remote=cap.is_remote,
                supports_streaming=cap.supports_streaming,
                supports_structured_output=cap.supports_structured_output,
                supports_embeddings=cap.supports_embeddings,
                context_window=cap.context_window,
                has_configured_secret=(
                    secret_store.has_secret(cap.provider) if cap.is_remote else True
                ),
                masked_secret_hint=(
                    secret_store.get_masked_hint(cap.provider)
                    if cap.is_remote
                    else None
                ),
                recommended_chat_models=list(cap.recommended_chat_models),
                recommended_small_models=list(cap.recommended_small_models),
            )
        )

    active_providers = {
        cfg.conversation_provider,
        cfg.extraction_provider,
        cfg.embedding_provider,
    }
    remote_active = any(
        PROVIDER_CAPABILITIES.get(p) is not None
        and PROVIDER_CAPABILITIES[p].is_remote
        for p in active_providers
    )

    return AISettingsDTO(
        conversation_provider=cfg.conversation_provider,
        conversation_model=cfg.conversation_model,
        extraction_provider=cfg.extraction_provider,
        extraction_model=cfg.extraction_model,
        embedding_provider=cfg.embedding_provider,
        embedding_model=cfg.embedding_model,
        hosted_data_consent=bool(cfg.hosted_data_consent),
        local_endpoint_url=cfg.local_endpoint_url,
        context_budget_tokens=cfg.context_budget_tokens,
        remote_transfer_active=remote_active,
        providers=providers,
    )


def update_ai_settings_dto(
    session: Session,
    req: UpdateAISettingsRequest,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> AISettingsDTO:
    cfg = session.get(AISettingsModel, owner_user_id)
    if cfg is None:
        get_ai_settings_dto(session, owner_user_id=owner_user_id)
        cfg = session.get(AISettingsModel, owner_user_id)
        assert cfg is not None

    if req.local_endpoint_url is not None:
        if not validate_local_endpoint_url(req.local_endpoint_url):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_local_endpoint",
                    "message": "Local endpoint URL must point to a loopback address (127.0.0.1 or localhost).",
                    "details": {},
                },
            )
        cfg.local_endpoint_url = req.local_endpoint_url

    if req.api_keys:
        secret_store = SecretStore()
        for prov_name, key_val in req.api_keys.items():
            if prov_name in PROVIDER_CAPABILITIES:
                secret_store.set_secret(prov_name, key_val)

    if req.conversation_provider is not None:
        cfg.conversation_provider = req.conversation_provider
    if req.conversation_model is not None:
        cfg.conversation_model = req.conversation_model
    if req.extraction_provider is not None:
        cfg.extraction_provider = req.extraction_provider
    if req.extraction_model is not None:
        cfg.extraction_model = req.extraction_model
    if req.embedding_provider is not None:
        cfg.embedding_provider = req.embedding_provider
    if req.embedding_model is not None:
        cfg.embedding_model = req.embedding_model
    if req.hosted_data_consent is not None:
        cfg.hosted_data_consent = 1 if req.hosted_data_consent else 0
    if req.context_budget_tokens is not None:
        cfg.context_budget_tokens = req.context_budget_tokens

    cfg.updated_at = utc_now_iso()
    session.flush()
    return get_ai_settings_dto(session, owner_user_id=owner_user_id)


def validate_ai_settings_dto(
    req: ValidateAISettingsRequest,
) -> ValidateAISettingsResponse:
    cap = PROVIDER_CAPABILITIES.get(req.provider)
    is_remote = cap.is_remote if cap else False
    valid, msg = check_provider_connectivity(
        provider=req.provider,
        local_endpoint_url=req.local_endpoint_url or "http://127.0.0.1:11434/v1",
        api_key_override=req.api_key,
    )
    return ValidateAISettingsResponse(
        valid=valid,
        provider=req.provider,
        is_remote=is_remote,
        message=msg,
    )


def export_workspace_data(
    session: Session,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> ExportResultResponse:
    """Export all user-owned content and derived records with provenance in an open JSON format."""
    now = utc_now_iso()
    export_id = new_id("exp")

    conversations = [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "archived_at": c.archived_at,
        }
        for c in session.scalars(
            select(ConversationModel).where(
                ConversationModel.owner_user_id == owner_user_id
            )
        ).all()
    ]
    conv_ids = {c["id"] for c in conversations}

    messages = [
        {
            "id": m.id,
            "conversation_id": m.conversation_id,
            "sequence_no": m.sequence_no,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at,
            "reply_to_message_id": m.reply_to_message_id,
            "provider": m.provider,
            "model": m.model,
            "content_hash": m.content_hash,
            "sources": json.loads(m.sources_json or "[]"),
        }
        for m in session.scalars(
            select(MessageModel).where(MessageModel.conversation_id.in_(conv_ids))
        ).all()
    ] if conv_ids else []

    concepts = [
        {
            "id": c.id,
            "canonical_name": c.canonical_name,
            "normalized_name": c.normalized_name,
            "description": c.description,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "merged_into_concept_id": c.merged_into_concept_id,
            "archived_at": c.archived_at,
        }
        for c in session.scalars(
            select(ConceptModel).where(ConceptModel.owner_user_id == owner_user_id)
        ).all()
    ]
    concept_ids = {c["id"] for c in concepts}

    aliases = [
        {
            "id": a.id,
            "concept_id": a.concept_id,
            "alias": a.alias,
            "normalized_alias": a.normalized_alias,
            "origin": a.origin,
            "created_at": a.created_at,
        }
        for a in session.scalars(
            select(ConceptAliasModel).where(
                ConceptAliasModel.concept_id.in_(concept_ids)
            )
        ).all()
    ] if concept_ids else []

    mentions = [
        {
            "id": m.id,
            "concept_id": m.concept_id,
            "message_id": m.message_id,
            "start_offset": m.start_offset,
            "end_offset": m.end_offset,
            "offset_unit": m.offset_unit,
            "surface_text": m.surface_text,
            "resolution": m.resolution,
            "created_at": m.created_at,
            "extraction_run_id": m.extraction_run_id,
        }
        for m in session.scalars(
            select(ConceptMentionModel).where(
                ConceptMentionModel.concept_id.in_(concept_ids)
            )
        ).all()
    ] if concept_ids else []

    annotations = [
        {
            "id": a.id,
            "message_id": a.message_id,
            "tag": a.tag,
            "start_offset": a.start_offset,
            "end_offset": a.end_offset,
            "offset_unit": a.offset_unit,
            "selected_text": a.selected_text,
            "origin": a.origin,
            "created_at": a.created_at,
            "removed_at": a.removed_at,
        }
        for a in session.scalars(
            select(AnnotationModel).where(
                AnnotationModel.owner_user_id == owner_user_id
            )
        ).all()
    ]

    user_states = [
        {
            "concept_id": s.concept_id,
            "first_encountered_at": s.first_encountered_at,
            "last_explored_at": s.last_explored_at,
            "self_assessment": s.self_assessment,
            "demonstration_status": s.demonstration_status,
            "updated_at": s.updated_at,
        }
        for s in session.scalars(
            select(UserConceptStateModel).where(
                UserConceptStateModel.owner_user_id == owner_user_id
            )
        ).all()
    ]

    world_claims = [
        {
            "id": wc.id,
            "subject_concept_id": wc.subject_concept_id,
            "predicate": wc.predicate,
            "object_concept_id": wc.object_concept_id,
            "claim_text": wc.claim_text,
            "polarity": wc.polarity,
            "status": wc.status,
            "source_kind": wc.source_kind,
            "confidence_hint": wc.confidence_hint,
            "created_at": wc.created_at,
            "valid_from": wc.valid_from,
        }
        for wc in session.scalars(
            select(WorldClaimModel).where(
                WorldClaimModel.owner_user_id == owner_user_id
            )
        ).all()
    ]

    user_relations = [
        {
            "id": ur.id,
            "subject_concept_id": ur.subject_concept_id,
            "predicate": ur.predicate,
            "object_concept_id": ur.object_concept_id,
            "explanation": ur.explanation,
            "origin": ur.origin,
            "established_at": ur.established_at,
            "withdrawn_at": ur.withdrawn_at,
            "source_suggestion_id": ur.source_suggestion_id,
        }
        for ur in session.scalars(
            select(UserRelationModel).where(
                UserRelationModel.owner_user_id == owner_user_id
            )
        ).all()
    ]

    suggestions = [
        {
            "id": sg.id,
            "suggestion_type": sg.suggestion_type,
            "subject_concept_id": sg.subject_concept_id,
            "predicate": sg.predicate,
            "object_concept_id": sg.object_concept_id,
            "explanation": sg.explanation,
            "confidence_hint": sg.confidence_hint,
            "status": sg.status,
            "extraction_run_id": sg.extraction_run_id,
            "created_at": sg.created_at,
            "resolved_at": sg.resolved_at,
        }
        for sg in session.scalars(
            select(KnowledgeSuggestionModel).where(
                KnowledgeSuggestionModel.owner_user_id == owner_user_id
            )
        ).all()
    ]

    hypotheses = [
        {
            "id": h.id,
            "statement": h.statement,
            "status": h.status,
            "created_at": h.created_at,
            "updated_at": h.updated_at,
            "supersedes_hypothesis_id": h.supersedes_hypothesis_id,
            "withdrawn_at": h.withdrawn_at,
        }
        for h in session.scalars(
            select(UserHypothesisModel).where(
                UserHypothesisModel.owner_user_id == owner_user_id
            )
        ).all()
    ]

    evidence = [
        {
            "id": ev.id,
            "message_id": ev.message_id,
            "annotation_id": ev.annotation_id,
            "external_uri": ev.external_uri,
            "quote": ev.quote,
            "summary": ev.summary,
            "summary_provider": ev.summary_provider,
            "summary_model": ev.summary_model,
            "summary_prompt_version": ev.summary_prompt_version,
            "summary_generated_at": ev.summary_generated_at,
            "start_offset": ev.start_offset,
            "end_offset": ev.end_offset,
            "source_role": ev.source_role,
            "extraction_run_id": ev.extraction_run_id,
            "captured_at": ev.captured_at,
        }
        for ev in session.scalars(
            select(EvidenceModel).where(EvidenceModel.owner_user_id == owner_user_id)
        ).all()
    ]

    events = [
        {
            "id": ke.id,
            "event_type": ke.event_type,
            "payload_version": ke.payload_version,
            "occurred_at": ke.occurred_at,
            "recorded_at": ke.recorded_at,
            "conversation_id": ke.conversation_id,
            "message_id": ke.message_id,
            "annotation_id": ke.annotation_id,
            "concept_id": ke.concept_id,
            "world_claim_id": ke.world_claim_id,
            "user_relation_id": ke.user_relation_id,
            "suggestion_id": ke.suggestion_id,
            "hypothesis_id": ke.hypothesis_id,
            "extraction_run_id": ke.extraction_run_id,
            "payload": json.loads(ke.payload_json or "{}"),
        }
        for ke in session.scalars(
            select(KnowledgeEventModel)
            .where(KnowledgeEventModel.owner_user_id == owner_user_id)
            .order_by(KnowledgeEventModel.occurred_at.asc())
        ).all()
    ]

    bundle = {
        "schema_version": "noema-export-v1.0",
        "exported_at": now,
        "owner_user_id": owner_user_id,
        "conversations": conversations,
        "messages": messages,
        "concepts": concepts,
        "concept_aliases": aliases,
        "concept_mentions": mentions,
        "annotations": annotations,
        "user_concept_states": user_states,
        "world_claims": world_claims,
        "user_relations": user_relations,
        "knowledge_suggestions": suggestions,
        "user_hypotheses": hypotheses,
        "evidence": evidence,
        "knowledge_events": events,
    }
    counts = {
        key: len(val)
        for key, val in bundle.items()
        if isinstance(val, list)
    }

    export_dir = Path(get_settings().export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    file_path = export_dir / f"{export_id}.json"
    file_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    return ExportResultResponse(
        export_id=export_id,
        status="completed",
        created_at=now,
        file_path=str(file_path),
        counts=counts,
        bundle=bundle,
    )

