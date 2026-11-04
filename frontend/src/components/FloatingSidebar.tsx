/** Hovering frosted-glass sidebar visible across Graph and Chat views, featuring live Related Chats. */

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
  if (!isOpen) {
    return (
      <div className="fixed top-5 left-5 z-30 flex items-center gap-2">
        <button
          type="button"
          onClick={onToggleOpen}
          title="Show sidebar"
          className="rounded-xl bg-black/75 backdrop-blur-xl border border-white/15 px-3.5 py-2 text-xs font-medium text-white hover:border-white/35 transition-colors shadow-xl"
        >
          ☰ Noema
        </button>
        <div className="rounded-xl bg-black/75 backdrop-blur-xl border border-white/15 p-1 flex items-center gap-1 shadow-xl">
          <button
            type="button"
            onClick={() => onSwitchSurface("graph")}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
              activeSurface === "graph"
                ? "bg-white text-black"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            Graph ({graphNodeCount})
          </button>
          <button
            type="button"
            onClick={() => onSwitchSurface("chat")}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
              activeSurface === "chat"
                ? "bg-white text-black"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            Chat
          </button>
        </div>
      </div>
    );
  }

  return (
    <aside
      aria-label="Workspace sidebar"
      className="fixed top-5 bottom-5 left-5 w-72 z-30 rounded-2xl bg-black/70 backdrop-blur-2xl border border-white/12 shadow-[0_16px_48px_rgba(0,0,0,0.85)] flex flex-col overflow-hidden"
    >
      {/* Top Header & Seamless Mode Switcher */}
      <div className="p-3.5 border-b border-white/10 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-white" />
            <span className="text-sm font-semibold tracking-tight text-white">
              Noema
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={onNewChat}
              className="text-xs bg-white hover:bg-zinc-200 text-black font-medium px-2.5 py-1 rounded-lg transition-colors"
            >
              + New
            </button>
            <button
              type="button"
              onClick={onToggleOpen}
              title="Minimize sidebar"
              className="text-xs text-zinc-500 hover:text-white px-1.5 py-1 rounded-lg"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Seamless Graph <-> Chat Switcher */}
        <div className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-white/[0.04] border border-white/10">
          <button
            type="button"
            onClick={() => onSwitchSurface("graph")}
            className={`py-1.5 rounded-lg text-xs font-medium transition-all ${
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
            className={`py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeSurface === "chat"
                ? "bg-white text-black shadow-sm"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            💬 Chat
          </button>
        </div>

        {/* Quick Search */}
        <input
          aria-label="Filter conversations"
          type="text"
          value={searchFilter}
          onChange={(e) => onSearchFilterChange(e.target.value)}
          placeholder="Search chats..."
          className="w-full rounded-xl bg-white/[0.04] border border-white/10 px-3 py-1.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/30"
        />
      </div>

      {/* Scrollable Body: Related Chats (in Chat mode) + Recent Chats */}
      <div className="flex-1 overflow-y-auto px-2.5 py-3 space-y-4">
        {activeSurface === "chat" && relatedConversations.length > 0 && (
          <div>
            <div className="px-2 mb-1.5 flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-300">
                Related to Current Chat
              </span>
              <span className="text-[10px] text-zinc-500">Live</span>
            </div>
            <div className="space-y-1">
              {relatedConversations.map((rel) => (
                <button
                  key={rel.conversation_id}
                  type="button"
                  onClick={() => onSelectConversation(rel.conversation_id)}
                  className="w-full text-left rounded-xl px-2.5 py-2 bg-white/[0.04] hover:bg-white/[0.09] border border-white/10 transition-colors"
                >
                  <div className="text-xs font-medium text-white truncate">
                    {rel.title || "Untitled chat"}
                  </div>
                  {rel.shared_concepts.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {rel.shared_concepts.slice(0, 3).map((conceptName) => (
                        <span
                          key={conceptName}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-zinc-200 truncate max-w-[110px]"
                        >
                          {conceptName}
                        </span>
                      ))}
                    </div>
                  )}
                  {rel.snippet && (
                    <p className="mt-1 text-[11px] text-zinc-400 line-clamp-2">
                      {rel.snippet}
                    </p>
                  )}
                </button>
              ))}
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
                  conv.id === activeConversationId && activeSurface === "chat";
                return (
                  <button
                    key={conv.id}
                    type="button"
                    onClick={() => onSelectConversation(conv.id)}
                    className={`w-full text-left rounded-xl px-2.5 py-2 text-xs transition-colors flex items-center justify-between gap-2 ${
                      isActive
                        ? "bg-white text-black font-medium"
                        : "text-zinc-300 hover:bg-white/[0.06] hover:text-white"
                    }`}
                  >
                    <span className="truncate">
                      {conv.title || "New conversation"}
                    </span>
                    {conv.extraction_status === "pending" && (
                      <span
                        title="Organizing in background..."
                        className={`w-1.5 h-1.5 rounded-full animate-pulse shrink-0 ${
                          isActive ? "bg-black" : "bg-zinc-400"
                        }`}
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
      <div className="p-2.5 border-t border-white/10 flex items-center justify-between gap-1.5 bg-black/40">
        <button
          type="button"
          onClick={onOpenSettings}
          className="flex-1 flex items-center gap-2 rounded-xl px-2.5 py-2 text-xs text-zinc-300 hover:text-white hover:bg-white/[0.06] transition-colors truncate"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full shrink-0 ${
              isAIReady ? "bg-white" : "bg-amber-400"
            }`}
          />
          <span className="truncate">⚙ {providerLabel}</span>
        </button>
        <button
          type="button"
          onClick={onOpenTimeline}
          title="Knowledge history & export"
          className="rounded-xl px-2.5 py-2 text-xs text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors shrink-0"
        >
          History
        </button>
      </div>
    </aside>
  );
};
