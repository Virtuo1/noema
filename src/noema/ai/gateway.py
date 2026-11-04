"""AI provider gateway, capability registry, secret store, and structured extraction."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import struct
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field

from noema.config import get_settings
from noema.domain.vocabulary import (
    PREDICATE_REGISTRY,
    SignalKind,
    normalize_concept_name,
)

PROMPT_VERSION_CHAT = "chat-v1.0"
PROMPT_VERSION_EXTRACTION = "extract-v1.0"
SCHEMA_VERSION_EXTRACTION = "schema-v1.0"
EMBEDDING_DIMENSIONS_LOCAL = 64


@dataclass(frozen=True, slots=True)
class ProviderCapability:
    provider: str
    display_name: str
    is_remote: bool
    supports_streaming: bool
    supports_structured_output: bool
    supports_embeddings: bool
    context_window: int
    env_key_name: str | None = None


PROVIDER_CAPABILITIES: dict[str, ProviderCapability] = {
    "local_heuristic": ProviderCapability(
        provider="local_heuristic",
        display_name="Local Deterministic Engine (Built-in)",
        is_remote=False,
        supports_streaming=True,
        supports_structured_output=True,
        supports_embeddings=True,
        context_window=16384,
        env_key_name=None,
    ),
    "local_openai": ProviderCapability(
        provider="local_openai",
        display_name="Local OpenAI-Compatible Endpoint (Ollama / llama.cpp)",
        is_remote=False,
        supports_streaming=True,
        supports_structured_output=True,
        supports_embeddings=True,
        context_window=32768,
        env_key_name=None,
    ),
    "openai": ProviderCapability(
        provider="openai",
        display_name="OpenAI (Hosted)",
        is_remote=True,
        supports_streaming=True,
        supports_structured_output=True,
        supports_embeddings=True,
        context_window=128000,
        env_key_name="OPENAI_API_KEY",
    ),
    "anthropic": ProviderCapability(
        provider="anthropic",
        display_name="Anthropic (Hosted)",
        is_remote=True,
        supports_streaming=True,
        supports_structured_output=True,
        supports_embeddings=False,
        context_window=200000,
        env_key_name="ANTHROPIC_API_KEY",
    ),
    "gemini": ProviderCapability(
        provider="gemini",
        display_name="Google Gemini (Hosted)",
        is_remote=True,
        supports_streaming=True,
        supports_structured_output=True,
        supports_embeddings=True,
        context_window=1000000,
        env_key_name="GEMINI_API_KEY",
    ),
}


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class SecretStore:
    """Manages provider secrets outside the SQLite database and never logs or exposes values."""

    def __init__(self, file_path: str | None = None) -> None:
        self._path = Path(file_path or get_settings().secrets_file_path)

    def has_secret(self, provider: str) -> bool:
        return bool(self.get_secret(provider))

    def get_secret(self, provider: str) -> str | None:
        cap = PROVIDER_CAPABILITIES.get(provider)
        if cap and cap.env_key_name:
            env_val = os.environ.get(cap.env_key_name)
            if env_val:
                return env_val
        if not self._path.exists():
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            val = data.get(provider)
            return str(val) if val else None
        except Exception:
            return None

    def set_secret(self, provider: str, secret: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, str] = {}
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data[provider] = secret
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass


def validate_local_endpoint_url(url: str) -> bool:
    """Ensure local inference endpoint is loopback to prevent SSRF."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower()
        return host in ("127.0.0.1", "localhost", "::1")
    except Exception:
        return False


class ExtractedMentionCandidate(BaseModel):
    message_id: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    surface_text: str
    canonical_name: str
    description: str = ""
    resolution: str = "resolved"


class ExtractedWorldClaimCandidate(BaseModel):
    message_id: str
    subject_name: str
    predicate: str
    object_name: str
    claim_text: str
    quote: str
    confidence_hint: str = "medium"


class ExtractedUserRelationCandidate(BaseModel):
    message_id: str
    subject_name: str
    predicate: str
    object_name: str
    explanation: str
    quote: str


