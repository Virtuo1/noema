/**
 * Centered Topic Context Card aligned directly above the bottom question box.
 * Shows saved notes, quotes, colored #tags, and connected topics while serving as
 * silent background context for any question asked in the question box below.
 */

import React from "react";
import type {
  ConceptDetailDTO,
  ConceptEvidenceResponse,
  GraphNodeDTO,
} from "../api/types";
import { getTagBadgeClasses } from "./FloatingComposer";

interface ConceptInspectorProps {
  concept: ConceptDetailDTO | undefined;
  evidence: ConceptEvidenceResponse | undefined;
  allConcepts: GraphNodeDTO[];
  onClose: () => void;
  onJumpToConversation: (conversationId: string) => void;
  onSelectRelatedConcept?: (conceptId: string) => void;
  onStartGroundedChat?: (conceptName: string) => void;
  onAcceptSuggestion?: (suggestionId: string) => void;
  onRejectSuggestion?: (suggestionId: string) => void;
  onDismissSuggestion?: (suggestionId: string) => void;
  onWithdrawRelation?: (relationId: string) => void;
  onReviewSignal?: (
    conceptId: string,
    evidenceId: string,
    action: "confirm" | "dismiss",
  ) => void;
  onCreateRelation?: (
    sourceId: string,
    targetId: string,
    predicate: string,
    explanation: string,
  ) => void;
  onMergeConcept?: (sourceId: string, targetId: string) => void;
}

