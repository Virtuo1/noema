/** Hovering frosted-glass sidebar + always-visible top-center Graph/Chat toggle + fixed-position sidebar button. */

import React from "react";
import type { ConversationDTO, RelatedConversationDTO } from "../api/types";

interface FloatingSidebarProps {
  isOpen: boolean;
  onToggleOpen: () => void;
  activeSurface: "graph" | "chat";
  onSwitchSurface: (surface: "graph" | "chat") => void;
  conversations: ConversationDTO[];
  relatedConversations: RelatedConversationDTO[];
  activeConversationId: string | null;
  onSelectConversation: (conversationId: string) => void;
  onNewChat: () => void;
  searchFilter: string;
  onSearchFilterChange: (value: string) => void;
  onOpenSettings: () => void;
  onOpenTimeline: () => void;
  isAIReady: boolean;
  providerLabel: string;
  graphNodeCount: number;
}

export const FloatingSidebar: React.FC<FloatingSidebarProps> = ({
  isOpen,
  onToggleOpen,
  activeSurface,
  onSwitchSurface,
  conversations,
  relatedConversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  searchFilter,
  onSearchFilterChange,
  onOpenSettings,
  onOpenTimeline,
  isAIReady,
  providerLabel,
  graphNodeCount,
}) => {
  return (
    <>
      {/* Fixed-Position Sidebar Maximize/Minimize Button (Exact same coordinates open or closed) */}
      <button
        type="button"
        onClick={onToggleOpen}
        aria-label={isOpen ? "Minimize sidebar" : "Maximize sidebar"}
        title={isOpen ? "Minimize sidebar" : "Maximize sidebar"}
        className="fixed top-7 left-7 z-40 w-8 h-8 rounded-xl bg-zinc-900/80 hover:bg-zinc-800/90 backdrop-blur-xl border border-white/[0.06] flex items-center justify-center text-xs text-zinc-300 hover:text-white transition-all duration-200 shadow-lg"
      >
        {isOpen ? "✕" : "☰"}
      </button>

      {/* Always-Visible Top Graph / Chat Pill Toggle (centered between sidebar and right edge, matching question box) */}
      <div
        className={`fixed top-5 right-6 z-30 transition-all duration-300 ease-out pointer-events-none flex justify-center ${
          isOpen ? "left-6 md:left-[20rem]" : "left-6"
        }`}
      >
        <div className="pointer-events-auto rounded-2xl bg-zinc-950/75 backdrop-blur-2xl border border-white/[0.06] p-1 flex items-center gap-1 shadow-[0_8px_30px_rgba(0,0,0,0.8)]">
          <button
            type="button"
            onClick={() => onSwitchSurface("graph")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-medium transition-all duration-200 ${
              activeSurface === "graph"
                ? "bg-white text-black shadow-sm"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            ◉ Graph ({graphNodeCount})
          </button>
          <button
            type="button"
            onClick={() => onSwitchSurface("chat")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-medium transition-all duration-200 ${
              activeSurface === "chat"
                ? "bg-white text-black shadow-sm"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            💬 Chat
          </button>
        </div>
      </div>

      {/* Hovering Frosted-Glass Sidebar with Smooth Transform + Opacity Transition */}
      <aside
        aria-label="Workspace sidebar"
        className={`fixed top-5 bottom-5 left-5 w-72 z-30 rounded-2xl bg-zinc-950/75 backdrop-blur-2xl border border-white/[0.05] shadow-[0_20px_60px_rgba(0,0,0,0.9)] flex flex-col overflow-hidden transition-all duration-300 ease-out ${
          isOpen
            ? "translate-x-0 opacity-100"
            : "-translate-x-6 opacity-0 pointer-events-none"
        }`}
      >
        {/* Top Header (padded left so fixed button sits cleanly in top-left corner) */}
        <div className="p-3.5 border-b border-white/[0.05] space-y-3">
          <div className="flex items-center justify-between pl-10 min-h-[2rem]">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold tracking-tight text-white">
                Noema
              </span>
            </div>
            <button
              type="button"
              onClick={onNewChat}
              className="text-xs bg-white/[0.08] hover:bg-white/[0.14] text-white font-medium px-2.5 py-1 rounded-lg transition-colors"
            >
              + New
            </button>
          </div>

          {/* Quick Search */}
          <input
            aria-label="Filter conversations"
            type="text"
            value={searchFilter}
            onChange={(e) => onSearchFilterChange(e.target.value)}
            placeholder="Search chats..."
            className="w-full rounded-xl bg-white/[0.03] border border-white/[0.06] px-3 py-1.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/20 transition-colors"
          />
        </div>

        {/* Scrollable Body: Related Chats (in Chat mode) + Recent Chats */}
        <div className="flex-1 overflow-y-auto px-2.5 py-3 space-y-4">
          {activeSurface === "chat" && relatedConversations.length > 0 && (
            <div className="animate-fade-in">
              <div className="px-2 mb-1.5 flex items-center justify-between">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                  Related Chats
                </span>
                <span className="text-[10px] text-zinc-600">Live</span>
              </div>
              <div className="space-y-1">
                {relatedConversations.map((rel) => {
                  const cid = rel.id || rel.conversation_id;
                  return (
                    <button
                      key={cid}
                      type="button"
                      onClick={() => onSelectConversation(cid)}
                      className="w-full text-left rounded-xl px-2.5 py-2 bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.05] transition-colors"
                    >
                      <div className="text-xs font-medium text-zinc-100 truncate">
                        {rel.title || "Untitled chat"}
                      </div>
                      {rel.shared_concepts.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {rel.shared_concepts
                            .slice(0, 3)
                            .map((conceptName) => (
                              <span
                                key={conceptName}
                                className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-300 truncate max-w-[110px]"
                              >
                                {conceptName}
                              </span>
                            ))}
                        </div>
                      )}
                      {rel.snippet && (
                        <p className="mt-1 text-[11px] text-zinc-500 line-clamp-2">
                          {rel.snippet}
                        </p>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div>
            <div className="px-2 mb-1.5 flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                Recent Chats
              </span>
              <span className="text-[10px] text-zinc-600">
                {conversations.length}
              </span>
            </div>
            {conversations.length === 0 ? (
              <p className="text-xs text-zinc-500 px-2 py-4 text-center">
                Ask a question below to start your first conversation.
              </p>
            ) : (
              <div className="space-y-0.5">
                {conversations.map((conv) => {
                  const isActive =
                    conv.id === activeConversationId &&
                    activeSurface === "chat";
                  return (
                    <button
                      key={conv.id}
                      type="button"
                      onClick={() => onSelectConversation(conv.id)}
                      className={`w-full text-left rounded-xl px-2.5 py-2 text-xs transition-all duration-150 flex items-center justify-between gap-2 ${
                        isActive
                          ? "bg-white/[0.12] text-white font-medium"
                          : "text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-200"
                      }`}
                    >
                      <span className="truncate">
                        {conv.title || "New conversation"}
                      </span>
                      {conv.extraction_status === "pending" && (
                        <span
                          title="Organizing in background..."
                          className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-pulse shrink-0"
                        />
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Footer: Timeline & AI Settings */}
        <div className="p-2.5 border-t border-white/[0.05] flex items-center justify-between gap-1.5 bg-black/30">
          <button
            type="button"
            onClick={onOpenSettings}
            className="flex-1 flex items-center gap-2 rounded-xl px-2.5 py-2 text-xs text-zinc-400 hover:text-white hover:bg-white/[0.05] transition-colors truncate"
          >
            <span
              className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                isAIReady ? "bg-emerald-400" : "bg-amber-400"
              }`}
            />
            <span className="truncate">⚙ {providerLabel}</span>
          </button>
          <button
            type="button"
            onClick={onOpenTimeline}
            title="Knowledge history & export"
            className="rounded-xl px-2.5 py-2 text-xs text-zinc-500 hover:text-white hover:bg-white/[0.05] transition-colors shrink-0"
          >
            History
          </button>
        </div>
      </aside>
    </>
  );
};