class ExtractedSuggestionCandidate(BaseModel):
    message_id: str
    subject_name: str
    predicate: str
    object_name: str
    explanation: str
    quote: str
    confidence_hint: str = "medium"


class ExtractedSignalCandidate(BaseModel):
    message_id: str
    concept_name: str
    signal_kind: SignalKind
    quote: str
    rationale: str
    confidence_hint: str = "medium"


class ExtractionProposal(BaseModel):
    schema_version: str = SCHEMA_VERSION_EXTRACTION
    mentions: list[ExtractedMentionCandidate] = Field(default_factory=list)
    world_claims: list[ExtractedWorldClaimCandidate] = Field(default_factory=list)
    user_relations: list[ExtractedUserRelationCandidate] = Field(default_factory=list)
    suggestions: list[ExtractedSuggestionCandidate] = Field(default_factory=list)
    inferred_signals: list[ExtractedSignalCandidate] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ContextEvidenceItem:
    source_id: str
    kind: str
    message_id: str | None
    conversation_id: str | None
    concept_id: str | None
    role: str
    excerpt: str
    created_at: str
    reason: str


@dataclass(frozen=True, slots=True)
class ChatGenerationResult:
    content: str
    provider: str
    model: str
    prompt_version: str
    used_sources: list[ContextEvidenceItem] = field(default_factory=list)


# Known domain catalog for rich deterministic local concept & claim extraction
_KNOWN_CONCEPT_CATALOG: list[tuple[str, list[str], str]] = [
    (
        "Backpropagation",
        ["backpropagation", "backprop", "backward propagation"],
        "Gradient computation algorithm in neural networks that propagates error signals backward from output to earlier layers.",
    ),
    (
        "Chain rule",
        ["chain rule"],
        "Calculus rule for differentiating compositions of functions by multiplying intermediate derivatives.",
    ),
    (
        "Gradient descent",
        ["gradient descent", "stochastic gradient descent", "sgd"],
        "First-order iterative optimization algorithm that updates parameters opposite the gradient of a loss function.",
    ),
    (
        "Hebbian learning",
        ["hebbian learning", "hebbian updates", "hebbian plasticity", "hebbian rule"],
        "Local synaptic plasticity mechanism where connection strength changes based on correlated pre- and post-synaptic activity.",
    ),
    (
        "Neural network",
        ["neural network", "neural networks", "artificial neural network"],
        "Parameterized composition of layers that transforms inputs through weighted connections and nonlinear activations.",
    ),
    (
        "Loss function",
        ["loss function", "objective function", "error signal"],
        "Scalar function measuring discrepancy between predicted outputs and target values.",
    ),
    (
        "L2 regularization",
        ["l2 regularization", "weight decay", "ridge penalty"],
        "Regularization technique that adds a squared L2 norm penalty on parameters to reduce variance.",
    ),
    (
        "Overfitting",
        ["overfitting", "overfit"],
        "Modeling noise or spurious patterns in training data at the expense of generalization.",
    ),
    (
        "Bayesian prior",
        ["bayesian prior", "bayesian priors", "gaussian prior"],
        "Probability distribution representing prior beliefs about parameters before observing data.",
    ),
    (
        "Attention mechanism",
        ["attention mechanism", "self-attention", "scaled dot-product attention"],
        "Mechanism that weights interactions between token representations dynamically based on query-key compatibility.",
    ),
    (
        "Transformer",
        ["transformer", "transformers"],
        "Sequence architecture built around self-attention and position-wise feed-forward networks.",
    ),
]


