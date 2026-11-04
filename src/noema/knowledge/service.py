"""Knowledge domain service: concepts, annotations, claims, states, relations, suggestions, hypotheses, and graph projection."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from noema.ai.gateway import (
    PROMPT_VERSION_SAVED_NOTE_SUMMARY,
    ExtractionProposal,
    _find_catalog_mentions_in_message,
)
from noema.api.schemas import (
    AnnotationCreateRequest,
    AnnotationDTO,
    AttachHypothesisEvidenceRequest,
    ConceptDetailDTO,
    ConceptEvidenceResponse,
    ConceptSignalsDTO,
    CreateHypothesisRequest,
    CreateUserRelationRequest,
    EventListResponse,
    EvidenceItemDTO,
    GraphCountsDTO,
    GraphEdgeDTO,
    GraphNodeDTO,
    GraphProjectionResponse,
    HypothesisDTO,
    HypothesisListResponse,
    InferredAnnotationSignalDTO,
    KnowledgeEventDTO,
    MergeConceptRequest,
    MessageAnnotationsResponse,
    RelatedConceptDTO,
    RelatedConceptListResponse,
    ReviseHypothesisRequest,
    SpanDTO,
    SuggestionAcceptRequest,
    SuggestionDTO,
    SuggestionListResponse,
    SuggestionRejectRequest,
    UserRelationDTO,
    WorldClaimDTO,
)
from noema.config import DEFAULT_OWNER_USER_ID
from noema.domain.vocabulary import (
    PREDICATE_REGISTRY,
    AnnotationTag,
    DemonstrationStatus,
    HypothesisStatus,
    KnowledgeEventType,
    ReviewStatus,
    SelfAssessment,
    SignalKind,
    SignalOrigin,
    SuggestionStatus,
    UserRelationOrigin,
    WorldClaimSourceKind,
    WorldClaimStatus,
    normalize_concept_name,
)
from noema.persistence.db import new_id, utc_now_iso
from noema.persistence.models import (
    AnnotationModel,
    BackgroundJobModel,
    ConceptAliasModel,
    ConceptMentionModel,
    ConceptModel,
    ConversationModel,
    EvidenceModel,
    ExtractionRunModel,
    HypothesisEvidenceModel,
    KnowledgeEventModel,
    KnowledgeSuggestionModel,
    MessageModel,
    SuggestionEvidenceModel,
    UserConceptStateModel,
    UserHypothesisModel,
    UserRelationEvidenceModel,
    UserRelationModel,
    UserStateEvidenceModel,
    WorldClaimEvidenceModel,
    WorldClaimModel,
)
from noema.retrieval.service import index_concept_document, index_hypothesis_document


def _predicate_label(predicate: str) -> str:
    meta = PREDICATE_REGISTRY.get(predicate)
    return meta.label if meta else predicate.replace("_", " ")


def _is_hierarchy(predicate: str) -> bool:
    meta = PREDICATE_REGISTRY.get(predicate)
    return meta.is_hierarchy if meta else False


def _record_event(
    session: Session,
    *,
    event_type: KnowledgeEventType | str,
    payload: dict[str, Any],
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
    occurred_at: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    annotation_id: str | None = None,
    concept_id: str | None = None,
    world_claim_id: str | None = None,
    user_relation_id: str | None = None,
    suggestion_id: str | None = None,
    hypothesis_id: str | None = None,
    extraction_run_id: str | None = None,
) -> KnowledgeEventModel:
    now = utc_now_iso()
    ev = KnowledgeEventModel(
        id=new_id("ev"),
        owner_user_id=owner_user_id,
        event_type=str(event_type),
        payload_version=1,
        occurred_at=occurred_at or now,
        recorded_at=now,
        conversation_id=conversation_id,
        message_id=message_id,
        annotation_id=annotation_id,
        concept_id=concept_id,
        world_claim_id=world_claim_id,
        user_relation_id=user_relation_id,
        suggestion_id=suggestion_id,
        hypothesis_id=hypothesis_id,
        extraction_run_id=extraction_run_id,
        payload_json=json.dumps(payload),
    )
    session.add(ev)
    return ev


def resolve_or_create_concept(
    session: Session,
    *,
    canonical_name: str,
    description: str = "",
    origin: str = "extractor",
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
    conversation_id: str | None = None,
    message_id: str | None = None,
    extraction_run_id: str | None = None,
) -> ConceptModel:
    norm = normalize_concept_name(canonical_name)
    if not norm:
        raise ValueError("Concept name cannot be empty.")

    existing = session.scalar(
        select(ConceptModel).where(
            ConceptModel.owner_user_id == owner_user_id,
            ConceptModel.normalized_name == norm,
        )
    )
    if existing is not None:
        while existing.merged_into_concept_id is not None:
            target = session.get(ConceptModel, existing.merged_into_concept_id)
            if target is None or target.id == existing.id:
                break
            existing = target
        if description and not existing.description:
            existing.description = description
            existing.updated_at = utc_now_iso()
        return existing

    alias_row = session.scalar(
        select(ConceptAliasModel).where(ConceptAliasModel.normalized_alias == norm)
    )
    if alias_row is not None:
        concept = session.get(ConceptModel, alias_row.concept_id)
        if concept is not None and concept.owner_user_id == owner_user_id:
            while concept.merged_into_concept_id is not None:
                target = session.get(ConceptModel, concept.merged_into_concept_id)
                if target is None or target.id == concept.id:
                    break
                concept = target
            return concept

    now = utc_now_iso()
    concept = ConceptModel(
        id=new_id("c"),
        owner_user_id=owner_user_id,
        canonical_name=canonical_name.strip(),
        normalized_name=norm,
        description=description.strip(),
        created_at=now,
        updated_at=now,
    )
    session.add(concept)
    session.flush()

    state = UserConceptStateModel(
        owner_user_id=owner_user_id,
        concept_id=concept.id,
        first_encountered_at=now,
        last_explored_at=None,
        self_assessment=SelfAssessment.UNKNOWN.value,
        demonstration_status=DemonstrationStatus.NONE.value,
        updated_at=now,
    )
    session.add(state)
    session.add(
        ConceptAliasModel(
            id=new_id("alias"),
            concept_id=concept.id,
            alias=concept.canonical_name,
            normalized_alias=norm,
            origin=origin if origin in ("user", "extractor", "import") else "extractor",
            created_at=now,
        )
    )
    session.flush()

    _record_event(
        session,
        event_type=KnowledgeEventType.CONCEPT_ENCOUNTERED,
        payload={
            "canonical_name": concept.canonical_name,
            "actor": origin,
        },
        owner_user_id=owner_user_id,
        occurred_at=now,
        conversation_id=conversation_id,
        message_id=message_id,
        concept_id=concept.id,
        extraction_run_id=extraction_run_id,
    )
    index_concept_document(session, concept, aliases=[concept.canonical_name], owner_user_id=owner_user_id)
    return concept


def _ensure_concept_state(
    session: Session,
    concept_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> UserConceptStateModel:
    state = session.get(UserConceptStateModel, (owner_user_id, concept_id))
    if state is None:
        now = utc_now_iso()
        state = UserConceptStateModel(
            owner_user_id=owner_user_id,
            concept_id=concept_id,
            first_encountered_at=now,
            last_explored_at=None,
            self_assessment=SelfAssessment.UNKNOWN.value,
            demonstration_status=DemonstrationStatus.NONE.value,
            updated_at=now,
        )
        session.add(state)
        session.flush()
    return state


def _resolve_concepts_for_annotation(
    session: Session,
    message: MessageModel,
    span: SpanDTO | None,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> tuple[list[ConceptModel], bool]:
    """Find concepts anchored in the message/span; also inspect nearby conversation messages if none extracted yet."""
    mentions = session.scalars(
        select(ConceptMentionModel).where(ConceptMentionModel.message_id == message.id)
    ).all()

    matched_ids: list[str] = []
    if mentions:
        for m in mentions:
            if span is not None and m.start_offset is not None and m.end_offset is not None:
                if m.end_offset <= span.start_offset or m.start_offset >= span.end_offset:
                    continue
            if m.concept_id not in matched_ids:
                matched_ids.append(m.concept_id)

    existing_rows = session.scalars(
        select(ConceptModel).where(
            ConceptModel.owner_user_id == owner_user_id,
            ConceptModel.merged_into_concept_id.is_(None),
        )
    ).all()
    existing_map = {
        c.normalized_name: (c.canonical_name, c.description) for c in existing_rows
    }

    if not matched_ids:
        # Also check deterministic catalog mentions immediately so explicit #aha works before background worker finishes
        target_text = (
            message.content[span.start_offset : span.end_offset]
            if span is not None
            else message.content
        )
        instant_candidates = _find_catalog_mentions_in_message(
            message.id, target_text, existing_map
        )
        for cand in instant_candidates:
            c_obj = resolve_or_create_concept(
                session,
                canonical_name=cand.canonical_name,
                description=cand.description,
                origin="user",
                owner_user_id=owner_user_id,
                conversation_id=message.conversation_id,
                message_id=message.id,
            )
            if c_obj.id not in matched_ids:
                matched_ids.append(c_obj.id)

    # When annotating a reply message (e.g. "I think I get it: the chain rule lets the error signal flow backward... #aha"),
    # also include concepts from the immediately preceding message in the turn pair.
    if message.sequence_no > 1:
        prev_msg = session.scalar(
            select(MessageModel).where(
                MessageModel.conversation_id == message.conversation_id,
                MessageModel.sequence_no == message.sequence_no - 1,
            )
        )
        if prev_msg is not None:
            prev_mentions = session.scalars(
                select(ConceptMentionModel).where(
                    ConceptMentionModel.message_id == prev_msg.id
                )
            ).all()
            for pm in prev_mentions:
                if pm.concept_id not in matched_ids:
                    matched_ids.append(pm.concept_id)
            if not prev_mentions:
                for cand in _find_catalog_mentions_in_message(
                    prev_msg.id, prev_msg.content, existing_map
                ):
                    c_obj = resolve_or_create_concept(
                        session,
                        canonical_name=cand.canonical_name,
                        description=cand.description,
                        origin="extractor",
                        owner_user_id=owner_user_id,
                        conversation_id=message.conversation_id,
                        message_id=prev_msg.id,
                    )
                    if c_obj.id not in matched_ids:
                        matched_ids.append(c_obj.id)

    concepts = [
        c
        for cid in matched_ids
        if (c := session.get(ConceptModel, cid)) is not None
    ]
    ambiguous = len(concepts) > 5 and span is None
    return concepts, ambiguous


def apply_annotation_to_concept_states(
    session: Session,
    annotation: AnnotationModel,
    message: MessageModel,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> tuple[list[str], bool]:
    span_dto = (
        SpanDTO(
            start_offset=annotation.start_offset,
            end_offset=annotation.end_offset,
        )
        if annotation.start_offset is not None and annotation.end_offset is not None
        else None
    )
    concepts, ambiguous = _resolve_concepts_for_annotation(
        session, message, span_dto, owner_user_id=owner_user_id
    )
    now = utc_now_iso()
    quote = annotation.selected_text or message.content

    ev_row = EvidenceModel(
        id=new_id("evd"),
        owner_user_id=owner_user_id,
        message_id=message.id,
        annotation_id=annotation.id,
        external_uri=None,
        quote=quote[:400],
        start_offset=annotation.start_offset,
        end_offset=annotation.end_offset,
        source_role="user" if message.role == "user" else "assistant",
        extraction_run_id=None,
        captured_at=now,
    )
    session.add(ev_row)
    session.flush()

    target_assessment: SelfAssessment | None = None
    if annotation.tag == AnnotationTag.AHA.value:
        target_assessment = SelfAssessment.SELF_REPORTS_UNDERSTANDING
    elif annotation.tag == AnnotationTag.CONFUSED.value:
        target_assessment = SelfAssessment.CONFUSED
    elif annotation.tag == AnnotationTag.QUESTION.value:
        target_assessment = SelfAssessment.UNCERTAIN

    affected_ids: list[str] = []
    if not ambiguous:
        for concept in concepts:
            affected_ids.append(concept.id)
            state = _ensure_concept_state(session, concept.id, owner_user_id)
            state.last_explored_at = now
            state.updated_at = now

            signal_kind = (
                SignalKind.SELF_REPORT
                if target_assessment is not None
                else SignalKind.EXPLORATION
            )
            existing_se = session.get(
                UserStateEvidenceModel, (owner_user_id, concept.id, ev_row.id)
            )
            if existing_se is None:
                session.add(
                    UserStateEvidenceModel(
                        owner_user_id=owner_user_id,
                        concept_id=concept.id,
                        evidence_id=ev_row.id,
                        signal_kind=signal_kind.value,
                        origin=SignalOrigin.EXPLICIT_ANNOTATION.value,
                        review_status=ReviewStatus.CONFIRMED.value,
                        confidence_hint=None,
                        rationale=f"Explicit #{annotation.tag} annotation by user",
                    )
                )

            if target_assessment is not None and state.self_assessment != target_assessment.value:
                before_val = state.self_assessment
                state.self_assessment = target_assessment.value
                _record_event(
                    session,
                    event_type=KnowledgeEventType.SELF_ASSESSMENT_CHANGED,
                    payload={
                        "before": before_val,
                        "after": target_assessment.value,
                        "basis": "explicit_annotation",
                        "tag": annotation.tag,
                        "actor": "user",
                    },
                    owner_user_id=owner_user_id,
                    occurred_at=now,
                    conversation_id=message.conversation_id,
                    message_id=message.id,
                    annotation_id=annotation.id,
                    concept_id=concept.id,
                )

    return affected_ids, ambiguous


def add_annotation(
    session: Session,
    *,
    message_id: str,
    req: AnnotationCreateRequest,
    idempotency_key: str | None = None,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> AnnotationDTO:
    message = session.get(MessageModel, message_id)
    if message is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "message_not_found",
                "message": f"Message '{message_id}' not found.",
                "details": {},
            },
        )

    if idempotency_key:
        existing = session.scalar(
            select(AnnotationModel).where(
                AnnotationModel.owner_user_id == owner_user_id,
                AnnotationModel.idempotency_key == idempotency_key,
                AnnotationModel.removed_at.is_(None),
            )
        )
        if existing is not None:
            return _to_annotation_dto(session, existing)

    start_offset: int | None = None
    end_offset: int | None = None
    selected_text: str | None = None

    if req.span is not None:
        if req.span.start_offset < 0 or req.span.end_offset > len(message.content) or req.span.start_offset >= req.span.end_offset:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_span",
                    "message": "Annotation span offsets are out of bounds for message content.",
                    "details": {"message_length": len(message.content)},
                },
            )
        start_offset = req.span.start_offset
        end_offset = req.span.end_offset
        selected_text = message.content[start_offset:end_offset]
    else:
        selected_text = message.content

    now = utc_now_iso()
    ann = AnnotationModel(
        id=new_id("ann"),
        owner_user_id=owner_user_id,
        message_id=message.id,
        tag=req.tag.value,
        start_offset=start_offset,
        end_offset=end_offset,
        offset_unit="unicode_codepoint",
        selected_text=selected_text,
        origin="user_explicit",
        idempotency_key=idempotency_key,
        created_at=now,
        removed_at=None,
    )
    session.add(ann)
    session.flush()

    affected_ids, ambiguous = apply_annotation_to_concept_states(
        session, ann, message, owner_user_id=owner_user_id
    )

    saved_evidence = session.scalar(
        select(EvidenceModel).where(EvidenceModel.annotation_id == ann.id)
    )
    if saved_evidence is not None:
        summary_key = (
            f"saved-note-summary:{saved_evidence.id}:{PROMPT_VERSION_SAVED_NOTE_SUMMARY}"
        )
        existing_job = session.scalar(
            select(BackgroundJobModel).where(
                BackgroundJobModel.idempotency_key == summary_key
            )
        )
        if existing_job is None:
            session.add(
                BackgroundJobModel(
                    id=new_id("job"),
                    owner_user_id=owner_user_id,
                    job_kind="knowledge_extraction",
                    source_generation_run_id=None,
                    payload_json=json.dumps(
                        {
                            "operation": "saved_note_summary",
                            "evidence_id": saved_evidence.id,
                        }
                    ),
                    status="queued",
                    idempotency_key=summary_key,
                    attempt_count=0,
                    lease_owner=None,
                    lease_expires_at=None,
                    available_at=now,
                    error_code=None,
                    created_at=now,
                    updated_at=now,
                    finished_at=None,
                )
            )

    _record_event(
        session,
        event_type=KnowledgeEventType.ANNOTATION_ADDED,
        payload={
            "tag": ann.tag,
            "actor": "user",
            "affected_concept_ids": affected_ids,
            "ambiguous_concept_mapping": ambiguous,
        },
        owner_user_id=owner_user_id,
        occurred_at=now,
        conversation_id=message.conversation_id,
        message_id=message.id,
        annotation_id=ann.id,
        concept_id=affected_ids[0] if len(affected_ids) == 1 else None,
    )

    if req.tag == AnnotationTag.HYPOTHESIS and selected_text:
        create_hypothesis(
            session,
            message_id=message.id,
            req=CreateHypothesisRequest(
                statement=selected_text,
                span=req.span,
            ),
            owner_user_id=owner_user_id,
        )

    session.flush()
    return AnnotationDTO(
        id=ann.id,
        message_id=ann.message_id,
        tag=AnnotationTag(ann.tag),
        origin="user_explicit",
        span=req.span,
        selected_text=ann.selected_text,
        created_at=ann.created_at,
        affected_concept_ids=affected_ids,
        ambiguous_concept_mapping=ambiguous,
    )


def _to_annotation_dto(session: Session, ann: AnnotationModel) -> AnnotationDTO:
    ev_rows = session.scalars(
        select(EvidenceModel).where(EvidenceModel.annotation_id == ann.id)
    ).all()
    affected_ids: list[str] = []
    for ev in ev_rows:
        se_rows = session.scalars(
            select(UserStateEvidenceModel).where(
                UserStateEvidenceModel.evidence_id == ev.id
            )
        ).all()
        for se in se_rows:
            if se.concept_id not in affected_ids:
                affected_ids.append(se.concept_id)

    span = (
        SpanDTO(start_offset=ann.start_offset, end_offset=ann.end_offset)
        if ann.start_offset is not None and ann.end_offset is not None
        else None
    )
    return AnnotationDTO(
        id=ann.id,
        message_id=ann.message_id,
        tag=AnnotationTag(ann.tag),
        origin="user_explicit",
        span=span,
        selected_text=ann.selected_text,
        created_at=ann.created_at,
        affected_concept_ids=affected_ids,
        ambiguous_concept_mapping=False,
    )


def list_message_annotations(
    session: Session,
    message_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> MessageAnnotationsResponse:
    message = session.get(MessageModel, message_id)
    if message is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "message_not_found",
                "message": f"Message '{message_id}' not found.",
                "details": {},
            },
        )
    explicit_rows = session.scalars(
        select(AnnotationModel)
        .where(
            AnnotationModel.message_id == message_id,
            AnnotationModel.owner_user_id == owner_user_id,
            AnnotationModel.removed_at.is_(None),
        )
        .order_by(AnnotationModel.created_at.asc())
    ).all()
    explicit_dtos = [_to_annotation_dto(session, row) for row in explicit_rows]

    inferred_dtos: list[InferredAnnotationSignalDTO] = []
    ev_rows = session.scalars(
        select(EvidenceModel).where(EvidenceModel.message_id == message_id)
    ).all()
    for ev in ev_rows:
        se_rows = session.scalars(
            select(UserStateEvidenceModel).where(
                UserStateEvidenceModel.evidence_id == ev.id,
                UserStateEvidenceModel.origin == SignalOrigin.AI_INFERRED.value,
            )
        ).all()
        for se in se_rows:
            concept = session.get(ConceptModel, se.concept_id)
            if concept is None:
                continue
            inferred_dtos.append(
                InferredAnnotationSignalDTO(
                    evidence_id=ev.id,
                    concept_id=concept.id,
                    concept_name=concept.canonical_name,
                    signal_kind=SignalKind(se.signal_kind),
                    origin=SignalOrigin(se.origin),
                    review_status=ReviewStatus(se.review_status),
                    confidence_hint=se.confidence_hint,
                    quote=ev.quote,
                    rationale=se.rationale,
                )
            )

    return MessageAnnotationsResponse(
        explicit=explicit_dtos,
        inferred_candidates=inferred_dtos,
    )


def remove_annotation(
    session: Session,
    annotation_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> None:
    ann = session.get(AnnotationModel, annotation_id)
    if ann is None or ann.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "annotation_not_found",
                "message": f"Annotation '{annotation_id}' not found.",
                "details": {},
            },
        )
    if ann.removed_at is not None:
        return

    now = utc_now_iso()
    ann.removed_at = now
    msg = session.get(MessageModel, ann.message_id)

    # Recompute self_assessment if this annotation had set it
    ev_rows = session.scalars(
        select(EvidenceModel).where(EvidenceModel.annotation_id == ann.id)
    ).all()
    affected_concepts: list[str] = []
    for ev in ev_rows:
        se_rows = session.scalars(
            select(UserStateEvidenceModel).where(
                UserStateEvidenceModel.evidence_id == ev.id
            )
        ).all()
        for se in se_rows:
            affected_concepts.append(se.concept_id)
            se.review_status = ReviewStatus.DISMISSED.value

    for cid in set(affected_concepts):
        state = session.get(UserConceptStateModel, (owner_user_id, cid))
        if state is not None and ann.tag in (
            AnnotationTag.AHA.value,
            AnnotationTag.CONFUSED.value,
            AnnotationTag.QUESTION.value,
        ):
            before_val = state.self_assessment
            # Check if another active explicit annotation exists for this concept
            other_active = session.scalars(
                select(AnnotationModel)
                .join(EvidenceModel, EvidenceModel.annotation_id == AnnotationModel.id)
                .join(
                    UserStateEvidenceModel,
                    UserStateEvidenceModel.evidence_id == EvidenceModel.id,
                )
                .where(
                    UserStateEvidenceModel.concept_id == cid,
                    AnnotationModel.removed_at.is_(None),
                    AnnotationModel.id != ann.id,
                )
                .order_by(AnnotationModel.created_at.desc())
            ).first()
            if other_active is not None:
                if other_active.tag == AnnotationTag.AHA.value:
                    state.self_assessment = SelfAssessment.SELF_REPORTS_UNDERSTANDING.value
                elif other_active.tag == AnnotationTag.CONFUSED.value:
                    state.self_assessment = SelfAssessment.CONFUSED.value
                elif other_active.tag == AnnotationTag.QUESTION.value:
                    state.self_assessment = SelfAssessment.UNCERTAIN.value
            else:
                state.self_assessment = SelfAssessment.UNKNOWN.value
            state.updated_at = now
            if before_val != state.self_assessment:
                _record_event(
                    session,
                    event_type=KnowledgeEventType.SELF_ASSESSMENT_CHANGED,
                    payload={
                        "before": before_val,
                        "after": state.self_assessment,
                        "basis": "annotation_removed",
                        "actor": "user",
                    },
                    owner_user_id=owner_user_id,
                    occurred_at=now,
                    conversation_id=msg.conversation_id if msg else None,
                    message_id=ann.message_id,
                    annotation_id=ann.id,
                    concept_id=cid,
                )

    _record_event(
        session,
        event_type=KnowledgeEventType.ANNOTATION_REMOVED,
        payload={"tag": ann.tag, "actor": "user"},
        owner_user_id=owner_user_id,
        occurred_at=now,
        conversation_id=msg.conversation_id if msg else None,
        message_id=ann.message_id,
        annotation_id=ann.id,
    )


def apply_extraction_proposal(
    session: Session,
    *,
    proposal: ExtractionProposal,
    extraction_run: ExtractionRunModel,
    conversation_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> None:
    """Validate and persist an extraction proposal atomically without conflating epistemic layers."""
    now = utc_now_iso()
    concept_by_name: dict[str, ConceptModel] = {}

    # 1. Mentions & concepts
    for m_cand in proposal.mentions:
        msg = session.get(MessageModel, m_cand.message_id)
        if msg is None or msg.conversation_id != conversation_id:
            continue
        if m_cand.start_offset < 0 or m_cand.end_offset > len(msg.content) or m_cand.start_offset >= m_cand.end_offset:
            continue

        concept = resolve_or_create_concept(
            session,
            canonical_name=m_cand.canonical_name,
            description=m_cand.description,
            origin="extractor",
            owner_user_id=owner_user_id,
            conversation_id=conversation_id,
            message_id=msg.id,
            extraction_run_id=extraction_run.id,
        )
        concept_by_name[normalize_concept_name(concept.canonical_name)] = concept

        # Deduplicate exact mention span
        existing_mention = session.scalar(
            select(ConceptMentionModel).where(
                ConceptMentionModel.concept_id == concept.id,
                ConceptMentionModel.message_id == msg.id,
                ConceptMentionModel.start_offset == m_cand.start_offset,
                ConceptMentionModel.end_offset == m_cand.end_offset,
            )
        )
        if existing_mention is None:
            session.add(
                ConceptMentionModel(
                    id=new_id("mn"),
                    concept_id=concept.id,
                    message_id=msg.id,
                    start_offset=m_cand.start_offset,
                    end_offset=m_cand.end_offset,
                    offset_unit="unicode_codepoint",
                    surface_text=m_cand.surface_text,
                    resolution=m_cand.resolution,
                    created_at=now,
                    extraction_run_id=extraction_run.id,
                )
            )

        ev = EvidenceModel(
            id=new_id("evd"),
            owner_user_id=owner_user_id,
            message_id=msg.id,
            annotation_id=None,
            external_uri=None,
            quote=msg.content[:320],
            start_offset=m_cand.start_offset,
            end_offset=m_cand.end_offset,
            source_role="user" if msg.role == "user" else "assistant",
            extraction_run_id=extraction_run.id,
            captured_at=now,
        )
        session.add(ev)
        session.flush()

        state = _ensure_concept_state(session, concept.id, owner_user_id)
        if state.first_encountered_at is None:
            state.first_encountered_at = now
        if msg.role == "user":
            state.last_explored_at = now
            state.updated_at = now
            session.add(
                UserStateEvidenceModel(
                    owner_user_id=owner_user_id,
                    concept_id=concept.id,
                    evidence_id=ev.id,
                    signal_kind=SignalKind.EXPLORATION.value,
                    origin=SignalOrigin.USER_STATEMENT.value,
                    review_status=ReviewStatus.CONFIRMED.value,
                    confidence_hint=None,
                    rationale="User actively discussed concept in conversation.",
                )
            )
            _record_event(
                session,
                event_type=KnowledgeEventType.CONCEPT_EXPLORED,
                payload={"canonical_name": concept.canonical_name, "actor": "user"},
                owner_user_id=owner_user_id,
                occurred_at=now,
                conversation_id=conversation_id,
                message_id=msg.id,
                concept_id=concept.id,
                extraction_run_id=extraction_run.id,
            )
        else:
            session.add(
                UserStateEvidenceModel(
                    owner_user_id=owner_user_id,
                    concept_id=concept.id,
                    evidence_id=ev.id,
                    signal_kind=SignalKind.ENCOUNTER.value,
                    origin=SignalOrigin.AI_INFERRED.value,
                    review_status=ReviewStatus.CONFIRMED.value,
                    confidence_hint=None,
                    rationale="Concept mentioned in assistant explanation.",
                )
            )

    # 2. World claims (sourced, provisional — never treated as user relations)
    for wc_cand in proposal.world_claims:
        msg = session.get(MessageModel, wc_cand.message_id)
        if msg is None or msg.conversation_id != conversation_id:
            continue
        subj = resolve_or_create_concept(
            session,
            canonical_name=wc_cand.subject_name,
            origin="extractor",
            owner_user_id=owner_user_id,
            conversation_id=conversation_id,
            message_id=msg.id,
            extraction_run_id=extraction_run.id,
        )
        obj = resolve_or_create_concept(
            session,
            canonical_name=wc_cand.object_name,
            origin="extractor",
            owner_user_id=owner_user_id,
            conversation_id=conversation_id,
            message_id=msg.id,
            extraction_run_id=extraction_run.id,
        )
        if subj.id == obj.id:
            continue

        existing_wc = session.scalar(
            select(WorldClaimModel).where(
                WorldClaimModel.owner_user_id == owner_user_id,
                WorldClaimModel.subject_concept_id == subj.id,
                WorldClaimModel.predicate == wc_cand.predicate,
                WorldClaimModel.object_concept_id == obj.id,
            )
        )
        if existing_wc is None:
            wc = WorldClaimModel(
                id=new_id("wc"),
                owner_user_id=owner_user_id,
                subject_concept_id=subj.id,
                predicate=wc_cand.predicate,
                object_concept_id=obj.id,
                claim_text=wc_cand.claim_text,
                polarity="affirmative",
                status=WorldClaimStatus.PROVISIONAL.value,
                source_kind=WorldClaimSourceKind.ASSISTANT_MESSAGE.value,
                confidence_hint=wc_cand.confidence_hint,
                created_at=now,
                valid_from=now,
            )
            session.add(wc)
            session.flush()
            _record_event(
                session,
                event_type=KnowledgeEventType.WORLD_CLAIM_RECORDED,
                payload={
                    "subject_id": subj.id,
                    "predicate": wc.predicate,
                    "object_id": obj.id,
                    "status": wc.status,
                    "source_kind": wc.source_kind,
                },
                owner_user_id=owner_user_id,
                occurred_at=now,
                conversation_id=conversation_id,
                message_id=msg.id,
                concept_id=subj.id,
                world_claim_id=wc.id,
                extraction_run_id=extraction_run.id,
            )
        else:
            wc = existing_wc

        ev = EvidenceModel(
            id=new_id("evd"),
            owner_user_id=owner_user_id,
            message_id=msg.id,
            annotation_id=None,
            external_uri=None,
            quote=wc_cand.quote[:320],
            start_offset=None,
            end_offset=None,
            source_role="assistant" if msg.role == "assistant" else "user",
            extraction_run_id=extraction_run.id,
            captured_at=now,
        )
        session.add(ev)
        session.flush()
        session.add(
            WorldClaimEvidenceModel(world_claim_id=wc.id, evidence_id=ev.id)
        )

    # 3. Pending suggestions (never insert into user_relations!)
    for s_cand in proposal.suggestions:
        msg = session.get(MessageModel, s_cand.message_id)
        if msg is None or msg.conversation_id != conversation_id:
            continue
        subj = resolve_or_create_concept(
            session,
            canonical_name=s_cand.subject_name,
            origin="extractor",
            owner_user_id=owner_user_id,
            conversation_id=conversation_id,
            message_id=msg.id,
            extraction_run_id=extraction_run.id,
        )
        obj = resolve_or_create_concept(
            session,
            canonical_name=s_cand.object_name,
            origin="extractor",
            owner_user_id=owner_user_id,
            conversation_id=conversation_id,
            message_id=msg.id,
            extraction_run_id=extraction_run.id,
        )
        if subj.id == obj.id:
            continue

        # Skip if already established in user_relations or already exists in knowledge_suggestions
        already_rel = session.scalar(
            select(UserRelationModel).where(
                UserRelationModel.owner_user_id == owner_user_id,
                UserRelationModel.withdrawn_at.is_(None),
                or_(
                    (UserRelationModel.subject_concept_id == subj.id)
                    & (UserRelationModel.object_concept_id == obj.id),
                    (UserRelationModel.subject_concept_id == obj.id)
                    & (UserRelationModel.object_concept_id == subj.id),
                ),
            )
        )
        if already_rel is not None:
            continue

        existing_sugg = session.scalar(
            select(KnowledgeSuggestionModel).where(
                KnowledgeSuggestionModel.owner_user_id == owner_user_id,
                or_(
                    (KnowledgeSuggestionModel.subject_concept_id == subj.id)
                    & (KnowledgeSuggestionModel.object_concept_id == obj.id),
                    (KnowledgeSuggestionModel.subject_concept_id == obj.id)
                    & (KnowledgeSuggestionModel.object_concept_id == subj.id),
                ),
            )
        )
        if existing_sugg is None:
            sugg = KnowledgeSuggestionModel(
                id=new_id("s"),
                owner_user_id=owner_user_id,
                suggestion_type="connection",
                subject_concept_id=subj.id,
                predicate=s_cand.predicate,
                object_concept_id=obj.id,
                explanation=s_cand.explanation,
                confidence_hint=s_cand.confidence_hint,
                status=SuggestionStatus.PENDING.value,
                extraction_run_id=extraction_run.id,
                created_at=now,
                resolved_at=None,
            )
            session.add(sugg)
            session.flush()
            ev = EvidenceModel(
                id=new_id("evd"),
                owner_user_id=owner_user_id,
                message_id=msg.id,
                annotation_id=None,
                external_uri=None,
                quote=s_cand.quote[:320],
                start_offset=None,
                end_offset=None,
                source_role="assistant" if msg.role == "assistant" else "user",
                extraction_run_id=extraction_run.id,
                captured_at=now,
            )
            session.add(ev)
            session.flush()
            session.add(
                SuggestionEvidenceModel(suggestion_id=sugg.id, evidence_id=ev.id)
            )
            _record_event(
                session,
                event_type=KnowledgeEventType.SUGGESTION_CREATED,
                payload={
                    "subject_id": subj.id,
                    "predicate": sugg.predicate,
                    "object_id": obj.id,
                    "status": "pending",
                    "actor": "extractor",
                },
                owner_user_id=owner_user_id,
                occurred_at=now,
                conversation_id=conversation_id,
                message_id=msg.id,
                concept_id=subj.id,
                suggestion_id=sugg.id,
                extraction_run_id=extraction_run.id,
            )

    # 4. Inferred candidate signals (always candidate status; never mutate self_assessment!)
    for sig_cand in proposal.inferred_signals:
        msg = session.get(MessageModel, sig_cand.message_id)
        if msg is None or msg.conversation_id != conversation_id:
            continue
        concept = resolve_or_create_concept(
            session,
            canonical_name=sig_cand.concept_name,
            origin="extractor",
            owner_user_id=owner_user_id,
            conversation_id=conversation_id,
            message_id=msg.id,
            extraction_run_id=extraction_run.id,
        )
        _ensure_concept_state(session, concept.id, owner_user_id)
        ev = EvidenceModel(
            id=new_id("evd"),
            owner_user_id=owner_user_id,
            message_id=msg.id,
            annotation_id=None,
            external_uri=None,
            quote=sig_cand.quote[:320],
            start_offset=None,
            end_offset=None,
            source_role="user" if msg.role == "user" else "assistant",
            extraction_run_id=extraction_run.id,
            captured_at=now,
        )
        session.add(ev)
        session.flush()
        session.add(
            UserStateEvidenceModel(
                owner_user_id=owner_user_id,
                concept_id=concept.id,
                evidence_id=ev.id,
                signal_kind=sig_cand.signal_kind.value,
                origin=SignalOrigin.AI_INFERRED.value,
                review_status=ReviewStatus.CANDIDATE.value,
                confidence_hint=sig_cand.confidence_hint,
                rationale=sig_cand.rationale,
            )
        )

    # 5. Re-link any explicit annotations on the turn's messages now that mentions are extracted
    turn_msg_ids = {m.message_id for m in proposal.mentions}
    for mid in turn_msg_ids:
        msg = session.get(MessageModel, mid)
        if msg is None:
            continue
        anns = session.scalars(
            select(AnnotationModel).where(
                AnnotationModel.message_id == mid,
                AnnotationModel.removed_at.is_(None),
            )
        ).all()
        for ann in anns:
            apply_annotation_to_concept_states(
                session, ann, msg, owner_user_id=owner_user_id
            )


def _evidence_to_dto(session: Session, ev: EvidenceModel) -> EvidenceItemDTO:
    msg = session.get(MessageModel, ev.message_id) if ev.message_id else None
    ann = session.get(AnnotationModel, ev.annotation_id) if ev.annotation_id else None
    ext = (
        session.get(ExtractionRunModel, ev.extraction_run_id)
        if ev.extraction_run_id
        else None
    )
    return EvidenceItemDTO(
        id=ev.id,
        message_id=ev.message_id,
        conversation_id=msg.conversation_id if msg else None,
        annotation_id=ev.annotation_id,
        annotation_tag=ann.tag if ann else None,
        quote=ev.quote,
        summary=ev.summary,
        summary_provider=ev.summary_provider,
        summary_model=ev.summary_model,
        summary_prompt_version=ev.summary_prompt_version,
        summary_generated_at=ev.summary_generated_at,
        start_offset=ev.start_offset,
        end_offset=ev.end_offset,
        source_role=ev.source_role,
        captured_at=ev.captured_at,
        extraction_provider=ext.provider if ext else None,
        extraction_model=ext.model if ext else None,
        extraction_prompt_version=ext.prompt_version if ext else None,
    )


def _suggestion_to_dto(
    session: Session, sugg: KnowledgeSuggestionModel
) -> SuggestionDTO:
    subj = session.get(ConceptModel, sugg.subject_concept_id)
    obj = session.get(ConceptModel, sugg.object_concept_id)
    ext = (
        session.get(ExtractionRunModel, sugg.extraction_run_id)
        if sugg.extraction_run_id
        else None
    )
    ev_links = session.scalars(
        select(SuggestionEvidenceModel).where(
            SuggestionEvidenceModel.suggestion_id == sugg.id
        )
    ).all()
    ev_dtos = [
        _evidence_to_dto(session, ev)
        for link in ev_links
        if (ev := session.get(EvidenceModel, link.evidence_id)) is not None
    ]
    return SuggestionDTO(
        id=sugg.id,
        suggestion_type=sugg.suggestion_type,
        subject_concept_id=sugg.subject_concept_id,
        subject_name=subj.canonical_name if subj else sugg.subject_concept_id,
        predicate=sugg.predicate,
        predicate_label=_predicate_label(sugg.predicate),
        object_concept_id=sugg.object_concept_id,
        object_name=obj.canonical_name if obj else sugg.object_concept_id,
        explanation=sugg.explanation,
        confidence_hint=sugg.confidence_hint,
        status=SuggestionStatus(sugg.status),
        extraction_run_id=sugg.extraction_run_id,
        provider=ext.provider if ext else None,
        model=ext.model if ext else None,
        prompt_version=ext.prompt_version if ext else None,
        created_at=sugg.created_at,
        resolved_at=sugg.resolved_at,
        evidence=ev_dtos,
    )


def _relation_to_dto(session: Session, rel: UserRelationModel) -> UserRelationDTO:
    subj = session.get(ConceptModel, rel.subject_concept_id)
    obj = session.get(ConceptModel, rel.object_concept_id)
    ev_links = session.scalars(
        select(UserRelationEvidenceModel).where(
            UserRelationEvidenceModel.user_relation_id == rel.id
        )
    ).all()
    ev_dtos = [
        _evidence_to_dto(session, ev)
        for link in ev_links
        if (ev := session.get(EvidenceModel, link.evidence_id)) is not None
    ]
    return UserRelationDTO(
        id=rel.id,
        subject_concept_id=rel.subject_concept_id,
        subject_name=subj.canonical_name if subj else rel.subject_concept_id,
        predicate=rel.predicate,
        predicate_label=_predicate_label(rel.predicate),
        object_concept_id=rel.object_concept_id,
        object_name=obj.canonical_name if obj else rel.object_concept_id,
        explanation=rel.explanation,
        origin=UserRelationOrigin(rel.origin),
        established_at=rel.established_at,
        withdrawn_at=rel.withdrawn_at,
        source_suggestion_id=rel.source_suggestion_id,
        evidence=ev_dtos,
    )


def list_suggestions(
    session: Session,
    *,
    status: str | None = "pending",
    concept_id: str | None = None,
    limit: int = 50,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> SuggestionListResponse:
    stmt = select(KnowledgeSuggestionModel).where(
        KnowledgeSuggestionModel.owner_user_id == owner_user_id
    )
    if status:
        stmt = stmt.where(KnowledgeSuggestionModel.status == status)
    if concept_id:
        stmt = stmt.where(
            or_(
                KnowledgeSuggestionModel.subject_concept_id == concept_id,
                KnowledgeSuggestionModel.object_concept_id == concept_id,
            )
        )
    stmt = stmt.order_by(KnowledgeSuggestionModel.created_at.desc()).limit(limit)
    rows = session.scalars(stmt).all()
    return SuggestionListResponse(
        items=[_suggestion_to_dto(session, r) for r in rows],
        next_cursor=None,
    )


def get_suggestion(
    session: Session,
    suggestion_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> SuggestionDTO:
    sugg = session.get(KnowledgeSuggestionModel, suggestion_id)
    if sugg is None or sugg.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "suggestion_not_found",
                "message": f"Suggestion '{suggestion_id}' not found.",
                "details": {},
            },
        )
    return _suggestion_to_dto(session, sugg)


def accept_suggestion(
    session: Session,
    suggestion_id: str,
    req: SuggestionAcceptRequest | None = None,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> UserRelationDTO:
    sugg = session.get(KnowledgeSuggestionModel, suggestion_id)
    if sugg is None or sugg.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "suggestion_not_found",
                "message": f"Suggestion '{suggestion_id}' not found.",
                "details": {},
            },
        )

    # Idempotent return if already accepted
    if sugg.status == SuggestionStatus.ACCEPTED.value:
        existing_rel = session.scalar(
            select(UserRelationModel).where(
                UserRelationModel.source_suggestion_id == sugg.id
            )
        )
        if existing_rel is not None:
            return _relation_to_dto(session, existing_rel)

    if sugg.status in (
        SuggestionStatus.REJECTED.value,
        SuggestionStatus.DISMISSED.value,
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "suggestion_already_resolved",
                "message": f"Suggestion '{suggestion_id}' was already {sugg.status}.",
                "details": {"status": sugg.status},
            },
        )

    predicate = (req.predicate if req and req.predicate else sugg.predicate).strip()
    explanation = (
        req.explanation if req and req.explanation is not None else sugg.explanation
    ).strip()

    now = utc_now_iso()
    sugg.status = SuggestionStatus.ACCEPTED.value
    sugg.resolved_at = now

    rel = UserRelationModel(
        id=new_id("ur"),
        owner_user_id=owner_user_id,
        subject_concept_id=sugg.subject_concept_id,
        predicate=predicate,
        object_concept_id=sugg.object_concept_id,
        explanation=explanation,
        origin=UserRelationOrigin.ACCEPTED_SUGGESTION.value,
        established_at=now,
        withdrawn_at=None,
        supersedes_relation_id=None,
        source_suggestion_id=sugg.id,
    )
    session.add(rel)
    session.flush()

    ev_links = session.scalars(
        select(SuggestionEvidenceModel).where(
            SuggestionEvidenceModel.suggestion_id == sugg.id
        )
    ).all()
    for link in ev_links:
        session.add(
            UserRelationEvidenceModel(
                user_relation_id=rel.id,
                evidence_id=link.evidence_id,
                evidence_role="assertion",
            )
        )

    # IMPORTANT: Acceptance establishes the user relation and records timeline events,
    # and NEVER upgrades `user_concept_states` (e.g. Hebbian learning) to understood!
    _ensure_concept_state(session, sugg.subject_concept_id, owner_user_id)
    _ensure_concept_state(session, sugg.object_concept_id, owner_user_id)

    _record_event(
        session,
        event_type=KnowledgeEventType.SUGGESTION_ACCEPTED,
        payload={
            "actor": "user",
            "predicate": predicate,
            "subject_concept_id": sugg.subject_concept_id,
            "object_concept_id": sugg.object_concept_id,
        },
        owner_user_id=owner_user_id,
        occurred_at=now,
        concept_id=sugg.subject_concept_id,
        user_relation_id=rel.id,
        suggestion_id=sugg.id,
    )
    _record_event(
        session,
        event_type=KnowledgeEventType.USER_RELATION_ESTABLISHED,
        payload={
            "actor": "user",
            "origin": rel.origin,
            "predicate": predicate,
            "subject_concept_id": rel.subject_concept_id,
            "object_concept_id": rel.object_concept_id,
        },
        owner_user_id=owner_user_id,
        occurred_at=now,
        concept_id=rel.subject_concept_id,
        user_relation_id=rel.id,
        suggestion_id=sugg.id,
    )
    session.flush()
    return _relation_to_dto(session, rel)


def reject_suggestion(
    session: Session,
    suggestion_id: str,
    req: SuggestionRejectRequest | None = None,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> SuggestionDTO:
    sugg = session.get(KnowledgeSuggestionModel, suggestion_id)
    if sugg is None or sugg.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "suggestion_not_found",
                "message": f"Suggestion '{suggestion_id}' not found.",
                "details": {},
            },
        )
    if sugg.status == SuggestionStatus.REJECTED.value:
        return _suggestion_to_dto(session, sugg)
    if sugg.status == SuggestionStatus.ACCEPTED.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "suggestion_already_resolved",
                "message": "Suggestion has already been accepted.",
                "details": {},
            },
        )

    now = utc_now_iso()
    sugg.status = SuggestionStatus.REJECTED.value
    sugg.resolved_at = now
    _record_event(
        session,
        event_type=KnowledgeEventType.SUGGESTION_REJECTED,
        payload={
            "actor": "user",
            "reason": req.reason if req else None,
            "subject_concept_id": sugg.subject_concept_id,
            "object_concept_id": sugg.object_concept_id,
        },
        owner_user_id=owner_user_id,
        occurred_at=now,
        concept_id=sugg.subject_concept_id,
        suggestion_id=sugg.id,
    )
    session.flush()
    return _suggestion_to_dto(session, sugg)


def dismiss_suggestion(
    session: Session,
    suggestion_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> SuggestionDTO:
    sugg = session.get(KnowledgeSuggestionModel, suggestion_id)
    if sugg is None or sugg.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "suggestion_not_found",
                "message": f"Suggestion '{suggestion_id}' not found.",
                "details": {},
            },
        )
    if sugg.status == SuggestionStatus.ACCEPTED.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "suggestion_already_resolved",
                "message": "Suggestion has already been accepted.",
                "details": {},
            },
        )
    now = utc_now_iso()
    sugg.status = SuggestionStatus.DISMISSED.value
    sugg.resolved_at = now
    _record_event(
        session,
        event_type=KnowledgeEventType.SUGGESTION_DISMISSED,
        payload={"actor": "user"},
        owner_user_id=owner_user_id,
        occurred_at=now,
        concept_id=sugg.subject_concept_id,
        suggestion_id=sugg.id,
    )
    session.flush()
    return _suggestion_to_dto(session, sugg)


def create_user_relation(
    session: Session,
    concept_id: str,
    req: CreateUserRelationRequest,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> UserRelationDTO:
    subj = session.get(ConceptModel, concept_id)
    obj = session.get(ConceptModel, req.target_concept_id)
    if subj is None or obj is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "concept_not_found",
                "message": "Subject or target concept not found.",
                "details": {},
            },
        )
    if subj.id == obj.id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "relation_conflict",
                "message": "Cannot link a concept to itself.",
                "details": {},
            },
        )

    now = utc_now_iso()
    rel = UserRelationModel(
        id=new_id("ur"),
        owner_user_id=owner_user_id,
        subject_concept_id=subj.id,
        predicate=req.predicate.strip(),
        object_concept_id=obj.id,
        explanation=req.explanation.strip(),
        origin=UserRelationOrigin.DIRECT_USER_ASSERTION.value,
        established_at=now,
    )
    session.add(rel)
    session.flush()

    if req.message_id:
        msg = session.get(MessageModel, req.message_id)
        if msg is not None:
            ev = EvidenceModel(
                id=new_id("evd"),
                owner_user_id=owner_user_id,
                message_id=msg.id,
                annotation_id=None,
                external_uri=None,
                quote=msg.content[:320],
                start_offset=None,
                end_offset=None,
                source_role="user" if msg.role == "user" else "assistant",
                extraction_run_id=None,
                captured_at=now,
            )
            session.add(ev)
            session.flush()
            session.add(
                UserRelationEvidenceModel(
                    user_relation_id=rel.id,
                    evidence_id=ev.id,
                    evidence_role="assertion",
                )
            )

    _record_event(
        session,
        event_type=KnowledgeEventType.USER_RELATION_ESTABLISHED,
        payload={
            "actor": "user",
            "origin": rel.origin,
            "predicate": rel.predicate,
            "subject_concept_id": subj.id,
            "object_concept_id": obj.id,
        },
        owner_user_id=owner_user_id,
        occurred_at=now,
        concept_id=subj.id,
        user_relation_id=rel.id,
    )
    session.flush()
    return _relation_to_dto(session, rel)


def get_user_relation(
    session: Session,
    relation_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> UserRelationDTO:
    rel = session.get(UserRelationModel, relation_id)
    if rel is None or rel.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "relation_not_found",
                "message": f"Relation '{relation_id}' not found.",
                "details": {},
            },
        )
    return _relation_to_dto(session, rel)


def withdraw_user_relation(
    session: Session,
    relation_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> UserRelationDTO:
    rel = session.get(UserRelationModel, relation_id)
    if rel is None or rel.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "relation_not_found",
                "message": f"Relation '{relation_id}' not found.",
                "details": {},
            },
        )
    if rel.withdrawn_at is None:
        now = utc_now_iso()
        rel.withdrawn_at = now
        _record_event(
            session,
            event_type=KnowledgeEventType.USER_RELATION_WITHDRAWN,
            payload={
                "actor": "user",
                "subject_concept_id": rel.subject_concept_id,
                "object_concept_id": rel.object_concept_id,
                "predicate": rel.predicate,
            },
            owner_user_id=owner_user_id,
            occurred_at=now,
            concept_id=rel.subject_concept_id,
            user_relation_id=rel.id,
        )
        session.flush()
    return _relation_to_dto(session, rel)


def _build_concept_signals_dto(
    state: UserConceptStateModel | None,
    mention_count: int,
) -> ConceptSignalsDTO:
    if state is None:
        return ConceptSignalsDTO(
            encountered=mention_count > 0,
            explored=False,
            first_encountered_at=None,
            last_explored_at=None,
            self_assessment=SelfAssessment.UNKNOWN,
            demonstration_status=DemonstrationStatus.NONE,
        )
    return ConceptSignalsDTO(
        encountered=bool(state.first_encountered_at) or mention_count > 0,
        explored=bool(state.last_explored_at),
        first_encountered_at=state.first_encountered_at,
        last_explored_at=state.last_explored_at,
        self_assessment=SelfAssessment(state.self_assessment),
        demonstration_status=DemonstrationStatus(state.demonstration_status),
    )


def get_concept_detail(
    session: Session,
    concept_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> ConceptDetailDTO:
    concept = session.get(ConceptModel, concept_id)
    if concept is None or concept.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "concept_not_found",
                "message": f"Concept '{concept_id}' not found.",
                "details": {},
            },
        )
    aliases = [
        a.alias
        for a in session.scalars(
            select(ConceptAliasModel).where(ConceptAliasModel.concept_id == concept.id)
        ).all()
    ]
    mentions = session.scalars(
        select(ConceptMentionModel).where(ConceptMentionModel.concept_id == concept.id)
    ).all()
    state = session.get(UserConceptStateModel, (owner_user_id, concept.id))

    user_rels = session.scalars(
        select(UserRelationModel).where(
            UserRelationModel.owner_user_id == owner_user_id,
            UserRelationModel.withdrawn_at.is_(None),
            or_(
                UserRelationModel.subject_concept_id == concept.id,
                UserRelationModel.object_concept_id == concept.id,
            ),
        )
    ).all()
    world_claims = session.scalars(
        select(WorldClaimModel).where(
            WorldClaimModel.owner_user_id == owner_user_id,
            or_(
                WorldClaimModel.subject_concept_id == concept.id,
                WorldClaimModel.object_concept_id == concept.id,
            ),
        )
    ).all()
    pending_suggs = session.scalars(
        select(KnowledgeSuggestionModel).where(
            KnowledgeSuggestionModel.owner_user_id == owner_user_id,
            KnowledgeSuggestionModel.status == SuggestionStatus.PENDING.value,
            or_(
                KnowledgeSuggestionModel.subject_concept_id == concept.id,
                KnowledgeSuggestionModel.object_concept_id == concept.id,
            ),
        )
    ).all()

    open_questions: list[str] = []
    for m in mentions:
        msg = session.get(MessageModel, m.message_id)
        if msg and msg.role == "user" and "?" in msg.content:
            q_text = msg.content.strip()
            if q_text not in open_questions:
                open_questions.append(q_text)

    return ConceptDetailDTO(
        id=concept.id,
        canonical_name=concept.canonical_name,
        normalized_name=concept.normalized_name,
        description=concept.description,
        aliases=aliases,
        signals=_build_concept_signals_dto(state, len(mentions)),
        mention_count=len(mentions),
        user_relation_count=len(user_rels),
        world_claim_count=len(world_claims),
        pending_suggestion_count=len(pending_suggs),
        open_questions=open_questions[:5],
        created_at=concept.created_at,
        updated_at=concept.updated_at,
        merged_into_concept_id=concept.merged_into_concept_id,
    )


def get_concept_evidence(
    session: Session,
    concept_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> ConceptEvidenceResponse:
    concept = session.get(ConceptModel, concept_id)
    if concept is None or concept.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "concept_not_found",
                "message": f"Concept '{concept_id}' not found.",
                "details": {},
            },
        )

    mentions_rows = session.scalars(
        select(ConceptMentionModel)
        .where(ConceptMentionModel.concept_id == concept.id)
        .order_by(ConceptMentionModel.created_at.desc())
    ).all()
    mention_evidence: list[EvidenceItemDTO] = []
    for m in mentions_rows:
        msg = session.get(MessageModel, m.message_id)
        if msg is None:
            continue
        ext = (
            session.get(ExtractionRunModel, m.extraction_run_id)
            if m.extraction_run_id
            else None
        )
        mention_evidence.append(
            EvidenceItemDTO(
                id=m.id,
                message_id=msg.id,
                conversation_id=msg.conversation_id,
                annotation_id=None,
                annotation_tag=None,
                quote=msg.content,
                start_offset=m.start_offset,
                end_offset=m.end_offset,
                source_role=msg.role,
                captured_at=m.created_at,
                extraction_provider=ext.provider if ext else None,
                extraction_model=ext.model if ext else None,
                extraction_prompt_version=ext.prompt_version if ext else None,
            )
        )

    se_rows = session.scalars(
        select(UserStateEvidenceModel).where(
            UserStateEvidenceModel.owner_user_id == owner_user_id,
            UserStateEvidenceModel.concept_id == concept.id,
        )
    ).all()
    annotations: list[AnnotationDTO] = []
    seen_ann_ids: set[str] = set()
    state_signals: list[InferredAnnotationSignalDTO] = []
    saved_notes_by_id: dict[str, EvidenceItemDTO] = {}

    for se in se_rows:
        ev = session.get(EvidenceModel, se.evidence_id)
        if ev is None:
            continue
        if (
            se.origin == SignalOrigin.EXPLICIT_ANNOTATION.value
            and se.review_status == ReviewStatus.CONFIRMED.value
            and ev.annotation_id is not None
        ):
            ann = session.get(AnnotationModel, ev.annotation_id)
            if ann is not None and ann.removed_at is None:
                saved_notes_by_id[ev.id] = _evidence_to_dto(session, ev)
        if ev.annotation_id and ev.annotation_id not in seen_ann_ids:
            ann = session.get(AnnotationModel, ev.annotation_id)
            if ann and ann.removed_at is None:
                seen_ann_ids.add(ann.id)
                annotations.append(_to_annotation_dto(session, ann))
        state_signals.append(
            InferredAnnotationSignalDTO(
                evidence_id=ev.id,
                concept_id=concept.id,
                concept_name=concept.canonical_name,
                signal_kind=SignalKind(se.signal_kind),
                origin=SignalOrigin(se.origin),
                review_status=ReviewStatus(se.review_status),
                confidence_hint=se.confidence_hint,
                quote=ev.quote,
                rationale=se.rationale,
            )
        )

    wc_rows = session.scalars(
        select(WorldClaimModel).where(
            WorldClaimModel.owner_user_id == owner_user_id,
            or_(
                WorldClaimModel.subject_concept_id == concept.id,
                WorldClaimModel.object_concept_id == concept.id,
            ),
        )
    ).all()
    wc_dtos: list[WorldClaimDTO] = []
    for wc in wc_rows:
        subj = session.get(ConceptModel, wc.subject_concept_id)
        obj = session.get(ConceptModel, wc.object_concept_id)
        wc_links = session.scalars(
            select(WorldClaimEvidenceModel).where(
                WorldClaimEvidenceModel.world_claim_id == wc.id
            )
        ).all()
        ev_items = [
            _evidence_to_dto(session, ev)
            for lnk in wc_links
            if (ev := session.get(EvidenceModel, lnk.evidence_id)) is not None
        ]
        wc_dtos.append(
            WorldClaimDTO(
                id=wc.id,
                subject_concept_id=wc.subject_concept_id,
                subject_name=subj.canonical_name if subj else wc.subject_concept_id,
                predicate=wc.predicate,
                predicate_label=_predicate_label(wc.predicate),
                object_concept_id=wc.object_concept_id,
                object_name=obj.canonical_name if obj else wc.object_concept_id,
                claim_text=wc.claim_text,
                polarity=wc.polarity,
                status=WorldClaimStatus(wc.status),
                source_kind=WorldClaimSourceKind(wc.source_kind),
                confidence_hint=wc.confidence_hint,
                created_at=wc.created_at,
                evidence=ev_items,
            )
        )

    ur_rows = session.scalars(
        select(UserRelationModel).where(
            UserRelationModel.owner_user_id == owner_user_id,
            UserRelationModel.withdrawn_at.is_(None),
            or_(
                UserRelationModel.subject_concept_id == concept.id,
                UserRelationModel.object_concept_id == concept.id,
            ),
        )
    ).all()
    ur_dtos = [_relation_to_dto(session, r) for r in ur_rows]

    sugg_rows = session.scalars(
        select(KnowledgeSuggestionModel).where(
            KnowledgeSuggestionModel.owner_user_id == owner_user_id,
            or_(
                KnowledgeSuggestionModel.subject_concept_id == concept.id,
                KnowledgeSuggestionModel.object_concept_id == concept.id,
            ),
        )
    ).all()
    sugg_dtos = [_suggestion_to_dto(session, s) for s in sugg_rows]

    return ConceptEvidenceResponse(
        concept_id=concept.id,
        mentions=mention_evidence,
        saved_notes=sorted(
            saved_notes_by_id.values(),
            key=lambda item: item.captured_at,
            reverse=True,
        ),
        annotations=annotations,
        state_signals=state_signals,
        world_claims=wc_dtos,
        user_relations=ur_dtos,
        suggestions=sugg_dtos,
    )


def get_related_concepts(
    session: Session,
    concept_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> RelatedConceptListResponse:
    ev = get_concept_evidence(session, concept_id, owner_user_id=owner_user_id)
    items: list[RelatedConceptDTO] = []

    for r in ev.user_relations:
        outgoing = r.subject_concept_id == concept_id
        other_id = r.object_concept_id if outgoing else r.subject_concept_id
        other_name = r.object_name if outgoing else r.subject_name
        items.append(
            RelatedConceptDTO(
                concept_id=other_id,
                canonical_name=other_name,
                predicate=r.predicate,
                predicate_label=r.predicate_label,
                direction="outgoing" if outgoing else "incoming",
                layer="user_established",
                status="active",
                origin=r.origin.value,
                evidence_count=len(r.evidence),
                relation_id=r.id,
            )
        )

    for wc in ev.world_claims:
        outgoing = wc.subject_concept_id == concept_id
        other_id = wc.object_concept_id if outgoing else wc.subject_concept_id
        other_name = wc.object_name if outgoing else wc.subject_name
        items.append(
            RelatedConceptDTO(
                concept_id=other_id,
                canonical_name=other_name,
                predicate=wc.predicate,
                predicate_label=wc.predicate_label,
                direction="outgoing" if outgoing else "incoming",
                layer="world",
                status=wc.status.value,
                origin=wc.source_kind.value,
                evidence_count=len(wc.evidence),
                world_claim_id=wc.id,
            )
        )

    for s in ev.suggestions:
        if s.status != SuggestionStatus.PENDING:
            continue
        outgoing = s.subject_concept_id == concept_id
        other_id = s.object_concept_id if outgoing else s.subject_concept_id
        other_name = s.object_name if outgoing else s.subject_name
        items.append(
            RelatedConceptDTO(
                concept_id=other_id,
                canonical_name=other_name,
                predicate=s.predicate,
                predicate_label=s.predicate_label,
                direction="outgoing" if outgoing else "incoming",
                layer="suggested",
                status=s.status.value,
                origin="ai_suggestion",
                evidence_count=len(s.evidence),
                suggestion_id=s.id,
            )
        )

    return RelatedConceptListResponse(items=items)


def merge_concepts(
    session: Session,
    source_concept_id: str,
    req: MergeConceptRequest,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> ConceptDetailDTO:
    source = session.get(ConceptModel, source_concept_id)
    target = session.get(ConceptModel, req.target_concept_id)
    if source is None or target is None or source.owner_user_id != owner_user_id or target.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "concept_not_found",
                "message": "Source or target concept not found.",
                "details": {},
            },
        )
    if source.id == target.id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "relation_conflict",
                "message": "Cannot merge a concept into itself.",
                "details": {},
            },
        )

    now = utc_now_iso()
    source.merged_into_concept_id = target.id
    source.archived_at = now
    source.updated_at = now
    target.updated_at = now

    # Preserve old canonical name and aliases on target
    existing_aliases = {
        a.normalized_alias
        for a in session.scalars(
            select(ConceptAliasModel).where(ConceptAliasModel.concept_id == target.id)
        ).all()
    }
    if source.normalized_name not in existing_aliases:
        session.add(
            ConceptAliasModel(
                id=new_id("alias"),
                concept_id=target.id,
                alias=source.canonical_name,
                normalized_alias=source.normalized_name,
                origin="user",
                created_at=now,
            )
        )

    # Redirect mentions
    for m in session.scalars(
        select(ConceptMentionModel).where(ConceptMentionModel.concept_id == source.id)
    ).all():
        m.concept_id = target.id

    # Redirect relations & avoid self-loops
    for ur in session.scalars(
        select(UserRelationModel).where(
            or_(
                UserRelationModel.subject_concept_id == source.id,
                UserRelationModel.object_concept_id == source.id,
            )
        )
    ).all():
        new_subj = target.id if ur.subject_concept_id == source.id else ur.subject_concept_id
        new_obj = target.id if ur.object_concept_id == source.id else ur.object_concept_id
        if new_subj == new_obj:
            session.delete(ur)
        else:
            ur.subject_concept_id = new_subj
            ur.object_concept_id = new_obj

    for wc in session.scalars(
        select(WorldClaimModel).where(
            or_(
                WorldClaimModel.subject_concept_id == source.id,
                WorldClaimModel.object_concept_id == source.id,
            )
        )
    ).all():
        new_subj = target.id if wc.subject_concept_id == source.id else wc.subject_concept_id
        new_obj = target.id if wc.object_concept_id == source.id else wc.object_concept_id
        if new_subj == new_obj:
            session.delete(wc)
        else:
            wc.subject_concept_id = new_subj
            wc.object_concept_id = new_obj

    for sg in session.scalars(
        select(KnowledgeSuggestionModel).where(
            or_(
                KnowledgeSuggestionModel.subject_concept_id == source.id,
                KnowledgeSuggestionModel.object_concept_id == source.id,
            )
        )
    ).all():
        new_subj = target.id if sg.subject_concept_id == source.id else sg.subject_concept_id
        new_obj = target.id if sg.object_concept_id == source.id else sg.object_concept_id
        if new_subj == new_obj:
            session.delete(sg)
        else:
            sg.subject_concept_id = new_subj
            sg.object_concept_id = new_obj

    _record_event(
        session,
        event_type=KnowledgeEventType.CONCEPT_MERGED,
        payload={
            "source_concept_id": source.id,
            "source_name": source.canonical_name,
            "target_concept_id": target.id,
            "target_name": target.canonical_name,
            "actor": "user",
        },
        owner_user_id=owner_user_id,
        occurred_at=now,
        concept_id=target.id,
    )
    session.flush()
    return get_concept_detail(session, target.id, owner_user_id=owner_user_id)


def review_candidate_signal(
    session: Session,
    *,
    concept_id: str,
    evidence_id: str,
    action: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> ConceptDetailDTO:
    se = session.get(UserStateEvidenceModel, (owner_user_id, concept_id, evidence_id))
    if se is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "signal_not_found",
                "message": "Candidate signal not found.",
                "details": {},
            },
        )
    now = utc_now_iso()
    state = _ensure_concept_state(session, concept_id, owner_user_id)
    if action == "confirm":
        se.review_status = ReviewStatus.CONFIRMED.value
        if se.signal_kind in (
            SignalKind.EXPLANATION.value,
            SignalKind.PROBLEM_SOLVING.value,
        ):
            confirmed_demos = session.scalars(
                select(UserStateEvidenceModel).where(
                    UserStateEvidenceModel.owner_user_id == owner_user_id,
                    UserStateEvidenceModel.concept_id == concept_id,
                    UserStateEvidenceModel.review_status == ReviewStatus.CONFIRMED.value,
                    UserStateEvidenceModel.signal_kind.in_(
                        [SignalKind.EXPLANATION.value, SignalKind.PROBLEM_SOLVING.value]
                    ),
                )
            ).all()
            before_demo = state.demonstration_status
            state.demonstration_status = (
                DemonstrationStatus.REPEATED_EVIDENCE.value
                if len(confirmed_demos) >= 2
                else DemonstrationStatus.SOME_EVIDENCE.value
            )
            state.updated_at = now
            _record_event(
                session,
                event_type=KnowledgeEventType.DEMONSTRATION_EVIDENCE_ADDED,
                payload={
                    "before": before_demo,
                    "after": state.demonstration_status,
                    "signal_kind": se.signal_kind,
                    "actor": "user",
                },
                owner_user_id=owner_user_id,
                occurred_at=now,
                concept_id=concept_id,
            )
    else:
        se.review_status = ReviewStatus.DISMISSED.value
        _record_event(
            session,
            event_type=KnowledgeEventType.CANDIDATE_SIGNAL_DISMISSED,
            payload={"signal_kind": se.signal_kind, "actor": "user"},
            owner_user_id=owner_user_id,
            occurred_at=now,
            concept_id=concept_id,
        )
    session.flush()
    return get_concept_detail(session, concept_id, owner_user_id=owner_user_id)


def _hypothesis_to_dto(
    session: Session, hyp: UserHypothesisModel
) -> HypothesisDTO:
    links = session.scalars(
        select(HypothesisEvidenceModel).where(
            HypothesisEvidenceModel.hypothesis_id == hyp.id
        )
    ).all()
    ev_dtos = [
        _evidence_to_dto(session, ev)
        for lnk in links
        if (ev := session.get(EvidenceModel, lnk.evidence_id)) is not None
    ]
    return HypothesisDTO(
        id=hyp.id,
        statement=hyp.statement,
        status=HypothesisStatus(hyp.status),
        created_at=hyp.created_at,
        updated_at=hyp.updated_at,
        supersedes_hypothesis_id=hyp.supersedes_hypothesis_id,
        withdrawn_at=hyp.withdrawn_at,
        evidence=ev_dtos,
    )


def create_hypothesis(
    session: Session,
    *,
    message_id: str,
    req: CreateHypothesisRequest,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> HypothesisDTO:
    msg = session.get(MessageModel, message_id)
    if msg is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "message_not_found",
                "message": f"Message '{message_id}' not found.",
                "details": {},
            },
        )
    now = utc_now_iso()
    hyp = UserHypothesisModel(
        id=new_id("hyp"),
        owner_user_id=owner_user_id,
        statement=req.statement.strip(),
        status=HypothesisStatus.ACTIVE.value,
        created_at=now,
        updated_at=now,
    )
    session.add(hyp)
    session.flush()

    ev = EvidenceModel(
        id=new_id("evd"),
        owner_user_id=owner_user_id,
        message_id=msg.id,
        annotation_id=None,
        external_uri=None,
        quote=req.statement[:320],
        start_offset=req.span.start_offset if req.span else None,
        end_offset=req.span.end_offset if req.span else None,
        source_role="user" if msg.role == "user" else "assistant",
        extraction_run_id=None,
        captured_at=now,
    )
    session.add(ev)
    session.flush()
    session.add(
        HypothesisEvidenceModel(
            hypothesis_id=hyp.id,
            evidence_id=ev.id,
            evidence_role="statement",
        )
    )
    index_hypothesis_document(session, hyp, owner_user_id=owner_user_id)
    _record_event(
        session,
        event_type=KnowledgeEventType.HYPOTHESIS_CREATED,
        payload={"statement": hyp.statement, "actor": "user"},
        owner_user_id=owner_user_id,
        occurred_at=now,
        conversation_id=msg.conversation_id,
        message_id=msg.id,
        hypothesis_id=hyp.id,
    )
    session.flush()
    return _hypothesis_to_dto(session, hyp)


def list_hypotheses(
    session: Session,
    *,
    status: str | None = None,
    limit: int = 50,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> HypothesisListResponse:
    stmt = select(UserHypothesisModel).where(
        UserHypothesisModel.owner_user_id == owner_user_id
    )
    if status:
        stmt = stmt.where(UserHypothesisModel.status == status)
    stmt = stmt.order_by(UserHypothesisModel.created_at.desc()).limit(limit)
    rows = session.scalars(stmt).all()
    return HypothesisListResponse(
        items=[_hypothesis_to_dto(session, r) for r in rows],
        next_cursor=None,
    )


def get_hypothesis(
    session: Session,
    hypothesis_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> HypothesisDTO:
    hyp = session.get(UserHypothesisModel, hypothesis_id)
    if hyp is None or hyp.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "hypothesis_not_found",
                "message": f"Hypothesis '{hypothesis_id}' not found.",
                "details": {},
            },
        )
    return _hypothesis_to_dto(session, hyp)


def revise_hypothesis(
    session: Session,
    *,
    hypothesis_id: str,
    req: ReviseHypothesisRequest,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> HypothesisDTO:
    old_hyp = session.get(UserHypothesisModel, hypothesis_id)
    if old_hyp is None or old_hyp.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "hypothesis_not_found",
                "message": f"Hypothesis '{hypothesis_id}' not found.",
                "details": {},
            },
        )
    now = utc_now_iso()
    old_hyp.status = HypothesisStatus.REVISED.value
    old_hyp.updated_at = now

    new_hyp = UserHypothesisModel(
        id=new_id("hyp"),
        owner_user_id=owner_user_id,
        statement=req.statement.strip(),
        status=HypothesisStatus.ACTIVE.value,
        created_at=now,
        updated_at=now,
        supersedes_hypothesis_id=old_hyp.id,
    )
    session.add(new_hyp)
    session.flush()

    if req.message_id:
        msg = session.get(MessageModel, req.message_id)
        if msg is not None:
            ev = EvidenceModel(
                id=new_id("evd"),
                owner_user_id=owner_user_id,
                message_id=msg.id,
                annotation_id=None,
                external_uri=None,
                quote=req.statement[:320],
                start_offset=None,
                end_offset=None,
                source_role="user" if msg.role == "user" else "assistant",
                extraction_run_id=None,
                captured_at=now,
            )
            session.add(ev)
            session.flush()
            session.add(
                HypothesisEvidenceModel(
                    hypothesis_id=new_hyp.id,
                    evidence_id=ev.id,
                    evidence_role="revision",
                )
            )

    index_hypothesis_document(session, new_hyp, owner_user_id=owner_user_id)
    _record_event(
        session,
        event_type=KnowledgeEventType.HYPOTHESIS_REVISED,
        payload={
            "previous_hypothesis_id": old_hyp.id,
            "previous_statement": old_hyp.statement,
            "new_hypothesis_id": new_hyp.id,
            "new_statement": new_hyp.statement,
            "actor": "user",
        },
        owner_user_id=owner_user_id,
        occurred_at=now,
        hypothesis_id=new_hyp.id,
    )
    session.flush()
    return _hypothesis_to_dto(session, new_hyp)


def attach_hypothesis_evidence(
    session: Session,
    *,
    hypothesis_id: str,
    req: AttachHypothesisEvidenceRequest,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> HypothesisDTO:
    hyp = session.get(UserHypothesisModel, hypothesis_id)
    if hyp is None or hyp.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "hypothesis_not_found",
                "message": f"Hypothesis '{hypothesis_id}' not found.",
                "details": {},
            },
        )
    msg = session.get(MessageModel, req.message_id)
    if msg is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "message_not_found",
                "message": f"Message '{req.message_id}' not found.",
                "details": {},
            },
        )
    now = utc_now_iso()
    ev = EvidenceModel(
        id=new_id("evd"),
        owner_user_id=owner_user_id,
        message_id=msg.id,
        annotation_id=None,
        external_uri=None,
        quote=(req.quote or msg.content)[:320],
        start_offset=None,
        end_offset=None,
        source_role="user" if msg.role == "user" else "assistant",
        extraction_run_id=None,
        captured_at=now,
    )
    session.add(ev)
    session.flush()
    session.add(
        HypothesisEvidenceModel(
            hypothesis_id=hyp.id,
            evidence_id=ev.id,
            evidence_role=req.evidence_role,
        )
    )
    if req.evidence_role == "support":
        hyp.status = HypothesisStatus.SUPPORTED.value
    elif req.evidence_role == "challenge":
        hyp.status = HypothesisStatus.CHALLENGED.value
    hyp.updated_at = now
    session.flush()
    return _hypothesis_to_dto(session, hyp)


def list_events(
    session: Session,
    *,
    concept_id: str | None = None,
    event_type: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 100,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> EventListResponse:
    stmt = select(KnowledgeEventModel).where(
        KnowledgeEventModel.owner_user_id == owner_user_id
    )
    if concept_id:
        stmt = stmt.where(KnowledgeEventModel.concept_id == concept_id)
    if event_type:
        stmt = stmt.where(KnowledgeEventModel.event_type == event_type)
    if after:
        stmt = stmt.where(KnowledgeEventModel.occurred_at >= after)
    if before:
        stmt = stmt.where(KnowledgeEventModel.occurred_at <= before)
    stmt = stmt.order_by(KnowledgeEventModel.occurred_at.desc()).limit(limit)
    rows = session.scalars(stmt).all()
    items: list[KnowledgeEventDTO] = []
    for r in rows:
        concept = session.get(ConceptModel, r.concept_id) if r.concept_id else None
        items.append(
            KnowledgeEventDTO(
                id=r.id,
                event_type=r.event_type,
                payload_version=r.payload_version,
                occurred_at=r.occurred_at,
                recorded_at=r.recorded_at,
                conversation_id=r.conversation_id,
                message_id=r.message_id,
                annotation_id=r.annotation_id,
                concept_id=r.concept_id,
                concept_name=concept.canonical_name if concept else None,
                world_claim_id=r.world_claim_id,
                user_relation_id=r.user_relation_id,
                suggestion_id=r.suggestion_id,
                hypothesis_id=r.hypothesis_id,
                payload=json.loads(r.payload_json or "{}"),
            )
        )
    return EventListResponse(items=items, next_cursor=None)


def get_event_detail(
    session: Session,
    event_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> KnowledgeEventDTO:
    r = session.get(KnowledgeEventModel, event_id)
    if r is None or r.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "event_not_found",
                "message": f"Event '{event_id}' not found.",
                "details": {},
            },
        )
    concept = session.get(ConceptModel, r.concept_id) if r.concept_id else None
    return KnowledgeEventDTO(
        id=r.id,
        event_type=r.event_type,
        payload_version=r.payload_version,
        occurred_at=r.occurred_at,
        recorded_at=r.recorded_at,
        conversation_id=r.conversation_id,
        message_id=r.message_id,
        annotation_id=r.annotation_id,
        concept_id=r.concept_id,
        concept_name=concept.canonical_name if concept else None,
        world_claim_id=r.world_claim_id,
        user_relation_id=r.user_relation_id,
        suggestion_id=r.suggestion_id,
        hypothesis_id=r.hypothesis_id,
        payload=json.loads(r.payload_json or "{}"),
    )


def project_knowledge_graph(
    session: Session,
    *,
    focus_concept_id: str | None = None,
    depth: int = 2,
    node_limit: int = 80,
    edge_limit: int = 120,
    layers: set[str] | None = None,
    predicates: set[str] | None = None,
    as_of: str | None = None,
    include_unsaved: bool = False,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> GraphProjectionResponse:
    """Return a bounded, filterable graph projection with optional historical `as_of` replay."""
    included_layers = layers or {"user", "world", "suggested"}
    effective_time = as_of or utc_now_iso()

    if as_of is not None:
        if len(as_of) < 10 or not as_of[0:4].isdigit():
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "history_unavailable_for_timestamp",
                    "message": f"Invalid or unsupported historical timestamp '{as_of}'.",
                    "details": {},
                },
            )

    concept_stmt = select(ConceptModel).where(
        ConceptModel.owner_user_id == owner_user_id,
        ConceptModel.merged_into_concept_id.is_(None),
        ConceptModel.created_at <= effective_time,
    )
    concept_rows = session.scalars(concept_stmt).all()
    if include_unsaved:
        all_concepts = {c.id: c for c in concept_rows}
    else:
        saved_concept_ids = set(
            session.scalars(
                select(UserStateEvidenceModel.concept_id)
                .join(
                    EvidenceModel,
                    EvidenceModel.id == UserStateEvidenceModel.evidence_id,
                )
                .join(AnnotationModel, AnnotationModel.id == EvidenceModel.annotation_id)
                .where(
                    UserStateEvidenceModel.owner_user_id == owner_user_id,
                    UserStateEvidenceModel.origin == SignalOrigin.EXPLICIT_ANNOTATION.value,
                    UserStateEvidenceModel.review_status == ReviewStatus.CONFIRMED.value,
                    AnnotationModel.owner_user_id == owner_user_id,
                    AnnotationModel.created_at <= effective_time,
                    or_(
                        AnnotationModel.removed_at.is_(None),
                        AnnotationModel.removed_at > effective_time,
                    ),
                )
                .distinct()
            ).all()
        )
        all_concepts = {c.id: c for c in concept_rows if c.id in saved_concept_ids}

    if focus_concept_id and focus_concept_id not in all_concepts:
        # Check if focus concept was merged
        raw_focus = session.get(ConceptModel, focus_concept_id)
        if raw_focus and raw_focus.merged_into_concept_id in all_concepts:
            focus_concept_id = raw_focus.merged_into_concept_id
        elif raw_focus is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "concept_not_found",
                    "message": f"Focus concept '{focus_concept_id}' not found.",
                    "details": {},
                },
            )

    # Replay historical self_assessment & demonstration_status if `as_of` is provided
    replayed_self: dict[str, str] = {}
    replayed_demo: dict[str, str] = {}
    replayed_explored: set[str] = set()
    if as_of is not None:
        events_up_to = session.scalars(
            select(KnowledgeEventModel)
            .where(
                KnowledgeEventModel.owner_user_id == owner_user_id,
                KnowledgeEventModel.occurred_at <= as_of,
            )
            .order_by(KnowledgeEventModel.occurred_at.asc())
        ).all()
        for ev in events_up_to:
            payload = json.loads(ev.payload_json or "{}")
            if ev.concept_id:
                if ev.event_type == KnowledgeEventType.CONCEPT_EXPLORED.value:
                    replayed_explored.add(ev.concept_id)
                elif ev.event_type == KnowledgeEventType.SELF_ASSESSMENT_CHANGED.value:
                    replayed_self[ev.concept_id] = str(payload.get("after", "unknown"))
                elif ev.event_type == KnowledgeEventType.DEMONSTRATION_EVIDENCE_ADDED.value:
                    replayed_demo[ev.concept_id] = str(payload.get("after", "some_evidence"))

    candidate_edges: list[GraphEdgeDTO] = []

    # Layer 1: user-established relations
    if "user" in included_layers or "user_established" in included_layers:
        ur_rows = session.scalars(
            select(UserRelationModel).where(
                UserRelationModel.owner_user_id == owner_user_id,
                UserRelationModel.established_at <= effective_time,
                or_(
                    UserRelationModel.withdrawn_at.is_(None),
                    UserRelationModel.withdrawn_at > effective_time,
                ),
            )
        ).all()
        for ur in ur_rows:
            if ur.subject_concept_id not in all_concepts or ur.object_concept_id not in all_concepts:
                continue
            if predicates and ur.predicate not in predicates:
                continue
            ev_count = len(
                session.scalars(
                    select(UserRelationEvidenceModel).where(
                        UserRelationEvidenceModel.user_relation_id == ur.id
                    )
                ).all()
            )
            candidate_edges.append(
                GraphEdgeDTO(
                    id=f"user-relation:{ur.id}",
                    source=ur.subject_concept_id,
                    target=ur.object_concept_id,
                    predicate=ur.predicate,
                    predicate_label=_predicate_label(ur.predicate),
                    layer="user_established",
                    status="active",
                    origin=ur.origin,
                    explanation=ur.explanation,
                    evidence_count=max(1, ev_count),
                    relation_id=ur.id,
                    suggestion_id=ur.source_suggestion_id,
                    is_hierarchy=_is_hierarchy(ur.predicate),
                    created_at=ur.established_at,
                )
            )

    # Layer 2: world claims
    if "world" in included_layers:
        wc_rows = session.scalars(
            select(WorldClaimModel).where(
                WorldClaimModel.owner_user_id == owner_user_id,
                WorldClaimModel.created_at <= effective_time,
            )
        ).all()
        for wc in wc_rows:
            if wc.subject_concept_id not in all_concepts or wc.object_concept_id not in all_concepts:
                continue
            if predicates and wc.predicate not in predicates:
                continue
            ev_count = len(
                session.scalars(
                    select(WorldClaimEvidenceModel).where(
                        WorldClaimEvidenceModel.world_claim_id == wc.id
                    )
                ).all()
            )
            candidate_edges.append(
                GraphEdgeDTO(
                    id=f"world-claim:{wc.id}",
                    source=wc.subject_concept_id,
                    target=wc.object_concept_id,
                    predicate=wc.predicate,
                    predicate_label=_predicate_label(wc.predicate),
                    layer="world",
                    status=wc.status,
                    origin=wc.source_kind,
                    explanation=wc.claim_text,
                    evidence_count=max(1, ev_count),
                    world_claim_id=wc.id,
                    is_hierarchy=_is_hierarchy(wc.predicate),
                    created_at=wc.created_at,
                )
            )

    # Layer 3: pending suggestions
    if "suggested" in included_layers:
        sugg_rows = session.scalars(
            select(KnowledgeSuggestionModel).where(
                KnowledgeSuggestionModel.owner_user_id == owner_user_id,
                KnowledgeSuggestionModel.created_at <= effective_time,
            )
        ).all()
        for sg in sugg_rows:
            if sg.subject_concept_id not in all_concepts or sg.object_concept_id not in all_concepts:
                continue
            if predicates and sg.predicate not in predicates:
                continue
            was_pending_at_time = sg.status == SuggestionStatus.PENDING.value or (
                as_of is not None
                and sg.resolved_at is not None
                and sg.resolved_at > as_of
            )
            if not was_pending_at_time:
                continue
            ev_count = len(
                session.scalars(
                    select(SuggestionEvidenceModel).where(
                        SuggestionEvidenceModel.suggestion_id == sg.id
                    )
                ).all()
            )
            candidate_edges.append(
                GraphEdgeDTO(
                    id=f"suggestion:{sg.id}",
                    source=sg.subject_concept_id,
                    target=sg.object_concept_id,
                    predicate=sg.predicate,
                    predicate_label=_predicate_label(sg.predicate),
                    layer="suggested",
                    status="pending",
                    origin="ai_suggestion",
                    explanation=sg.explanation,
                    evidence_count=max(1, ev_count),
                    suggestion_id=sg.id,
                    is_hierarchy=_is_hierarchy(sg.predicate),
                    created_at=sg.created_at,
                )
            )

    # Neighborhood traversal from focus_concept_id if specified
    if focus_concept_id and focus_concept_id in all_concepts:
        visited = {focus_concept_id}
        frontier = {focus_concept_id}
        for _hop in range(max(1, depth)):
            next_frontier: set[str] = set()
            for e in candidate_edges:
                if e.source in frontier and e.target not in visited:
                    next_frontier.add(e.target)
                elif e.target in frontier and e.source not in visited:
                    next_frontier.add(e.source)
            visited.update(next_frontier)
            frontier = next_frontier
        selected_concept_ids = list(visited)
    else:
        selected_concept_ids = list(all_concepts.keys())

    total_candidate_nodes = len(selected_concept_ids)
    kept_concept_ids = set(selected_concept_ids[:node_limit])
    if focus_concept_id and focus_concept_id in all_concepts:
        kept_concept_ids.add(focus_concept_id)

    filtered_edges = [
        e
        for e in candidate_edges
        if e.source in kept_concept_ids and e.target in kept_concept_ids
    ]
    total_candidate_edges = len(filtered_edges)
    kept_edges = filtered_edges[:edge_limit]

    # Compute node degrees and hierarchy targets
    degree_by_id: dict[str, int] = {cid: 0 for cid in kept_concept_ids}
    hierarchy_targets: set[str] = set()
    hierarchy_sources: set[str] = set()
    neighbors_by_id: dict[str, list[str]] = {cid: [] for cid in kept_concept_ids}

    for edge in kept_edges:
        degree_by_id[edge.source] = degree_by_id.get(edge.source, 0) + 1
        degree_by_id[edge.target] = degree_by_id.get(edge.target, 0) + 1
        neighbors_by_id.setdefault(edge.source, []).append(edge.target)
        neighbors_by_id.setdefault(edge.target, []).append(edge.source)
        if edge.is_hierarchy or edge.predicate in ("is_a", "part_of", "depends_on"):
            hierarchy_targets.add(edge.target)
            hierarchy_sources.add(edge.source)

    def _infer_category(cname: str, desc: str) -> str:
        if desc.startswith("[") and "]" in desc:
            cat = desc[1 : desc.index("]")].strip()
            if cat:
                return cat
        combined = f"{cname} {desc}".lower()
        topic_rules = [
            ("Neural Networks & AI", ("neural", "backprop", "transformer", "attention", "layer", "deep learning", "network", "llm", "model")),
            ("Mathematics & Calculus", ("chain rule", "calculus", "derivative", "jacobian", "matrix", "linear", "gradient", "theorem", "equation")),
            ("Optimization & Stats", ("descent", "loss", "regularization", "bayesian", "prior", "gaussian", "overfitting", "variance", "probability")),
            ("Neuroscience & Biology", ("hebbian", "synap", "neuron", "biological", "plasticity", "brain", "cortex")),
            ("Food & Nutrition", ("apple", "pie", "food", "fruit", "recipe", "cooking", "bake", "nutrition", "ingredient")),
            ("Computer Science", ("algorithm", "database", "graph", "system", "code", "architecture", "memory", "compiler")),
            ("Physics & Systems", ("quantum", "energy", "entropy", "thermodynamics", "force", "wave", "mechanics")),
        ]
        for label, keywords in topic_rules:
            if any(k in combined for k in keywords):
                return label
        return "Core Concepts"

    raw_categories: dict[str, str] = {}
    for cid in kept_concept_ids:
        c = all_concepts[cid]
        raw_categories[cid] = _infer_category(c.canonical_name, c.description or "")

    # Propagate categories across connected neighbors if a node defaulted to "Core Concepts"
    for cid in kept_concept_ids:
        if raw_categories[cid] == "Core Concepts":
            for nb in neighbors_by_id.get(cid, []):
                if raw_categories.get(nb) and raw_categories[nb] != "Core Concepts":
                    raw_categories[cid] = raw_categories[nb]
                    break

    saved_notes_by_concept: dict[str, list[tuple[EvidenceModel, AnnotationModel]]] = {}
    if not include_unsaved and kept_concept_ids:
        saved_note_rows = session.execute(
            select(EvidenceModel, AnnotationModel, UserStateEvidenceModel.concept_id)
            .join(
                UserStateEvidenceModel,
                UserStateEvidenceModel.evidence_id == EvidenceModel.id,
            )
            .join(AnnotationModel, AnnotationModel.id == EvidenceModel.annotation_id)
            .where(
                UserStateEvidenceModel.owner_user_id == owner_user_id,
                UserStateEvidenceModel.concept_id.in_(kept_concept_ids),
                UserStateEvidenceModel.origin == SignalOrigin.EXPLICIT_ANNOTATION.value,
                UserStateEvidenceModel.review_status == ReviewStatus.CONFIRMED.value,
                AnnotationModel.owner_user_id == owner_user_id,
                AnnotationModel.created_at <= effective_time,
                or_(
                    AnnotationModel.removed_at.is_(None),
                    AnnotationModel.removed_at > effective_time,
                ),
            )
            .order_by(AnnotationModel.created_at.desc())
        ).all()
        for evidence, annotation, concept_key in saved_note_rows:
            saved_notes_by_concept.setdefault(concept_key, []).append(
                (evidence, annotation)
            )

    nodes: list[GraphNodeDTO] = []
    for cid in kept_concept_ids:
        c = all_concepts[cid]
        mentions = session.scalars(
            select(ConceptMentionModel)
            .where(
                ConceptMentionModel.concept_id == c.id,
                ConceptMentionModel.created_at <= effective_time,
            )
            .order_by(ConceptMentionModel.created_at.desc())
        ).all()
        if as_of is not None:
            signals = ConceptSignalsDTO(
                encountered=True,
                explored=c.id in replayed_explored or len(mentions) > 0,
                first_encountered_at=c.created_at,
                last_explored_at=c.updated_at if c.id in replayed_explored else None,
                self_assessment=SelfAssessment(replayed_self.get(c.id, "unknown")),
                demonstration_status=DemonstrationStatus(replayed_demo.get(c.id, "none")),
            )
        else:
            state = session.get(UserConceptStateModel, (owner_user_id, c.id))
            signals = _build_concept_signals_dto(state, len(mentions))

        top_quote = ""
        source_conv_id: str | None = None
        source_conv_title = ""
        tags: list[str] = []
        if include_unsaved:
            msg_ids = [m.message_id for m in mentions]
            if msg_ids:
                latest_msg = session.get(MessageModel, msg_ids[0])
                if latest_msg is not None:
                    top_quote = latest_msg.content[:180]
                    source_conv_id = latest_msg.conversation_id
                    conv_row = session.get(ConversationModel, latest_msg.conversation_id)
                    if conv_row is not None:
                        source_conv_title = conv_row.title
            ann_rows = session.scalars(
                select(AnnotationModel).where(
                    AnnotationModel.message_id.in_(msg_ids),
                    AnnotationModel.removed_at.is_(None),
                )
            ).all()
            for a in ann_rows:
                if a.tag not in tags:
                    tags.append(a.tag)
            displayed_note_count = len(mentions)
        else:
            saved_note_rows = saved_notes_by_concept.get(c.id, [])
            displayed_note_count = len(saved_note_rows)
            for _, annotation in saved_note_rows:
                if annotation.tag not in tags:
                    tags.append(annotation.tag)
            if saved_note_rows:
                latest_evidence, _ = saved_note_rows[0]
                top_quote = (latest_evidence.summary or latest_evidence.quote)[:180]
                latest_msg = session.get(MessageModel, latest_evidence.message_id)
                if latest_msg is not None:
                    source_conv_id = latest_msg.conversation_id
                    conv_row = session.get(ConversationModel, latest_msg.conversation_id)
                    if conv_row is not None:
                        source_conv_title = conv_row.title

        deg = degree_by_id.get(cid, 0)
        importance = round(
            1.0
            + displayed_note_count * 0.65
            + deg * 0.85
            + (1.4 if tags else 0.0),
            2,
        )
        if cid in hierarchy_targets or deg >= 3 or displayed_note_count >= 3:
            h_level = 1
        elif deg >= 1 or displayed_note_count >= 2 or tags:
            h_level = 2
        else:
            h_level = 3

        clean_desc = c.description or ""
        if clean_desc.startswith("[") and "]" in clean_desc:
            clean_desc = clean_desc[clean_desc.index("]") + 1 :].strip()

        nodes.append(
            GraphNodeDTO(
                id=c.id,
                kind="concept",
                label=c.canonical_name,
                description=clean_desc,
                category=raw_categories[cid],
                hierarchy_level=h_level,
                importance=importance,
                tags=tags,
                top_quote=top_quote,
                source_conversation_id=source_conv_id,
                source_conversation_title=source_conv_title,
                signals=signals,
                mention_count=displayed_note_count,
                open_question_count=0,
            )
        )

    # Ensure every category has at least one level-1 hub node so semantic zoom always shows cluster anchors
    by_cat: dict[str, list[GraphNodeDTO]] = {}
    for n in nodes:
        by_cat.setdefault(n.category, []).append(n)
    for _cat_name, cat_nodes in by_cat.items():
        if not any(n.hierarchy_level == 1 for n in cat_nodes):
            top_node = max(cat_nodes, key=lambda item: item.importance)
            top_node.hierarchy_level = 1

    nodes.sort(key=lambda n: (-n.importance, n.label.lower()))
    omitted_nodes = max(0, total_candidate_nodes - len(nodes))
    omitted_edges = max(0, total_candidate_edges - len(kept_edges))

    return GraphProjectionResponse(
        as_of=effective_time,
        focus_concept_id=focus_concept_id,
        nodes=nodes,
        edges=kept_edges,
        truncated=(omitted_nodes > 0 or omitted_edges > 0),
        counts=GraphCountsDTO(
            nodes=len(nodes),
            edges=len(kept_edges),
            omitted_nodes=omitted_nodes,
            omitted_edges=omitted_edges,
        ),
    )
