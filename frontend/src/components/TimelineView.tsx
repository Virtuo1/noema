/** Append-only knowledge event ledger showing temporal transitions and revisions. */

import React from "react";
import type { KnowledgeEventDTO } from "../api/types";

interface TimelineViewProps {
  events: KnowledgeEventDTO[];
  onReturnToChat: () => void;
  onSelectConcept: (conceptId: string) => void;
  onJumpToConversation: (conversationId: string) => void;
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
      className="space-y-4 max-w-4xl mx-auto"
    >
      <div className="flex items-center justify-between bg-slate-900 border border-slate-800 rounded-lg p-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-100">
            Knowledge Timeline & Revision Ledger
          </h2>
          <p className="text-xs text-slate-400">
            Preserves how your personal model changed over time—including first
            encounters, #aha self-reports, confusions, accepted/rejected
            suggestions, and revisions.
          </p>
        </div>
        <button
          type="button"
          onClick={onReturnToChat}
          className="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white"
        >
          ← Return to Conversation
        </button>
      </div>

      {events.length === 0 ? (
        <div className="p-6 text-center text-xs text-slate-400 bg-slate-900/50 border border-slate-800 rounded-lg">
          No knowledge events recorded yet. Start a conversation or annotate a
          passage with #aha or #confused.
        </div>
      ) : (
        <ol className="space-y-2.5">
          {events.map((ev) => {
            const beforeVal = ev.payload.before as string | undefined;
            const afterVal = ev.payload.after as string | undefined;
            const tagVal = ev.payload.tag as string | undefined;
            return (
              <li
                key={ev.id}
                className="p-3 rounded-lg border border-slate-800 bg-slate-900/70 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
              >
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-indigo-300 font-mono text-[11px]">
                      {ev.event_type}
                    </span>
                    {ev.concept_name && ev.concept_id && (
                      <button
                        type="button"
                        onClick={() => onSelectConcept(ev.concept_id!)}
                        className="font-semibold text-slate-100 hover:underline"
                      >
                        {ev.concept_name}
                      </button>
                    )}
                    {tagVal && (
                      <span className="px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                        #{tagVal}
                      </span>
                    )}
                  </div>
                  {beforeVal !== undefined && afterVal !== undefined && (
                    <div className="text-slate-300">
                      Transition:{" "}
                      <span className="text-slate-400">{beforeVal}</span> →{" "}
                      <span className="text-amber-300 font-medium">
                        {afterVal}
                      </span>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-3 text-[11px] text-slate-400 shrink-0">
                  <span>{new Date(ev.occurred_at).toLocaleString()}</span>
                  {ev.conversation_id && (
                    <button
                      type="button"
                      onClick={() => onJumpToConversation(ev.conversation_id!)}
                      className="text-indigo-400 hover:underline"
                    >
                      Source Chat →
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
