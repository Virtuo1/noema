"""Hybrid retrieval, FTS5 lexical search, exact vector ranking, and context construction."""

from __future__ import annotations

import hashlib
import re

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from noema.ai.gateway import (
    EMBEDDING_DIMENSIONS_LOCAL,
    ContextEvidenceItem,
    compute_deterministic_embedding,
    cosine_similarity,
    pack_vector,
    unpack_vector,
)
from noema.api.schemas import SearchResponse, SearchResultDTO
from noema.config import DEFAULT_OWNER_USER_ID
from noema.domain.vocabulary import normalize_concept_name
from noema.persistence.db import new_id, utc_now_iso
from noema.persistence.models import (
    AISettingsModel,
    AnnotationModel,
    ConceptMentionModel,
    ConceptModel,
    DocumentEmbeddingModel,
    MessageModel,
    SearchDocumentModel,
    UserHypothesisModel,
    UserRelationModel,
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def chunk_message_text(
    content: str, max_chars: int = 500
) -> list[tuple[int, int, str]]:
    """Split message text around paragraph/sentence boundaries while keeping exact offsets."""
    if not content:
        return []
    if len(content) <= max_chars:
        return [(0, len(content), content)]

    chunks: list[tuple[int, int, str]] = []
    start = 0
    length = len(content)
    while start < length:
        end = min(start + max_chars, length)
        if end < length:
            split_pos = content.rfind("\n\n", start, end)
            if split_pos <= start:
                split_pos = content.rfind(". ", start, end)
                if split_pos > start:
                    end = split_pos + 1
            else:
                end = split_pos
        chunk_str = content[start:end]
        if chunk_str.strip():
            chunks.append((start, end, chunk_str))
        start = end
        while start < length and content[start] in (" ", "\n"):
            start += 1
    return chunks


def _upsert_fts_row(
    session: Session, doc_id: str, owner_user_id: str, kind: str, doc_text: str
) -> None:
    session.execute(
        text("DELETE FROM search_documents_fts WHERE document_id = :doc_id"),
        {"doc_id": doc_id},
    )
    session.execute(
        text(
            """
            INSERT INTO search_documents_fts (document_id, owner_user_id, kind, text)
            VALUES (:doc_id, :owner_user_id, :kind, :text)
            """
        ),
        {
            "doc_id": doc_id,
            "owner_user_id": owner_user_id,
            "kind": kind,
            "text": doc_text,
        },
    )


def _upsert_embedding_row(
    session: Session,
    doc_id: str,
    doc_text: str,
    content_hash: str,
    provider: str,
    model: str,
    now: str,
) -> None:
    vec = compute_deterministic_embedding(doc_text, EMBEDDING_DIMENSIONS_LOCAL)
    blob = pack_vector(vec)
    existing = session.scalar(
        select(DocumentEmbeddingModel).where(
            DocumentEmbeddingModel.document_id == doc_id,
            DocumentEmbeddingModel.provider == provider,
            DocumentEmbeddingModel.model == model,
            DocumentEmbeddingModel.dimensions == EMBEDDING_DIMENSIONS_LOCAL,
        )
    )
    if existing is not None:
        if existing.content_hash != content_hash:
            existing.vector_blob = blob
            existing.content_hash = content_hash
            existing.created_at = now
    else:
        session.add(
            DocumentEmbeddingModel(
                id=new_id("emb"),
                document_id=doc_id,
                provider=provider,
                model=model,
                dimensions=EMBEDDING_DIMENSIONS_LOCAL,
                vector_blob=blob,
                content_hash=content_hash,
                created_at=now,
            )
        )


def index_message_documents(
    session: Session,
    message: MessageModel,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
    create_embeddings: bool = True,
) -> list[SearchDocumentModel]:
    now = utc_now_iso()
    ai_cfg = session.get(AISettingsModel, owner_user_id)
    emb_provider = ai_cfg.embedding_provider if ai_cfg else "local_heuristic"
    emb_model = ai_cfg.embedding_model if ai_cfg else "noema-local-embed-v1"

    # Remove old search documents for this message if re-indexing
    old_docs = session.scalars(
        select(SearchDocumentModel).where(SearchDocumentModel.message_id == message.id)
    ).all()
    for old_doc in old_docs:
        session.execute(
            text("DELETE FROM search_documents_fts WHERE document_id = :doc_id"),
            {"doc_id": old_doc.id},
        )
        session.delete(old_doc)
    session.flush()

    docs: list[SearchDocumentModel] = []
    for idx, (start_off, end_off, chunk_text) in enumerate(
        chunk_message_text(message.content)
    ):
        chash = _sha256_text(chunk_text)
        doc = SearchDocumentModel(
            id=new_id("sdoc"),
            owner_user_id=owner_user_id,
            kind="message_chunk",
            message_id=message.id,
            concept_id=None,
            hypothesis_id=None,
            chunk_index=idx,
            start_offset=start_off,
            end_offset=end_off,
            text=chunk_text,
            content_hash=chash,
            updated_at=now,
        )
        session.add(doc)
        session.flush()
        _upsert_fts_row(session, doc.id, owner_user_id, "message_chunk", chunk_text)
        if create_embeddings and emb_provider != "fail_embedding":
            _upsert_embedding_row(
                session, doc.id, chunk_text, chash, emb_provider, emb_model, now
            )
        docs.append(doc)
    return docs


def index_concept_document(
    session: Session,
    concept: ConceptModel,
    aliases: list[str] | None = None,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> SearchDocumentModel:
    now = utc_now_iso()
    ai_cfg = session.get(AISettingsModel, owner_user_id)
    emb_provider = ai_cfg.embedding_provider if ai_cfg else "local_heuristic"
    emb_model = ai_cfg.embedding_model if ai_cfg else "noema-local-embed-v1"

    alias_str = ", ".join(aliases or [])
    doc_text = f"{concept.canonical_name}. {concept.description} {alias_str}".strip()
    chash = _sha256_text(doc_text)

    existing = session.scalar(
        select(SearchDocumentModel).where(
            SearchDocumentModel.concept_id == concept.id,
            SearchDocumentModel.kind == "concept",
        )
    )
    if existing is None:
        doc = SearchDocumentModel(
            id=new_id("sdoc"),
            owner_user_id=owner_user_id,
            kind="concept",
            message_id=None,
            concept_id=concept.id,
            hypothesis_id=None,
            chunk_index=0,
            start_offset=None,
            end_offset=None,
            text=doc_text,
            content_hash=chash,
            updated_at=now,
        )
        session.add(doc)
        session.flush()
    else:
        doc = existing
        doc.text = doc_text
        doc.content_hash = chash
        doc.updated_at = now
        session.flush()

    _upsert_fts_row(session, doc.id, owner_user_id, "concept", doc_text)
    if emb_provider != "fail_embedding":
        _upsert_embedding_row(
            session, doc.id, doc_text, chash, emb_provider, emb_model, now
        )
    return doc


def index_hypothesis_document(
    session: Session,
    hypothesis: UserHypothesisModel,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> SearchDocumentModel:
    now = utc_now_iso()
    ai_cfg = session.get(AISettingsModel, owner_user_id)
    emb_provider = ai_cfg.embedding_provider if ai_cfg else "local_heuristic"
    emb_model = ai_cfg.embedding_model if ai_cfg else "noema-local-embed-v1"

    doc_text = hypothesis.statement.strip()
    chash = _sha256_text(doc_text)
    existing = session.scalar(
        select(SearchDocumentModel).where(
            SearchDocumentModel.hypothesis_id == hypothesis.id,
            SearchDocumentModel.kind == "hypothesis",
        )
    )
    if existing is None:
        doc = SearchDocumentModel(
            id=new_id("sdoc"),
            owner_user_id=owner_user_id,
            kind="hypothesis",
            message_id=None,
            concept_id=None,
            hypothesis_id=hypothesis.id,
            chunk_index=0,
            start_offset=None,
            end_offset=None,
            text=doc_text,
            content_hash=chash,
            updated_at=now,
        )
        session.add(doc)
        session.flush()
    else:
        doc = existing
        doc.text = doc_text
        doc.content_hash = chash
        doc.updated_at = now
        session.flush()

    _upsert_fts_row(session, doc.id, owner_user_id, "hypothesis", doc_text)
    if emb_provider != "fail_embedding":
        _upsert_embedding_row(
            session, doc.id, doc_text, chash, emb_provider, emb_model, now
        )
    return doc


def cleanup_fts_for_document_ids(session: Session, doc_ids: list[str]) -> None:
    for doc_id in doc_ids:
        session.execute(
            text("DELETE FROM search_documents_fts WHERE document_id = :doc_id"),
            {"doc_id": doc_id},
        )


def _build_fts_match_expression(query: str) -> str:
    tokens = [
        tok
        for tok in re.findall(r"[a-zA-Z0-9]{2,}", query.lower())
        if tok
        not in {
            "how",
            "does",
            "what",
            "why",
            "the",
            "and",
            "for",
            "with",
            "can",
            "you",
            "are",
            "that",
            "this",
            "from",
            "into",
        }
    ]
    if not tokens:
        tokens = re.findall(r"[a-zA-Z0-9]+", query.lower())
    if not tokens:
        return ""
    return " OR ".join(f'"{t}"' for t in tokens[:10])


def hybrid_search(
    session: Session,
    *,
    query: str,
    kind: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 10,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
    exclude_conversation_id: str | None = None,
) -> SearchResponse:
    if not query.strip():
        return SearchResponse(query=query, items=[])

    fts_expr = _build_fts_match_expression(query)
    lexical_ranks: dict[str, int] = {}
    if fts_expr:
        sql = """
            SELECT document_id
            FROM search_documents_fts
            WHERE search_documents_fts MATCH :expr
              AND owner_user_id = :owner_user_id
        """
        params: dict[str, str] = {"expr": fts_expr, "owner_user_id": owner_user_id}
        if kind:
            sql += " AND kind = :kind"
            params["kind"] = kind
        sql += " ORDER BY bm25(search_documents_fts) LIMIT 40"
        rows = session.execute(text(sql), params).fetchall()
        for rank_idx, row in enumerate(rows, start=1):
            lexical_ranks[str(row[0])] = rank_idx

    # Exact vector cosine ranking over eligible documents in the same embedding space
    ai_cfg = session.get(AISettingsModel, owner_user_id)
    emb_provider = ai_cfg.embedding_provider if ai_cfg else "local_heuristic"
    emb_model = ai_cfg.embedding_model if ai_cfg else "noema-local-embed-v1"

    query_vec = compute_deterministic_embedding(query, EMBEDDING_DIMENSIONS_LOCAL)
    doc_stmt = select(SearchDocumentModel).where(
        SearchDocumentModel.owner_user_id == owner_user_id
    )
    if kind:
        doc_stmt = doc_stmt.where(SearchDocumentModel.kind == kind)
    if after:
        doc_stmt = doc_stmt.where(SearchDocumentModel.updated_at >= after)
    if before:
        doc_stmt = doc_stmt.where(SearchDocumentModel.updated_at <= before)

    eligible_docs = {d.id: d for d in session.scalars(doc_stmt).all()}
    vector_scores: list[tuple[str, float]] = []
    if eligible_docs:
        emb_rows = session.scalars(
            select(DocumentEmbeddingModel).where(
                DocumentEmbeddingModel.document_id.in_(list(eligible_docs.keys())),
                DocumentEmbeddingModel.provider == emb_provider,
                DocumentEmbeddingModel.model == emb_model,
                DocumentEmbeddingModel.dimensions == EMBEDDING_DIMENSIONS_LOCAL,
            )
        ).all()
        for emb in emb_rows:
            vec = unpack_vector(emb.vector_blob, emb.dimensions)
            sim = cosine_similarity(query_vec, vec)
            if sim > 0.08:
                vector_scores.append((emb.document_id, sim))

    vector_scores.sort(key=lambda item: item[1], reverse=True)
    semantic_ranks: dict[str, int] = {
        doc_id: idx for idx, (doc_id, _sim) in enumerate(vector_scores[:40], start=1)
    }

    # Graph & structured concept boost channel
    q_norm = normalize_concept_name(query)
    matched_concepts = session.scalars(
        select(ConceptModel).where(
            ConceptModel.owner_user_id == owner_user_id,
            ConceptModel.merged_into_concept_id.is_(None),
        )
    ).all()
    seed_concept_ids = {
        c.id
        for c in matched_concepts
        if c.normalized_name and c.normalized_name in q_norm
    }
    # 1-hop expansion along user-established relations
    expanded_concept_ids = set(seed_concept_ids)
    if seed_concept_ids:
        rels = session.scalars(
            select(UserRelationModel).where(
                UserRelationModel.owner_user_id == owner_user_id,
                UserRelationModel.withdrawn_at.is_(None),
                (UserRelationModel.subject_concept_id.in_(seed_concept_ids))
                | (UserRelationModel.object_concept_id.in_(seed_concept_ids)),
            )
        ).all()
        for r in rels:
            expanded_concept_ids.add(r.subject_concept_id)
            expanded_concept_ids.add(r.object_concept_id)

    graph_doc_ids: set[str] = set()
    if expanded_concept_ids:
        mention_msg_ids = set(
            session.scalars(
                select(ConceptMentionModel.message_id).where(
                    ConceptMentionModel.concept_id.in_(expanded_concept_ids)
                )
            ).all()
        )
        for doc_id, doc in eligible_docs.items():
            if doc.concept_id in expanded_concept_ids or (
                doc.message_id and doc.message_id in mention_msg_ids
            ):
                graph_doc_ids.add(doc_id)

    # Reciprocal Rank Fusion (RRF) + provenance boosts
    candidate_ids = (
        (set(lexical_ranks.keys()) | set(semantic_ranks.keys()) | graph_doc_ids)
        & set(eligible_docs.keys())
    )
    results: list[SearchResultDTO] = []

    for doc_id in candidate_ids:
        doc = eligible_docs[doc_id]
        msg: MessageModel | None = None
        if doc.message_id:
            msg = session.get(MessageModel, doc.message_id)
            if msg is None:
                continue
            if exclude_conversation_id and msg.conversation_id == exclude_conversation_id:
                continue

        score = 0.0
        channels: list[str] = []
        if doc_id in lexical_ranks:
            score += 1.0 / (20.0 + lexical_ranks[doc_id])
            channels.append("lexical_fts")
        if doc_id in semantic_ranks:
            score += 1.0 / (25.0 + semantic_ranks[doc_id])
            channels.append("semantic_vector")
        if doc_id in graph_doc_ids:
            score += 0.035
            channels.append("knowledge_graph")

        # Boost user-authored evidence and explicit user annotations (#aha, #confused, #question)
        if msg is not None:
            if msg.role == "user":
                score += 0.012
            anns = session.scalars(
                select(AnnotationModel).where(
                    AnnotationModel.message_id == msg.id,
                    AnnotationModel.removed_at.is_(None),
                )
            ).all()
            if anns:
                score += 0.025
                if "annotated_evidence" not in channels:
                    channels.append("annotated_evidence")

        results.append(
            SearchResultDTO(
                document_id=doc.id,
                kind=doc.kind,  # type: ignore[arg-type]
                excerpt=doc.text[:260],
                score=round(score, 5),
                channels=channels,
                message_id=doc.message_id,
                conversation_id=msg.conversation_id if msg else None,
                concept_id=doc.concept_id,
                hypothesis_id=doc.hypothesis_id,
                created_at=msg.created_at if msg else doc.updated_at,
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    return SearchResponse(query=query, items=results[:limit])


def build_turn_context(
    session: Session,
    *,
    query: str,
    current_conversation_id: str,
    budget_tokens: int = 1600,
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
) -> list[ContextEvidenceItem]:
    """Retrieve a small, high-signal bundle of prior personal context within budget."""
    search_res = hybrid_search(
        session,
        query=query,
        kind="message_chunk",
        limit=6,
        owner_user_id=owner_user_id,
        exclude_conversation_id=current_conversation_id,
    )
    items: list[ContextEvidenceItem] = []
    used_tokens = 0
    seen_messages: set[str] = set()

    for hit in search_res.items:
        if not hit.message_id or hit.message_id in seen_messages:
            continue
        msg = session.get(MessageModel, hit.message_id)
        if msg is None:
            continue
        approx_tokens = max(1, len(hit.excerpt) // 4)
        if used_tokens + approx_tokens > budget_tokens:
            break
        seen_messages.add(hit.message_id)
        used_tokens += approx_tokens
        items.append(
            ContextEvidenceItem(
                source_id=hit.document_id,
                kind="message",
                message_id=msg.id,
                conversation_id=msg.conversation_id,
                concept_id=hit.concept_id,
                role=msg.role,
                excerpt=hit.excerpt,
                created_at=msg.created_at,
                reason=f"Retrieved via {', '.join(hit.channels)}",
            )
        )
        if len(items) >= 3:
            break

    return items
