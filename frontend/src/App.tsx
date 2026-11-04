/**
 * Noema — Seamless Full-Screen Graph & Chat Workspace
 * - Default UI mode: Full-screen Obsidian-style hierarchical & semantic-zoom knowledge graph
 * - Floating frosted-glass sidebar (with live Related Chats in chat mode)
 * - Floating frosted-glass bottom question box with #tag autocomplete popup
 * - Submitting a question in Graph mode transitions seamlessly into Chat view
 */

import React, { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./api/client";
import type { UpdateAISettingsPayload } from "./api/types";
import { ConceptInspector } from "./components/ConceptInspector";
import { FloatingComposer } from "./components/FloatingComposer";
import { FloatingSidebar } from "./components/FloatingSidebar";
import { GraphView } from "./components/GraphView";
import { SettingsAndOwnershipView } from "./components/SettingsAndOwnershipView";
import { TimelineView } from "./components/TimelineView";

export const App: React.FC = () => {
  const queryClient = useQueryClient();

  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [composerText, setComposerText] = useState<string>("");
  const [streamingContent, setStreamingContent] = useState<string | null>(null);
  const [streamingUserText, setStreamingUserText] = useState<string | null>(
    null,
  );
  const [searchFilter, setSearchFilter] = useState<string>("");

  // Graph is the default UI mode filling the viewport
  const [activeSurface, setActiveSurface] = useState<"graph" | "chat">("graph");
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
  const [selectedConceptId, setSelectedConceptId] = useState<string | null>(
    null,
  );

  // Overlays
  const [settingsOpen, setSettingsOpen] = useState<boolean>(false);
  const [timelineOpen, setTimelineOpen] = useState<boolean>(false);
  const [lastFailedTurnId, setLastFailedTurnId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Queries
  const conversationsQuery = useQuery({
    queryKey: ["conversations", searchFilter],
    queryFn: () => apiClient.listConversations(searchFilter || undefined),
  });

  // Ensure an active conversation exists in background without forcing Chat view
  useEffect(() => {
    if (
      !activeConversationId &&
      conversationsQuery.data &&
      conversationsQuery.data.length > 0
    ) {
      setActiveConversationId(conversationsQuery.data[0].id);
    }
  }, [activeConversationId, conversationsQuery.data]);

  const messagesQuery = useQuery({
    queryKey: ["messages", activeConversationId],
    queryFn: () =>
      activeConversationId
        ? apiClient.listMessages(activeConversationId)
        : Promise.resolve([]),
    enabled: Boolean(activeConversationId),
  });

  // Continuously updated Related Chats for the active conversation
  const relatedConversationsQuery = useQuery({
    queryKey: [
      "related-conversations",
      activeConversationId,
      messagesQuery.data?.length ?? 0,
    ],
    queryFn: () =>
      activeConversationId
        ? apiClient.listRelatedConversations(activeConversationId)
        : Promise.resolve([]),
    enabled: Boolean(activeConversationId),
    refetchInterval: 4000,
  });

  const graphQuery = useQuery({
    queryKey: ["graph"],
    queryFn: () =>
      apiClient.getGraph({
        focusConceptId: null,
        layers: ["user_established", "world", "suggested"],
        asOf: null,
      }),
    refetchInterval: 4000,
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
    queryKey: ["concept-evidence", selectedConceptId],
    queryFn: () =>
      selectedConceptId
        ? apiClient.getConceptEvidence(selectedConceptId)
        : Promise.resolve(undefined),
    enabled: Boolean(selectedConceptId),
  });

  const eventsQuery = useQuery({
    queryKey: ["events"],
    queryFn: () => apiClient.listEvents(),
    enabled: timelineOpen,
  });

  const settingsQuery = useQuery({
    queryKey: ["ai-settings"],
    queryFn: () => apiClient.getAISettings(),
  });

  // Mutations
  const createConversationMutation = useMutation({
    mutationFn: (title: string) => apiClient.createConversation(title),
    onSuccess: (conv) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      setActiveConversationId(conv.id);
      setActiveSurface("chat");
    },
  });

  const sendTurnMutation = useMutation({
    mutationFn: async (content: string) => {
      let convId = activeConversationId;
      if (!convId) {
        const created = await apiClient.createConversation("");
        convId = created.id;
        setActiveConversationId(convId);
      }
      setStreamingUserText(content);
      setStreamingContent("");
      await apiClient.sendTurnStream(
        convId,
        content,
        {
          onDelta: (delta) => {
            setStreamingContent((prev) => (prev ?? "") + delta);
          },
          onFailed: (turnId) => {
            if (turnId) setLastFailedTurnId(turnId);
          },
        },
        "personalized",
      );
    },
    onSettled: () => {
      setStreamingUserText(null);
      setStreamingContent(null);
      setComposerText("");
      queryClient.invalidateQueries({ queryKey: ["messages"] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({ queryKey: ["related-conversations"] });
      queryClient.invalidateQueries({ queryKey: ["graph"] });
    },
  });

  const retryTurnMutation = useMutation({
    mutationFn: (turnId: string) => apiClient.retryTurn(turnId),
    onSuccess: () => {
      setLastFailedTurnId(null);
      queryClient.invalidateQueries({ queryKey: ["messages"] });
      queryClient.invalidateQueries({ queryKey: ["graph"] });
    },
  });

  const createRelationMutation = useMutation({
    mutationFn: (payload: {
      conceptId: string;
      targetConceptId: string;
      predicate: string;
      explanation: string;
    }) =>
      apiClient.createUserRelation(
        payload.conceptId,
        payload.targetConceptId,
        payload.predicate,
        payload.explanation,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["graph"] });
      queryClient.invalidateQueries({ queryKey: ["concept"] });
      queryClient.invalidateQueries({ queryKey: ["concept-evidence"] });
    },
  });

  const reviewSignalMutation = useMutation({
    mutationFn: (payload: {
      conceptId: string;
      evidenceId: string;
      decision: "confirm" | "dismiss";
    }) =>
      apiClient.reviewCandidateSignal(
        payload.conceptId,
        payload.evidenceId,
        payload.decision,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["concept"] });
      queryClient.invalidateQueries({ queryKey: ["concept-evidence"] });
      queryClient.invalidateQueries({ queryKey: ["graph"] });
    },
  });

  useEffect(() => {
    if (
      activeSurface === "chat" &&
      typeof messagesEndRef.current?.scrollIntoView === "function"
    ) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messagesQuery.data, streamingContent, activeSurface]);

  // Submitting from the bottom box seamlessly transitions into Chat view
  const handleSendQuestion = () => {
    const trimmed = composerText.trim();
    if (!trimmed) return;
    setSelectedConceptId(null);
    setActiveSurface("chat");
    sendTurnMutation.mutate(trimmed);
  };

  const handleJumpToMessage = (conversationId: string | null) => {
    if (conversationId) {
      setActiveConversationId(conversationId);
      setSelectedConceptId(null);
      setActiveSurface("chat");
    }
  };

  const messages = messagesQuery.data ?? [];
  const activeProviderCap = (settingsQuery.data?.providers ?? []).find(
    (p) => p.provider === settingsQuery.data?.conversation_provider,
  );
  const isAIReady = Boolean(
    !activeProviderCap?.is_remote || activeProviderCap?.has_configured_secret,
  );
  const providerLabel =
    settingsQuery.data?.conversation_provider === "google_gemini"
      ? `Gemini (${settingsQuery.data.conversation_model})`
      : settingsQuery.data?.conversation_provider === "openai_compatible"
        ? `OpenAI (${settingsQuery.data.conversation_model})`
        : settingsQuery.data?.conversation_provider === "anthropic"
          ? "Anthropic"
          : settingsQuery.data?.conversation_provider === "ollama"
            ? "Ollama"
            : "Connect API Key";

  return (
    <div className="relative w-screen h-screen bg-black text-zinc-100 overflow-hidden font-sans">
      {/* Hovering Frosted-Glass Left Sidebar (Visible in both Graph and Chat views) */}
      <FloatingSidebar
        isOpen={sidebarOpen}
        onToggleOpen={() => setSidebarOpen((prev) => !prev)}
        activeSurface={activeSurface}
        onSwitchSurface={(surface) => {
          setActiveSurface(surface);
          if (surface === "chat") {
            setSelectedConceptId(null);
          }
        }}
        conversations={conversationsQuery.data ?? []}
        relatedConversations={relatedConversationsQuery.data ?? []}
        activeConversationId={activeConversationId}
        onSelectConversation={(id) => {
          setActiveConversationId(id);
          setSelectedConceptId(null);
          setActiveSurface("chat");
        }}
        onNewChat={() => createConversationMutation.mutate("")}
        searchFilter={searchFilter}
        onSearchFilterChange={setSearchFilter}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenTimeline={() => setTimelineOpen(true)}
        isAIReady={isAIReady}
        providerLabel={providerLabel}
        graphNodeCount={graphQuery.data?.nodes.length ?? 0}
      />

      {/* Background Surface: Seamless transition between Full-Screen Graph and Chat Stream */}
      {activeSurface === "graph" ? (
        <GraphView
          graph={graphQuery.data}
          isLoading={graphQuery.isLoading}
          selectedConceptId={selectedConceptId}
          onSelectConcept={(conceptId) => setSelectedConceptId(conceptId)}
          onOpenConversation={(convId) => {
            setActiveConversationId(convId);
            setSelectedConceptId(null);
            setActiveSurface("chat");
          }}
        />
      ) : (
        <main
          aria-label="Chat surface"
          className={`w-full h-full overflow-y-auto pt-8 pb-36 px-6 transition-all duration-300 ${
            sidebarOpen ? "md:pl-[20rem]" : ""
          }`}
        >
          <div className="max-w-2xl mx-auto space-y-6">
            {/* Subtle API Key Notice if external provider has no key */}
            {settingsQuery.data && !isAIReady && (
              <div className="rounded-2xl bg-white/[0.04] backdrop-blur-xl border border-white/15 p-4 flex items-center justify-between gap-4">
                <div className="text-xs text-zinc-300">
                  Connect your API key to chat with{" "}
                  <strong className="text-white">
                    {settingsQuery.data.conversation_provider}
                  </strong>
                  .
                </div>
                <button
                  type="button"
                  onClick={() => setSettingsOpen(true)}
                  className="shrink-0 rounded-xl bg-white text-black font-medium px-3 py-1.5 text-xs"
                >
                  Connect Key
                </button>
              </div>
            )}

            {/* Empty Conversation State */}
            {messages.length === 0 && streamingUserText === null && (
              <div className="py-24 text-center space-y-3">
                <h2 className="text-xl font-medium text-white tracking-tight">
                  Start exploring a topic
                </h2>
                <p className="text-xs text-zinc-500 max-w-md mx-auto leading-relaxed">
                  Type a question below. Use{" "}
                  <span className="text-zinc-300 font-mono">#</span> in your
                  message to tag key moments (like{" "}
                  <span className="text-zinc-300 font-mono">#aha</span> or{" "}
                  <span className="text-zinc-300 font-mono">#confused</span>) —
                  Noema automatically categorizes and links your knowledge in
                  the background.
                </p>
              </div>
            )}

            {/* Message Stream */}
            {messages.map((msg) => {
              const isUser = msg.role === "user";
              return (
                <article
                  key={msg.id}
                  className={`flex flex-col ${
                    isUser ? "items-end" : "items-start"
                  }`}
                >
                  <div
                    className={`max-w-[88%] rounded-2xl px-5 py-3.5 text-sm leading-relaxed ${
                      isUser
                        ? "bg-white text-black font-normal"
                        : "bg-white/[0.04] border border-white/10 text-zinc-100"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>

                    {/* Inline saved tags on message */}
                    {msg.annotations.length > 0 && (
                      <div className="mt-2.5 flex flex-wrap gap-1.5">
                        {msg.annotations.map((ann) => (
                          <span
                            key={ann.id}
                            className={`inline-flex items-center text-[11px] font-mono px-2 py-0.5 rounded-md ${
                              isUser
                                ? "bg-black/10 text-black"
                                : "bg-white/10 text-zinc-200"
                            }`}
                          >
                            #{ann.tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Subtle clickable concept pills under assistant messages */}
                  {!isUser && msg.mentions.length > 0 && (
                    <div className="mt-1.5 px-1 flex flex-wrap items-center gap-1.5">
                      {msg.mentions.map((m) => (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => {
                            setSelectedConceptId(m.concept_id);
                          }}
                          className="text-[11px] text-zinc-500 hover:text-white px-2 py-0.5 rounded-full bg-white/[0.03] hover:bg-white/[0.08] border border-white/10 transition-colors"
                        >
                          {m.canonical_name}
                        </button>
                      ))}
                    </div>
                  )}
                </article>
              );
            })}

            {/* Live Streaming Turn Preview */}
            {streamingUserText !== null && (
              <>
                <article className="flex flex-col items-end">
                  <div className="max-w-[88%] rounded-2xl px-5 py-3.5 text-sm leading-relaxed bg-white text-black">
                    <p className="whitespace-pre-wrap">{streamingUserText}</p>
                  </div>
                </article>
                <article className="flex flex-col items-start">
                  <div className="max-w-[88%] rounded-2xl px-5 py-3.5 text-sm leading-relaxed bg-white/[0.04] border border-white/10 text-zinc-100">
                    {streamingContent ? (
                      <p className="whitespace-pre-wrap">{streamingContent}</p>
                    ) : (
                      <span className="text-xs text-zinc-500 animate-pulse">
                        Thinking...
                      </span>
                    )}
                  </div>
                </article>
              </>
            )}

            {/* Failed Turn Retry Banner */}
            {lastFailedTurnId && (
              <div
                role="alert"
                className="rounded-2xl border border-white/20 bg-white/[0.05] p-4 flex items-center justify-between"
              >
                <div className="text-xs text-zinc-200">
                  Response interrupted. Your message is safely saved.
                </div>
                <button
                  type="button"
                  onClick={() => retryTurnMutation.mutate(lastFailedTurnId)}
                  className="rounded-xl bg-white px-3 py-1.5 text-xs font-medium text-black"
                >
                  Retry
                </button>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </main>
      )}

      {/* Floating Frosted-Glass Concept Drawer (when a node or concept pill is clicked) */}
      {selectedConceptId && (
        <div className="fixed top-5 bottom-24 right-5 z-30 rounded-2xl overflow-hidden shadow-[0_20px_60px_rgba(0,0,0,0.9)] border border-white/15 bg-black/85 backdrop-blur-2xl">
          <ConceptInspector
            concept={conceptDetailQuery.data}
            evidence={conceptEvidenceQuery.data}
            allConcepts={graphQuery.data?.nodes ?? []}
            onClose={() => setSelectedConceptId(null)}
            onJumpToConversation={(convId) => handleJumpToMessage(convId)}
            onStartGroundedChat={(conceptName) => {
              setComposerText(`Tell me more about ${conceptName}`);
              setSelectedConceptId(null);
              setActiveSurface("chat");
            }}
            onAcceptSuggestion={(id) => {
              void apiClient.acceptSuggestion(id).then(() => {
                void queryClient.invalidateQueries({ queryKey: ["graph"] });
                void queryClient.invalidateQueries({
                  queryKey: ["concept-evidence"],
                });
              });
            }}
            onRejectSuggestion={(id) => {
              void apiClient.rejectSuggestion(id).then(() => {
                void queryClient.invalidateQueries({ queryKey: ["graph"] });
                void queryClient.invalidateQueries({
                  queryKey: ["concept-evidence"],
                });
              });
            }}
            onDismissSuggestion={(id) => {
              void apiClient.dismissSuggestion(id).then(() => {
                void queryClient.invalidateQueries({ queryKey: ["graph"] });
                void queryClient.invalidateQueries({
                  queryKey: ["concept-evidence"],
                });
              });
            }}
            onWithdrawRelation={(id) => {
              void apiClient.withdrawRelation(id).then(() => {
                void queryClient.invalidateQueries({ queryKey: ["graph"] });
                void queryClient.invalidateQueries({
                  queryKey: ["concept-evidence"],
                });
              });
            }}
            onCreateRelation={(sourceId, targetId, predicate, explanation) =>
              createRelationMutation.mutate({
                conceptId: sourceId,
                targetConceptId: targetId,
                predicate,
                explanation,
              })
            }
            onReviewSignal={(conceptId, evidenceId, decision) =>
              reviewSignalMutation.mutate({ conceptId, evidenceId, decision })
            }
            onMergeConcept={(sourceId, targetId) => {
              void apiClient.mergeConcept(sourceId, targetId).then(() => {
                setSelectedConceptId(targetId);
                void queryClient.invalidateQueries({ queryKey: ["graph"] });
                void queryClient.invalidateQueries({ queryKey: ["concept"] });
              });
            }}
          />
        </div>
      )}

      {/* Floating Frosted-Glass Question Box at the bottom (with #tag autocomplete popup) */}
      <FloatingComposer
        value={composerText}
        onChange={setComposerText}
        onSubmit={handleSendQuestion}
        isSending={sendTurnMutation.isPending}
        activeSurface={activeSurface}
        sidebarOpen={sidebarOpen}
      />

      {/* Settings & API Key Frosted Modal */}
      {settingsOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xl flex items-center justify-center p-4 overflow-y-auto">
          <div className="w-full max-w-2xl rounded-3xl bg-zinc-950 border border-white/15 shadow-2xl overflow-hidden max-h-[90vh] overflow-y-auto">
            <SettingsAndOwnershipView
              settings={settingsQuery.data}
              onUpdateSettings={async (payload: UpdateAISettingsPayload) => {
                await apiClient.updateAISettings(payload);
                await queryClient.invalidateQueries({
                  queryKey: ["ai-settings"],
                });
              }}
              onValidateProvider={(provider, localUrl, apiKey) =>
                apiClient.validateAISettings(provider, localUrl, apiKey)
              }
              onExportWorkspace={() => apiClient.exportWorkspace()}
              onReturnToChat={() => setSettingsOpen(false)}
            />
          </div>
        </div>
      )}

      {/* History & Export Frosted Modal */}
      {timelineOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xl flex items-center justify-center p-4 overflow-y-auto">
          <div className="w-full max-w-2xl rounded-3xl bg-zinc-950 border border-white/15 shadow-2xl overflow-hidden max-h-[90vh] overflow-y-auto">
            <TimelineView
              events={eventsQuery.data ?? []}
              onReturnToChat={() => setTimelineOpen(false)}
              onSelectConcept={(conceptId) => {
                setTimelineOpen(false);
                setSelectedConceptId(conceptId);
              }}
              onJumpToConversation={(convId) => {
                setTimelineOpen(false);
                setActiveConversationId(convId);
                setActiveSurface("chat");
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
