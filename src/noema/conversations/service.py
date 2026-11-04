"""Conversations domain service: conversations, immutable messages, turns, and SSE streaming."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from noema.ai.gateway import (
    PROMPT_VERSION_CHAT,
    ProviderError,
    complete_chat,
    stream_chat_tokens,
)
from noema.api.schemas import (
    AnnotationCreateRequest,
    AnnotationDTO,
    ConceptMentionBriefDTO,
    ConversationDTO,
    ConversationListResponse,
    CreateConversationRequest,
    CreateTurnRequest,
    MessageDTO,
    MessageListResponse,
    SourceReferenceDTO,
    TurnAcceptedResponse,
    TurnStatusResponse,
    UpdateConversationRequest,
)
from noema.config import DEFAULT_OWNER_USER_ID
from noema.domain.vocabulary import parse_command_tags
from noema.knowledge.service import _to_annotation_dto, add_annotation
from noema.persistence.db import new_id, session_scope, utc_now_iso
from noema.persistence.models import (
    AISettingsModel,
    AnnotationModel,
    ConceptMentionModel,
    ConceptModel,
    ConversationModel,
    GenerationRunModel,
    MessageModel,
    SearchDocumentModel,
)
from noema.retrieval.service import (
    build_turn_context,
    cleanup_fts_for_document_ids,
    index_message_documents,
)
from noema.worker.runner import (
    enqueue_turn_jobs,
    get_turn_extraction_status,
)


def _sha256_text(text_val: str) -> str:
    return hashlib.sha256(text_val.encode("utf-8")).hexdigest()


def _to_conversation_dto(
    session: Session, conv: ConversationModel
) -> ConversationDTO:
    latest_run = session.scalar(
        select(GenerationRunModel)
        .where(GenerationRunModel.conversation_id == conv.id)
        .order_by(GenerationRunModel.created_at.desc())
        .limit(1)
    )
    latest_turn_status = latest_run.status if latest_run else None
    extraction_status = None
    if latest_run is not None:
        extraction_status, _err = get_turn_extraction_status(session, latest_run.id)

    return ConversationDTO(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        archived_at=conv.archived_at,
        latest_turn_status=latest_turn_status,
        extraction_status=extraction_status,
    )


def _to_message_dto(session: Session, msg: MessageModel) -> MessageDTO:
    anns = session.scalars(
        select(AnnotationModel)
        .where(
            AnnotationModel.message_id == msg.id,
            AnnotationModel.removed_at.is_(None),
        )
        .order_by(AnnotationModel.created_at.asc())
    ).all()
    ann_dtos = [_to_annotation_dto(session, a) for a in anns]

    mentions = session.scalars(
        select(ConceptMentionModel)
        .where(ConceptMentionModel.message_id == msg.id)
        .order_by(ConceptMentionModel.start_offset.asc())
    ).all()
    mention_dtos: list[ConceptMentionBriefDTO] = []
    for m in mentions:
        c = session.get(ConceptModel, m.concept_id)
        if c is not None:
            mention_dtos.append(
                ConceptMentionBriefDTO(
                    id=m.id,
                    concept_id=c.id,
                    canonical_name=c.canonical_name,
                    surface_text=m.surface_text,
                    start_offset=m.start_offset,
                    end_offset=m.end_offset,
                    resolution=m.resolution,
                )
            )

    raw_sources = json.loads(msg.sources_json or "[]")
    sources = [SourceReferenceDTO(**s) for s in raw_sources]

    return MessageDTO(
        id=msg.id,
        conversation_id=msg.conversation_id,
        sequence_no=msg.sequence_no,
        role=msg.role,  # type: ignore[arg-type]
        content=msg.content,
        created_at=msg.created_at,
        reply_to_message_id=msg.reply_to_message_id,
        provider=msg.provider,
        model=msg.model,
        annotations=ann_dtos,
        mentions=mention_dtos,
        sources=sources,
    )


def create_conversation(
    session: Session,
    req: CreateConversationRequest,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> ConversationDTO:
    now = utc_now_iso()
    title = req.title.strip() or "New Exploration"
    conv = ConversationModel(
        id=new_id("conv"),
        owner_user_id=owner_user_id,
        title=title,
        created_at=now,
        updated_at=now,
        archived_at=None,
    )
    session.add(conv)
    session.flush()
    return _to_conversation_dto(session, conv)


def list_conversations(
    session: Session,
    *,
    q: str | None = None,
    limit: int = 50,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> ConversationListResponse:
    stmt = select(ConversationModel).where(
        ConversationModel.owner_user_id == owner_user_id,
        ConversationModel.archived_at.is_(None),
    )
    if q and q.strip():
        stmt = stmt.where(ConversationModel.title.ilike(f"%{q.strip()}%"))
    stmt = stmt.order_by(ConversationModel.updated_at.desc()).limit(limit)
    rows = session.scalars(stmt).all()
    return ConversationListResponse(
        items=[_to_conversation_dto(session, r) for r in rows],
        next_cursor=None,
    )


def get_conversation(
    session: Session,
    conversation_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> ConversationDTO:
    conv = session.get(ConversationModel, conversation_id)
    if conv is None or conv.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "conversation_not_found",
                "message": f"Conversation '{conversation_id}' not found.",
                "details": {},
            },
        )
    return _to_conversation_dto(session, conv)


def update_conversation(
    session: Session,
    conversation_id: str,
    req: UpdateConversationRequest,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> ConversationDTO:
    conv = session.get(ConversationModel, conversation_id)
    if conv is None or conv.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "conversation_not_found",
                "message": f"Conversation '{conversation_id}' not found.",
                "details": {},
            },
        )
    now = utc_now_iso()
    if req.title is not None:
        conv.title = req.title.strip() or conv.title
    if req.archived is True:
        conv.archived_at = now
    elif req.archived is False:
        conv.archived_at = None
    conv.updated_at = now
    session.flush()
    return _to_conversation_dto(session, conv)


def delete_conversation(
    session: Session,
    conversation_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> None:
    """Delete conversation and all dependent search documents, FTS entries, embeddings, mentions, and messages."""
    conv = session.get(ConversationModel, conversation_id)
    if conv is None or conv.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "conversation_not_found",
                "message": f"Conversation '{conversation_id}' not found.",
                "details": {},
            },
        )
    msg_ids = list(
        session.scalars(
            select(MessageModel.id).where(
                MessageModel.conversation_id == conversation_id
            )
        ).all()
    )
    if msg_ids:
        doc_ids = list(
            session.scalars(
                select(SearchDocumentModel.id).where(
                    SearchDocumentModel.message_id.in_(msg_ids)
                )
            ).all()
        )
        cleanup_fts_for_document_ids(session, doc_ids)

    session.delete(conv)
    session.flush()


def list_messages(
    session: Session,
    conversation_id: str,
    limit: int = 200,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> MessageListResponse:
    conv = session.get(ConversationModel, conversation_id)
    if conv is None or conv.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "conversation_not_found",
                "message": f"Conversation '{conversation_id}' not found.",
                "details": {},
            },
        )
    rows = session.scalars(
        select(MessageModel)
        .where(MessageModel.conversation_id == conversation_id)
        .order_by(MessageModel.sequence_no.asc())
        .limit(limit)
    ).all()
    return MessageListResponse(
        items=[_to_message_dto(session, r) for r in rows],
        next_cursor=None,
    )


def execute_turn(
    *,
    conversation_id: str,
    req: CreateTurnRequest,
    idempotency_key: str | None = None,
    database_url: str | None = None,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> TurnAcceptedResponse:
    """Execute a conversation turn while keeping LLM generation outside any DB transaction."""
    # Check idempotency or bare #command first
    with session_scope(database_url) as session:
        conv = session.get(ConversationModel, conversation_id)
        if conv is None or conv.owner_user_id != owner_user_id:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "conversation_not_found",
                    "message": f"Conversation '{conversation_id}' not found.",
                    "details": {},
                },
            )

        if idempotency_key:
            existing_run = session.scalar(
                select(GenerationRunModel).where(
                    GenerationRunModel.owner_user_id == owner_user_id,
                    GenerationRunModel.idempotency_key == idempotency_key,
                )
            )
            if existing_run is not None:
                um = session.get(MessageModel, existing_run.user_message_id)
                am = (
                    session.get(MessageModel, existing_run.assistant_message_id)
                    if existing_run.assistant_message_id
                    else None
                )
                ext_status, _ = get_turn_extraction_status(session, existing_run.id)
                return TurnAcceptedResponse(
                    turn_id=existing_run.id,
                    status=existing_run.status,
                    user_message=_to_message_dto(session, um),  # type: ignore[arg-type]
                    assistant_message=_to_message_dto(session, am) if am else None,
                    assistant_message_id=existing_run.assistant_message_id,
                    stream_url=f"/api/v1/turns/{existing_run.id}/stream",
                    extraction_status=ext_status,
                )

        parsed_cmd = parse_command_tags(req.content)

        # Targeting rule for bare standalone #command (e.g. `#aha`):
        # Apply immediately to the most recent prior message in the conversation without requiring a dialog
        if parsed_cmd.is_bare_command_only and parsed_cmd.tags:
            prior_msg = session.scalar(
                select(MessageModel)
                .where(MessageModel.conversation_id == conversation_id)
                .order_by(MessageModel.sequence_no.desc())
                .limit(1)
            )
            if prior_msg is not None:
                applied: list[AnnotationDTO] = []
                for tag in parsed_cmd.tags:
                    ann_dto = add_annotation(
                        session,
                        message_id=prior_msg.id,
                        req=AnnotationCreateRequest(tag=tag, span=None),
                        owner_user_id=owner_user_id,
                    )
                    applied.append(ann_dto)
                session.flush()
                return TurnAcceptedResponse(
                    turn_id=f"cmd_{new_id()}",
                    status="succeeded",
                    user_message=_to_message_dto(session, prior_msg),
                    assistant_message=None,
                    assistant_message_id=None,
                    stream_url="",
                    extraction_status="not_required",
                    applied_annotations=applied,
                    targeted_message_id=prior_msg.id,
                )

        # Transaction 1: persist user message + pending generation run + retrieve personal context
        max_seq = (
            session.scalar(
                select(func.max(MessageModel.sequence_no)).where(
                    MessageModel.conversation_id == conversation_id
                )
            )
            or 0
        )
        prev_msg = session.scalar(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.sequence_no.desc())
            .limit(1)
        )
        now = utc_now_iso()
        user_msg = MessageModel(
            id=new_id("msg"),
            conversation_id=conversation_id,
            sequence_no=max_seq + 1,
            role="user",
            content=req.content,
            created_at=now,
            reply_to_message_id=prev_msg.id if prev_msg else None,
            provider=None,
            model=None,
            content_hash=_sha256_text(req.content),
            sources_json="[]",
        )
        session.add(user_msg)
        if conv.title in ("", "New Exploration"):
            short_title = req.content.strip().split("\n")[0][:56]
            conv.title = short_title
        conv.updated_at = now
        session.flush()

        # Index user message chunks immediately for lexical search
        index_message_documents(
            session, user_msg, owner_user_id=owner_user_id, create_embeddings=False
        )

        # Apply any inline #commands (such as `I think I get it... #aha`) directly to the user message
        applied_inline: list[AnnotationDTO] = []
        for tag in parsed_cmd.tags:
            ann_dto = add_annotation(
                session,
                message_id=user_msg.id,
                req=AnnotationCreateRequest(tag=tag, span=None),
                owner_user_id=owner_user_id,
            )
            applied_inline.append(ann_dto)

        ai_cfg = session.get(AISettingsModel, owner_user_id)
        chat_provider = (
            ai_cfg.conversation_provider if ai_cfg else "local_heuristic"
        )
        chat_model = ai_cfg.conversation_model if ai_cfg else "noema-local-chat-v1"
        hosted_consent = bool(ai_cfg.hosted_data_consent) if ai_cfg else False
        local_url = (
            ai_cfg.local_endpoint_url
            if ai_cfg
            else "http://127.0.0.1:11434/v1"
        )
        budget = ai_cfg.context_budget_tokens if ai_cfg else 1600

        retrieved_context = (
            build_turn_context(
                session,
                query=req.content,
                current_conversation_id=conversation_id,
                budget_tokens=budget,
                owner_user_id=owner_user_id,
            )
            if req.context_mode == "personalized"
            else []
        )

        prior_rows = session.scalars(
            select(MessageModel)
            .where(
                MessageModel.conversation_id == conversation_id,
                MessageModel.id != user_msg.id,
            )
            .order_by(MessageModel.sequence_no.asc())
        ).all()
        prior_messages = [
            {"role": r.role, "content": r.content} for r in prior_rows[-10:]
        ]

        gen_run = GenerationRunModel(
            id=new_id("turn"),
            owner_user_id=owner_user_id,
            conversation_id=conversation_id,
            user_message_id=user_msg.id,
            assistant_message_id=None,
            status="running",
            provider=chat_provider,
            model=chat_model,
            prompt_version=PROMPT_VERSION_CHAT,
            context_mode=req.context_mode,
            idempotency_key=idempotency_key,
            error_code=None,
            error_message=None,
            sources_json="[]",
            created_at=now,
            updated_at=now,
            finished_at=None,
        )
        session.add(gen_run)
        session.flush()
        turn_id = gen_run.id
        user_msg_id = user_msg.id

    # External LLM call outside DB transaction!
    try:
        gen_result = complete_chat(
            provider=chat_provider,
            model=chat_model,
            user_content=req.content,
            prior_messages=prior_messages,
            retrieved_context=retrieved_context,
            hosted_data_consent=hosted_consent,
            local_endpoint_url=local_url,
        )
    except ProviderError as exc:
        with session_scope(database_url) as session:
            run = session.get(GenerationRunModel, turn_id)
            if run is not None:
                fin = utc_now_iso()
                run.status = "failed"
                run.error_code = exc.code
                run.error_message = exc.message
                run.updated_at = fin
                run.finished_at = fin
            um = session.get(MessageModel, user_msg_id)
            return TurnAcceptedResponse(
                turn_id=turn_id,
                status="failed",
                user_message=_to_message_dto(session, um),  # type: ignore[arg-type]
                assistant_message=None,
                assistant_message_id=None,
                stream_url=f"/api/v1/turns/{turn_id}/stream",
                extraction_status="not_queued",
                applied_annotations=applied_inline,
                targeted_message_id=user_msg_id if applied_inline else None,
            )

    # Transaction 2: save assistant message + mark run complete + enqueue durable extraction/embedding jobs
    with session_scope(database_url) as session:
        run = session.get(GenerationRunModel, turn_id)
        um = session.get(MessageModel, user_msg_id)
        conv = session.get(ConversationModel, conversation_id)
        if run is None or um is None or conv is None:
            raise RuntimeError("Turn state vanished unexpectedly.")

        fin = utc_now_iso()
        sources_payload = [
            {
                "source_id": item.source_id,
                "kind": item.kind,
                "message_id": item.message_id,
                "conversation_id": item.conversation_id,
                "concept_id": item.concept_id,
                "role": item.role,
                "excerpt": item.excerpt,
                "created_at": item.created_at,
                "reason": item.reason,
            }
            for item in gen_result.used_sources
        ]
        sources_json_str = json.dumps(sources_payload)

        asst_msg = MessageModel(
            id=new_id("msg"),
            conversation_id=conversation_id,
            sequence_no=um.sequence_no + 1,
            role="assistant",
            content=gen_result.content,
            created_at=fin,
            reply_to_message_id=um.id,
            provider=gen_result.provider,
            model=gen_result.model,
            content_hash=_sha256_text(gen_result.content),
            sources_json=sources_json_str,
        )
        session.add(asst_msg)
        session.flush()

        index_message_documents(
            session, asst_msg, owner_user_id=owner_user_id, create_embeddings=False
        )

        run.assistant_message_id = asst_msg.id
        run.status = "succeeded"
        run.sources_json = sources_json_str
        run.updated_at = fin
        run.finished_at = fin
        conv.updated_at = fin

        enqueue_turn_jobs(
            session,
            generation_run_id=run.id,
            conversation_id=conversation_id,
            user_message_id=um.id,
            assistant_message_id=asst_msg.id,
            owner_user_id=owner_user_id,
        )
        session.flush()

        return TurnAcceptedResponse(
            turn_id=run.id,
            status=run.status,
            user_message=_to_message_dto(session, um),
            assistant_message=_to_message_dto(session, asst_msg),
            assistant_message_id=asst_msg.id,
            stream_url=f"/api/v1/turns/{run.id}/stream",
            extraction_status="queued",
            applied_annotations=applied_inline,
            targeted_message_id=um.id if applied_inline else None,
        )


def retry_turn(
    *,
    turn_id: str,
    database_url: str | None = None,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> TurnAcceptedResponse:
    """Retry a failed generation using the existing user message without duplicating it."""
    with session_scope(database_url) as session:
        run = session.get(GenerationRunModel, turn_id)
        if run is None or run.owner_user_id != owner_user_id:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "turn_not_found",
                    "message": f"Turn '{turn_id}' not found.",
                    "details": {},
                },
            )
        um = session.get(MessageModel, run.user_message_id)
        if um is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "message_not_found",
                    "message": "User message for turn not found.",
                    "details": {},
                },
            )
        if run.status == "succeeded" and run.assistant_message_id:
            am = session.get(MessageModel, run.assistant_message_id)
            ext_status, _ = get_turn_extraction_status(session, run.id)
            return TurnAcceptedResponse(
                turn_id=run.id,
                status=run.status,
                user_message=_to_message_dto(session, um),
                assistant_message=_to_message_dto(session, am) if am else None,
                assistant_message_id=run.assistant_message_id,
                stream_url=f"/api/v1/turns/{run.id}/stream",
                extraction_status=ext_status,
            )

        ai_cfg = session.get(AISettingsModel, owner_user_id)
        chat_provider = (
            ai_cfg.conversation_provider if ai_cfg else "local_heuristic"
        )
        chat_model = ai_cfg.conversation_model if ai_cfg else "noema-local-chat-v1"
        hosted_consent = bool(ai_cfg.hosted_data_consent) if ai_cfg else False
        local_url = (
            ai_cfg.local_endpoint_url
            if ai_cfg
            else "http://127.0.0.1:11434/v1"
        )
        budget = ai_cfg.context_budget_tokens if ai_cfg else 1600
        conversation_id = run.conversation_id
        user_content = um.content
        user_msg_id = um.id

        # Strip simulated error marker on retry if user is testing recovery, or use current configured provider
        effective_content = user_content.replace("[simulate_chat_error]", "").strip() or user_content

        retrieved_context = (
            build_turn_context(
                session,
                query=effective_content,
                current_conversation_id=conversation_id,
                budget_tokens=budget,
                owner_user_id=owner_user_id,
            )
            if run.context_mode == "personalized"
            else []
        )
        prior_rows = session.scalars(
            select(MessageModel)
            .where(
                MessageModel.conversation_id == conversation_id,
                MessageModel.sequence_no < um.sequence_no,
            )
            .order_by(MessageModel.sequence_no.asc())
        ).all()
        prior_messages = [
            {"role": r.role, "content": r.content} for r in prior_rows[-10:]
        ]
        run.status = "running"
        run.provider = chat_provider
        run.model = chat_model
        run.error_code = None
        run.error_message = None
        run.updated_at = utc_now_iso()

    try:
        gen_result = complete_chat(
            provider=chat_provider,
            model=chat_model,
            user_content=effective_content,
            prior_messages=prior_messages,
            retrieved_context=retrieved_context,
            hosted_data_consent=hosted_consent,
            local_endpoint_url=local_url,
        )
    except ProviderError as exc:
        with session_scope(database_url) as session:
            run = session.get(GenerationRunModel, turn_id)
            um = session.get(MessageModel, user_msg_id)
            if run is not None:
                fin = utc_now_iso()
                run.status = "failed"
                run.error_code = exc.code
                run.error_message = exc.message
                run.updated_at = fin
                run.finished_at = fin
            return TurnAcceptedResponse(
                turn_id=turn_id,
                status="failed",
                user_message=_to_message_dto(session, um),  # type: ignore[arg-type]
                assistant_message=None,
                assistant_message_id=None,
                stream_url=f"/api/v1/turns/{turn_id}/stream",
                extraction_status="not_queued",
            )

    with session_scope(database_url) as session:
        run = session.get(GenerationRunModel, turn_id)
        um = session.get(MessageModel, user_msg_id)
        conv = session.get(ConversationModel, conversation_id)
        if run is None or um is None or conv is None:
            raise RuntimeError("Turn vanished during retry.")

        fin = utc_now_iso()
        sources_payload = [
            {
                "source_id": item.source_id,
                "kind": item.kind,
                "message_id": item.message_id,
                "conversation_id": item.conversation_id,
                "concept_id": item.concept_id,
                "role": item.role,
                "excerpt": item.excerpt,
                "created_at": item.created_at,
                "reason": item.reason,
            }
            for item in gen_result.used_sources
        ]
        sources_json_str = json.dumps(sources_payload)

        max_seq = (
            session.scalar(
                select(func.max(MessageModel.sequence_no)).where(
                    MessageModel.conversation_id == conversation_id
                )
            )
            or um.sequence_no
        )
        asst_msg = MessageModel(
            id=new_id("msg"),
            conversation_id=conversation_id,
            sequence_no=max_seq + 1,
            role="assistant",
            content=gen_result.content,
            created_at=fin,
            reply_to_message_id=um.id,
            provider=gen_result.provider,
            model=gen_result.model,
            content_hash=_sha256_text(gen_result.content),
            sources_json=sources_json_str,
        )
        session.add(asst_msg)
        session.flush()
        index_message_documents(
            session, asst_msg, owner_user_id=owner_user_id, create_embeddings=False
        )

        run.assistant_message_id = asst_msg.id
        run.status = "succeeded"
        run.sources_json = sources_json_str
        run.updated_at = fin
        run.finished_at = fin
        conv.updated_at = fin

        enqueue_turn_jobs(
            session,
            generation_run_id=run.id,
            conversation_id=conversation_id,
            user_message_id=um.id,
            assistant_message_id=asst_msg.id,
            owner_user_id=owner_user_id,
        )
        session.flush()

        return TurnAcceptedResponse(
            turn_id=run.id,
            status=run.status,
            user_message=_to_message_dto(session, um),
            assistant_message=_to_message_dto(session, asst_msg),
            assistant_message_id=asst_msg.id,
            stream_url=f"/api/v1/turns/{run.id}/stream",
            extraction_status="queued",
        )


def get_turn_status(
    session: Session,
    turn_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> TurnStatusResponse:
    run = session.get(GenerationRunModel, turn_id)
    if run is None or run.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "turn_not_found",
                "message": f"Turn '{turn_id}' not found.",
                "details": {},
            },
        )
    ext_status, ext_err = get_turn_extraction_status(session, run.id)
    raw_sources = json.loads(run.sources_json or "[]")
    return TurnStatusResponse(
        turn_id=run.id,
        conversation_id=run.conversation_id,
        status=run.status,
        user_message_id=run.user_message_id,
        assistant_message_id=run.assistant_message_id,
        provider=run.provider,
        model=run.model,
        prompt_version=run.prompt_version,
        error_code=run.error_code,
        error_message=run.error_message,
        sources=[SourceReferenceDTO(**s) for s in raw_sources],
        extraction_status=ext_status,
        extraction_error_code=ext_err,
        created_at=run.created_at,
        finished_at=run.finished_at,
    )


def format_turn_sse_stream(
    session: Session,
    turn_id: str,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> Iterator[str]:
    status_dto = get_turn_status(session, turn_id, owner_user_id=owner_user_id)
    yield f"id: 1\nevent: turn.started\ndata: {json.dumps({'turn_id': turn_id, 'status': status_dto.status})}\n\n"

    if status_dto.status == "failed":
        yield (
            f"id: 2\nevent: turn.failed\ndata: "
            f"{json.dumps({'turn_id': turn_id, 'error_code': status_dto.error_code, 'message': status_dto.error_message})}\n\n"
        )
        return

    if status_dto.assistant_message_id:
        am = session.get(MessageModel, status_dto.assistant_message_id)
        if am is not None:
            ev_id = 2
            for delta in stream_chat_tokens(am.content):
                yield f"id: {ev_id}\nevent: assistant.delta\ndata: {json.dumps({'delta': delta})}\n\n"
                ev_id += 1
            msg_dto = _to_message_dto(session, am)
            yield f"id: {ev_id}\nevent: assistant.message\ndata: {msg_dto.model_dump_json()}\n\n"
            ev_id += 1
            completed_payload = {
                "turn_id": turn_id,
                "assistant_message_id": am.id,
                "provider": status_dto.provider,
                "model": status_dto.model,
                "sources": [s.model_dump() for s in status_dto.sources],
                "extraction_status": status_dto.extraction_status,
            }
            yield f"id: {ev_id}\nevent: turn.completed\ndata: {json.dumps(completed_payload)}\n\n"
            ev_id += 1
            yield (
                f"id: {ev_id}\nevent: knowledge.status\ndata: "
                f"{json.dumps({'turn_id': turn_id, 'extraction_status': status_dto.extraction_status})}\n\n"
            )
