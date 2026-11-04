# Initial API design

## 1. API conventions

- Base path: `/api/v1`.
- JSON uses `snake_case`, UUID string IDs, and UTC RFC 3339 timestamps.
- The local installation has one implicit owner. The client never supplies `owner_user_id`; authorization is derived from the local principal. A hosted deployment must add explicit authentication and workspace scoping before exposure.
- All list endpoints support bounded pagination. Use opaque cursors for messages/events where stable ordering matters.
- Mutations accept an `Idempotency-Key` header where retries could duplicate a turn, annotation, relation, or suggestion resolution.
- Errors use a stable envelope: `{"error":{"code":"...","message":"...","details":{}}}`. Never return secrets or raw provider traces.
- API DTOs expose provenance and status explicitly. Avoid returning a generic `confidence` without its scope/model.

## 2. Main resources

### Conversations

| Method and path | Purpose |
|---|---|
| `POST /conversations` | Create an empty conversation; optional editable title. |
| `GET /conversations?cursor=&limit=&q=` | List conversations by recent activity; search optional. |
| `GET /conversations/{conversation_id}` | Retrieve title, timestamps, and turn status. |
| `PATCH /conversations/{conversation_id}` | Rename/archive. |
| `GET /conversations/{conversation_id}/messages?cursor=&limit=` | Retrieve ordered message history with annotations and generation metadata. |
| `POST /conversations/{conversation_id}/turns` | Persist a user message and start assistant generation. |
| `GET /turns/{turn_id}` | Retrieve generation status, user/assistant message IDs, and failure details. |
| `GET /turns/{turn_id}/stream` | SSE stream of assistant deltas and final metadata; reconnect using `Last-Event-ID`. |
| `POST /turns/{turn_id}/retry` | Retry a failed generation using the existing user message and a new generation attempt. |

Create conversation request:

```json
{"title":"Learning theory"}
```

Create and continue conversation request:

```http
POST /api/v1/conversations/conv_2/turns
Idempotency-Key: 4c8a...
Content-Type: application/json
```

```json
{
  "content":"How does backpropagation use the chain rule?",
  "context_mode":"personalized",
  "client_message_id":"local-msg-93"
}
```

Accepted response (`202`):

```json
{
  "turn_id":"turn_11",
  "status":"running",
  "user_message":{"id":"msg_41","sequence_no":12,"role":"user","content":"How does backpropagation use the chain rule?"},
  "assistant_message_id":null,
  "stream_url":"/api/v1/turns/turn_11/stream"
}
```

SSE events may be `turn.started`, `assistant.delta`, `assistant.message`, `turn.completed`, `turn.failed`, and `knowledge.status`. Include event IDs. Completion metadata contains the assistant message ID, provider/model display name, source references used, and extraction status (usually `queued`). The HTTP stream is transport only; it is not the source of truth.

Message response shape:

```json
{
  "id":"msg_41",
  "conversation_id":"conv_2",
  "sequence_no":12,
  "role":"user",
  "content":"How does backpropagation use the chain rule?",
  "created_at":"2026-11-04T10:05:00Z",
  "annotations":[],
  "sources":[]
}
```

### Annotations

| Method and path | Purpose |
|---|---|
| `POST /messages/{message_id}/annotations` | Add an explicit annotation to a whole message or selected span. |
| `GET /messages/{message_id}/annotations` | List explicit and inferred annotations, clearly labeled. |
| `DELETE /annotations/{annotation_id}` | Remove an annotation; only explicit user action can remove an explicit tag. |

Request:

```json
{
  "tag":"aha",
  "span":{"start_offset":0,"end_offset":88,"offset_unit":"unicode_codepoint"}
}
```

The span is optional; omitted means whole message. Response includes annotation ID, `origin: "user_explicit"`, timestamp, anchored quote, and affected concept IDs (possibly empty or ambiguous). Annotation creation also records a timeline event. Do not create a self-understanding state for every concept mentioned if span-to-concept mapping is unclear.

### Concepts and knowledge graph

| Method and path | Purpose |
|---|---|
| `GET /knowledge/graph?focus_concept_id=&depth=&node_limit=&edge_limit=&layers=&predicates=&as_of=` | Return a bounded graph projection. |
| `GET /concepts/{concept_id}` | Retrieve concept identity, aliases, current personal signals, summaries, and counts. |
| `GET /concepts/{concept_id}/evidence?kind=&cursor=&limit=` | Retrieve messages, annotations, events, claims, and relation evidence. |
| `GET /concepts/{concept_id}/related?layers=&depth=&limit=` | Retrieve ranked neighboring concepts with relation kind, origin, evidence, and status. |
| `GET /concepts/{concept_id}/history?before=&after=&cursor=` | Retrieve events for the concept. |
| `POST /concepts/{concept_id}/relations` | Record a direct user-established relation with evidence/target concept. |
| `POST /concepts/{concept_id}/merge` | Explicitly merge a duplicate concept into another; emits a merge event. |

### User hypotheses

| Method and path | Purpose |
|---|---|
| `GET /hypotheses?status=active&cursor=&limit=` | List the user's active or historical hypotheses. |
| `POST /messages/{message_id}/hypotheses` | Preserve a user-authored hypothesis anchored to a message/span. |
| `GET /hypotheses/{hypothesis_id}` | Retrieve statement, status, source evidence, and revisions. |
| `POST /hypotheses/{hypothesis_id}/revise` | Create a successor hypothesis and mark the prior version revised. |
| `POST /hypotheses/{hypothesis_id}/evidence` | Attach supporting or challenging evidence. |

