# Knowledge representation and understanding model

## 1. The model is an evidence ledger, not a score of the person

The system does not have direct access to a user's mind. It can preserve what the user said, what they marked, what they explored, and what they demonstrated in an interaction. It may organize these signals into useful current views, but it must not present those views as a complete or objective measure of knowledge.

The product therefore stores observable signals and their sources. It avoids a single scalar such as `knowledge_score = 0.82`. A value that looks precise would hide the difference between familiarity, confidence, demonstrated explanation, and uncertainty.

## 2. Four personal states

These are independent dimensions, not a ladder that must be climbed:

| Dimension | Meaning | Safe evidence | What it does not mean |
|---|---|---|---|
| Encountered | The concept appeared in material the user saw or discussed | Message mention, source opened, imported note | The user noticed or retained it |
| Explored | The user actively asked, reasoned, compared, or returned to the concept | User questions, discussion across turns, explicit revisit | The user understands it |
| Self-report | What the user explicitly says about their own understanding | `#aha`, `#confused`, or a user-confirmed first-person statement | Independent proof of mastery |
| Demonstrated evidence | The user explained, applied, compared, predicted, or solved something related | User-authored explanation or problem-solving evidence linked to the concept/relation | Permanent mastery or ability in every context |

An implementation can display simple language derived from these dimensions (“You marked this as understood,” “You have explored this several times,” “You explained this in a later conversation”). It should avoid a single status badge named “knows.”

## 3. Explicit and inferred signals

### Explicit signals

Explicit signals are user actions or user-confirmed statements. UI annotations are the strongest low-friction form. Store their exact message/span, timestamp, tag, and explicit origin. Never let an extractor rewrite them. A user can remove or change their own annotation; the change itself is recorded.

For natural statements such as “I’m still confused about regularization,” an extractor may propose an explicit self-report tied to the user's own message and quote span. Because the model may misread sarcasm or hypotheticals, initial policy should either ask for confirmation or label it as an inferred interpretation until confirmed. The user-written `#confused` action remains explicit without confirmation.

### Inferred signals

Signals inferred from conversation are stored separately with:

- source role and exact evidence span;
- inference type (possible confusion, explanation, comparison, application, uncertainty, contradiction);
- model, prompt/schema version, and extraction run;
- a qualitative review label (`low|medium|high`) used only to sort or filter proposals;
- status (`candidate|confirmed|dismissed`) if surfaced for user review.

An inferred signal must not overwrite `self_assessment`. In the first prototype, inferred signals may appear as “possible evidence” in the concept history, with status `candidate`. A UI annotation updates the corresponding self-report immediately. A free-text statement that appears to express understanding or confusion remains a candidate until the user confirms it; extracted demonstration evidence also remains a candidate until confirmed. This prevents sarcasm, role-play, or assistant wording from silently becoming a claim about the user.

### Confidence discipline

Model confidence is not necessarily calibrated across prompts or providers. Keep it as an opaque ranking hint scoped to a particular model and extraction version. Do not compare confidence values from different models as if they share a probability scale. UI should prefer provenance labels and user review over percentages.

## 4. What counts as evidence of understanding?

Understanding has no universal database test. For a practical initial model, store *evidence forms* rather than claim a concept is mastered:

- **Explanation:** user describes an idea in their own words.
- **Application:** user uses it to solve a problem or make a prediction.
- **Comparison:** user explains a meaningful distinction or relation.
- **Correction/revision:** user identifies and repairs a prior misconception.
- **Explicit reflection:** user describes what they understand or still do not understand.

An extractor may suggest one of these evidence forms and link it to the user message. The UI should allow the user to confirm or dismiss an inferred interpretation. A qualitative projection such as `some_evidence` or `repeated_evidence` is only a summary of retained evidence. `repeated_evidence` should require evidence on distinct occasions, not repeated wording in one answer. An explicit later confusion or correction can change the projection to `contradictory_evidence` or prompt a fresh review; prior evidence stays in the event history.

The product should not automatically generate quizzes or score users in the initial version. If assessments are later added, they need an explicit product model, user consent, calibrated domain-specific scoring, and clear limits.

## 5. Relationship classes

The same pair of concepts may have separate world and personal relations:

