import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./api/client";
import type { AnnotationTag } from "./api/types";
import { ConceptInspector } from "./components/ConceptInspector";
import { GraphView } from "./components/GraphView";
import { SettingsAndOwnershipView } from "./components/SettingsAndOwnershipView";
import { TimelineView } from "./components/TimelineView";

const ANNOTATION_TAGS: AnnotationTag[] = [
  "aha",
  "confused",
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
  const [contextMode, setContextMode] = useState<
    "personalized" | "conversation_only"
  >("personalized");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeLayers, setActiveLayers] = useState<string[]>([
    "user",
    "world",
    "suggested",
  ]);
  const [asOfTimestamp, setAsOfTimestamp] = useState("");
  const [lastFailedTurnId, setLastFailedTurnId] = useState<string | null>(null);
  const [statusNotice, setStatusNotice] = useState<string | null>(null);

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
      return apiClient.sendTurn(targetConvId, content, contextMode);
    },
    onSuccess: (res) => {
      setMessageInput("");
      if (res.status === "failed") {
        setLastFailedTurnId(res.turn_id);
        setStatusNotice(
          "Assistant generation failed. Your message is safely saved and can be retried.",
        );
      } else {
        setLastFailedTurnId(null);
        if (res.applied_annotations.length > 0) {
          setStatusNotice(
            `Applied #${res.applied_annotations.map((a) => a.tag).join(", #")} annotation.`,
          );
        } else {
          setStatusNotice(null);
        }
      }
      invalidateAll();
    },
  });

  const retryTurnMutation = useMutation({
    mutationFn: (turnId: string) => apiClient.retryTurn(turnId),
    onSuccess: (res) => {
      if (res.status === "succeeded") {
        setLastFailedTurnId(null);
        setStatusNotice("Turn retry succeeded.");
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
    onSuccess: (ann) => {
      setStatusNotice(`Marked message as #${ann.tag}.`);
      invalidateAll();
    },
  });

  const removeAnnotationMutation = useMutation({
    mutationFn: (annotationId: string) =>
      apiClient.removeAnnotation(annotationId),
    onSuccess: () => {
      setStatusNotice("Annotation undone.");
      invalidateAll();
    },
  });

  const acceptSuggestionMutation = useMutation({
    mutationFn: (suggestionId: string) =>
      apiClient.acceptSuggestion(suggestionId),
    onSuccess: () => {
      setStatusNotice(
        "Connection accepted into your personal knowledge map (without marking target concept as understood).",
      );
      invalidateAll();
    },
  });

  const rejectSuggestionMutation = useMutation({
    mutationFn: (suggestionId: string) =>
      apiClient.rejectSuggestion(suggestionId),
    onSuccess: () => {
      setStatusNotice("Suggestion rejected and recorded in history.");
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

  const handleToggleLayer = (layer: string) => {
    setActiveLayers((prev) =>
      prev.includes(layer) ? prev.filter((l) => l !== layer) : [...prev, layer],
    );
  };

  const activeConversation = conversationsQuery.data?.find(
    (c) => c.id === activeConvId,
  );
  const messages = messagesQuery.data ?? [];
  const pendingSuggestions = pendingSuggestionsQuery.data ?? [];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Navigation & Privacy / Continuity Bar */}
      <header className="border-b border-slate-800 bg-slate-900/80 px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-slate-100">
              Noema
            </h1>
            <p className="text-xs text-slate-400">
              Local-first personal knowledge environment
            </p>
          </div>
          <span
            className={`text-[11px] px-2 py-0.5 rounded border ${
              aiSettingsQuery.data?.remote_transfer_active
                ? "bg-amber-950/60 border-amber-700 text-amber-300"
                : "bg-emerald-950/60 border-emerald-800 text-emerald-300"
            }`}
          >
            {aiSettingsQuery.data?.remote_transfer_active
              ? "Hosted Provider Active"
              : "Local-Only Storage & Inference"}
          </span>
        </div>

        {/* Navigation Surfaces (Chat is always primary) */}
        <nav
          aria-label="Workspace Surfaces"
          className="flex flex-wrap items-center gap-1.5 text-xs"
        >
          {(
            [
              { id: "chat", label: "Chat Workspace (Primary)" },
              {
                id: "graph",
                label: `Knowledge Graph (${graphQuery.data?.counts.nodes ?? 0})`,
              },
              {
                id: "timeline",
                label: `Timeline (${eventsQuery.data?.length ?? 0})`,
              },
              { id: "settings", label: "AI & Data Ownership" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveSurface(tab.id)}
              className={`px-3 py-1.5 rounded font-medium transition ${
                activeSurface === tab.id
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-800/80 hover:bg-slate-800 text-slate-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Main Content Layout */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 p-4 max-w-[1600px] w-full mx-auto">
        {/* Left Sidebar: Conversations & Hybrid Search */}
        <aside
          aria-label="Conversations and Search"
          className="lg:col-span-3 space-y-4"
        >
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Explorations
              </h2>
              <button
                type="button"
                onClick={() => createConvMutation.mutate("")}
                className="px-2.5 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white"
              >
                + New Chat
              </button>
            </div>

            {conversationsQuery.data && conversationsQuery.data.length > 0 ? (
              <ul className="space-y-1.5 max-h-60 overflow-y-auto">
                {conversationsQuery.data.map((conv) => (
                  <li
                    key={conv.id}
                    className={`group flex items-center justify-between gap-2 px-2.5 py-2 rounded text-xs cursor-pointer border ${
                      conv.id === activeConvId
                        ? "bg-indigo-950/50 border-indigo-600 text-slate-100"
                        : "bg-slate-950/60 border-slate-800/80 text-slate-300 hover:bg-slate-800/50"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedConversationId(conv.id);
                        setActiveSurface("chat");
                      }}
                      className="text-left truncate flex-1 font-medium"
                    >
                      {conv.title || "Untitled exploration"}
                    </button>
                    <button
                      type="button"
                      aria-label={`Delete conversation ${conv.title}`}
                      onClick={() => deleteConvMutation.mutate(conv.id)}
                      className="opacity-60 hover:opacity-100 text-slate-400 hover:text-rose-400 text-[11px]"
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-400">
                Ask any question on the right—no folder or concept setup needed.
              </p>
            )}
          </div>

          {/* Hybrid Search Box */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 space-y-2.5">
            <label
              htmlFor="hybrid-search-input"
              className="text-xs font-semibold uppercase tracking-wider text-slate-400 block"
            >
              Hybrid Prior Search (FTS5 + Vector + Graph)
            </label>
            <input
              id="hybrid-search-input"
              type="search"
              placeholder="Search prior ideas, concepts, #aha..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-100"
            />
            {searchResultsQuery.data && searchResultsQuery.data.length > 0 && (
              <ul className="space-y-2 pt-1 max-h-60 overflow-y-auto">
                {searchResultsQuery.data.map((hit) => (
                  <li
                    key={hit.document_id}
                    className="p-2 rounded bg-slate-950 border border-slate-800 text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between text-[10px] text-indigo-300">
                      <span>{hit.kind}</span>
                      <span>{hit.channels.join(" + ")}</span>
                    </div>
                    <p className="text-slate-200 line-clamp-2">{hit.excerpt}</p>
                    <div className="flex gap-2">
                      {hit.conversation_id && (
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedConversationId(hit.conversation_id!);
                            setActiveSurface("chat");
                          }}
                          className="text-[11px] text-indigo-400 hover:underline"
                        >
                          Open Chat →
                        </button>
                      )}
                      {hit.concept_id && (
                        <button
                          type="button"
                          onClick={() => setSelectedConceptId(hit.concept_id!)}
                          className="text-[11px] text-emerald-400 hover:underline"
                        >
                          Inspect Concept →
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>

        {/* Center Primary Workspace */}
        <main className={selectedConceptId ? "lg:col-span-6" : "lg:col-span-9"}>
          {statusNotice && (
            <div
              role="status"
              className="mb-3 p-2.5 rounded-lg bg-slate-900 border border-indigo-700/80 text-xs text-indigo-200 flex items-center justify-between"
            >
              <span>{statusNotice}</span>
              <button
                type="button"
                onClick={() => setStatusNotice(null)}
                className="text-slate-400 hover:text-slate-200 ml-2"
              >
                Dismiss
              </button>
            </div>
          )}

          {activeSurface === "chat" && (
            <section
              aria-label="Conversation Workspace"
              className="bg-slate-900 border border-slate-800 rounded-lg flex flex-col min-h-[75vh]"
            >
              {/* Conversation Header with Separate Turn & Extraction Statuses */}
              <div className="border-b border-slate-800 px-4 py-2.5 flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="font-medium text-slate-200">
                  {activeConversation?.title ||
                    "Start exploring an idea in conversation"}
                </div>
                <div className="flex items-center gap-2">
                  {activeConversation?.latest_turn_status && (
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                      Turn: {activeConversation.latest_turn_status}
                    </span>
                  )}
                  {activeConversation?.extraction_status &&
                    activeConversation.extraction_status !== "none" && (
                      <span
                        className={`px-2 py-0.5 rounded border ${
                          activeConversation.extraction_status === "failed"
                            ? "bg-rose-950/60 border-rose-700 text-rose-300"
                            : "bg-slate-950 border-slate-800 text-slate-400"
                        }`}
                      >
                        Background Extraction:{" "}
                        {activeConversation.extraction_status}
                      </span>
                    )}
                </div>
              </div>

              {/* Message Stream */}
              <div className="flex-1 p-4 space-y-4 overflow-y-auto">
                {messages.length === 0 ? (
                  <div className="text-center py-12 space-y-2">
                    <p className="text-sm text-slate-300 font-medium">
                      Ask a question or explore a mechanism.
                    </p>
                    <p className="text-xs text-slate-400 max-w-md mx-auto">
                      No manual filing required. You can mark moments with{" "}
                      <code className="text-emerald-300">#aha</code> or{" "}
                      <code className="text-amber-300">#confused</code> anytime,
                      and prior insights will be retrieved with source links.
                    </p>
                  </div>
                ) : (
                  messages.map((msg) => (
                    <article
                      key={msg.id}
                      className={`p-3.5 rounded-lg border space-y-2.5 ${
                        msg.role === "user"
                          ? "bg-slate-950/90 border-slate-800 ml-6"
                          : "bg-slate-900/90 border-slate-700/80 mr-6"
                      }`}
                    >
                      <div className="flex items-center justify-between text-[11px] text-slate-400">
                        <span className="font-semibold uppercase tracking-wider">
                          {msg.role === "user" ? "You" : "Assistant"}
                        </span>
                        {msg.provider && msg.model && (
                          <span>
                            {msg.provider} / {msg.model}
                          </span>
                        )}
                      </div>

                      <div className="text-sm text-slate-100 whitespace-pre-wrap leading-relaxed">
                        {msg.content}
                      </div>

                      {/* Retrieved Prior Personal Context Sources */}
                      {msg.sources.length > 0 && (
                        <div className="p-2.5 rounded bg-indigo-950/30 border border-indigo-800/60 space-y-1 text-xs">
                          <div className="font-semibold text-indigo-300 text-[11px]">
                            Used Prior Personal Context (Evidence-Linked):
                          </div>
                          {msg.sources.map((src) => (
                            <div
                              key={src.source_id}
                              className="flex items-center justify-between gap-2 text-slate-300"
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
                                  View Source →
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Extracted Concept Mentions */}
                      {msg.mentions.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5 pt-1">
                          <span className="text-[11px] text-slate-400">
                            Concepts:
                          </span>
                          {Array.from(
                            new Map(
                              msg.mentions.map((m) => [m.concept_id, m]),
                            ).values(),
                          ).map((m) => (
                            <button
                              key={m.id}
                              type="button"
                              onClick={() => setSelectedConceptId(m.concept_id)}
                              className="px-2 py-0.5 rounded-full bg-slate-800 hover:bg-indigo-900/60 border border-slate-700 text-[11px] text-slate-200"
                            >
                              {m.canonical_name}
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Active Explicit Annotations with One-Click Undo */}
                      {msg.annotations.length > 0 && (
                        <div className="flex flex-wrap items-center gap-2 pt-1">
                          {msg.annotations.map((ann) => (
                            <span
                              key={ann.id}
                              className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-950/80 border border-emerald-700 text-emerald-200 text-xs"
                            >
                              <span>#{ann.tag} (user explicit)</span>
                              <button
                                type="button"
                                aria-label={`Undo #${ann.tag} annotation`}
                                onClick={() =>
                                  removeAnnotationMutation.mutate(ann.id)
                                }
                                className="text-emerald-400 hover:text-white underline text-[11px]"
                              >
                                Undo
                              </button>
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Quick Lightweight Annotation Bar */}
                      <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-slate-800/60">
                        <span className="text-[11px] text-slate-400 mr-1">
                          Mark:
                        </span>
                        {ANNOTATION_TAGS.map((tag) => (
                          <button
                            key={tag}
                            type="button"
                            onClick={() =>
                              addAnnotationMutation.mutate({
                                messageId: msg.id,
                                tag,
                              })
                            }
                            className="px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-[11px] text-slate-300"
                          >
                            #{tag}
                          </button>
                        ))}
                      </div>
                    </article>
                  ))
                )}

                {/* Failed Turn Retry Banner */}
                {lastFailedTurnId && (
                  <div className="p-3 rounded border border-rose-800 bg-rose-950/30 flex items-center justify-between text-xs text-rose-200">
                    <span>
                      Chat generation failed. Your message is preserved.
                    </span>
                    <button
                      type="button"
                      onClick={() => retryTurnMutation.mutate(lastFailedTurnId)}
                      className="px-3 py-1 rounded bg-rose-700 hover:bg-rose-600 text-white font-medium"
                    >
                      Retry Turn Generation
                    </button>
                  </div>
                )}

                {/* Quiet Contextual Suggestion Card (Optional, non-blocking) */}
                {pendingSuggestions.length > 0 && (
                  <div className="p-3 rounded-lg border border-amber-800/60 bg-amber-950/20 space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-amber-300">
                        Possible connection suggested by the assistant (Pending
                        — not in your personal map until accepted)
                      </span>
                    </div>
                    {pendingSuggestions.slice(0, 2).map((s) => (
                      <div
                        key={s.id}
                        className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 border-t border-amber-900/40"
                      >
                        <div>
                          <div className="font-medium text-slate-100">
                            {s.subject_name}{" "}
                            <span className="text-amber-300">
                              —[{s.predicate_label}]→
                            </span>{" "}
                            {s.object_name}
                          </div>
                          <p className="text-slate-300">{s.explanation}</p>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <button
                            type="button"
                            onClick={() =>
                              acceptSuggestionMutation.mutate(s.id)
                            }
                            className="px-2.5 py-1 rounded bg-emerald-700 hover:bg-emerald-600 text-white"
                          >
                            Accept
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              rejectSuggestionMutation.mutate(s.id)
                            }
                            className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200"
                          >
                            Reject
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              dismissSuggestionMutation.mutate(s.id)
                            }
                            className="px-2 py-1 rounded bg-slate-900 text-slate-400"
                          >
                            Dismiss
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Chat Input Bar */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!messageInput.trim()) return;
                  sendTurnMutation.mutate(messageInput);
                }}
                className="border-t border-slate-800 p-3 space-y-2 bg-slate-950/60"
              >
                <div className="flex gap-2">
                  <input
                    type="text"
                    aria-label="Message or #command input"
                    placeholder="Ask a question, explain an idea, or type #aha / #confused..."
                    value={messageInput}
                    onChange={(e) => setMessageInput(e.target.value)}
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100"
                  />
                  <button
                    type="submit"
                    disabled={
                      !messageInput.trim() || sendTurnMutation.isPending
                    }
                    className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-sm font-medium text-white"
                  >
                    {sendTurnMutation.isPending ? "Sending..." : "Send"}
                  </button>
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-400">
                  <span>
                    Supported direct commands: <code>#aha</code>,{" "}
                    <code>#confused</code>, <code>#question</code>,{" "}
                    <code>#connection</code>, <code>#hypothesis</code>,{" "}
                    <code>#revisit</code>, <code>#important</code>
                  </span>
                  <label className="flex items-center gap-1.5">
                    <span>Context:</span>
                    <select
                      value={contextMode}
                      onChange={(e) =>
                        setContextMode(
                          e.target.value as
                            "personalized" | "conversation_only",
                        )
                      }
                      className="bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-slate-200"
                    >
                      <option value="personalized">
                        Personalized (Retrieve prior evidence)
                      </option>
                      <option value="conversation_only">
                        Current conversation only
                      </option>
                    </select>
                  </label>
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
              onUpdateSettings={(payload) => {
                void apiClient.updateAISettings(payload).then(() => {
                  void queryClient.invalidateQueries({
                    queryKey: ["aiSettings"],
                  });
                });
              }}
              onValidateProvider={(provider, localUrl) =>
                apiClient.validateAISettings(provider, localUrl)
              }
              onExportWorkspace={() => apiClient.exportWorkspace()}
              onReturnToChat={() => setActiveSurface("chat")}
            />
          )}
        </main>

        {/* Right Side Panel: Concept Evidence & Provenance Inspector */}
        {selectedConceptId && (
          <div className="lg:col-span-3">
            <ConceptInspector
              concept={conceptDetailQuery.data}
              evidence={conceptEvidenceQuery.data}
              allConcepts={graphQuery.data?.nodes ?? []}
              onClose={() => setSelectedConceptId(null)}
              onJumpToConversation={(convId) => {
                setSelectedConversationId(convId);
                setActiveSurface("chat");
              }}
              onStartGroundedChat={(conceptName) => {
                setActiveSurface("chat");
                setMessageInput(
                  `Let's explore how ${conceptName} connects to what I looked at earlier.`,
                );
              }}
              onAcceptSuggestion={(sid) => acceptSuggestionMutation.mutate(sid)}
              onRejectSuggestion={(sid) => rejectSuggestionMutation.mutate(sid)}
              onDismissSuggestion={(sid) =>
                dismissSuggestionMutation.mutate(sid)
              }
              onWithdrawRelation={(relId) => {
                void apiClient.withdrawRelation(relId).then(() => {
                  invalidateAll();
                });
              }}
              onReviewSignal={(cid, evId, action) => {
                void apiClient
                  .reviewCandidateSignal(cid, evId, action)
                  .then(() => {
                    invalidateAll();
                  });
              }}
              onCreateRelation={(srcId, tgtId, pred, expl) => {
                void apiClient
                  .createUserRelation(srcId, tgtId, pred, expl)
                  .then(() => {
                    invalidateAll();
                  });
              }}
              onMergeConcept={(srcId, tgtId) => {
                void apiClient.mergeConcept(srcId, tgtId).then((merged) => {
                  setSelectedConceptId(merged.id);
                  invalidateAll();
                });
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