Creating a hypothesis is a user action or a confirmation of an extracted candidate, not an automatic consequence of any speculative sentence. Revision creates a new row linked by `supersedes_hypothesis_id`; it does not replace the prior statement.

Create request:

```json
{
  "statement":"Local learning rules may be more biologically plausible than global gradient propagation.",
  "span":{"start_offset":0,"end_offset":90,"offset_unit":"unicode_codepoint"}
}
```

Graph query example:

```http
GET /api/v1/knowledge/graph?focus_concept_id=c_bp&depth=1&node_limit=80&edge_limit=120&layers=user,world,suggested
```

Response:

```json
{
  "as_of":"2026-11-04T10:15:00Z",
  "focus_concept_id":"c_bp",
  "nodes":[
    {"id":"c_bp","kind":"concept","label":"Backpropagation","signals":{"encountered":true,"explored":true,"self_assessment":"self_reports_understanding","demonstration_status":"none"}},
    {"id":"c_hb","kind":"concept","label":"Hebbian learning","signals":{"encountered":true,"explored":true,"self_assessment":"unknown","demonstration_status":"none"}}
  ],
  "edges":[
    {"id":"suggestion:s_4","source":"c_bp","target":"c_hb","predicate":"contrasts_with_learning","layer":"suggested","status":"pending","evidence_count":2,"suggestion_id":"s_4"}
  ],
  "truncated":false,
  "counts":{"nodes":2,"edges":1,"omitted_nodes":0,"omitted_edges":0}
}
```

For `as_of`, the backend replays relevant state changes up to the timestamp. A response that cannot be reconstructed should return an explicit unsupported-history error rather than a misleading current graph.

### Suggestions and relationships

| Method and path | Purpose |
|---|---|
| `GET /suggestions?status=pending&concept_id=&cursor=&limit=` | List pending or historical suggestions. |
| `GET /suggestions/{suggestion_id}` | Retrieve explanation, source evidence, model provenance, and status. |
| `POST /suggestions/{suggestion_id}/accept` | Establish the personal relation; idempotently returns created relation. |
| `POST /suggestions/{suggestion_id}/reject` | Reject and retain suggestion history; optional reason. |
| `POST /suggestions/{suggestion_id}/dismiss` | Hide without asserting that the suggestion is wrong. |
| `GET /relations/{relation_id}` | Retrieve relation, endpoints, evidence, history, and origin. |
| `POST /relations/{relation_id}/withdraw` | Withdraw a current user relation while preserving history. |

Accept request may provide an edited predicate or explanation; if edited, store the user's version in the relation/evidence and preserve the original suggestion. The assistant cannot call this operation on behalf of the user.

### Search and timeline

| Method and path | Purpose |
|---|---|
| `GET /search?q=&kind=&after=&before=&limit=` | Hybrid search across messages, concepts, and hypotheses; returns ranked results with source IDs and channel/rank metadata. |
| `GET /events?concept_id=&event_type=&after=&before=&cursor=&limit=` | Retrieve a user's knowledge timeline. |
| `GET /events/{event_id}` | Retrieve event details and linked evidence. |

Search returns snippets and provenance, not raw embeddings or internal ranking vectors. UI can request evidence detail by source ID.

### Provider configuration and data ownership

| Method and path | Purpose |
|---|---|
| `GET /settings/ai` | Return configured provider names, selected task/model mapping, and capabilities; never return secrets. |
| `PUT /settings/ai` | Update provider/model preferences and hosted-data consent. |
| `POST /settings/ai/validate` | Validate a provider configuration without logging credentials or message content. |
| `POST /export` | Start a full data export and return job/status. |
| `DELETE /conversations/{conversation_id}` | Delete conversation and dependent messages, mentions, annotations, evidence, search documents, embeddings, and derived personal records according to retention rules. |

Secret setup should use a local secret store/OS keychain integration, not `GET`/`PUT` plaintext values. Export and deletion should have explicit result/status endpoints if they become asynchronous.

## 3. Domain behavior behind endpoints

- The API layer validates shape, ownership, and limits; domain services enforce relation/state invariants.
- Accepting a suggestion and creating a user relation plus event is one database transaction.
- Adding an annotation and updating state projections/events is one transaction.
- Chat generation and extraction model calls happen outside DB transactions; durable run/job rows bracket external work.
- Graph/search endpoints return source IDs and status fields so clients can link to evidence without reconstructing provenance.
- A suggestion's status and a user relation are separate resources. Rejection never creates an edge.
- An API retry with the same idempotency key returns the original turn/result and does not duplicate content.

## 4. Status and error examples

Representative error codes:

- `conversation_not_found`, `concept_not_found`, `message_not_found` (`404`)
- `invalid_span`, `unsupported_annotation_tag`, `invalid_relation_predicate` (`422`)
- `suggestion_already_resolved`, `relation_conflict` (`409`)
- `provider_not_configured`, `provider_unavailable`, `generation_failed` (appropriate `4xx`/`5xx` plus retryability)
- `history_unavailable_for_timestamp` (`422`)
- `rate_limited` (`429`) if later needed for hosted deployment.

Error details should identify a field or retryability but never include full prompts, source text, or credentials unless the user explicitly opens a local diagnostic view.

## 5. OpenAPI and compatibility

FastAPI can publish an OpenAPI document for request/response contracts. Treat `/api/v1` DTOs as public within the frontend/backend boundary: generate a TypeScript client/types where practical instead of hand-maintaining mirrored schemas. Make additive response fields backward-compatible; version breaking changes in a later API prefix. Keep persistence entities separate from API response models.