1. **World claim:** a proposition about the conceptual domain, with polarity, source, status, and evidence. Example: “Backpropagation uses the chain rule.” A language model answer alone starts as provisional.
2. **User-established relation:** a connection the user directly articulated, explicitly annotated, or accepted. Example: “I see how local Hebbian updates contrast with global gradient propagation.” This is a record of the user's map, not proof of mastery.
3. **AI suggestion:** a candidate connection generated by the system. It has an explanation and evidence, remains pending, and is excluded from established personal edges until accepted.
4. **Inferred relation candidate:** extraction detects that the user may have stated a relation. Keep it as a candidate/suggestion until source and intent are clear. A direct unambiguous user assertion can be recorded as `direct_user_assertion` with the original user message as evidence, never with an assistant explanation as the only support.

Predicates should be typed, directional where appropriate, and open to extension. A small initial vocabulary can include `is_a`, `part_of`, `depends_on`, `prerequisite_for`, `uses`, `causes`, `contrasts_with`, `analogous_to`, and `related_to`. Keep the predicate label and a short human-readable description. Avoid reducing every relationship to a generic “related” edge.

For symmetric predicates such as `contrasts_with`, the service should canonicalize duplicate inverse rows for query/display while retaining the user's natural direction in evidence. Do not infer that relation symmetry from predicate spelling alone; use explicit predicate metadata.

## 6. Uncertainty and contradictions

Uncertainty is represented on the claim or signal it qualifies, not as a global property of a concept:

- a self-report can be `uncertain`;
- a world claim can be provisional, supported, challenged, or superseded;
- a suggestion can be pending, accepted, rejected, or dismissed;
- a personal evidence projection can reflect no, some, repeated, or contradictory evidence;
- each derived record has provenance and timestamps.

When later evidence conflicts with an earlier claim or self-report, append a contradiction/revision event and retain both sources. The current view may prioritize the newer user statement while showing the earlier one in history. Do not silently edit old text or erase the timeline.

Do not infer forgetting simply because a user has not visited a topic for a while. A recency cue can say “not revisited since…”; actual uncertainty or decline needs fresh evidence from the user or an explicitly consented assessment workflow.

## 7. State transitions and authority rules

| Input/event | May update current projection? | Authority |
|---|---|---|
| Concept mention in a user/assistant message | `encountered_at`, possibly `last_explored_at` if the user actively engages | Evidence of exposure only |
| Repeated active questions or discussion | `last_explored_at`; exploration count may be derived | Not understanding |
| User attaches `#aha` | Explicit `self_assessment=self_reports_understanding` for linked concepts if the mapping is clear | Strong self-report, not mastery proof |
| User attaches `#confused` | Explicit self-report `confused`; keep older evidence | Current report can supersede current summary, history remains |
| User explanation/problem-solving | Add candidate demonstration evidence; on confirmation, projection may become `some_evidence` | Evidence, not automatic mastery |
| AI detects possible explanation/confusion | Add candidate inferred signal only | Low authority; no silent self-report mutation |
| User accepts suggestion | Create established user relation and event | Explicit acceptance of connection only |
| Assistant describes a relation | May create provisional world claim with assistant-message evidence | Never a user relation by itself |
| User corrects a prior hypothesis | Add new version/revision event, retain old hypothesis | User's current statement is authoritative for their belief, not necessarily objective fact |

The `#aha` annotation should only update state for concepts tied to the annotated span/message with adequate resolution. If several concepts are mentioned and it is unclear which one the user means, preserve the annotation and ask no follow-up by default; show the ambiguity in the evidence view rather than applying it indiscriminately.

## 8. Historical representation

Each consequential state change emits a knowledge event with actor, source reference, occurred/recorded timestamps, and a typed delta. The current state table is updated atomically. A historical query replays events up to time `T`, applying `before`/`after` transitions and omitting entities not yet created. This supports “what did my map look like then?” without interpreting old evidence through today's state.

Events are append-only in normal operation. User deletion is an explicit privacy operation: it deletes source content and dependent evidence/derived data, and removes or redacts event payloads that would preserve the deleted content. History is valuable but does not override data ownership.

## 9. Presentation language

Prefer:

- “You first explored this on…”
- “You marked this passage as `aha`.”
- “You explained this in your own words here.”
- “Possible connection suggested by the assistant.”
- “Your current reflection says you are unsure.”
- “This earlier claim was revised later.”

Avoid unqualified claims such as “You know this,” “Mastered,” “Your confidence is 83%,” or “The graph proves…”
