/**
 * Noema — Seamless Full-Screen Graph & Chat Workspace
 * - Default UI mode: Full-screen Obsidian-style hierarchical & semantic-zoom knowledge graph
 * - Top-center Graph/Chat toggle + fixed-position sidebar button + smooth transitions
 * - Centered Topic Context Card aligned above the question box (passes topic notes as silent background context)
 * - Esc acts as universal back button (closes modals -> closes topic card -> returns from Chat to Graph)
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./api/client";
import type { UpdateAISettingsPayload } from "./api/types";
import { ConceptInspector } from "./components/ConceptInspector";
import {
  FloatingComposer,
  getTagBadgeClasses,
} from "./components/FloatingComposer";
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

  // Universal Esc Back Button: Modal -> Topic Card -> Chat back to Graph
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (settingsOpen) {
        setSettingsOpen(false);
        return;
      }
      if (timelineOpen) {
        setTimelineOpen(false);
        return;
      }
      if (selectedConceptId) {
        setSelectedConceptId(null);
        return;
      }
      if (activeSurface === "chat") {
        setActiveSurface("graph");
      }
    };
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, [settingsOpen, timelineOpen, selectedConceptId, activeSurface]);

  // Queries
  const conversationsQuery = useQuery({
    queryKey: ["conversations", searchFilter],
    queryFn: () => apiClient.listConversations(searchFilter || undefined),
  });

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
    refetchInterval: 5000,
  });

  const graphQuery = useQuery({
    queryKey: ["graph"],
    queryFn: () =>
      apiClient.getGraph({
        focusConceptId: null,
        layers: ["user_established", "world", "suggested"],
        asOf: null,
      }),
    refetchInterval: 5000,
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
      setSelectedConceptId(null);
      setActiveSurface("chat");
    },
  });

  const sendTurnMutation = useMutation({
    mutationFn: async (payload: {
      content: string;
      focusConceptId: string | null;
    }) => {
      let convId = activeConversationId;
      if (!convId) {
        const created = await apiClient.createConversation("");
        convId = created.id;
        setActiveConversationId(convId);
      }
      setStreamingUserText(payload.content);
      setStreamingContent("");
      await apiClient.sendTurnStream(
        convId,
        payload.content,
        {
          onDelta: (delta) => {
            setStreamingContent((prev) => (prev ?? "") + delta);
          },
          onFailed: (turnId) => {
            if (turnId) setLastFailedTurnId(turnId);
          },
        },
        "personalized",
        payload.focusConceptId,
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

  useEffect(() => {
    if (
      activeSurface === "chat" &&
      typeof messagesEndRef.current?.scrollIntoView === "function"
    ) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messagesQuery.data, streamingContent, activeSurface]);

  const handleSelectConcept = useCallback((conceptId: string) => {
    setSelectedConceptId((prev) => (prev === conceptId ? null : conceptId));
  }, []);

  // Submitting from the bottom box transitions smoothly into Chat view while passing any open topic card as silent background context
  const handleSendQuestion = () => {
    const trimmed = composerText.trim();
    if (!trimmed) return;
    const focusId = selectedConceptId;
    setSelectedConceptId(null);
    setActiveSurface("chat");
    sendTurnMutation.mutate({ content: trimmed, focusConceptId: focusId });
  };

  const handleJumpToMessage = useCallback((conversationId: string | null) => {
    if (conversationId) {
      setActiveConversationId(conversationId);
      setSelectedConceptId(null);
      setActiveSurface("chat");
    }
  }, []);

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

  const activeTopicNode = (graphQuery.data?.nodes ?? []).find(
    (n) => n.id === selectedConceptId,
  );
  const activeTopicName =
    conceptDetailQuery.data?.canonical_name ?? activeTopicNode?.label ?? null;

  return (
    <div className="relative w-screen h-screen bg-black text-zinc-100 overflow-hidden font-sans">
      {/* Hovering Frosted-Glass Left Sidebar + Top-Middle Graph/Chat Toggle */}
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

      {/* Background Surface: Smooth transition between Full-Screen Graph and Chat Stream */}
      {activeSurface === "graph" ? (
        <GraphView
          graph={graphQuery.data}
          isLoading={graphQuery.isLoading}
          selectedConceptId={selectedConceptId}
          onSelectConcept={handleSelectConcept}
          onOpenConversation={handleJumpToMessage}
        />
      ) : (
        <main
          aria-label="Chat surface"
          className={`w-full h-full overflow-y-auto pt-20 pb-40 px-6 transition-all duration-300 ease-out animate-fade-in ${
            sidebarOpen ? "md:pl-[20rem]" : ""
          }`}
        >
          <div className="max-w-2xl mx-auto space-y-8">
            {/* Subtle API Key Notice if external provider has no key */}
            {settingsQuery.data && !isAIReady && (
              <div className="rounded-2xl bg-white/[0.03] backdrop-blur-xl border border-white/[0.08] p-4 flex items-center justify-between gap-4 animate-fade-in">
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
              <div className="py-24 text-center space-y-3 animate-fade-in">
                <h2 className="text-xl font-medium text-white tracking-tight">
                  Start exploring a topic
                </h2>
                <p className="text-xs text-zinc-500 max-w-md mx-auto leading-relaxed">
                  Type a question below. Use{" "}
                  <span className="text-zinc-300 font-mono">#</span> in your
                  message to tag key moments (like{" "}
                  <span className="text-emerald-300 font-mono">#aha</span> or{" "}
                  <span className="text-rose-300 font-mono">#confused</span>) —
                  or press <span className="text-zinc-300 font-mono">Esc</span>{" "}
                  at any time to return to the graph.
                </p>
              </div>
            )}

            {/* Message Stream: User prompt in a subtle box; Assistant text directly on background with smooth fade-in */}
            {messages.map((msg) => {
              const isUser = msg.role === "user";
              return (
                <article
                  key={msg.id}
                  className={`flex flex-col animate-fade-in ${
                    isUser ? "items-end" : "items-start"
                  }`}
                >
                  {isUser ? (
                    <div className="max-w-[85%] rounded-2xl bg-white/[0.07] border border-white/[0.08] px-5 py-3.5 text-sm leading-relaxed text-zinc-100">
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                      {msg.annotations.length > 0 && (
                        <div className="mt-2.5 flex flex-wrap gap-1.5">
                          {msg.annotations.map((ann) => (
                            <span
                              key={ann.id}
                              className={`inline-flex items-center text-[11px] font-mono px-2 py-0.5 rounded-md border ${getTagBadgeClasses(
                                ann.tag,
                              )}`}
                            >
                              #{ann.tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    /* Assistant outputs directly onto the pure black background */
                    <div className="w-full py-1 text-[15px] leading-relaxed text-zinc-200">
                      <p className="whitespace-pre-wrap">{msg.content}</p>

                      {msg.annotations.length > 0 && (
                        <div className="mt-2.5 flex flex-wrap gap-1.5">
                          {msg.annotations.map((ann) => (
                            <span
                              key={ann.id}
                              className={`inline-flex items-center text-[11px] font-mono px-2 py-0.5 rounded-md border ${getTagBadgeClasses(
                                ann.tag,
                              )}`}
                            >
                              #{ann.tag}
                            </span>
                          ))}
                        </div>
                      )}

                      {msg.mentions.length > 0 && (
                        <div className="mt-3 flex flex-wrap items-center gap-1.5">
                          {msg.mentions.map((m) => (
                            <button
                              key={m.id}
                              type="button"
                              onClick={() => handleSelectConcept(m.concept_id)}
                              className="text-[11px] text-zinc-400 hover:text-white px-2.5 py-0.5 rounded-full bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.06] transition-colors"
                            >
                              {m.canonical_name}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </article>
              );
            })}

            {/* Live Streaming Turn Preview */}
            {streamingUserText !== null && (
              <>
                <article className="flex flex-col items-end animate-fade-in">
                  <div className="max-w-[85%] rounded-2xl bg-white/[0.07] border border-white/[0.08] px-5 py-3.5 text-sm leading-relaxed text-zinc-100">
                    <p className="whitespace-pre-wrap">{streamingUserText}</p>
                  </div>
                </article>
                <article className="flex flex-col items-start animate-fade-in">
                  <div className="w-full py-1 text-[15px] leading-relaxed text-zinc-200">
                    {streamingContent ? (
                      <p className="whitespace-pre-wrap animate-fade-in">
                        {streamingContent}
                      </p>
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
                className="rounded-2xl border border-white/[0.1] bg-white/[0.04] p-4 flex items-center justify-between animate-fade-in"
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

      {/* Centered Topic Context Card aligned directly above the bottom Question Box (with darkening + blur backdrop over background) */}
      {selectedConceptId && (
        <>
          <div
            data-testid="topic-card-backdrop"
            aria-hidden="true"
            onClick={() => setSelectedConceptId(null)}
            className="fixed inset-0 z-20 bg-black/65 backdrop-blur-md transition-all duration-300 animate-fade-in"
          />
          <div
            className={`fixed bottom-24 right-6 z-30 transition-all duration-300 ease-out pointer-events-none flex justify-center ${
              sidebarOpen ? "left-6 md:left-[20rem]" : "left-6"
            }`}
          >
            <div className="w-full max-w-2xl pointer-events-auto">
              <ConceptInspector
                concept={conceptDetailQuery.data}
                evidence={conceptEvidenceQuery.data}
                allConcepts={graphQuery.data?.nodes ?? []}
                onClose={() => setSelectedConceptId(null)}
                onJumpToConversation={(convId) => handleJumpToMessage(convId)}
                onSelectRelatedConcept={(cid) => setSelectedConceptId(cid)}
              />
            </div>
          </div>
        </>
      )}

      {/* Floating Frosted-Glass Question Box at the bottom (with #tag autocomplete & active topic pill) */}
      <FloatingComposer
        value={composerText}
        onChange={setComposerText}
        onSubmit={handleSendQuestion}
        isSending={sendTurnMutation.isPending}
        activeSurface={activeSurface}
        sidebarOpen={sidebarOpen}
        activeTopicName={activeTopicName}
        onClearActiveTopic={() => setSelectedConceptId(null)}
      />

      {/* Settings & API Key Frosted Modal */}
      {settingsOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xl flex items-center justify-center p-4 overflow-y-auto animate-fade-in">
          <div className="w-full max-w-2xl rounded-3xl bg-zinc-950 border border-white/[0.08] shadow-2xl overflow-hidden max-h-[90vh] overflow-y-auto">
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
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xl flex items-center justify-center p-4 overflow-y-auto animate-fade-in">
          <div className="w-full max-w-2xl rounded-3xl bg-zinc-950 border border-white/[0.08] shadow-2xl overflow-hidden max-h-[90vh] overflow-y-auto">
            <TimelineView
              events={eventsQuery.data ?? []}
              onReturnToChat={() => setTimelineOpen(false)}
              onSelectConcept={(conceptId) => {
                setTimelineOpen(false);
                setSelectedConceptId(conceptId);
              }}
              onJumpToConversation={(convId) => {
                setTimelineOpen(false);
                setSelectedConceptId(null);
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
