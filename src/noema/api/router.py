"""FastAPI /api/v1 route definitions delegating to domain services."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from noema.api.schemas import (
    AISettingsDTO,
    AnnotationCreateRequest,
    AnnotationDTO,
    AttachHypothesisEvidenceRequest,
    ConceptDetailDTO,
    ConceptEvidenceResponse,
    ConversationDTO,
    ConversationListResponse,
    CreateConversationRequest,
    CreateHypothesisRequest,
    CreateTurnRequest,
    CreateUserRelationRequest,
    EventListResponse,
    ExportResultResponse,
    GraphProjectionResponse,
    HypothesisDTO,
    HypothesisListResponse,
    KnowledgeEventDTO,
    MergeConceptRequest,
    MessageAnnotationsResponse,
    MessageListResponse,
    RelatedConceptListResponse,
    ReviseHypothesisRequest,
    SearchResponse,
    SuggestionAcceptRequest,
    SuggestionDTO,
    SuggestionListResponse,
    SuggestionRejectRequest,
    TurnAcceptedResponse,
    TurnStatusResponse,
    UpdateAISettingsRequest,
    UpdateConversationRequest,
    UserRelationDTO,
    ValidateAISettingsRequest,
    ValidateAISettingsResponse,
)
from noema.conversations.service import (
    create_conversation,
    delete_conversation,
    execute_turn,
    format_turn_sse_stream,
    get_conversation,
    get_turn_status,
    list_conversations,
    list_messages,
    retry_turn,
    stream_execute_turn,
    update_conversation,
)
from noema.knowledge.service import (
    accept_suggestion,
    add_annotation,
    attach_hypothesis_evidence,
    create_hypothesis,
    create_user_relation,
    dismiss_suggestion,
    get_concept_detail,
    get_concept_evidence,
    get_event_detail,
    get_hypothesis,
    get_related_concepts,
    get_suggestion,
    get_user_relation,
    list_events,
    list_hypotheses,
    list_message_annotations,
    list_suggestions,
    merge_concepts,
    project_knowledge_graph,
    reject_suggestion,
    remove_annotation,
    review_candidate_signal,
    revise_hypothesis,
    withdraw_user_relation,
)
from noema.ownership.service import (
    export_workspace_data,
    get_ai_settings_dto,
    update_ai_settings_dto,
    validate_ai_settings_dto,
)
from noema.persistence.db import session_scope
from noema.retrieval.service import hybrid_search
from noema.worker.runner import (
    drain_background_jobs,
    retry_failed_extraction_for_turn,
)

router = APIRouter(prefix="/api/v1")


def get_db_session() -> Generator[Session, None, None]:
    with session_scope() as session:
        yield session


@router.post("/conversations", response_model=ConversationDTO, status_code=201)
def post_conversation(
    req: CreateConversationRequest,
    session: Session = Depends(get_db_session),
) -> ConversationDTO:
    return create_conversation(session, req)


@router.get("/conversations", response_model=ConversationListResponse)
def get_conversations(
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> ConversationListResponse:
    return list_conversations(session, q=q, limit=limit)


@router.get("/conversations/{conversation_id}", response_model=ConversationDTO)
def get_conversation_by_id(
    conversation_id: str,
    session: Session = Depends(get_db_session),
) -> ConversationDTO:
    return get_conversation(session, conversation_id)


@router.patch("/conversations/{conversation_id}", response_model=ConversationDTO)
def patch_conversation(
    conversation_id: str,
    req: UpdateConversationRequest,
    session: Session = Depends(get_db_session),
) -> ConversationDTO:
    return update_conversation(session, conversation_id, req)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation_by_id(
    conversation_id: str,
    session: Session = Depends(get_db_session),
) -> Response:
    delete_conversation(session, conversation_id)
    return Response(status_code=204)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
)
def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    session: Session = Depends(get_db_session),
) -> MessageListResponse:
    return list_messages(session, conversation_id, limit=limit)


@router.post(
    "/conversations/{conversation_id}/turns",
    response_model=TurnAcceptedResponse,
    status_code=202,
)
def post_conversation_turn(
    conversation_id: str,
    req: CreateTurnRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TurnAcceptedResponse:
    result = execute_turn(
        conversation_id=conversation_id,
        req=req,
        idempotency_key=idempotency_key,
    )
    if result.extraction_status == "queued":
        background_tasks.add_task(drain_background_jobs)
    return result


@router.post("/conversations/{conversation_id}/turns/stream")
def post_conversation_turn_stream(
    conversation_id: str,
    req: CreateTurnRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> StreamingResponse:
    background_tasks.add_task(drain_background_jobs)
    return StreamingResponse(
        stream_execute_turn(
            conversation_id=conversation_id,
            req=req,
            idempotency_key=idempotency_key,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/turns/{turn_id}", response_model=TurnStatusResponse)
def get_turn(
    turn_id: str,
    session: Session = Depends(get_db_session),
) -> TurnStatusResponse:
    return get_turn_status(session, turn_id)


@router.get("/turns/{turn_id}/stream")
def stream_turn(
    turn_id: str,
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    events = list(format_turn_sse_stream(session, turn_id))
    return StreamingResponse(
        iter(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/turns/{turn_id}/retry",
    response_model=TurnAcceptedResponse,
    status_code=202,
)
def post_retry_turn(
    turn_id: str,
    background_tasks: BackgroundTasks,
) -> TurnAcceptedResponse:
    res = retry_turn(turn_id=turn_id)
    if res.extraction_status == "queued":
        background_tasks.add_task(drain_background_jobs)
    return res


@router.post("/turns/{turn_id}/retry-extraction")
def post_retry_turn_extraction(
    turn_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db_session),
) -> dict[str, str]:
    status = retry_failed_extraction_for_turn(session, turn_id)
    if status == "queued":
        background_tasks.add_task(drain_background_jobs, None, 10, True)
    return {"turn_id": turn_id, "extraction_status": status}


@router.post(
    "/messages/{message_id}/annotations",
    response_model=AnnotationDTO,
    status_code=201,
)
def post_message_annotation(
    message_id: str,
    req: AnnotationCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(get_db_session),
) -> AnnotationDTO:
    return add_annotation(
        session,
        message_id=message_id,
        req=req,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/messages/{message_id}/annotations",
    response_model=MessageAnnotationsResponse,
)
def get_message_annotations(
    message_id: str,
    session: Session = Depends(get_db_session),
) -> MessageAnnotationsResponse:
    return list_message_annotations(session, message_id)


@router.delete("/annotations/{annotation_id}", status_code=204)
def delete_annotation_by_id(
    annotation_id: str,
    session: Session = Depends(get_db_session),
) -> Response:
    remove_annotation(session, annotation_id)
    return Response(status_code=204)


@router.get("/knowledge/graph", response_model=GraphProjectionResponse)
def get_knowledge_graph(
    focus_concept_id: str | None = Query(default=None),
    depth: int = Query(default=2, ge=1, le=4),
    node_limit: int = Query(default=80, ge=1, le=300),
    edge_limit: int = Query(default=120, ge=1, le=500),
    layers: str | None = Query(default=None),
    predicates: str | None = Query(default=None),
    as_of: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> GraphProjectionResponse:
    layer_set = (
        {item.strip() for item in layers.split(",") if item.strip()}
        if layers
        else None
    )
    predicate_set = (
        {item.strip() for item in predicates.split(",") if item.strip()}
        if predicates
        else None
    )
    return project_knowledge_graph(
        session,
        focus_concept_id=focus_concept_id,
        depth=depth,
        node_limit=node_limit,
        edge_limit=edge_limit,
        layers=layer_set,
        predicates=predicate_set,
        as_of=as_of,
    )


@router.get("/concepts/{concept_id}", response_model=ConceptDetailDTO)
def get_concept(
    concept_id: str,
    session: Session = Depends(get_db_session),
) -> ConceptDetailDTO:
    return get_concept_detail(session, concept_id)


@router.get("/concepts/{concept_id}/evidence", response_model=ConceptEvidenceResponse)
def get_concept_evidence_route(
    concept_id: str,
    session: Session = Depends(get_db_session),
) -> ConceptEvidenceResponse:
    return get_concept_evidence(session, concept_id)


@router.get(
    "/concepts/{concept_id}/related", response_model=RelatedConceptListResponse
)
def get_concept_related_route(
    concept_id: str,
    session: Session = Depends(get_db_session),
) -> RelatedConceptListResponse:
    return get_related_concepts(session, concept_id)


@router.get("/concepts/{concept_id}/history", response_model=EventListResponse)
def get_concept_history_route(
    concept_id: str,
    before: str | None = Query(default=None),
    after: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    session: Session = Depends(get_db_session),
) -> EventListResponse:
    return list_events(
        session, concept_id=concept_id, before=before, after=after, limit=limit
    )


@router.post(
    "/concepts/{concept_id}/relations",
    response_model=UserRelationDTO,
    status_code=201,
)
def post_concept_relation(
    concept_id: str,
    req: CreateUserRelationRequest,
    session: Session = Depends(get_db_session),
) -> UserRelationDTO:
    return create_user_relation(session, concept_id, req)


@router.post("/concepts/{concept_id}/merge", response_model=ConceptDetailDTO)
def post_concept_merge(
    concept_id: str,
    req: MergeConceptRequest,
    session: Session = Depends(get_db_session),
) -> ConceptDetailDTO:
    return merge_concepts(session, concept_id, req)


@router.post(
    "/concepts/{concept_id}/signals/{evidence_id}/review",
    response_model=ConceptDetailDTO,
)
def post_review_candidate_signal(
    concept_id: str,
    evidence_id: str,
    action: str = Query(pattern="^(confirm|dismiss)$"),
    session: Session = Depends(get_db_session),
) -> ConceptDetailDTO:
    return review_candidate_signal(
        session, concept_id=concept_id, evidence_id=evidence_id, action=action
    )


@router.get("/hypotheses", response_model=HypothesisListResponse)
def get_hypotheses_route(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> HypothesisListResponse:
    return list_hypotheses(session, status=status, limit=limit)


@router.post(
    "/messages/{message_id}/hypotheses",
    response_model=HypothesisDTO,
    status_code=201,
)
def post_message_hypothesis(
    message_id: str,
    req: CreateHypothesisRequest,
    session: Session = Depends(get_db_session),
) -> HypothesisDTO:
    return create_hypothesis(session, message_id=message_id, req=req)


@router.get("/hypotheses/{hypothesis_id}", response_model=HypothesisDTO)
def get_hypothesis_route(
    hypothesis_id: str,
    session: Session = Depends(get_db_session),
) -> HypothesisDTO:
    return get_hypothesis(session, hypothesis_id)


@router.post("/hypotheses/{hypothesis_id}/revise", response_model=HypothesisDTO)
def post_revise_hypothesis(
    hypothesis_id: str,
    req: ReviseHypothesisRequest,
    session: Session = Depends(get_db_session),
) -> HypothesisDTO:
    return revise_hypothesis(session, hypothesis_id=hypothesis_id, req=req)


@router.post("/hypotheses/{hypothesis_id}/evidence", response_model=HypothesisDTO)
def post_hypothesis_evidence(
    hypothesis_id: str,
    req: AttachHypothesisEvidenceRequest,
    session: Session = Depends(get_db_session),
) -> HypothesisDTO:
    return attach_hypothesis_evidence(
        session, hypothesis_id=hypothesis_id, req=req
    )


@router.get("/suggestions", response_model=SuggestionListResponse)
def get_suggestions_route(
    status: str | None = Query(default="pending"),
    concept_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> SuggestionListResponse:
    return list_suggestions(
        session, status=status, concept_id=concept_id, limit=limit
    )


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionDTO)
def get_suggestion_route(
    suggestion_id: str,
    session: Session = Depends(get_db_session),
) -> SuggestionDTO:
    return get_suggestion(session, suggestion_id)


@router.post("/suggestions/{suggestion_id}/accept", response_model=UserRelationDTO)
def post_accept_suggestion(
    suggestion_id: str,
    req: SuggestionAcceptRequest | None = None,
    session: Session = Depends(get_db_session),
) -> UserRelationDTO:
    return accept_suggestion(session, suggestion_id, req)


@router.post("/suggestions/{suggestion_id}/reject", response_model=SuggestionDTO)
def post_reject_suggestion(
    suggestion_id: str,
    req: SuggestionRejectRequest | None = None,
    session: Session = Depends(get_db_session),
) -> SuggestionDTO:
    return reject_suggestion(session, suggestion_id, req)


@router.post("/suggestions/{suggestion_id}/dismiss", response_model=SuggestionDTO)
def post_dismiss_suggestion(
    suggestion_id: str,
    session: Session = Depends(get_db_session),
) -> SuggestionDTO:
    return dismiss_suggestion(session, suggestion_id)


@router.get("/relations/{relation_id}", response_model=UserRelationDTO)
def get_relation_route(
    relation_id: str,
    session: Session = Depends(get_db_session),
) -> UserRelationDTO:
    return get_user_relation(session, relation_id)


@router.post("/relations/{relation_id}/withdraw", response_model=UserRelationDTO)
def post_withdraw_relation(
    relation_id: str,
    session: Session = Depends(get_db_session),
) -> UserRelationDTO:
    return withdraw_user_relation(session, relation_id)


@router.get("/search", response_model=SearchResponse)
def get_search_route(
    q: str = Query(default=""),
    kind: str | None = Query(default=None),
    after: str | None = Query(default=None),
    before: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_db_session),
) -> SearchResponse:
    return hybrid_search(
        session, query=q, kind=kind, after=after, before=before, limit=limit
    )


@router.get("/events", response_model=EventListResponse)
def get_events_route(
    concept_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    after: str | None = Query(default=None),
    before: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    session: Session = Depends(get_db_session),
) -> EventListResponse:
    return list_events(
        session,
        concept_id=concept_id,
        event_type=event_type,
        after=after,
        before=before,
        limit=limit,
    )


@router.get("/events/{event_id}", response_model=KnowledgeEventDTO)
def get_event_route(
    event_id: str,
    session: Session = Depends(get_db_session),
) -> KnowledgeEventDTO:
    return get_event_detail(session, event_id)


@router.get("/settings/ai", response_model=AISettingsDTO)
def get_ai_settings_route(
    session: Session = Depends(get_db_session),
) -> AISettingsDTO:
    return get_ai_settings_dto(session)


@router.put("/settings/ai", response_model=AISettingsDTO)
def put_ai_settings_route(
    req: UpdateAISettingsRequest,
    session: Session = Depends(get_db_session),
) -> AISettingsDTO:
    return update_ai_settings_dto(session, req)


@router.post("/settings/ai/validate", response_model=ValidateAISettingsResponse)
def post_validate_ai_settings_route(
    req: ValidateAISettingsRequest,
) -> ValidateAISettingsResponse:
    return validate_ai_settings_dto(req)


@router.post("/export", response_model=ExportResultResponse)
def post_export_route(
    session: Session = Depends(get_db_session),
) -> ExportResultResponse:
    return export_workspace_data(session)


@router.post("/worker/drain")
def post_worker_drain() -> dict[str, Any]:
    processed = drain_background_jobs(force_ready=True)
    return {"processed_jobs": processed}