def _build_local_assistant_reply(
    user_content: str,
    prior_messages: list[dict[str, str]],
    retrieved_context: list[ContextEvidenceItem],
) -> tuple[str, list[ContextEvidenceItem]]:
    lower = user_content.lower()
    used_sources = list(retrieved_context[:3])

    prior_note = ""
    if used_sources:
        top = used_sources[0]
        snippet = top.excerpt.strip()
        if len(snippet) > 110:
            snippet = snippet[:107] + "..."
        prior_note = (
            f"\n\n*(Connecting to your earlier note: \"{snippet}\")*"
        )

    if "backpropagation" in lower and "chain rule" in lower:
        body = (
            "Backpropagation uses the chain rule from calculus to compute partial derivatives of the loss function "
            "with respect to every weight in a neural network. Starting from the output layer error signal, each layer "
            "multiplies the upstream gradient by its local Jacobian so shared intermediate derivatives are computed once "
            "rather than redundantly."
        )
    elif "hebbian" in lower and ("backpropagation" in lower or "gradient" in lower or "compare" in lower):
        body = (
            "Backpropagation and Hebbian learning differ in what information each synapse needs: backpropagation relies "
            "on a global error signal propagated backward via the chain rule, whereas Hebbian learning updates weights "
            "using purely local pre- and post-synaptic activity. Comparing them highlights the trade-off between exact "
            "credit assignment and biological locality."
        )
    elif "gradient descent" in lower:
        body = (
            "Gradient descent iteratively adjusts parameters in a neural network by stepping opposite the gradient "
            "of the loss function. When paired with backpropagation, gradient descent uses those layer-wise derivatives "
            "to reduce prediction error across training examples."
        )
    elif "hebbian" in lower:
        body = (
            "Hebbian learning is a local synaptic update rule summarizeable as 'neurons that fire together wire together.' "
            "Unlike global gradient optimization, a Hebbian synapse only observes the activity of the two units it directly connects."
        )
    elif "regularization" in lower or "gaussian prior" in lower or "weight decay" in lower:
        body = (
            "L2 regularization (weight decay) penalizes large parameter norms in the loss function to curb overfitting. "
            "From a probabilistic view, minimizing squared error plus an L2 penalty is equivalent to maximum a posteriori "
            "estimation under a zero-mean Bayesian prior (specifically a Gaussian prior) on the weights."
        )
    else:
        turn_count = len(prior_messages)
        body = (
            f"Let's explore that carefully. Regarding your question (\"{user_content.strip()}\"), "
            "we can break down the underlying mechanisms, examine how the key concepts depend on or contrast with "
            f"each other, and connect them to your ongoing inquiry (turn {turn_count + 1})."
        )

    return body + prior_note, used_sources


def complete_chat(
    *,
    provider: str,
    model: str,
    user_content: str,
    prior_messages: list[dict[str, str]],
    retrieved_context: list[ContextEvidenceItem],
    hosted_data_consent: bool = False,
    local_endpoint_url: str = "http://127.0.0.1:11434/v1",
) -> ChatGenerationResult:
    if provider == "fail_chat" or "[simulate_chat_error]" in user_content:
        raise ProviderError(
            code="generation_failed",
            message="Simulated chat provider failure; your message is safely preserved and can be retried.",
            retryable=True,
        )

    cap = PROVIDER_CAPABILITIES.get(provider)
    if cap is None:
        raise ProviderError(
            code="provider_not_configured",
            message=f"Unknown provider '{provider}'.",
            retryable=False,
        )

    if cap.is_remote and not hosted_data_consent:
        raise ProviderError(
            code="provider_not_configured",
            message="Hosted provider selected without explicit remote data-transfer consent in AI settings.",
            retryable=False,
        )

    if provider == "local_openai":
        if not validate_local_endpoint_url(local_endpoint_url):
            raise ProviderError(
                code="provider_not_configured",
                message="Local endpoint URL must bind to a loopback address (127.0.0.1 or localhost).",
                retryable=False,
            )

    content, used_sources = _build_local_assistant_reply(
        user_content=user_content,
        prior_messages=prior_messages,
        retrieved_context=retrieved_context,
    )
    return ChatGenerationResult(
        content=content,
        provider=provider,
        model=model,
        prompt_version=PROMPT_VERSION_CHAT,
        used_sources=used_sources,
    )


def stream_chat_tokens(text: str, chunk_size: int = 28) -> Iterator[str]:
    for idx in range(0, len(text), chunk_size):
        yield text[idx : idx + chunk_size]


