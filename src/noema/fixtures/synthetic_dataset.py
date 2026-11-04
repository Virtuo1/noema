"""Synthetic, consented evaluation dataset for retrieval and extraction review (Phase 0/2)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SyntheticTurn:
    role: str
    content: str
    expected_concepts: list[str] = field(default_factory=list)
    explicit_annotation: str | None = None


@dataclass(frozen=True, slots=True)
class SyntheticConversation:
    slug: str
    title: str
    turns: list[SyntheticTurn]
    expected_world_claims: list[tuple[str, str, str]] = field(default_factory=list)
    expected_suggestions: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RetrievalEvalCase:
    query: str
    expected_conversation_slug: str
    expected_term: str
    rationale: str


SYNTHETIC_CONVERSATIONS: list[SyntheticConversation] = [
    SyntheticConversation(
        slug="conv_optimization_and_hebbian",
        title="Gradient Descent and Synaptic Plasticity",
        turns=[
            SyntheticTurn(
                role="user",
                content="How does gradient descent update parameters in a neural network, and how is that different from biological Hebbian learning?",
                expected_concepts=["Gradient descent", "Neural network", "Hebbian learning"],
            ),
            SyntheticTurn(
                role="assistant",
                content=(
                    "Gradient descent minimizes a global loss function by stepping opposite the gradient "
                    "across parameters in a neural network. By contrast, Hebbian learning is a local synaptic "
                    "plasticity rule ('cells that fire together wire together') that depends only on pre- and "
                    "post-synaptic activity rather than a global error signal."
                ),
                expected_concepts=["Gradient descent", "Neural network", "Hebbian learning"],
            ),
        ],
        expected_world_claims=[
            ("Gradient descent", "uses", "Neural network"),
        ],
    ),
    SyntheticConversation(
        slug="conv_backprop_chain_rule",
        title="Backpropagation and the Chain Rule",
        turns=[
            SyntheticTurn(
                role="user",
                content="How does backpropagation use the chain rule to compute gradients?",
                expected_concepts=["Backpropagation", "Chain rule"],
            ),
            SyntheticTurn(
                role="assistant",
                content=(
                    "Backpropagation uses the chain rule from calculus to compute partial derivatives of the loss "
                    "with respect to each weight layer by layer, reusing intermediate Jacobians from the output "
                    "backward to earlier layers."
                ),
                expected_concepts=["Backpropagation", "Chain rule"],
            ),
            SyntheticTurn(
                role="user",
                content="I think I get it: the chain rule lets the error signal flow backward through the network. #aha",
                expected_concepts=["Chain rule", "Backpropagation"],
                explicit_annotation="aha",
            ),
        ],
        expected_world_claims=[
            ("Backpropagation", "uses_mechanism", "Chain rule"),
        ],
        expected_suggestions=[
            ("Backpropagation", "contrasts_with_learning", "Hebbian learning"),
        ],
    ),
    SyntheticConversation(
        slug="conv_regularization_confusion",
        title="Regularization and Overfitting",
        turns=[
            SyntheticTurn(
                role="user",
                content="Why does L2 regularization prevent overfitting, and how does it relate to Bayesian priors? #confused",
                expected_concepts=["L2 regularization", "Overfitting", "Bayesian prior"],
                explicit_annotation="confused",
            ),
            SyntheticTurn(
                role="assistant",
                content=(
                    "L2 regularization penalizes large weight norms, which reduces model variance and prevents "
                    "overfitting. In Bayesian inference, an L2 penalty corresponds to a zero-mean Gaussian prior "
                    "on the weights under maximum a posteriori estimation."
                ),
                expected_concepts=["L2 regularization", "Overfitting", "Bayesian prior"],
            ),
        ],
        expected_world_claims=[
            ("L2 regularization", "analogous_to", "Bayesian prior"),
        ],
    ),
]


RETRIEVAL_EVAL_CASES: list[RetrievalEvalCase] = [
    RetrievalEvalCase(
        query="How does backpropagation use the chain rule and how does it compare to gradient descent?",
        expected_conversation_slug="conv_optimization_and_hebbian",
        expected_term="gradient descent",
        rationale="Should retrieve prior optimization explanation without flooding unrelated regularization turns.",
    ),
    RetrievalEvalCase(
        query="I want to compare local Hebbian updates with global error propagation.",
        expected_conversation_slug="conv_backprop_chain_rule",
        expected_term="chain rule",
        rationale="Should retrieve the user's #aha passage about error signal flowing backward via the chain rule.",
    ),
    RetrievalEvalCase(
        query="Can we revisit why weight decay acts like a Gaussian prior?",
        expected_conversation_slug="conv_regularization_confusion",
        expected_term="Bayesian prior",
        rationale="Should retrieve the earlier confusion-tagged turn on L2 regularization and Bayesian priors.",
    ),
]

