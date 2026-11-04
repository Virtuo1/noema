"""Phase 0 contracts and epistemic boundary tests."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text

from noema.domain.vocabulary import (
    PREDICATE_REGISTRY,
    AnnotationTag,
    EpistemicLayer,
    SelfAssessment,
    canonicalize_symmetric_endpoints,
    normalize_concept_name,
    parse_command_tags,
)
from noema.fixtures.synthetic_dataset import RETRIEVAL_EVAL_CASES, SYNTHETIC_CONVERSATIONS
from noema.persistence.db import init_db, new_id, session_scope, utc_now_iso
from noema.persistence.models import (
    AnnotationModel,
    ConceptModel,
    ConversationModel,
    KnowledgeSuggestionModel,
    MessageModel,
    UserConceptStateModel,
    UserRelationModel,
    WorldClaimModel,
)


def test_sqlite_schema_and_epistemic_separation(tmp_path: Path) -> None:
    db_file = tmp_path / "phase0_test.db"
    db_url = f"sqlite:///{db_file}"
    engine = init_db(db_url)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    expected_tables = {
        "app_users",
        "ai_settings",
        "conversations",
        "messages",
        "generation_runs",
        "concepts",
        "concept_aliases",
        "concept_mentions",
        "annotations",
        "world_claims",
        "user_concept_states",
        "user_relations",
        "knowledge_suggestions",
        "background_jobs",
        "extraction_runs",
        "evidence",
        "world_claim_evidence",
        "user_state_evidence",
        "user_relation_evidence",
        "suggestion_evidence",
        "user_hypotheses",
        "hypothesis_evidence",
        "knowledge_events",
        "search_documents",
        "document_embeddings",
    }
    assert expected_tables.issubset(tables)

    with engine.connect() as conn:
        fk_enabled = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert fk_enabled == 1

    # Verify the 5 distinct epistemic record layers do not conflate
    assert len(set(EpistemicLayer)) == 5
    now = utc_now_iso()
    with session_scope(db_url) as session:
        conv = ConversationModel(
            id=new_id("conv"),
            owner_user_id="u_local_owner",
            title="Backpropagation study",
            created_at=now,
            updated_at=now,
        )
        session.add(conv)
        msg = MessageModel(
            id=new_id("msg"),
            conversation_id=conv.id,
            sequence_no=1,
            role="user",
            content="I think I get it: the chain rule lets the error signal flow backward.",
            created_at=now,
            content_hash="abc123",
        )
        session.add(msg)
        c_bp = ConceptModel(
            id="c_bp",
            owner_user_id="u_local_owner",
            canonical_name="Backpropagation",
            normalized_name=normalize_concept_name("Backpropagation"),
            created_at=now,
            updated_at=now,
        )
        c_cr = ConceptModel(
            id="c_cr",
            owner_user_id="u_local_owner",
            canonical_name="Chain rule",
            normalized_name=normalize_concept_name("Chain rule"),
            created_at=now,
            updated_at=now,
        )
        c_hb = ConceptModel(
            id="c_hb",
            owner_user_id="u_local_owner",
            canonical_name="Hebbian learning",
            normalized_name=normalize_concept_name("Hebbian learning"),
            created_at=now,
            updated_at=now,
        )
        session.add_all([c_bp, c_cr, c_hb])
        session.flush()

        # 1. Source annotation (explicit user tag)
        ann = AnnotationModel(
            id=new_id("ann"),
            owner_user_id="u_local_owner",
            message_id=msg.id,
            tag=AnnotationTag.AHA.value,
            origin="user_explicit",
            created_at=now,
        )
        # 2. World claim (provisional model statement)
        wc = WorldClaimModel(
            id=new_id("wc"),
            owner_user_id="u_local_owner",
            subject_concept_id=c_bp.id,
            predicate="uses_mechanism",
            object_concept_id=c_cr.id,
            claim_text="Backpropagation uses the chain rule to compute gradients.",
            status="provisional",
            source_kind="assistant_message",
            created_at=now,
            valid_from=now,
        )
        # 3. Personal state (self_reports_understanding, demonstration=none)
        state_bp = UserConceptStateModel(
            owner_user_id="u_local_owner",
            concept_id=c_bp.id,
            first_encountered_at=now,
            last_explored_at=now,
            self_assessment=SelfAssessment.SELF_REPORTS_UNDERSTANDING.value,
            demonstration_status="none",
            updated_at=now,
        )
        # 4. Pending suggestion (does NOT create a user_relation)
        sugg = KnowledgeSuggestionModel(
            id="s_4",
            owner_user_id="u_local_owner",
            suggestion_type="connection",
            subject_concept_id=c_bp.id,
            predicate="contrasts_with_learning",
            object_concept_id=c_hb.id,
            explanation="Compare global gradient propagation with local update rules.",
            status="pending",
            created_at=now,
        )
        session.add_all([ann, wc, state_bp, sugg])
        session.flush()

        active_relations = session.query(UserRelationModel).all()
        assert len(active_relations) == 0


def test_command_parsing_and_predicates() -> None:
    bare = parse_command_tags("#aha")
    assert bare.tags == [AnnotationTag.AHA]
    assert bare.is_bare_command_only is True

    inline = parse_command_tags("I think I get it #aha and want to #revisit #not_a_command")
    assert inline.tags == [AnnotationTag.AHA, AnnotationTag.REVISIT]
    assert inline.is_bare_command_only is False

    literal_only = parse_command_tags("Studying #channel-1 and #python3 today")
    assert literal_only.tags == []
    assert literal_only.is_bare_command_only is False

    assert PREDICATE_REGISTRY["is_a"].is_hierarchy is True
    assert PREDICATE_REGISTRY["contrasts_with_learning"].is_symmetric is True
    assert canonicalize_symmetric_endpoints("c_z", "contrasts_with", "c_a") == ("c_a", "c_z")


def test_synthetic_dataset_present() -> None:
    assert len(SYNTHETIC_CONVERSATIONS) >= 3
    assert len(RETRIEVAL_EVAL_CASES) >= 3
