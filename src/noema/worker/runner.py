"""Durable SQLite-backed background job runner with leases, bounded retries, and idempotency."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select

from noema.ai.gateway import (
    PROMPT_VERSION_EXTRACTION,
    SCHEMA_VERSION_EXTRACTION,
    ProviderError,
    extract_structured,
)
from noema.config import DEFAULT_OWNER_USER_ID
from noema.knowledge.service import apply_extraction_proposal
from noema.persistence.db import new_id, session_scope, utc_now_iso
from noema.persistence.models import (
    AISettingsModel,
    BackgroundJobModel,
    ConceptModel,
    ExtractionRunModel,
    GenerationRunModel,
    MessageModel,
)
from noema.retrieval.service import index_message_documents

MAX_JOB_ATTEMPTS = 3
LEASE_DURATION_SECONDS = 30


def _iso_after_seconds(seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def enqueue_turn_jobs(
    session: Any,
    *,
    generation_run_id: str,
    conversation_id: str,
    user_message_id: str,
    assistant_message_id: str | None,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> list[BackgroundJobModel]:
    """Enqueue extraction and embedding jobs in the same DB transaction as turn completion."""
    now = utc_now_iso()
    payload = json.dumps(
        {
            "conversation_id": conversation_id,
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
        }
    )
    created: list[BackgroundJobModel] = []
    for kind in ("knowledge_extraction", "embedding"):
        idem_key = f"{kind}:{generation_run_id}:{PROMPT_VERSION_EXTRACTION}"
        existing = session.scalar(
            select(BackgroundJobModel).where(
                BackgroundJobModel.idempotency_key == idem_key
            )
        )
        if existing is not None:
            created.append(existing)
            continue
        job = BackgroundJobModel(
            id=new_id("job"),
            owner_user_id=owner_user_id,
            job_kind=kind,
            source_generation_run_id=generation_run_id,
            payload_json=payload,
            status="queued",
            idempotency_key=idem_key,
            attempt_count=0,
            lease_owner=None,
            lease_expires_at=None,
            available_at=now,
            error_code=None,
            created_at=now,
            updated_at=now,
            finished_at=None,
        )
        session.add(job)
        created.append(job)
    return created


def process_next_background_job(
    database_url: str | None = None,
    worker_id: str = "local-worker-1",
) -> bool:
    """Claim one eligible background job, run external work outside DB tx, and commit result."""
    now = utc_now_iso()
    claimed_job_id: str | None = None
    job_kind: str = ""
    owner_user_id: str = DEFAULT_OWNER_USER_ID
    payload: dict[str, Any] = {}
    extraction_provider = "local_heuristic"
    extraction_model = "noema-local-extractor-v1"
    local_endpoint_url = "http://127.0.0.1:11434/v1"
    user_msg_dict: dict[str, Any] | None = None
    asst_msg_dict: dict[str, Any] | None = None
    existing_concepts: dict[str, tuple[str, str]] = {}
    extraction_run_id: str | None = None

    # Short transaction 1: claim lease and load immutable inputs
    with session_scope(database_url) as session:
        job = session.scalar(
            select(BackgroundJobModel)
            .where(
                or_(
                    (BackgroundJobModel.status == "queued")
                    & (BackgroundJobModel.available_at <= now),
                    (BackgroundJobModel.status == "running")
                    & (BackgroundJobModel.lease_expires_at <= now),
                )
            )
            .order_by(BackgroundJobModel.created_at.asc())
            .limit(1)
        )
        if job is None:
            return False

        job.status = "running"
        job.attempt_count += 1
        job.lease_owner = worker_id
        job.lease_expires_at = _iso_after_seconds(LEASE_DURATION_SECONDS)
        job.updated_at = now

        claimed_job_id = job.id
        job_kind = job.job_kind
        owner_user_id = job.owner_user_id
        payload = json.loads(job.payload_json or "{}")

        ai_cfg = session.get(AISettingsModel, owner_user_id)
        if ai_cfg is not None:
            extraction_provider = ai_cfg.extraction_provider
            extraction_model = ai_cfg.extraction_model
            local_endpoint_url = ai_cfg.local_endpoint_url

        user_msg_id = payload.get("user_message_id")
        asst_msg_id = payload.get("assistant_message_id")
        if user_msg_id:
            um = session.get(MessageModel, user_msg_id)
            if um:
                user_msg_dict = {
                    "id": um.id,
                    "conversation_id": um.conversation_id,
                    "role": um.role,
                    "content": um.content,
                }
        if asst_msg_id:
            am = session.get(MessageModel, asst_msg_id)
            if am:
                asst_msg_dict = {
                    "id": am.id,
                    "conversation_id": am.conversation_id,
                    "role": am.role,
                    "content": am.content,
                }

        if job_kind == "knowledge_extraction":
            concepts = session.scalars(
                select(ConceptModel).where(
                    ConceptModel.owner_user_id == owner_user_id,
                    ConceptModel.merged_into_concept_id.is_(None),
                )
            ).all()
            existing_concepts = {
                c.normalized_name: (c.canonical_name, c.description)
                for c in concepts
            }
            ext_run = ExtractionRunModel(
                id=new_id("ext"),
                background_job_id=job.id,
                provider=extraction_provider,
                model=extraction_model,
                prompt_version=PROMPT_VERSION_EXTRACTION,
                schema_version=SCHEMA_VERSION_EXTRACTION,
                output_status="running",
                created_at=now,
                finished_at=None,
            )
            session.add(ext_run)
            session.flush()
            extraction_run_id = ext_run.id

    if claimed_job_id is None:
        return False

    # External model / computation outside any DB transaction!
    try:
        if job_kind == "knowledge_extraction":
            if user_msg_dict is None:
                raise ProviderError(
                    code="missing_source_message",
                    message="Source user message missing for extraction.",
                    retryable=False,
                )
            proposal = extract_structured(
                provider=extraction_provider,
                model=extraction_model,
                user_message=user_msg_dict,
                assistant_message=asst_msg_dict,
                existing_concepts=existing_concepts,
                local_endpoint_url=local_endpoint_url,
            )

            # Short transaction 2: apply validated proposal and complete job
            with session_scope(database_url) as session:
                job = session.get(BackgroundJobModel, claimed_job_id)
                ext_run = (
                    session.get(ExtractionRunModel, extraction_run_id)
                    if extraction_run_id
                    else None
                )
                if job is not None and ext_run is not None:
                    apply_extraction_proposal(
                        session,
                        proposal=proposal,
                        extraction_run=ext_run,
                        conversation_id=str(payload.get("conversation_id", "")),
                        owner_user_id=owner_user_id,
                    )
                    fin = utc_now_iso()
                    ext_run.output_status = "succeeded"
                    ext_run.finished_at = fin
                    job.status = "succeeded"
                    job.lease_owner = None
                    job.lease_expires_at = None
                    job.updated_at = fin
                    job.finished_at = fin

        elif job_kind == "embedding":
            with session_scope(database_url) as session:
                ai_cfg = session.get(AISettingsModel, owner_user_id)
                if ai_cfg and ai_cfg.embedding_provider == "fail_embedding":
                    raise ProviderError(
                        code="embedding_provider_failed",
                        message="Embedding provider unavailable; lexical FTS remains active.",
                        retryable=True,
                    )
                for msg_key in ("user_message_id", "assistant_message_id"):
                    mid = payload.get(msg_key)
                    if mid:
                        msg_obj = session.get(MessageModel, mid)
                        if msg_obj is not None:
                            index_message_documents(
                                session,
                                msg_obj,
                                owner_user_id=owner_user_id,
                                create_embeddings=True,
                            )
                job = session.get(BackgroundJobModel, claimed_job_id)
                if job is not None:
                    fin = utc_now_iso()
                    job.status = "succeeded"
                    job.lease_owner = None
                    job.lease_expires_at = None
                    job.updated_at = fin
                    job.finished_at = fin

    except Exception as exc:
        err_code = getattr(exc, "code", "worker_execution_failed")
        retryable = getattr(exc, "retryable", True)
        with session_scope(database_url) as session:
            job = session.get(BackgroundJobModel, claimed_job_id)
            if job is not None:
                fin = utc_now_iso()
                job.error_code = str(err_code)
                job.lease_owner = None
                job.lease_expires_at = None
                job.updated_at = fin
                if retryable and job.attempt_count < MAX_JOB_ATTEMPTS:
                    backoff = 2 ** job.attempt_count
                    job.status = "queued"
                    job.available_at = _iso_after_seconds(backoff)
                else:
                    job.status = "failed"
                    job.finished_at = fin
            if extraction_run_id:
                ext_run = session.get(ExtractionRunModel, extraction_run_id)
                if ext_run is not None:
                    ext_run.output_status = "failed"
                    ext_run.finished_at = utc_now_iso()

    return True


def drain_background_jobs(
    database_url: str | None = None,
    max_jobs: int = 25,
    force_ready: bool = False,
) -> int:
    """Process queued background jobs up to `max_jobs`."""
    processed = 0
    for _ in range(max_jobs):
        if force_ready:
            with session_scope(database_url) as session:
                now = utc_now_iso()
                queued = session.scalars(
                    select(BackgroundJobModel).where(
                        BackgroundJobModel.status == "queued"
                    )
                ).all()
                for q in queued:
                    q.available_at = now
        if not process_next_background_job(database_url=database_url):
            break
        processed += 1
    return processed


def get_turn_extraction_status(
    session: Any, generation_run_id: str
) -> tuple[str, str | None]:
    jobs = session.scalars(
        select(BackgroundJobModel).where(
            BackgroundJobModel.source_generation_run_id == generation_run_id,
            BackgroundJobModel.job_kind == "knowledge_extraction",
        )
    ).all()
    if not jobs:
        return "none", None
    latest = jobs[-1]
    return latest.status, latest.error_code


def retry_failed_extraction_for_turn(
    session: Any, turn_id: str, owner_user_id: str = DEFAULT_OWNER_USER_ID
) -> str:
    run = session.get(GenerationRunModel, turn_id)
    if run is None or run.owner_user_id != owner_user_id:
        return "not_found"
    jobs = session.scalars(
        select(BackgroundJobModel).where(
            BackgroundJobModel.source_generation_run_id == turn_id,
            BackgroundJobModel.job_kind == "knowledge_extraction",
        )
    ).all()
    now = utc_now_iso()
    for job in jobs:
        job.status = "queued"
        job.attempt_count = 0
        job.error_code = None
        job.available_at = now
        job.updated_at = now
        job.finished_at = None
    session.flush()
    return "queued"