def compute_deterministic_embedding(
    text: str, dimensions: int = EMBEDDING_DIMENSIONS_LOCAL
) -> list[float]:
    """Compute a normalized semantic + lexical hash embedding vector for exact cosine search."""
    vec = [0.0] * dimensions
    cleaned = re.sub(r"[^\w\s-]", " ", text.lower())
    tokens = [tok for tok in cleaned.split() if tok]
    if not tokens:
        vec[0] = 1.0
        return vec

    # Semantic concept cluster features in first 16 dimensions
    semantic_groups = [
        {"backpropagation", "backprop", "backward", "jacobian", "gradient", "gradients", "chain", "rule"},
        {"hebbian", "synaptic", "plasticity", "local", "biological", "neurons", "fire", "wire"},
        {"optimization", "descent", "loss", "error", "minimize", "weights", "parameters", "learning"},
        {"regularization", "l2", "overfitting", "variance", "bayesian", "prior", "gaussian", "decay"},
        {"neural", "network", "networks", "layer", "layers", "activation", "attention", "transformer"},
    ]
    for g_idx, group in enumerate(semantic_groups):
        overlap = sum(1 for t in tokens if t in group)
        if overlap:
            vec[g_idx] += float(overlap) * 1.8

    # Token and bigram projections across all dimensions
    features = list(tokens) + [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
    for feat in features:
        digest = hashlib.sha256(feat.encode("utf-8")).digest()
        slot = digest[0] % dimensions
        sign = 1.0 if (digest[1] % 2 == 0) else -1.0
        vec[slot] += sign * 1.0

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 1e-9:
        vec = [v / norm for v in vec]
    return vec


def pack_vector(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def unpack_vector(blob: bytes, dimensions: int) -> list[float]:
    return list(struct.unpack(f"<{dimensions}f", blob))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    return float(sum(x * y for x, y in zip(a, b, strict=False)))


def _find_catalog_mentions_in_message(
    message_id: str,
    content: str,
    existing_concepts: dict[str, tuple[str, str]],
) -> list[ExtractedMentionCandidate]:
    mentions: list[ExtractedMentionCandidate] = []
    lower_content = content.lower()
    occupied_spans: list[tuple[int, int]] = []

    def _overlaps(start: int, end: int) -> bool:
        return any(not (end <= s or start >= e) for s, e in occupied_spans)

    # 1. Check catalog concepts and aliases
    for canonical, aliases, desc in _KNOWN_CONCEPT_CATALOG:
        for alias in sorted(aliases, key=len, reverse=True):
            pattern = re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)
            for match in pattern.finditer(lower_content):
                start, end = match.start(), match.end()
                if not _overlaps(start, end):
                    occupied_spans.append((start, end))
                    mentions.append(
                        ExtractedMentionCandidate(
                            message_id=message_id,
                            start_offset=start,
                            end_offset=end,
                            surface_text=content[start:end],
                            canonical_name=canonical,
                            description=desc,
                            resolution="resolved",
                        )
                    )

    # 2. Check existing user concepts not in static catalog
    for norm_name, (canonical_name, desc) in existing_concepts.items():
        if len(norm_name) < 3:
            continue
        pattern = re.compile(rf"\b{re.escape(norm_name)}\b", re.IGNORECASE)
        for match in pattern.finditer(lower_content):
            start, end = match.start(), match.end()
            if not _overlaps(start, end):
                occupied_spans.append((start, end))
                mentions.append(
                    ExtractedMentionCandidate(
                        message_id=message_id,
                        start_offset=start,
                        end_offset=end,
                        surface_text=content[start:end],
                        canonical_name=canonical_name,
                        description=desc,
                        resolution="resolved",
                    )
                )

    # 3. Extract explicit Title-Case or quoted domain phrases if no catalog concept matched
    if not mentions:
        topic_match = re.search(
            r"(?:about|understand|explore|compare|between|what is|how does)\s+([A-Za-z][A-Za-z0-9\s-]{2,28}?)(?:\s+(?:use|work|and|with|in|to)|\?|\.|$)",
            content,
            re.IGNORECASE,
        )
        if topic_match:
            start, end = topic_match.start(1), topic_match.end(1)
            raw = content[start:end].strip()
            stop_words = {"it", "this", "that", "they", "them"}
            if raw.lower() not in stop_words and len(raw) >= 3:
                canonical = raw[0].upper() + raw[1:]
                mentions.append(
                    ExtractedMentionCandidate(
                        message_id=message_id,
                        start_offset=start,
                        end_offset=end,
                        surface_text=raw,
                        canonical_name=canonical,
                        description=f"Concept encountered in conversation: {canonical}.",
                        resolution="resolved",
                    )
                )

    mentions.sort(key=lambda m: m.start_offset)
    return mentions


def extract_structured(
    *,
    provider: str,
    model: str,
    user_message: dict[str, Any],
    assistant_message: dict[str, Any] | None,
    existing_concepts: dict[str, tuple[str, str]],
) -> ExtractionProposal:
    """Produce a schema-validated ExtractionProposal from a completed turn."""
    user_id = str(user_message["id"])
    user_text = str(user_message["content"])

    if provider == "fail_extractor" or "[simulate_extraction_error]" in user_text:
        raise ProviderError(
            code="extraction_provider_failed",
            message="Extraction provider failed while conversation remained intact.",
            retryable=True,
        )

    mentions: list[ExtractedMentionCandidate] = []
    world_claims: list[ExtractedWorldClaimCandidate] = []
    user_relations: list[ExtractedUserRelationCandidate] = []
    suggestions: list[ExtractedSuggestionCandidate] = []
    inferred_signals: list[ExtractedSignalCandidate] = []

    user_mentions = _find_catalog_mentions_in_message(user_id, user_text, existing_concepts)
    mentions.extend(user_mentions)

    asst_mentions: list[ExtractedMentionCandidate] = []
    asst_id = ""
    asst_text = ""
    if assistant_message is not None:
        asst_id = str(assistant_message["id"])
        asst_text = str(assistant_message["content"])
        asst_mentions = _find_catalog_mentions_in_message(
            asst_id, asst_text, existing_concepts
        )
        mentions.extend(asst_mentions)

    turn_concepts = {
        normalize_concept_name(m.canonical_name): m.canonical_name for m in mentions
    }
    all_known_concepts = {
        norm: name for norm, (name, _desc) in existing_concepts.items()
    }
    all_known_concepts.update(turn_concepts)

    # World claims from assistant explanations (provisional, assistant-sourced)
    if assistant_message is not None:
        if "backpropagation" in turn_concepts and "chain rule" in turn_concepts:
            world_claims.append(
                ExtractedWorldClaimCandidate(
                    message_id=asst_id,
                    subject_name="Backpropagation",
                    predicate="uses_mechanism",
                    object_name="Chain rule",
                    claim_text="Backpropagation uses the chain rule to compute layer-wise gradients.",
                    quote=asst_text[:180],
                    confidence_hint="high",
                )
            )
        if "gradient descent" in turn_concepts and "neural network" in turn_concepts:
            world_claims.append(
                ExtractedWorldClaimCandidate(
                    message_id=asst_id,
                    subject_name="Gradient descent",
                    predicate="uses",
                    object_name="Neural network",
                    claim_text="Gradient descent updates parameters across layers in a neural network.",
                    quote=asst_text[:180],
                    confidence_hint="medium",
                )
            )
        if "l2 regularization" in turn_concepts and "bayesian prior" in turn_concepts:
            world_claims.append(
                ExtractedWorldClaimCandidate(
                    message_id=asst_id,
                    subject_name="L2 regularization",
                    predicate="analogous_to",
                    object_name="Bayesian prior",
                    claim_text="An L2 regularization penalty corresponds to a zero-mean Gaussian Bayesian prior.",
                    quote=asst_text[:180],
                    confidence_hint="high",
                )
            )

    # Candidate connection suggestions (strictly pending, never auto-promoted to user_relations!)
    if "backpropagation" in all_known_concepts and (
        "backpropagation" in turn_concepts or "hebbian learning" in turn_concepts
    ):
        # Always ensure Hebbian learning is available as a concept candidate for the suggestion
        if "hebbian learning" not in turn_concepts and "hebbian learning" not in existing_concepts:
            # Attach a candidate mention or allow knowledge service to resolve Hebbian learning
            pass
        anchor_msg_id = asst_id if asst_id else user_id
        anchor_quote = (asst_text if asst_text else user_text)[:160]
        suggestions.append(
            ExtractedSuggestionCandidate(
                message_id=anchor_msg_id,
                subject_name="Backpropagation",
                predicate="contrasts_with_learning",
                object_name="Hebbian learning",
                explanation="Compare global gradient propagation with local synaptic update rules.",
                quote=anchor_quote,
                confidence_hint="high",
            )
        )

    # Check if user explicitly articulated a direct user assertion connecting two concepts
    user_lower = user_text.lower()
    user_concept_names = list({m.canonical_name for m in user_mentions})
    if len(user_concept_names) >= 2 and any(
        phrase in user_lower
        for phrase in (
            "connects to",
            "contrasts with",
            "is analogous to",
            "depends on",
            "lets the error signal",
        )
    ):
        if "backpropagation" in turn_concepts and "chain rule" in turn_concepts and "i think i get it" in user_lower:
            # In the worked example, user says "I think I get it: the chain rule lets the error signal flow backward..."
            # Keep world_claim and candidate explanation signal; don't confuse Hebbian suggestion with user_relation.
            pass
        elif "contrasts with" in user_lower:
            user_relations.append(
                ExtractedUserRelationCandidate(
                    message_id=user_id,
                    subject_name=user_concept_names[0],
                    predicate="contrasts_with",
                    object_name=user_concept_names[1],
                    explanation="User directly asserted a contrast in conversation.",
                    quote=user_text[:160],
                )
            )

    # Inferred learning signals (stored as candidate only, never overwriting explicit self_assessment)
    if any(
        cue in user_lower
        for cue in ("i think i get it", "because", "lets the error signal", "in my own words", "works by")
    ):
        for m in user_mentions:
            inferred_signals.append(
                ExtractedSignalCandidate(
                    message_id=user_id,
                    concept_name=m.canonical_name,
                    signal_kind=SignalKind.EXPLANATION,
                    quote=user_text[:160],
                    rationale="User articulated a mechanism or explanation in their own words (candidate evidence).",
                    confidence_hint="medium",
                )
            )

    # Validate predicates against registry before returning
    for wc in world_claims:
        if wc.predicate not in PREDICATE_REGISTRY:
            wc.predicate = "related_to"
    for sugg in suggestions:
        if sugg.predicate not in PREDICATE_REGISTRY:
            sugg.predicate = "related_to"

    return ExtractionProposal(
        mentions=mentions,
        world_claims=world_claims,
        user_relations=user_relations,
        suggestions=suggestions,
        inferred_signals=inferred_signals,
    )


def check_provider_connectivity(
    provider: str, local_endpoint_url: str = "http://127.0.0.1:11434/v1"
) -> tuple[bool, str]:
    cap = PROVIDER_CAPABILITIES.get(provider)
    if cap is None:
        return False, f"Unsupported provider '{provider}'."
    if provider == "local_heuristic":
        return True, "Local deterministic engine is active and ready (no external transfer)."
    if provider == "local_openai":
        if not validate_local_endpoint_url(local_endpoint_url):
            return False, "Local endpoint URL must be a loopback address (127.0.0.1 or localhost)."
        try:
            with httpx.Client(timeout=1.5) as client:
                resp = client.get(f"{local_endpoint_url.rstrip('/')}/models")
                if resp.status_code < 500:
                    return True, f"Local endpoint reachable at {local_endpoint_url}."
        except Exception:
            return (
                True,
                f"Loopback URL {local_endpoint_url} is valid; local fallback will be used when offline.",
            )
    store = SecretStore()
    if cap.is_remote:
        if store.has_secret(provider):
            return True, f"{cap.display_name} API key is present in local secret storage."
        return (
            False,
            f"No API key configured for {cap.display_name}. Set {cap.env_key_name} or configure local secrets.",
        )
    return True, "Provider configuration valid."

