/** Typed HTTP client for the /api/v1 backend. */

import type {
  AISettingsDTO,
  AnnotationDTO,
  AnnotationTag,
  ConceptDetailDTO,
  ConceptEvidenceResponse,
  ConversationDTO,
  ExportResultResponse,
  GraphProjectionResponse,
  KnowledgeEventDTO,
  MessageDTO,
  SearchResultDTO,
  SpanDTO,
  SuggestionDTO,
  TurnAcceptedResponse,
  TurnStatusResponse,
  UpdateAISettingsPayload,
  UserRelationDTO,
} from "./types";

const API_BASE = "/api/v1";

async function requestJson<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  if (response.status === 204) {
    return undefined as unknown as T;
  }
  const data: unknown = await response.json();
  if (!response.ok) {
    const errObj = data as { error?: { message?: string; code?: string } };
    throw new Error(
      errObj?.error?.message || `Request failed with status ${response.status}`,
    );
  }
  return data as T;
}

export const apiClient = {
  listConversations: async (q?: string): Promise<ConversationDTO[]> => {
    const params = q ? `?q=${encodeURIComponent(q)}` : "";
    const res = await requestJson<{ items: ConversationDTO[] }>(
      `/conversations${params}`,
    );
    return res.items;
  },

  createConversation: async (title = ""): Promise<ConversationDTO> =>
    requestJson<ConversationDTO>("/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),

  deleteConversation: async (conversationId: string): Promise<void> =>
    requestJson<void>(`/conversations/${conversationId}`, {
      method: "DELETE",
    }),

  listMessages: async (conversationId: string): Promise<MessageDTO[]> => {
    const res = await requestJson<{ items: MessageDTO[] }>(
      `/conversations/${conversationId}/messages`,
    );
    return res.items;
  },

  sendTurn: async (
    conversationId: string,
    content: string,
    contextMode: "personalized" | "conversation_only" = "personalized",
  ): Promise<TurnAcceptedResponse> => {
    const idemKey = `turn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    return requestJson<TurnAcceptedResponse>(
      `/conversations/${conversationId}/turns`,
      {
        method: "POST",
        headers: { "Idempotency-Key": idemKey },
        body: JSON.stringify({ content, context_mode: contextMode }),
      },
    );
  },

  sendTurnStream: async (
    conversationId: string,
    content: string,
    callbacks: {
      onDelta: (delta: string) => void;
      onFailed?: (turnId: string, message: string) => void;
    },
    contextMode: "personalized" | "conversation_only" = "personalized",
  ): Promise<void> => {
    const idemKey = `turn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const response = await fetch(
      `${API_BASE}/conversations/${conversationId}/turns/stream`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idemKey,
        },
        body: JSON.stringify({ content, context_mode: contextMode }),
      },
    );

    if (!response.body) {
      // Fallback for test environments without ReadableStream body
      const res = await apiClient.sendTurn(
        conversationId,
        content,
        contextMode,
      );
      if (res.status === "failed") {
        callbacks.onFailed?.(
          res.turn_id,
          res.error_message || "Generation failed.",
        );
      } else if (res.assistant_message?.content) {
        callbacks.onDelta(res.assistant_message.content);
      }
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";

      for (const block of blocks) {
        let eventName = "";
        let dataLine = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) {
            eventName = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataLine = line.slice(5).trim();
          }
        }
        if (!dataLine) continue;
        try {
          const parsed = JSON.parse(dataLine) as Record<string, unknown>;
          if (
            eventName === "assistant.delta" &&
            typeof parsed.delta === "string"
          ) {
            callbacks.onDelta(parsed.delta);
          } else if (eventName === "turn.failed") {
            callbacks.onFailed?.(
              String(parsed.turn_id ?? ""),
              String(
                parsed.message ??
                  "Assistant generation failed. Your message is safely saved.",
              ),
            );
          }
        } catch {
          // Ignore malformed chunk
        }
      }
    }
  },

  getTurnStatus: async (turnId: string): Promise<TurnStatusResponse> =>
    requestJson<TurnStatusResponse>(`/turns/${turnId}`),

  retryTurn: async (turnId: string): Promise<TurnAcceptedResponse> =>
    requestJson<TurnAcceptedResponse>(`/turns/${turnId}/retry`, {
      method: "POST",
    }),

  retryTurnExtraction: async (
    turnId: string,
  ): Promise<{ turn_id: string; extraction_status: string }> =>
    requestJson<{ turn_id: string; extraction_status: string }>(
      `/turns/${turnId}/retry-extraction`,
      { method: "POST" },
    ),

  addAnnotation: async (
    messageId: string,
    tag: AnnotationTag,
    span: SpanDTO | null = null,
  ): Promise<AnnotationDTO> =>
    requestJson<AnnotationDTO>(`/messages/${messageId}/annotations`, {
      method: "POST",
      body: JSON.stringify({ tag, span }),
    }),

  removeAnnotation: async (annotationId: string): Promise<void> =>
    requestJson<void>(`/annotations/${annotationId}`, {
      method: "DELETE",
    }),

  getGraph: async (params: {
    focusConceptId?: string | null;
    layers?: string[];
    asOf?: string | null;
  }): Promise<GraphProjectionResponse> => {
    const search = new URLSearchParams();
    if (params.focusConceptId) {
      search.set("focus_concept_id", params.focusConceptId);
    }
    if (params.layers && params.layers.length > 0) {
      search.set("layers", params.layers.join(","));
    }
    if (params.asOf) {
      search.set("as_of", params.asOf);
    }
    const qs = search.toString() ? `?${search.toString()}` : "";
    return requestJson<GraphProjectionResponse>(`/knowledge/graph${qs}`);
  },

  getConcept: async (conceptId: string): Promise<ConceptDetailDTO> =>
    requestJson<ConceptDetailDTO>(`/concepts/${conceptId}`),

  getConceptEvidence: async (
    conceptId: string,
  ): Promise<ConceptEvidenceResponse> =>
    requestJson<ConceptEvidenceResponse>(`/concepts/${conceptId}/evidence`),

  createUserRelation: async (
    conceptId: string,
    targetConceptId: string,
    predicate: string,
    explanation: string,
  ): Promise<UserRelationDTO> =>
    requestJson<UserRelationDTO>(`/concepts/${conceptId}/relations`, {
      method: "POST",
      body: JSON.stringify({
        target_concept_id: targetConceptId,
        predicate,
        explanation,
      }),
    }),

  mergeConcept: async (
    sourceConceptId: string,
    targetConceptId: string,
  ): Promise<ConceptDetailDTO> =>
    requestJson<ConceptDetailDTO>(`/concepts/${sourceConceptId}/merge`, {
      method: "POST",
      body: JSON.stringify({ target_concept_id: targetConceptId }),
    }),

  reviewCandidateSignal: async (
    conceptId: string,
    evidenceId: string,
    action: "confirm" | "dismiss",
  ): Promise<ConceptDetailDTO> =>
    requestJson<ConceptDetailDTO>(
      `/concepts/${conceptId}/signals/${evidenceId}/review?action=${action}`,
      { method: "POST" },
    ),

  listSuggestions: async (
    status = "pending",
    conceptId?: string | null,
  ): Promise<SuggestionDTO[]> => {
    const search = new URLSearchParams({ status });
    if (conceptId) search.set("concept_id", conceptId);
    const res = await requestJson<{ items: SuggestionDTO[] }>(
      `/suggestions?${search.toString()}`,
    );
    return res.items;
  },

  acceptSuggestion: async (suggestionId: string): Promise<UserRelationDTO> =>
    requestJson<UserRelationDTO>(`/suggestions/${suggestionId}/accept`, {
      method: "POST",
    }),

  rejectSuggestion: async (
    suggestionId: string,
    reason?: string,
  ): Promise<SuggestionDTO> =>
    requestJson<SuggestionDTO>(`/suggestions/${suggestionId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  dismissSuggestion: async (suggestionId: string): Promise<SuggestionDTO> =>
    requestJson<SuggestionDTO>(`/suggestions/${suggestionId}/dismiss`, {
      method: "POST",
    }),

  withdrawRelation: async (relationId: string): Promise<UserRelationDTO> =>
    requestJson<UserRelationDTO>(`/relations/${relationId}/withdraw`, {
      method: "POST",
    }),

  search: async (q: string): Promise<SearchResultDTO[]> => {
    const res = await requestJson<{ items: SearchResultDTO[] }>(
      `/search?q=${encodeURIComponent(q)}`,
    );
    return res.items;
  },

  listEvents: async (
    conceptId?: string | null,
  ): Promise<KnowledgeEventDTO[]> => {
    const qs = conceptId ? `?concept_id=${encodeURIComponent(conceptId)}` : "";
    const res = await requestJson<{ items: KnowledgeEventDTO[] }>(
      `/events${qs}`,
    );
    return res.items;
  },

  getAISettings: async (): Promise<AISettingsDTO> =>
    requestJson<AISettingsDTO>("/settings/ai"),

  updateAISettings: async (
    payload: UpdateAISettingsPayload,
  ): Promise<AISettingsDTO> =>
    requestJson<AISettingsDTO>("/settings/ai", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  validateAISettings: async (
    provider: string,
    localEndpointUrl?: string,
    apiKey?: string,
  ): Promise<{ valid: boolean; message: string; is_remote: boolean }> =>
    requestJson<{ valid: boolean; message: string; is_remote: boolean }>(
      "/settings/ai/validate",
      {
        method: "POST",
        body: JSON.stringify({
          provider,
          local_endpoint_url: localEndpointUrl,
          api_key: apiKey,
        }),
      },
    ),

  exportWorkspace: async (): Promise<ExportResultResponse> =>
    requestJson<ExportResultResponse>("/export", { method: "POST" }),
};
