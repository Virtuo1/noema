/** Modular floating frosted-glass question bar with inline #tag autocomplete popup. */

import React, { useMemo, useRef, useState } from "react";
import type { AnnotationTag } from "../api/types";

export interface TagOption {
  tag: AnnotationTag;
  label: string;
  description: string;
}

export const AVAILABLE_TAGS: TagOption[] = [
  {
    tag: "aha",
    label: "#aha",
    description: "Mark a breakthrough or clear realization",
  },
  {
    tag: "confused",
    label: "#confused",
    description: "Flag something unclear or puzzling",
  },
  {
    tag: "question",
    label: "#question",
    description: "Save an open question to explore further",
  },
  {
    tag: "important",
    label: "#important",
    description: "Highlight a core idea worth remembering",
  },
  {
    tag: "connection",
    label: "#connection",
    description: "Note a link between two topics",
  },
  {
    tag: "hypothesis",
    label: "#hypothesis",
    description: "Record a tentative mental model or theory",
  },
  {
    tag: "revisit",
    label: "#revisit",
    description: "Bookmark this topic to review later",
  },
];

interface FloatingComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  isSending: boolean;
  activeSurface: "graph" | "chat";
  sidebarOpen: boolean;
  placeholder?: string;
}

export const FloatingComposer: React.FC<FloatingComposerProps> = ({
  value,
  onChange,
  onSubmit,
  isSending,
  activeSurface,
  sidebarOpen,
  placeholder,
}) => {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Detect if the user is currently typing a #tag token at the end or cursor
  const activeTagMatch = useMemo(() => {
    const match = /(?:^|\s)#([a-zA-Z]*)$/.exec(value);
    if (!match) return null;
    const query = (match[1] ?? "").toLowerCase();
    const matches = AVAILABLE_TAGS.filter((item) =>
      item.tag.toLowerCase().startsWith(query),
    );
    // Hide popup if exact tag is already completed and followed by space, or if no matches
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

  const defaultPlaceholder =
    activeSurface === "graph"
      ? "Ask anything to transition into chat... (type # for tags)"
      : "Ask a follow-up or save a thought with #aha, #confused, #important...";

  return (
    <div
      className={`fixed bottom-6 right-6 z-30 transition-all duration-300 pointer-events-none flex justify-center ${
        sidebarOpen ? "left-6 md:left-[21rem]" : "left-6"
      }`}
    >
      <div className="w-full max-w-2xl pointer-events-auto relative">
        {/* #Tag Autocomplete Popup */}
        {activeTagMatch && (
          <div
            role="listbox"
            aria-label="Tag suggestions"
            className="mb-2.5 rounded-2xl bg-black/85 backdrop-blur-2xl border border-white/15 shadow-2xl overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-150"
          >
            <div className="px-3.5 py-2 border-b border-white/10 flex items-center justify-between text-[11px] text-zinc-400">
              <span className="font-medium text-zinc-200">Save with tag</span>
              <span>Tab to complete · click to insert</span>
            </div>
            <div className="max-h-56 overflow-y-auto divide-y divide-white/5">
              {activeTagMatch.matches.map((item, idx) => {
                const isSelected = idx === selectedIndex;
                return (
                  <button
                    key={item.tag}
                    type="button"
                    onClick={() => applyTagSuggestion(item.tag)}
                    className={`w-full text-left px-3.5 py-2.5 flex items-center justify-between gap-3 transition-colors ${
                      isSelected
                        ? "bg-white/10 text-white"
                        : "text-zinc-300 hover:bg-white/5"
                    }`}
                  >
                    <span className="font-mono text-xs font-semibold text-white">
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
          className="flex items-center gap-2 rounded-2xl bg-black/75 backdrop-blur-2xl border border-white/15 px-4 py-2.5 shadow-[0_12px_40px_rgba(0,0,0,0.85)] focus-within:border-white/35 transition-colors"
        >
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
            className="rounded-xl bg-white hover:bg-zinc-200 disabled:bg-white/10 disabled:text-zinc-600 text-black font-medium px-4 py-2 text-xs transition-all shrink-0"
          >
            {isSending ? "..." : "Ask"}
          </button>
        </form>
      </div>
    </div>
  );
};