export const ConceptInspector: React.FC<ConceptInspectorProps> = ({
  concept,
  evidence,
  allConcepts,
  onClose,
  onJumpToConversation,
  onSelectRelatedConcept,
}) => {
  const graphNode = allConcepts.find((n) => n.id === concept?.id);
  const category = graphNode?.category || "General";
  const cleanDescription = (concept?.description ?? "").replace(
    /^\[[^\]]+\]\s*/,
    "",
  );

  // Collect unique tags across annotations
  const tags = Array.from(
    new Set([
      ...(graphNode?.tags ?? []),
      ...(evidence?.annotations.map((a) => a.tag) ?? []),
    ]),
  );

  // Collect connected topics from user relations and world claims
  const connectedTopics = React.useMemo(() => {
    if (!concept || !evidence) return [];
    const seen = new Set<string>();
    const list: { id: string; name: string; relation: string }[] = [];

    for (const rel of evidence.user_relations) {
      const otherId =
        rel.subject_concept_id === concept.id
          ? rel.object_concept_id
          : rel.subject_concept_id;
      const otherName =
        rel.subject_concept_id === concept.id
          ? rel.object_name
          : rel.subject_name;
      if (!seen.has(otherId)) {
        seen.add(otherId);
        list.push({
          id: otherId,
          name: otherName,
          relation: rel.predicate_label,
        });
      }
    }
    for (const wc of evidence.world_claims) {
      const otherId =
        wc.subject_concept_id === concept.id
          ? wc.object_concept_id
          : wc.subject_concept_id;
      const otherName =
        wc.subject_concept_id === concept.id ? wc.object_name : wc.subject_name;
      if (!seen.has(otherId)) {
        seen.add(otherId);
        list.push({
          id: otherId,
          name: otherName,
          relation: wc.predicate_label,
        });
      }
    }
    return list;
  }, [concept, evidence]);

  if (!concept) {
    return (
      <div className="w-full max-w-2xl rounded-3xl bg-zinc-950/90 backdrop-blur-2xl border border-white/[0.08] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.95)] animate-fade-in">
        <div className="flex items-center justify-between">
          <span className="text-xs text-zinc-400 animate-pulse">
            Loading topic notes...
          </span>
          <button
            type="button"
            onClick={onClose}
            className="text-xs text-zinc-500 hover:text-white px-2 py-1 rounded-lg"
          >
            Esc
          </button>
        </div>
      </div>
    );
  }

  return (
    <aside
      aria-label="Topic context card"
      className="w-full max-w-2xl max-h-[58vh] flex flex-col rounded-3xl bg-zinc-950/90 backdrop-blur-2xl border border-white/[0.08] shadow-[0_24px_80px_rgba(0,0,0,0.95)] overflow-hidden animate-fade-in"
    >
      {/* Header */}
      <div className="px-6 pt-5 pb-4 border-b border-white/[0.06] flex items-start justify-between gap-4">
        <div className="space-y-1.5 min-w-0">
          <div className="flex items-center flex-wrap gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-md bg-white/[0.06] text-zinc-300 border border-white/[0.06]">
              {category}
            </span>
            {tags.map((t) => (
              <span
                key={t}
                className={`text-[10px] font-mono px-2 py-0.5 rounded-md border ${getTagBadgeClasses(
                  t,
                )}`}
              >
                #{t}
              </span>
            ))}
          </div>
          <h2 className="text-lg font-semibold text-white tracking-tight truncate">
            {concept.canonical_name}
          </h2>
          {cleanDescription && (
            <p className="text-xs text-zinc-400 leading-relaxed">
              {cleanDescription}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={onClose}
          title="Close (Esc)"
          className="shrink-0 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.06] px-2.5 py-1 text-[11px] text-zinc-400 hover:text-white transition-colors"
        >
          Esc ✕
        </button>
      </div>

      {/* Scrollable Saved Notes & Context */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
        {/* Saved Notes & Excerpts */}
        <div>
          <div className="flex items-center justify-between mb-2.5">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
              Saved Notes & Excerpts ({evidence?.mentions.length ?? 0})
            </h3>
          </div>

          {!evidence || evidence.mentions.length === 0 ? (
            <p className="text-xs text-zinc-500 py-2">
              No saved excerpts yet. Ask a question below to explore{" "}
              {concept.canonical_name}.
            </p>
          ) : (
            <div className="space-y-2.5">
              {evidence.mentions.map((item) => (
                <div
                  key={item.id}
                  className="rounded-2xl bg-white/[0.03] border border-white/[0.05] p-3.5 space-y-2 hover:border-white/[0.1] transition-colors"
                >
                  <p className="text-xs text-zinc-200 leading-relaxed whitespace-pre-wrap">
                    “{item.quote}”
                  </p>
                  <div className="flex items-center justify-between text-[11px] text-zinc-500">
                    <div className="flex items-center gap-2">
                      <span>
                        {item.source_role === "user" ? "Your note" : "AI note"}
                      </span>
                      {item.annotation_tag && (
                        <span
                          className={`font-mono text-[10px] px-1.5 py-0.5 rounded border ${getTagBadgeClasses(
                            item.annotation_tag,
                          )}`}
                        >
                          #{item.annotation_tag}
                        </span>
                      )}
                    </div>
                    {item.conversation_id && (
                      <button
                        type="button"
                        onClick={() =>
                          onJumpToConversation(item.conversation_id!)
                        }
                        className="text-zinc-300 hover:text-white font-medium transition-colors"
                      >
                        Open chat →
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Connected Topics */}
        {connectedTopics.length > 0 && (
          <div>
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400 mb-2">
              Connected Topics
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {connectedTopics.map((ct) => (
                <button
                  key={ct.id}
                  type="button"
                  onClick={() => onSelectRelatedConcept?.(ct.id)}
                  className="text-xs px-3 py-1 rounded-xl bg-white/[0.04] hover:bg-white/[0.09] border border-white/[0.06] text-zinc-200 transition-colors"
                >
                  {ct.name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Subtle Footer explaining background context behavior */}
      <div className="px-6 py-2.5 border-t border-white/[0.05] bg-black/40 flex items-center justify-between text-[11px] text-zinc-500">
        <span className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
          Used as silent background context when you ask below
        </span>
        <span>Press Esc to close</span>
      </div>
    </aside>
  );
};
