/**
 * Full-height centered Topic Context Card aligned above the bottom question box.
 * Clean, uncluttered view of saved notes and excerpts for the selected topic.
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
  const cleanDescription = (concept?.description ?? "").replace(
    /^\[[^\]]+\]\s*/,
    "",
  );

  const tags = Array.from(
    new Set([
      ...(graphNode?.tags ?? []),
      ...(evidence?.annotations.map((a) => a.tag) ?? []),
    ]),
  );

  const connectedTopics = React.useMemo(() => {
    if (!concept || !evidence) return [];
    const seen = new Set<string>();
    const list: { id: string; name: string }[] = [];

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
        list.push({ id: otherId, name: otherName });
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
        list.push({ id: otherId, name: otherName });
      }
    }
    return list;
  }, [concept, evidence]);

  if (!concept) {
    return (
      <div className="w-full max-w-2xl h-full rounded-3xl bg-zinc-950/90 backdrop-blur-2xl border border-white/[0.08] p-8 shadow-[0_24px_80px_rgba(0,0,0,0.95)] flex items-center justify-center animate-fade-in">
        <span className="text-xs text-zinc-500 animate-pulse">
          Loading topic...
        </span>
      </div>
    );
  }

  return (
    <aside
      aria-label="Topic context card"
      className="w-full max-w-2xl h-full flex flex-col rounded-3xl bg-zinc-950/90 backdrop-blur-2xl border border-white/[0.08] shadow-[0_24px_80px_rgba(0,0,0,0.95)] overflow-hidden animate-fade-in"
    >
      {/* Clean Header */}
      <div className="px-7 pt-6 pb-5 border-b border-white/[0.06] flex items-start justify-between gap-4">
        <div className="space-y-2 min-w-0">
          <div className="flex items-center flex-wrap gap-2">
            <h2 className="text-xl font-semibold text-white tracking-tight">
              {concept.canonical_name}
            </h2>
            {tags.map((t) => (
              <span
                key={t}
                className={`text-[11px] font-mono px-2 py-0.5 rounded-md border ${getTagBadgeClasses(
                  t,
                )}`}
              >
                #{t}
              </span>
            ))}
          </div>
          {cleanDescription && (
            <p className="text-sm text-zinc-400 leading-relaxed">
              {cleanDescription}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={onClose}
          title="Close (Esc)"
          className="shrink-0 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.06] px-2.5 py-1 text-xs text-zinc-400 hover:text-white transition-colors"
        >
          ✕
        </button>
      </div>

      {/* Scrollable Notes & Context */}
      <div className="flex-1 overflow-y-auto px-7 py-6 space-y-6">
        {!evidence || evidence.mentions.length === 0 ? (
          <p className="text-sm text-zinc-500 py-8 text-center">
            No saved notes yet. Ask a question below to explore{" "}
            {concept.canonical_name}.
          </p>
        ) : (
          <div className="space-y-3.5">
            {evidence.mentions.map((item) => (
              <div
                key={item.id}
                className="rounded-2xl bg-white/[0.03] border border-white/[0.05] p-4 space-y-2.5 hover:border-white/[0.1] transition-colors"
              >
                <p className="text-sm text-zinc-200 leading-relaxed whitespace-pre-wrap">
                  {item.quote}
                </p>
                {(item.annotation_tag || item.conversation_id) && (
                  <div className="flex items-center justify-between pt-1 text-xs">
                    <div>
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
                        className="text-zinc-400 hover:text-white transition-colors"
                      >
                        Open chat →
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {connectedTopics.length > 0 && (
          <div className="pt-2 border-t border-white/[0.05]">
            <div className="flex flex-wrap gap-1.5 pt-3">
              {connectedTopics.map((ct) => (
                <button
                  key={ct.id}
                  type="button"
                  onClick={() => onSelectRelatedConcept?.(ct.id)}
                  className="text-xs px-3 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.09] border border-white/[0.06] text-zinc-300 hover:text-white transition-colors"
                >
                  {ct.name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
