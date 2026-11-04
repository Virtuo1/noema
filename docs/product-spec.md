# Product specification

## 1. Product summary

**Working description:** a personal knowledge environment in which a person explores ideas through conversation while the application quietly builds a navigable, evidence-backed model of concepts they have encountered, explored, questioned, connected, or demonstrated understanding of.

The product joins two activities that are usually separated: open-ended conversation and the gradual accumulation of personal knowledge. Chat remains the primary work surface. The structured model is a useful byproduct and a way back into prior thinking, not a filing task the user must perform after every conversation.

## 2. Problem and opportunity

Conversations are good for local exploration but weak at continuity. Important explanations and questions get buried; a later conversation may repeat earlier work without using it. Note-taking systems preserve material but often ask the user to classify, link, and maintain it manually. A graph alone does not solve either problem: an attractive network can still misrepresent what its owner knows.

The opportunity is to let conversation remain fluid while making accumulated evidence discoverable. The application should help a user resume a line of thought, inspect why a concept or relationship appears in their personal model, and correct an AI interpretation without losing the original history.

## 3. Product outcomes

The initial product should demonstrate these outcomes:

1. A user can explore an idea in an ordinary chat flow with little organizational overhead.
2. The assistant can use a small, relevant selection of the user's prior conversations and knowledge evidence.
3. Extracted concepts and candidate relationships become inspectable records with provenance, not invisible facts.
4. The user can explicitly mark a particular message or passage as understood, confusing, important, or worth revisiting.
5. The user can see the personal knowledge graph, distinguish their connections from suggestions, and open the supporting conversation.
6. The user can review a timeline showing when the model changed and what evidence caused the change.

Success is not measured by number of nodes, edges, or annotations. The core test is whether the user can recover a relevant prior idea with less effort and whether the system avoids overstating what they understand.

## 4. Users and initial assumptions

### Primary user

One individual curious across multiple domains who uses conversation to learn, reason, and develop ideas. They value continuity and data ownership, and do not want to maintain a manual taxonomy.

### Initial assumptions

- The first release serves one local user and one personal workspace.
- A conversation is the default place to think; users do not need to create folders or choose a concept before asking.
- Users may opt into hosted models, but some users will prefer a local model. Provider and model are configuration choices, not product identity.
- Users can correct, dismiss, or delete AI-derived material. The system should make these controls easy to find.
- The application is not a certified measure of learning, memory, expertise, or mental state.

## 5. Core interaction model

### Exploration first

The default screen is a chat workspace. The user asks, questions, explains, and reflects. The assistant may draw on prior context, but should keep answers focused and make it possible to inspect the sources behind personalized references.

### Background organization

After a user message and assistant turn are safely stored, an asynchronous task may extract concepts, mentions, explicit annotations, candidate relations, and knowledge signals. Extraction does not block the next turn. A lightweight indicator can show that prior material is being incorporated; a user should not have to wait for the graph to finish updating before continuing.

### Lightweight annotations

The user can attach one or more annotations to a message or selected passage. The initial UI should offer buttons/menu actions for `aha`, `confused`, `question`, `connection`, `hypothesis`, `revisit`, and `important`. Typing tags such as `#aha` can be a convenient shortcut, but must resolve to the same structured annotation and must not cause arbitrary hashtag text to be treated as a command without an explicit parsing rule. An annotation applies to the selected evidence span, or to the whole message when no span is selected.

Explicit annotations are preserved as user-authored records. The AI may add an inferred signal with lower authority and clear provenance, but may not rewrite an explicit annotation.

### Graph and history

The graph is a secondary exploration surface. It gives an overview, lets a user follow a relationship, and opens evidence or starts a chat grounded in a selected concept. Suggestions are visually and behaviorally distinct from accepted connections. The timeline supports review of changes rather than presenting understanding as a one-way score.

## 6. Core workflows

### A. Explore and resume an idea

1. User starts or opens a conversation and asks a question.
2. Assistant builds a focused answer using current conversation context and, where useful, retrieved personal evidence.
3. User continues naturally. They do not need to classify the conversation.
4. On a later visit, the assistant retrieves a small set of relevant prior messages, concepts, and unresolved questions, then cites or links those sources in the UI.

