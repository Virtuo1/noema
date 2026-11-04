import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./api/client";
import type { AnnotationTag } from "./api/types";
import { ConceptInspector } from "./components/ConceptInspector";
import { GraphView } from "./components/GraphView";
import { SettingsAndOwnershipView } from "./components/SettingsAndOwnershipView";
import { TimelineView } from "./components/TimelineView";

const EXTRA_TAGS: AnnotationTag[] = [
  "question",
  "connection",
  "hypothesis",
  "revisit",
  "important",
];

type ActiveSurface = "chat" | "graph" | "timeline" | "settings";

export default function App(): React.ReactElement {
  const queryClient = useQueryClient();

  const [activeSurface, setActiveSurface] = useState<ActiveSurface>("chat");
  const [selectedConversationId, setSelectedConversationId] = useState<
    string | null
  >(null);
  const [selectedConceptId, setSelectedConceptId] = useState<string | null>(
    null,
  );
  const [messageInput, setMessageInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeLayers, setActiveLayers] = useState<string[]>([
    "user",
    "world",
    "suggested",
  ]);
  const [asOfTimestamp, setAsOfTimestamp] = useState("");
  const [lastFailedTurnId, setLastFailedTurnId] = useState<string | null>(null);
  const [statusNotice, setStatusNotice] = useState<string | null>(null);
  const [openTagMenuMsgId, setOpenTagMenuMsgId] = useState<string | null>(null);

  // Queries
  const conversationsQuery = useQuery({
    queryKey: ["conversations"],
    queryFn: () => apiClient.listConversations(),
  });

  const activeConvId =
    selectedConversationId ?? conversationsQuery.data?.[0]?.id ?? null;

  const messagesQuery = useQuery({
    queryKey: ["messages", activeConvId],
    queryFn: () =>
      activeConvId ? apiClient.listMessages(activeConvId) : Promise.resolve([]),
    enabled: Boolean(activeConvId),
  });

  const graphQuery = useQuery({
    queryKey: ["graph", selectedConceptId, activeLayers, asOfTimestamp],
    queryFn: () =>
      apiClient.getGraph({
        focusConceptId: null,
        layers: activeLayers,
        asOf: asOfTimestamp.trim() || null,
      }),
  });

  const pendingSuggestionsQuery = useQuery({
    queryKey: ["suggestions", "pending"],
    queryFn: () => apiClient.listSuggestions("pending"),
  });

  const conceptDetailQuery = useQuery({
    queryKey: ["concept", selectedConceptId],
    queryFn: () =>
      selectedConceptId
        ? apiClient.getConcept(selectedConceptId)
        : Promise.resolve(undefined),
    enabled: Boolean(selectedConceptId),
  });

  const conceptEvidenceQuery = useQuery({
    queryKey: ["conceptEvidence", selectedConceptId],
    queryFn: () =>
      selectedConceptId
        ? apiClient.getConceptEvidence(selectedConceptId)
        : Promise.resolve(undefined),
    enabled: Boolean(selectedConceptId),
  });

  const eventsQuery = useQuery({
    queryKey: ["events", selectedConceptId],
    queryFn: () => apiClient.listEvents(selectedConceptId),
  });

  const aiSettingsQuery = useQuery({
    queryKey: ["aiSettings"],
    queryFn: () => apiClient.getAISettings(),
  });

  const searchResultsQuery = useQuery({
    queryKey: ["search", searchQuery],
    queryFn: () =>
      searchQuery.trim()
        ? apiClient.search(searchQuery.trim())
        : Promise.resolve([]),
    enabled: searchQuery.trim().length > 1,
  });

  const invalidateAll = () => {
    void queryClient.invalidateQueries({ queryKey: ["conversations"] });
    void queryClient.invalidateQueries({ queryKey: ["messages"] });
    void queryClient.invalidateQueries({ queryKey: ["graph"] });
    void queryClient.invalidateQueries({ queryKey: ["suggestions"] });
    void queryClient.invalidateQueries({ queryKey: ["concept"] });
    void queryClient.invalidateQueries({ queryKey: ["conceptEvidence"] });
    void queryClient.invalidateQueries({ queryKey: ["events"] });
  };

  const createConvMutation = useMutation({
    mutationFn: (title?: string) => apiClient.createConversation(title ?? ""),
    onSuccess: (conv) => {
      setSelectedConversationId(conv.id);
      setActiveSurface("chat");
      invalidateAll();
    },
  });

  const deleteConvMutation = useMutation({
    mutationFn: (convId: string) => apiClient.deleteConversation(convId),
    onSuccess: () => {
      setSelectedConversationId(null);
      invalidateAll();
    },
  });

  const sendTurnMutation = useMutation({
    mutationFn: async (content: string) => {
      let targetConvId = activeConvId;
      if (!targetConvId) {
        const created = await apiClient.createConversation("");
        targetConvId = created.id;
        setSelectedConversationId(created.id);
      }
      return apiClient.sendTurn(targetConvId, content, "personalized");
    },
    onSuccess: (res) => {
      setMessageInput("");
      if (res.status === "failed") {
        setLastFailedTurnId(res.turn_id);
        setStatusNotice(
          res.error_message ||
            "Assistant generation failed. Your message is safely saved and can be retried.",
        );
      } else {
        setLastFailedTurnId(null);
        setStatusNotice(null);
      }
      invalidateAll();
    },
  });

  const retryTurnMutation = useMutation({
    mutationFn: (turnId: string) => apiClient.retryTurn(turnId),
    onSuccess: (res) => {
      if (res.status === "succeeded") {
        setLastFailedTurnId(null);
        setStatusNotice(null);
      }
      invalidateAll();
    },
  });

  const addAnnotationMutation = useMutation({
    mutationFn: ({
      messageId,
      tag,
    }: {
      messageId: string;
      tag: AnnotationTag;
    }) => apiClient.addAnnotation(messageId, tag, null),
    onSuccess: () => {
      setOpenTagMenuMsgId(null);
      invalidateAll();
    },
  });

  const removeAnnotationMutation = useMutation({
    mutationFn: (annotationId: string) =>
      apiClient.removeAnnotation(annotationId),
    onSuccess: () => {
      invalidateAll();
    },
  });

  const acceptSuggestionMutation = useMutation({
    mutationFn: (suggestionId: string) =>
      apiClient.acceptSuggestion(suggestionId),
    onSuccess: () => {
      invalidateAll();
    },
  });

  const rejectSuggestionMutation = useMutation({
    mutationFn: (suggestionId: string) =>
      apiClient.rejectSuggestion(suggestionId),
    onSuccess: () => {
      invalidateAll();
    },
  });

  const dismissSuggestionMutation = useMutation({
    mutationFn: (suggestionId: string) =>
      apiClient.dismissSuggestion(suggestionId),
    onSuccess: () => {
      invalidateAll();
    },
  });

  const withdrawRelationMutation = useMutation({
    mutationFn: (relationId: string) => apiClient.withdrawRelation(relationId),
    onSuccess: () => {
      invalidateAll();
    },
  });

  const reviewSignalMutation = useMutation({
    mutationFn: ({
      conceptId,
      evidenceId,
      action,
    }: {
      conceptId: string;
      evidenceId: string;
      action: "confirm" | "dismiss";
    }) => apiClient.reviewCandidateSignal(conceptId, evidenceId, action),
    onSuccess: () => {
      invalidateAll();
    },
  });

  const createRelationMutation = useMutation({
    mutationFn: ({
      sourceId,
      targetId,
      predicate,
      explanation,
    }: {
      sourceId: string;
      targetId: string;
      predicate: string;
      explanation: string;
    }) =>
      apiClient.createUserRelation(sourceId, targetId, predicate, explanation),
    onSuccess: () => {
      invalidateAll();
    },
  });

  const mergeConceptMutation = useMutation({
    mutationFn: ({
      sourceId,
      targetId,
    }: {
      sourceId: string;
      targetId: string;
    }) => apiClient.mergeConcept(sourceId, targetId),
    onSuccess: (_res, vars) => {
      setSelectedConceptId(vars.targetId);
      invalidateAll();
    },
  });

  const handleToggleLayer = (layer: string) => {
    setActiveLayers((prev) =>
      prev.includes(layer) ? prev.filter((l) => l !== layer) : [...prev, layer],
    );
  };

  const messages = messagesQuery.data ?? [];
  const pendingSuggestions = pendingSuggestionsQuery.data ?? [];
  const topSuggestion = pendingSuggestions[0];

  const activeProviderDisplay =
    aiSettingsQuery.data?.providers.find(
      (p) => p.provider === aiSettingsQuery.data?.conversation_provider,
    )?.display_name ?? "Local";

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex">
      {/* Minimal Left Sidebar */}
      <aside
        aria-label="Conversations and Navigation"
        className="w-64 shrink-0 border-r border-zinc-900 bg-zinc-950 flex flex-col justify-between p-3 select-none"
      >
        <div className="space-y-3 flex-1 flex flex-col min-h-0">
          {/* Brand & Quick Model Pill */}
          <div className="flex items-center justify-between px-1.5 pt-1">
            <h1 className="text-base font-semibold tracking-tight text-zinc-100">
              Noema
            </h1>
            <button
              type="button"
              onClick={() => setActiveSurface("settings")}
              title="Configure AI Models & API Keys"
              className="text-[11px] px-2 py-0.5 rounded-full bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-300 truncate max-w-[130px] transition"
            >
              ⚙ {activeProviderDisplay}
            </button>
          </div>

          {/* New Chat Button */}
          <button
            type="button"
            onClick={() => createConvMutation.mutate("")}
            className="w-full py-2 px-3 rounded-lg bg-zinc-100 hover:bg-white text-zinc-950 text-xs font-medium text-left flex items-center justify-between transition"
          >
            <span>New conversation</span>
            <span className="text-sm leading-none">+</span>
          </button>

          {/* Compact Search */}
          <div className="relative">
            <input
              id="hybrid-search-input"
              type="search"
              placeholder="Search notes & concepts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-zinc-900/80 border border-zinc-800/90 focus:border-zinc-700 focus:outline-none rounded-lg px-2.5 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-500"
            />
            {searchQuery.trim().length > 1 &&
              searchResultsQuery.data &&
              searchResultsQuery.data.length > 0 && (
                <ul className="mt-1.5 space-y-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1.5 max-h-56 overflow-y-auto shadow-xl">
                  {searchResultsQuery.data.map((hit) => (
                    <li
                      key={hit.document_id}
                      className="p-2 rounded hover:bg-zinc-800/70 text-xs space-y-1"
                    >
                      <p className="text-zinc-200 line-clamp-2">
                        {hit.excerpt}
                      </p>
                      <div className="flex gap-2 text-[11px]">
                        {hit.conversation_id && (
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedConversationId(hit.conversation_id!);
                              setActiveSurface("chat");
                              setSearchQuery("");
                            }}
                            className="text-indigo-400 hover:underline"
                          >
                            Open chat
                          </button>
                        )}
                        {hit.concept_id && (
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedConceptId(hit.concept_id!);
                              setSearchQuery("");
                            }}
                            className="text-emerald-400 hover:underline"
                          >
                            Inspect concept
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
          </div>

          {/* Conversation List */}
          <div className="flex-1 overflow-y-auto space-y-0.5 pt-1">
            {conversationsQuery.data && conversationsQuery.data.length > 0 ? (
              conversationsQuery.data.map((conv) => {
                const isActive =
                  conv.id === activeConvId && activeSurface === "chat";
                return (
                  <div
                    key={conv.id}
                    className={`group flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs transition ${
                      isActive
                        ? "bg-zinc-900 text-zinc-100"
                        : "text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedConversationId(conv.id);
                        setActiveSurface("chat");
                      }}
                      className="text-left truncate flex-1 py-0.5"
                    >
                      {conv.title || "New conversation"}
                    </button>
                    <button
                      type="button"
                      aria-label={`Delete conversation ${conv.title}`}
                      onClick={() => deleteConvMutation.mutate(conv.id)}
                      className="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-rose-400 pl-2 text-[11px]"
                    >
                      ✕
                    </button>
                  </div>
                );
              })
            ) : (
              <p className="text-xs text-zinc-500 px-2 py-4">
                Your conversations will appear here.
              </p>
            )}
          </div>
        </div>

        {/* Clean Bottom Surface Navigation */}
        <nav
          aria-label="Workspace Surfaces"
          className="pt-3 border-t border-zinc-900 space-y-1 text-xs"
        >
          {(
            [
              { id: "chat", label: "Chat Workspace (Primary)" },
              {
                id: "graph",
                label: `Knowledge Map (${graphQuery.data?.counts.nodes ?? 0})`,
              },
              {
                id: "timeline",
                label: `Timeline (${eventsQuery.data?.length ?? 0})`,
              },
              { id: "settings", label: "AI Models & Keys" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveSurface(tab.id)}
              className={`w-full text-left px-2.5 py-1.5 rounded-lg transition ${
                activeSurface === tab.id
                  ? "bg-zinc-900 text-zinc-100 font-medium"
                  : "text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </aside>

      {/* Main Workspace Area */}
      <main className="flex-1 flex flex-col min-w-0 relative">
        {statusNotice && (
          <div
            role="status"
            className="mx-auto mt-3 max-w-2xl w-full px-4 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-200 flex items-center justify-between"
          >
            <span>{statusNotice}</span>
            <button
              type="button"
              onClick={() => setStatusNotice(null)}
              className="text-zinc-400 hover:text-zinc-200 ml-3"
            >
              ✕
            </button>
          </div>
        )}

        {activeSurface === "chat" && (
          <section
            aria-label="Conversation Workspace"
            className="flex-1 flex flex-col max-w-3xl w-full mx-auto px-4 sm:px-6"
          >
            {/* Message Stream */}
            <div className="flex-1 py-8 space-y-6 overflow-y-auto">
              {messages.length === 0 ? (
                <div className="py-24 text-center space-y-4">
                  <h2 className="text-xl font-medium text-zinc-100">
                    What are you exploring today?
                  </h2>
                  <p className="text-sm text-zinc-400 max-w-md mx-auto leading-relaxed">
                    Just chat naturally. A lightweight background organizer
                    quietly extracts key concepts and links your ideas over
                    time.
                  </p>
                  {aiSettingsQuery.data?.conversation_provider ===
                    "local_heuristic" && (
                    <div className="pt-2">
                      <button
                        type="button"
                        onClick={() => setActiveSurface("settings")}
                        className="px-3.5 py-1.5 rounded-full bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs text-zinc-300 transition"
                      >
                        Connect OpenAI, Gemini, Claude, or Local Ollama →
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                messages.map((msg) => {
                  const uniqueMentions = Array.from(
                    new Map(
                      msg.mentions.map((m) => [m.concept_id, m]),
                    ).values(),
                  );
                  return (
                    <article
                      key={msg.id}
                      className={`group space-y-2 ${
                        msg.role === "user"
                          ? "ml-auto max-w-xl bg-zinc-900/90 border border-zinc-800/80 rounded-2xl px-4 py-3"
                          : "max-w-2xl py-1"
                      }`}
                    >
                      <div className="text-sm text-zinc-100 whitespace-pre-wrap leading-relaxed">
                        {msg.content}
                      </div>

                      {/* Compact Collapsible Prior Context Pill */}
                      {msg.sources.length > 0 && (
                        <details className="text-xs text-zinc-400 pt-1">
                          <summary className="cursor-pointer hover:text-zinc-200 inline-flex items-center gap-1.5">
                            <span className="text-indigo-400">
                              Referenced {msg.sources.length} prior note
                              {msg.sources.length > 1 ? "s" : ""}
                            </span>
                          </summary>
                          <div className="mt-2 space-y-1.5 pl-3 border-l border-zinc-800">
                            {msg.sources.map((src) => (
                              <div
                                key={src.source_id}
                                className="flex items-center justify-between gap-2 text-zinc-300"
                              >
                                <span className="truncate italic">
                                  "{src.excerpt}"
                                </span>
                                {src.conversation_id && (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setSelectedConversationId(
                                        src.conversation_id!,
                                      )
                                    }
                                    className="text-indigo-400 hover:underline shrink-0 text-[11px]"
                                  >
                                    Open →
                                  </button>
                                )}
                              </div>
                            ))}
                          </div>
                        </details>
                      )}

                      {/* Subtle Concept Chips + Active Annotations + Hover Action Bar */}
                      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {uniqueMentions.map((m) => (
                            <button
                              key={m.id}
                              type="button"
                              onClick={() => setSelectedConceptId(m.concept_id)}
                              className="px-2 py-0.5 rounded-md bg-zinc-900 hover:bg-zinc-800 border border-zinc-800/90 text-[11px] text-zinc-300 transition"
                            >
                              {m.canonical_name}
                            </button>
                          ))}

                          {msg.annotations.map((ann) => (
                            <span
                              key={ann.id}
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-950/60 border border-emerald-800/80 text-emerald-200 text-[11px]"
                            >
                              <span>#{ann.tag}</span>
                              <button
                                type="button"
                                aria-label={`Undo #${ann.tag} annotation`}
                                onClick={() =>
                                  removeAnnotationMutation.mutate(ann.id)
                                }
                                className="text-emerald-400 hover:text-white ml-0.5"
                              >
                                ×
                              </button>
                            </span>
                          ))}
                        </div>

                        {/* Subtle Hover-Only Quick Reactions */}
                        <div className="opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition flex items-center gap-1 relative">
                          <button
                            type="button"
                            onClick={() =>
                              addAnnotationMutation.mutate({
                                messageId: msg.id,
                                tag: "aha",
                              })
                            }
                            className="px-2 py-0.5 rounded bg-zinc-900 hover:bg-zinc-800 text-[11px] text-zinc-400 hover:text-emerald-300"
                          >
                            💡 Aha
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              addAnnotationMutation.mutate({
                                messageId: msg.id,
                                tag: "confused",
                              })
                            }
                            className="px-2 py-0.5 rounded bg-zinc-900 hover:bg-zinc-800 text-[11px] text-zinc-400 hover:text-amber-300"
                          >
                            🤔 Confused
                          </button>
                          <button
                            type="button"
                            aria-label="More tags"
                            onClick={() =>
                              setOpenTagMenuMsgId(
                                openTagMenuMsgId === msg.id ? null : msg.id,
                              )
                            }
                            className="px-1.5 py-0.5 rounded bg-zinc-900 hover:bg-zinc-800 text-[11px] text-zinc-400"
                          >
                            +
                          </button>
                          {openTagMenuMsgId === msg.id && (
                            <div className="absolute right-0 bottom-7 z-20 bg-zinc-900 border border-zinc-800 rounded-lg p-1 flex gap-1 shadow-xl">
                              {EXTRA_TAGS.map((tag) => (
                                <button
                                  key={tag}
                                  type="button"
                                  onClick={() =>
                                    addAnnotationMutation.mutate({
                                      messageId: msg.id,
                                      tag,
                                    })
                                  }
                                  className="px-2 py-0.5 rounded hover:bg-zinc-800 text-[11px] text-zinc-300"
                                >
                                  #{tag}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </article>
                  );
                })
              )}

              {/* Failed Turn Retry Banner */}
              {lastFailedTurnId && (
                <div className="p-3 rounded-xl border border-rose-900/70 bg-rose-950/20 flex items-center justify-between text-xs text-rose-200">
                  <span>
                    Could not reach the AI provider. Your message was saved.
                  </span>
                  <button
                    type="button"
                    onClick={() => retryTurnMutation.mutate(lastFailedTurnId)}
                    className="px-3 py-1 rounded-lg bg-rose-700 hover:bg-rose-600 text-white font-medium"
                  >
                    Retry
                  </button>
                </div>
              )}
            </div>

            {/* Single-Line Quiet Suggestion Pill (when available) */}
            {topSuggestion && (
              <div className="mb-2 px-3.5 py-2 rounded-xl border border-zinc-800 bg-zinc-900/70 flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="text-zinc-300">
                  <span className="text-amber-300 font-medium">
                    Suggested link:
                  </span>{" "}
                  {topSuggestion.subject_name} → {topSuggestion.predicate_label}{" "}
                  → {topSuggestion.object_name}
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() =>
                      acceptSuggestionMutation.mutate(topSuggestion.id)
                    }
                    className="px-2.5 py-0.5 rounded-md bg-emerald-700 hover:bg-emerald-600 text-white"
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      rejectSuggestionMutation.mutate(topSuggestion.id)
                    }
                    className="px-2 py-0.5 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                  >
                    Ignore
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      dismissSuggestionMutation.mutate(topSuggestion.id)
                    }
                    className="px-1.5 py-0.5 text-zinc-500 hover:text-zinc-300"
                  >
                    ✕
                  </button>
                </div>
              </div>
            )}

            {/* Clean Chat Composer */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!messageInput.trim()) return;
                sendTurnMutation.mutate(messageInput);
              }}
              className="pb-6 pt-2"
            >
              <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 focus-within:border-zinc-700 rounded-2xl px-3.5 py-2 shadow-sm">
                <input
                  type="text"
                  aria-label="Message or #command input"
                  placeholder="Ask anything, or include #aha or #confused..."
                  value={messageInput}
                  onChange={(e) => setMessageInput(e.target.value)}
                  className="flex-1 bg-transparent text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={!messageInput.trim() || sendTurnMutation.isPending}
                  className="px-3.5 py-1.5 rounded-xl bg-zinc-100 hover:bg-white disabled:opacity-30 text-xs font-medium text-zinc-950 transition"
                >
                  {sendTurnMutation.isPending ? "..." : "Send"}
                </button>
              </div>
            </form>
          </section>
        )}

        {activeSurface === "graph" && (
          <GraphView
            graph={graphQuery.data}
            isLoading={graphQuery.isLoading}
            selectedConceptId={selectedConceptId}
            onSelectConcept={(cid) => setSelectedConceptId(cid)}
            activeLayers={activeLayers}
            onToggleLayer={handleToggleLayer}
            asOfTimestamp={asOfTimestamp}
            onChangeAsOf={setAsOfTimestamp}
            onReturnToChat={() => setActiveSurface("chat")}
            onAcceptSuggestion={(sid) => acceptSuggestionMutation.mutate(sid)}
            onRejectSuggestion={(sid) => rejectSuggestionMutation.mutate(sid)}
          />
        )}

        {activeSurface === "timeline" && (
          <TimelineView
            events={eventsQuery.data ?? []}
            onReturnToChat={() => setActiveSurface("chat")}
            onSelectConcept={(cid) => setSelectedConceptId(cid)}
            onJumpToConversation={(convId) => {
              setSelectedConversationId(convId);
              setActiveSurface("chat");
            }}
          />
        )}

        {activeSurface === "settings" && (
          <SettingsAndOwnershipView
            settings={aiSettingsQuery.data}
            onUpdateSettings={async (payload) => {
              await apiClient.updateAISettings(payload);
              await queryClient.invalidateQueries({
                queryKey: ["aiSettings"],
              });
            }}
            onValidateProvider={(provider, localUrl, apiKey) =>
              apiClient.validateAISettings(provider, localUrl, apiKey)
            }
            onExportWorkspace={() => apiClient.exportWorkspace()}
            onReturnToChat={() => setActiveSurface("chat")}
          />
        )}

        {/* Slide-Over Concept Drawer (Only visible when a concept is clicked) */}
        {selectedConceptId && (
          <ConceptInspector
            concept={conceptDetailQuery.data}
            evidence={conceptEvidenceQuery.data}
            allConcepts={graphQuery.data?.nodes ?? []}
            onClose={() => setSelectedConceptId(null)}
            onJumpToConversation={(convId) => {
              setSelectedConversationId(convId);
              setSelectedConceptId(null);
              setActiveSurface("chat");
            }}
            onStartGroundedChat={(conceptName) => {
              setMessageInput(
                `Help me connect my notes on ${conceptName} and test my understanding.`,
              );
              setSelectedConceptId(null);
              setActiveSurface("chat");
            }}
            onAcceptSuggestion={(sid) => acceptSuggestionMutation.mutate(sid)}
            onRejectSuggestion={(sid) => rejectSuggestionMutation.mutate(sid)}
            onDismissSuggestion={(sid) => dismissSuggestionMutation.mutate(sid)}
            onWithdrawRelation={(rid) => withdrawRelationMutation.mutate(rid)}
            onReviewSignal={(conceptId, evidenceId, action) =>
              reviewSignalMutation.mutate({ conceptId, evidenceId, action })
            }
            onCreateRelation={(sourceId, targetId, predicate, explanation) =>
              createRelationMutation.mutate({
                sourceId,
                targetId,
                predicate,
                explanation,
              })
            }
            onMergeConcept={(sourceId, targetId) =>
              mergeConceptMutation.mutate({ sourceId, targetId })
            }
          />
        )}
      </main>
    </div>
  );
}
