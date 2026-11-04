/** Clean, human-readable knowledge activity timeline. */

import React from "react";
import type { KnowledgeEventDTO } from "../api/types";

interface TimelineViewProps {
  events: KnowledgeEventDTO[];
  onReturnToChat: () => void;
  onSelectConcept: (conceptId: string) => void;
  onJumpToConversation: (conversationId: string) => void;
}

function formatReadableEvent(ev: KnowledgeEventDTO): {
  icon: string;
  summary: string;
  detail?: string;
} {
  const name = ev.concept_name || "an idea";
  const tag = ev.payload.tag as string | undefined;
  const after = ev.payload.after as string | undefined;

  switch (ev.event_type) {
    case "concept_first_encountered":
      return {
        icon: "🌱",
        summary: `First encountered ${name}`,
      };
    case "concept_explored":
      return {
        icon: "💬",
        summary: `Explored ${name} in conversation`,
      };
    case "self_assessment_changed":
      if (after === "self_reports_understanding") {
        return {
          icon: "💡",
          summary: `Marked ${name} as an Aha moment`,
        };
      }
      if (after === "confused") {
        return {
          icon: "🤔",
          summary: `Marked ${name} as Confused`,
        };
      }
      return {
        icon: "📝",
        summary: `Updated note on ${name}`,
      };
    case "annotation_added":
      return {
        icon: tag === "aha" ? "💡" : tag === "confused" ? "🤔" : "🔖",
        summary: `Tagged message with #${tag ?? "note"}`,
      };
    case "suggestion_accepted":
      return {
        icon: "🔗",
        summary: `Accepted connection involving ${name}`,
      };
    case "suggestion_rejected":
      return {
        icon: "✕",
        summary: `Ignored suggested link for ${name}`,
      };
    case "user_relation_created":
      return {
        icon: "🔗",
        summary: `Connected ${name} in your map`,
      };
    case "demonstration_evidence_recorded":
      return {
        icon: "✨",
        summary: `Explained ${name} in your own words`,
      };
    default:
      return {
        icon: "•",
        summary: `Updated ${name}`,
      };
  }
}

export const TimelineView: React.FC<TimelineViewProps> = ({
  events,
  onReturnToChat,
  onSelectConcept,
  onJumpToConversation,
}) => {
  return (
    <section
      aria-label="Knowledge Event History"
      className="max-w-2xl mx-auto py-6 px-4 space-y-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">
            Knowledge Timeline & Revision Ledger
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            How your ideas and connections have evolved over time.
          </p>
        </div>
        <button
          type="button"
          onClick={onReturnToChat}
          className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200 transition"
        >
          ← Return to Conversation
        </button>
      </div>

      {events.length === 0 ? (
        <div className="p-10 text-center text-sm text-zinc-400 bg-zinc-900/40 border border-zinc-800/80 rounded-xl">
          No activity yet. Start chatting and your key concepts and moments will
          appear here automatically.
        </div>
      ) : (
        <ol className="space-y-2.5">
          {events.map((ev) => {
            const formatted = formatReadableEvent(ev);
            return (
              <li
                key={ev.id}
                className="p-3.5 rounded-xl border border-zinc-800/80 bg-zinc-900/50 flex items-center justify-between gap-3 text-xs"
              >
                <div className="flex items-center gap-3">
                  <span className="text-base select-none">
                    {formatted.icon}
                  </span>
                  <div>
                    <div className="text-zinc-100 font-medium">
                      {formatted.summary}
                    </div>
                    <div className="text-[11px] text-zinc-500 mt-0.5">
                      {new Date(ev.occurred_at).toLocaleString()}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {ev.concept_id && (
                    <button
                      type="button"
                      onClick={() => onSelectConcept(ev.concept_id!)}
                      className="px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
                    >
                      Inspect
                    </button>
                  )}
                  {ev.conversation_id && (
                    <button
                      type="button"
                      onClick={() => onJumpToConversation(ev.conversation_id!)}
                      className="px-2.5 py-1 rounded-md text-indigo-400 hover:bg-zinc-800"
                    >
                      Chat →
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
};