### B. Mark an understanding moment

1. User marks a message or passage `aha`.
2. The annotation is immediately saved as explicit user evidence and appears in the timeline.
3. The concept's current projection records an explicit self-report signal, not a proven mastery claim.
4. The graph may change visual status to “self-reported understanding”; it does not silently label the concept “understood.”

### C. Review an AI-extracted concept or connection

1. The extractor identifies a concept mention and possible relation, linking each to the source message and extraction run.
2. A relation inferred from the conversation is either recorded as a candidate user connection or placed in a suggestion, depending on whether the user actually asserted it. The extraction model cannot accept its own suggestion on the user's behalf.
3. User opens the suggestion, sees why it was proposed and which evidence was used, and accepts, rejects, or leaves it pending.
4. Acceptance creates a user-established relation and a knowledge event; rejection is also retained as history. Neither action rewrites the source message.

### D. Inspect a concept and its development

1. User selects a concept from search, chat, or graph.
2. The concept view shows mentions, annotations, relevant conversations, current knowledge signals, user-established links, and pending suggestions separately.
3. A timeline shows first encounter, exploration, confusion, self-report, demonstrated evidence, relation acceptance/rejection, and later revisions.

### E. Correct the model

1. User renames/merges a duplicate concept, removes an incorrect mention, corrects a relation, or deletes personal data.
2. The correction is applied to current projections and recorded as an event where useful.
3. The original evidence remains unless the user explicitly deletes it. On deletion, dependent indexes and derived records are removed or marked unavailable according to the deletion policy.

## 7. Functional requirements

### Core requirements for the initial prototype

- **FR-1 Conversations:** create, list, continue, and retrieve conversations and immutable message history.
- **FR-2 Assistant:** stream or return assistant responses through a provider abstraction; preserve provider/model metadata per turn.
- **FR-3 Context retrieval:** search prior messages and structured knowledge using lexical and semantic signals, and provide source references for retrieved context.
- **FR-4 Extraction:** enqueue background extraction after completed turns; identify concepts, message-level mentions, explicit annotations, candidate relations, unresolved questions, and possible learning signals.
- **FR-5 Provenance:** every extracted entity or claim must trace to source evidence and, for AI-created records, the extraction run and model/prompt version.
- **FR-6 Annotations:** create, list, and remove explicit user annotations on messages or passages; support multiple annotations.
- **FR-7 Knowledge state:** distinguish encounter, exploration, self-report, demonstrated evidence, and uncertainty. Repeated discussion alone must not imply understanding.
- **FR-8 Suggestions:** list, inspect, accept, and reject proposed connections. Acceptance is a user action that creates a user-established relation.
- **FR-9 Graph projection:** return a bounded, filterable graph with hierarchy and arbitrary relations, source links, status, and temporal filters.
- **FR-10 History:** record and retrieve knowledge events with timestamps and evidence references; support a historical “as of” graph query for the prototype's event types.
- **FR-11 Export/delete:** export all user-owned content and derived records in a documented open format; delete conversations and data with derived-index cleanup.
- **FR-12 Provider control:** configure hosted/local providers and select a model for conversation and extraction independently, even if the same model is used initially.

### Future capabilities, not initial requirements

- Multi-user accounts, sharing, collaborative graphs, cloud sync, and conflict-free offline merge.
- Automatic prerequisite curricula, quizzes, spaced repetition, mastery scores, or claims of objectively measuring learning.
- Continuous desktop capture, browser ingestion, PDF/library indexing, voice, mobile clients, and external knowledge imports.
- Automated concept ontology construction, broad world-knowledge ingestion, web research agents, and autonomous graph edits.
- Community graph templates, public profiles, and social recommendations.
- Multiple users/workspaces per installation and role-based access control.

## 8. Non-functional requirements

