"""Domain vocabulary, epistemic layer invariants, predicates, and command rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class EpistemicLayer(StrEnum):
    SOURCE = "source"
    WORLD_CLAIM = "world_claim"
    PERSONAL_STATE = "personal_state"
    USER_RELATION = "user_relation"
    SUGGESTION = "suggestion"


class AnnotationTag(StrEnum):
    AHA = "aha"
    CONFUSED = "confused"
    QUESTION = "question"
    CONNECTION = "connection"
    HYPOTHESIS = "hypothesis"
    REVISIT = "revisit"
    IMPORTANT = "important"


class SelfAssessment(StrEnum):
    UNKNOWN = "unknown"
    CONFUSED = "confused"
    UNCERTAIN = "uncertain"
    SELF_REPORTS_UNDERSTANDING = "self_reports_understanding"


class DemonstrationStatus(StrEnum):
    NONE = "none"
    SOME_EVIDENCE = "some_evidence"
    REPEATED_EVIDENCE = "repeated_evidence"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"


class WorldClaimStatus(StrEnum):
    PROVISIONAL = "provisional"
    SUPPORTED = "supported"
    CHALLENGED = "challenged"
    SUPERSEDED = "superseded"


class WorldClaimSourceKind(StrEnum):
    ASSISTANT_MESSAGE = "assistant_message"
    USER_SOURCE = "user_source"
    CURATED = "curated"


class UserRelationOrigin(StrEnum):
    DIRECT_USER_ASSERTION = "direct_user_assertion"
    ACCEPTED_SUGGESTION = "accepted_suggestion"
    EXPLICIT_ANNOTATION = "explicit_annotation"


class SuggestionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DISMISSED = "dismissed"


class HypothesisStatus(StrEnum):
    ACTIVE = "active"
    SUPPORTED = "supported"
    CHALLENGED = "challenged"
    REVISED = "revised"
    WITHDRAWN = "withdrawn"


class SignalKind(StrEnum):
    ENCOUNTER = "encounter"
    EXPLORATION = "exploration"
    SELF_REPORT = "self_report"
    EXPLANATION = "explanation"
    PROBLEM_SOLVING = "problem_solving"
    CONTRADICTION = "contradiction"


class SignalOrigin(StrEnum):
    EXPLICIT_ANNOTATION = "explicit_annotation"
    USER_STATEMENT = "user_statement"
    AI_INFERRED = "ai_inferred"


class ReviewStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    DISMISSED = "dismissed"


class KnowledgeEventType(StrEnum):
    CONCEPT_ENCOUNTERED = "concept_encountered"
    CONCEPT_EXPLORED = "concept_explored"
    ANNOTATION_ADDED = "annotation_added"
    ANNOTATION_REMOVED = "annotation_removed"
    SELF_ASSESSMENT_CHANGED = "self_assessment_changed"
    DEMONSTRATION_EVIDENCE_ADDED = "demonstration_evidence_added"
    USER_RELATION_ESTABLISHED = "user_relation_established"
    USER_RELATION_WITHDRAWN = "user_relation_withdrawn"
    SUGGESTION_CREATED = "suggestion_created"
    SUGGESTION_ACCEPTED = "suggestion_accepted"
    SUGGESTION_REJECTED = "suggestion_rejected"
    SUGGESTION_DISMISSED = "suggestion_dismissed"
    WORLD_CLAIM_RECORDED = "world_claim_recorded"
    CLAIM_CHALLENGED = "claim_challenged"
    HYPOTHESIS_CREATED = "hypothesis_created"
    HYPOTHESIS_REVISED = "hypothesis_revised"
    CONCEPT_MERGED = "concept_merged"
    CANDIDATE_SIGNAL_CONFIRMED = "candidate_signal_confirmed"
    CANDIDATE_SIGNAL_DISMISSED = "candidate_signal_dismissed"


@dataclass(frozen=True, slots=True)
class PredicateMeta:
    code: str
    label: str
    description: str
    is_hierarchy: bool = False
    is_symmetric: bool = False


PREDICATE_REGISTRY: dict[str, PredicateMeta] = {
    "is_a": PredicateMeta(
        code="is_a",
        label="is a kind of",
        description="Taxonomic or subtype hierarchy relation",
        is_hierarchy=True,
        is_symmetric=False,
    ),
    "part_of": PredicateMeta(
        code="part_of",
        label="is part of",
        description="Compositional or structural containment",
        is_hierarchy=True,
        is_symmetric=False,
    ),
    "prerequisite_for": PredicateMeta(
        code="prerequisite_for",
        label="is a prerequisite for",
        description="Foundational concept helpful before studying the target",
        is_hierarchy=True,
        is_symmetric=False,
    ),
    "depends_on": PredicateMeta(
        code="depends_on",
        label="depends on",
        description="Conceptual or mathematical dependency",
        is_hierarchy=False,
        is_symmetric=False,
    ),
    "uses": PredicateMeta(
        code="uses",
        label="uses",
        description="Applies or incorporates another concept or mechanism",
        is_hierarchy=False,
        is_symmetric=False,
    ),
    "uses_mechanism": PredicateMeta(
        code="uses_mechanism",
        label="uses mechanism",
        description="Implements or relies on a specific mechanism",
        is_hierarchy=False,
        is_symmetric=False,
    ),
    "causes": PredicateMeta(
        code="causes",
        label="causes",
        description="Produces or leads to an effect or phenomenon",
        is_hierarchy=False,
        is_symmetric=False,
    ),
    "contrasts_with": PredicateMeta(
        code="contrasts_with",
        label="contrasts with",
        description="Differs along an explicit conceptual dimension",
        is_hierarchy=False,
        is_symmetric=True,
    ),
    "contrasts_with_learning": PredicateMeta(
        code="contrasts_with_learning",
        label="contrasts with (learning mechanism)",
        description="Contrasts global vs local or alternative learning mechanisms",
        is_hierarchy=False,
        is_symmetric=True,
    ),
    "analogous_to": PredicateMeta(
        code="analogous_to",
        label="is analogous to",
        description="Shares structural similarity across contexts or domains",
        is_hierarchy=False,
        is_symmetric=True,
    ),
    "related_to": PredicateMeta(
        code="related_to",
        label="relates to",
        description="General user-established or exploratory association",
        is_hierarchy=False,
        is_symmetric=True,
    ),
}

VALID_ANNOTATION_TAGS: frozenset[str] = frozenset(tag.value for tag in AnnotationTag)
_HASHTAG_TOKEN_RE = re.compile(r"(?:^|(?<=\s))#([a-zA-Z_][a-zA-Z0-9_-]*)(?=\s|$|[.,!?;:])")


@dataclass(frozen=True, slots=True)
class ParsedCommandInput:
    tags: list[AnnotationTag]
    cleaned_text: str
    is_bare_command_only: bool


def parse_command_tags(content: str) -> ParsedCommandInput:
    """Extract recognized standalone #commands while leaving unknown hashtags literal.

    Targeting rule:
    - If `is_bare_command_only` is True (e.g. user sends just `#aha`), the command targets
      the most recent prior message in the conversation (typically the assistant's explanation)
      without sending a new LLM generation request, or targets the user's message if explicitly attached.
    - If combined with substantive message text (e.g. `I think I get it: ... #aha`), the
      annotation is anchored directly to the user's new message while keeping the original message text.
    """
    recognized: list[AnnotationTag] = []
    seen: set[AnnotationTag] = set()

    for match in _HASHTAG_TOKEN_RE.finditer(content):
        token = match.group(1).lower()
        if token in VALID_ANNOTATION_TAGS:
            tag = AnnotationTag(token)
            if tag not in seen:
                seen.add(tag)
                recognized.append(tag)

    stripped = content.strip()
    tokens = stripped.split()
    is_bare = bool(tokens) and all(
        t.startswith("#") and t[1:].lower() in VALID_ANNOTATION_TAGS for t in tokens
    )
    return ParsedCommandInput(
        tags=recognized,
        cleaned_text=content,
        is_bare_command_only=is_bare,
    )


def normalize_concept_name(name: str) -> str:
    """Normalize concept/alias strings for lookup while preserving display form separately."""
    collapsed = " ".join(name.strip().lower().split())
    return re.sub(r"[^\w\s-]", "", collapsed).strip()


def canonicalize_symmetric_endpoints(
    subject_id: str, predicate: str, object_id: str
) -> tuple[str, str]:
    """Return canonical (subject_id, object_id) order for symmetric predicates when deduplicating."""
    meta = PREDICATE_REGISTRY.get(predicate)
    if meta and meta.is_symmetric and subject_id > object_id:
        return object_id, subject_id
    return subject_id, object_id
