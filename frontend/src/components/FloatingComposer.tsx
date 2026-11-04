/** Modular floating frosted-glass question bar with colored #tag autocomplete and active background topic pill. */

import React, { useMemo, useRef, useState } from "react";
import type { AnnotationTag } from "../api/types";

export interface TagOption {
  tag: AnnotationTag;
  label: string;
  description: string;
  badgeClass: string;
}

export const TAG_COLOR_MAP: Record<string, string> = {
  aha: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  confused: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  question: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  important: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  connection: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  hypothesis: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  revisit: "bg-teal-500/15 text-teal-300 border-teal-500/30",
};

export function getTagBadgeClasses(tag: string): string {
  const clean = tag.replace(/^#/, "").toLowerCase();
  return (
    TAG_COLOR_MAP[clean] ?? "bg-zinc-500/15 text-zinc-300 border-zinc-500/30"
  );
}

export const AVAILABLE_TAGS: TagOption[] = [
  {
    tag: "aha",
    label: "#aha",
    description: "Mark a breakthrough or clear realization",
    badgeClass: TAG_COLOR_MAP.aha!,
  },
  {
    tag: "confused",
    label: "#confused",
    description: "Flag something unclear or puzzling",
    badgeClass: TAG_COLOR_MAP.confused!,
  },
  {
    tag: "question",
    label: "#question",
    description: "Save an open question to explore further",
    badgeClass: TAG_COLOR_MAP.question!,
  },
  {
    tag: "important",
    label: "#important",
    description: "Highlight a core idea worth remembering",
    badgeClass: TAG_COLOR_MAP.important!,
  },
  {
    tag: "connection",
    label: "#connection",
    description: "Note a link between two topics",
    badgeClass: TAG_COLOR_MAP.connection!,
  },
  {
    tag: "hypothesis",
    label: "#hypothesis",
    description: "Record a tentative mental model or theory",
    badgeClass: TAG_COLOR_MAP.hypothesis!,
  },
  {
    tag: "revisit",
    label: "#revisit",
    description: "Bookmark this topic to review later",
    badgeClass: TAG_COLOR_MAP.revisit!,
  },
];

interface FloatingComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  isSending: boolean;
  activeSurface: "graph" | "chat";
  sidebarOpen: boolean;
  activeTopicName?: string | null;
  onClearActiveTopic?: () => void;
  placeholder?: string;
}

export const FloatingComposer: React.FC<FloatingComposerProps> = ({
  value,
  onChange,
  onSubmit,
  isSending,
  activeSurface,
  sidebarOpen,
  activeTopicName,
  onClearActiveTopic,
  placeholder,
}) => {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const activeTagMatch = useMemo(() => {
    const match = /(?:^|\s)#([a-zA-Z]*)$/.exec(value);
    if (!match) return null;
    const query = (match[1] ?? "").toLowerCase();
    const matches = AVAILABLE_TAGS.filter((item) =>
      item.tag.toLowerCase().startsWith(query),
    );
    if (matches.length === 0) return null;
    return {
      query,
      matches,
    };
  }, [value]);

  const applyTagSuggestion = (tag: AnnotationTag) => {
    const nextValue = value.replace(/(^|\s)#[a-zA-Z]*$/, `$1#${tag} `);
    onChange(nextValue);
    setSelectedIndex(0);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (activeTagMatch && activeTagMatch.matches.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % activeTagMatch.matches.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex(
          (prev) =>
            (prev - 1 + activeTagMatch.matches.length) %
            activeTagMatch.matches.length,
        );
        return;
      }
      if (e.key === "Tab") {
        e.preventDefault();
        const picked =
          activeTagMatch.matches[
            Math.min(selectedIndex, activeTagMatch.matches.length - 1)
          ];
        if (picked) {
          applyTagSuggestion(picked.tag);
        }
        return;
      }
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim() || isSending) return;
    onSubmit();
  };

  const defaultPlaceholder = activeTopicName
    ? `Ask about ${activeTopicName} (notes included as background)...`
    : activeSurface === "graph"
      ? "Ask anything to transition into chat... (type # for tags)"
      : "Ask a follow-up or save a thought with #aha, #confused, #important...";

  return (
    <div
      className={`fixed bottom-6 right-6 z-30 transition-all duration-300 ease-out pointer-events-none flex justify-center ${
        sidebarOpen ? "left-6 md:left-[20rem]" : "left-6"
      }`}
    >
      <div className="w-full max-w-2xl pointer-events-auto relative">
        {/* Colored #Tag Autocomplete Popup */}
        {activeTagMatch && (
          <div
            role="listbox"
            aria-label="Tag suggestions"
            className="mb-2.5 rounded-2xl bg-zinc-950/90 backdrop-blur-2xl border border-white/[0.08] shadow-2xl overflow-hidden animate-fade-in"
          >
            <div className="px-3.5 py-2 border-b border-white/[0.06] flex items-center justify-between text-[11px] text-zinc-400">
              <span className="font-medium text-zinc-200">Save with tag</span>
              <span>Tab to complete · click to insert</span>
            </div>
            <div className="max-h-56 overflow-y-auto divide-y divide-white/[0.04]">
              {activeTagMatch.matches.map((item, idx) => {
                const isSelected = idx === selectedIndex;
                return (
                  <button
                    key={item.tag}
                    type="button"
                    onClick={() => applyTagSuggestion(item.tag)}
                    className={`w-full text-left px-3.5 py-2.5 flex items-center justify-between gap-3 transition-colors ${
                      isSelected
                        ? "bg-white/[0.08] text-white"
                        : "text-zinc-300 hover:bg-white/[0.04]"
                    }`}
                  >
                    <span
                      className={`font-mono text-xs font-medium px-2 py-0.5 rounded-md border ${item.badgeClass}`}
                    >
                      {item.label}
                    </span>
                    <span className="text-xs text-zinc-400 truncate">
                      {item.description}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Frosted-Glass Floating Question Box */}
        <form
          onSubmit={handleFormSubmit}
          className="flex items-center gap-2 rounded-2xl bg-zinc-950/80 backdrop-blur-2xl border border-white/[0.08] px-4 py-2.5 shadow-[0_12px_40px_rgba(0,0,0,0.85)] focus-within:border-white/20 transition-all duration-200"
        >
          {activeTopicName && (
            <span className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-xl bg-white/[0.07] border border-white/[0.08] text-zinc-200 shrink-0">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
              <span className="truncate max-w-[140px]">{activeTopicName}</span>
              {onClearActiveTopic && (
                <button
                  type="button"
                  onClick={onClearActiveTopic}
                  title="Remove topic background context"
                  className="text-zinc-400 hover:text-white ml-0.5"
                >
                  ×
                </button>
              )}
            </span>
          )}
          <input
            ref={inputRef}
            aria-label="Message or #command input"
            type="text"
            value={value}
            onChange={(e) => {
              onChange(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            disabled={isSending}
            placeholder={placeholder ?? defaultPlaceholder}
            className="flex-1 bg-transparent text-sm text-white placeholder-zinc-500 focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isSending || !value.trim()}
            className="rounded-xl bg-white hover:bg-zinc-200 disabled:bg-white/[0.06] disabled:text-zinc-600 text-black font-medium px-4 py-2 text-xs transition-all duration-200 shrink-0"
          >
            {isSending ? "..." : "Ask"}
          </button>
        </form>
      </div>
    </div>
  );
};