- **Low friction:** the common chat turn requires no mandatory tagging or filing.
- **Responsiveness:** conversational response time must not wait on extraction or graph layout. Retrieval should have an explicit latency budget established during prototype evaluation.
- **Reliability:** a failed extraction must not lose a conversation turn; jobs must be retryable and idempotent.
- **Explainability:** any personalized statement about the user's past or understanding should be traceable to evidence and should reveal whether it was explicit, inferred, or demonstrated.
- **Privacy:** local data remains local by default. Before using a hosted provider, disclose what message/context is sent and provide a configuration path to disable hosted calls.
- **Portability:** provide a complete export independent of proprietary graph/vector formats. Database migrations should be versioned.
- **Extensibility:** isolate provider, embedding, retrieval, graph projection, and rendering choices behind boundaries without introducing remote services prematurely.
- **Accessibility:** chat, annotation, graph selection, and evidence navigation need keyboard and screen-reader paths; color cannot be the only status signal.
- **Maintainability:** keep a modular monolith and explicit ownership of entities; avoid circular imports and direct cross-domain table mutation.

Initial performance and availability numbers remain open until there is a representative dataset and prototype. Do not promise scale targets based only on intuition.

## 9. Explicitly out of scope for the initial version

- Replacing the user's note editor, browser, task manager, or source-management system.
- Treating an LLM's internal world knowledge as a verified world model.
- Inferring expertise, intelligence, diagnosis, or durable mastery from chat frequency or style.
- A perfect map of every conversation or a graph that displays every relation at once.
- Distributed microservices, a dedicated graph database, autonomous agents, or multi-tenant cloud infrastructure.
- Reliable multi-device synchronization while offline.
- An all-domain ontology or source-of-truth encyclopedia.
- Automatically promoting AI-discovered conceptual links into the user's own knowledge.

## 10. Product principles

1. **Reduce cognitive load:** organization is mostly automatic and never mandatory on every turn.
2. **Preserve agency:** user assertions and AI suggestions remain distinguishable; only the user can establish their personal connections in the initial product.
3. **Keep evidence close:** derived knowledge links back to the message, annotation, or source that supports it.
4. **Maintain continuity:** retrieve prior work when it helps, without flooding the current conversation.
5. **Be honest about uncertainty:** exposure, exploration, self-report, and demonstrated understanding are separate signals.
6. **Support non-linear thought:** hierarchy helps orient the user; cross-links remain first-class.
7. **Retain history:** revisions add events instead of erasing how the model changed, subject to user deletion.
8. **Keep data portable:** user-owned records are exportable in ordinary formats.

## 11. Open product decisions

These should be answered through prototype use rather than blocking architecture:

1. **What is the user-facing vocabulary?** “Knowledge,” “understanding,” “confidence,” and “evidence” can feel evaluative. Test neutral labels such as “encountered,” “explored,” “you marked as understood,” and “shown in your explanations.”
2. **When should the assistant surface a connection?** Inline interruptions may add friction. Start with a quiet suggestion inbox and an opt-in contextual mention; measure usefulness before increasing interruption.
3. **How much graph is useful by default?** A focused neighborhood may be more navigable than a full map. Prototype both overview and concept-centered views.
4. **Should free-form `#tags` be parsed?** Recommendation: UI annotation actions first; parse known tags only when they appear as standalone tokens in user messages, show confirmation/undo, and preserve literal text.
5. **What exactly counts as demonstrated understanding?** For the MVP, store observable evidence such as the user explaining a concept, comparing ideas, or solving a problem. Do not claim mastery; let the user decide whether evidence is meaningful.
6. **What hosted deployment is desired later?** It changes account, encryption, operational, sync, and database decisions. The local prototype intentionally avoids prematurely settling this.
7. **What deletion semantics are desired for event history?** User control requires deletion to remove source and derived personal data. An audit event may be retained only if it does not preserve content the user intended to erase; default recommendation is hard deletion of linked personal content and no retained payload.

## 12. Prototype validation questions

- Can a user resume a prior exploration with fewer repeated explanations or searches?
- Are cited retrieved passages relevant enough to be trusted?
- Does the graph explain itself through evidence and status, or does it feel like another inbox to maintain?
- Do explicit annotations feel fast, and do inferred learning signals feel unobtrusive and correctable?
- Can a user tell a suggestion from a personally established relation at a glance?
- Does the timeline help the user reflect without implying that knowledge is a simple score?
