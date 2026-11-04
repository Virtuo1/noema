/** Clean slide-over concept drawer showing personal status, connections, and source chat quotes. */

import React, { useState } from "react";
import type {
  ConceptDetailDTO,
  ConceptEvidenceResponse,
  GraphNodeDTO,
} from "../api/types";
import {
  formatDemonstrationLabel,
  formatSelfAssessmentLabel,
} from "./GraphView";

interface ConceptInspectorProps {
  concept: ConceptDetailDTO | undefined;
  evidence: ConceptEvidenceResponse | undefined;
  allConcepts: GraphNodeDTO[];
  onClose: () => void;
  onJumpToConversation: (conversationId: string) => void;
  onStartGroundedChat: (conceptName: string) => void;
  onAcceptSuggestion: (suggestionId: string) => void;
  onRejectSuggestion: (suggestionId: string) => void;
  onDismissSuggestion: (suggestionId: string) => void;
  onWithdrawRelation: (relationId: string) => void;
  onReviewSignal: (
    conceptId: string,
    evidenceId: string,
    action: "confirm" | "dismiss",
  ) => void;
  onCreateRelation: (
    sourceId: string,
    targetId: string,
    predicate: string,
    explanation: string,
  ) => void;
  onMergeConcept: (sourceId: string, targetId: string) => void;
}

export const ConceptInspector: React.FC<ConceptInspectorProps> = ({
  concept,
  evidence,
  allConcepts,
  onClose,
  onJumpToConversation,
  onStartGroundedChat,
  onAcceptSuggestion,
  onRejectSuggestion,
  onDismissSuggestion,
  onWithdrawRelation,
  onReviewSignal,
  onCreateRelation,
  onMergeConcept,
}) => {
  const [targetConceptId, setTargetConceptId] = useState("");
  const [predicate, setPredicate] = useState("contrasts_with");
  const [explanation, setExplanation] = useState("");
  const [mergeTargetId, setMergeTargetId] = useState("");

  if (!concept) return null;

  const otherConcepts = allConcepts.filter((c) => c.id !== concept.id);
  const pendingSuggestions =
    evidence?.suggestions.filter((s) => s.status === "pending") ?? [];
  const candidateSignals =
    evidence?.state_signals.filter((s) => s.review_status === "candidate") ??
    [];

  return (
    <aside
      aria-label={`Concept Evidence: ${concept.canonical_name}`}
      className="fixed inset-y-0 right-0 z-40 w-full max-w-md bg-zinc-950 border-l border-zinc-800 shadow-2xl flex flex-col"
    >
      {/* Header */}
      <div className="px-5 py-4 border-b border-zinc-800/80 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-zinc-100">
            {concept.canonical_name}
          </h3>
          {concept.description && (
            <p className="text-xs text-zinc-400 mt-1">{concept.description}</p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="px-2.5 py-1 rounded-md bg-zinc-900 hover:bg-zinc-800 text-xs text-zinc-300"
        >
          ✕
        </button>
      </div>

      {/* Scrollable Body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6 text-xs">
        {/* Status & Quick Chat Action */}
        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-3.5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="text-[11px] text-zinc-400">Your status</div>
              <div className="text-zinc-100 font-medium mt-0.5">
                {formatSelfAssessmentLabel(concept.signals)}
              </div>
              <div className="text-[11px] text-zinc-400 mt-0.5">
                {formatDemonstrationLabel(concept.signals)}
              </div>
            </div>
            <button
              type="button"
              onClick={() => onStartGroundedChat(concept.canonical_name)}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium"
            >
              Ask about this →
            </button>
          </div>
        </div>

        {/* Pending AI Suggestions */}
        {pendingSuggestions.length > 0 && (
          <div className="space-y-2">
            <h4 className="font-medium text-amber-300">
              Suggested Connections
            </h4>
            {pendingSuggestions.map((s) => (
              <div
                key={s.id}
                className="p-3 rounded-lg border border-amber-800/60 bg-amber-950/20 space-y-2"
              >
                <div className="font-medium text-zinc-100">
                  {s.subject_name}{" "}
                  <span className="text-amber-300">
                    → {s.predicate_label} →
                  </span>{" "}
                  {s.object_name}
                </div>
                <p className="text-zinc-300">{s.explanation}</p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onAcceptSuggestion(s.id)}
                    className="px-2.5 py-1 rounded bg-emerald-700 hover:bg-emerald-600 text-white"
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    onClick={() => onRejectSuggestion(s.id)}
                    className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
                  >
                    Ignore
                  </button>
                  <button
                    type="button"
                    onClick={() => onDismissSuggestion(s.id)}
                    className="px-2 py-1 text-zinc-400 hover:text-zinc-200"
                  >
                    Later
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Candidate Signals */}
        {candidateSignals.length > 0 && (
          <div className="space-y-2">
            <h4 className="font-medium text-purple-300">
              Noticed in your messages
            </h4>
            {candidateSignals.map((sig) => (
              <div
                key={sig.evidence_id}
                className="p-3 rounded-lg border border-purple-900/60 bg-purple-950/20 space-y-2"
              >
                <blockquote className="text-zinc-200 italic border-l-2 border-purple-600 pl-2">
                  "{sig.quote}"
                </blockquote>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      onReviewSignal(concept.id, sig.evidence_id, "confirm")
                    }
                    className="px-2.5 py-1 rounded bg-purple-700 hover:bg-purple-600 text-white"
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      onReviewSignal(concept.id, sig.evidence_id, "dismiss")
                    }
                    className="px-2.5 py-1 rounded bg-zinc-800 text-zinc-300"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Established Connections */}
        {evidence && evidence.user_relations.length > 0 && (
          <div className="space-y-2">
            <h4 className="font-medium text-zinc-300">Your Connections</h4>
            {evidence.user_relations.map((rel) => (
              <div
                key={rel.id}
                className="p-2.5 rounded-lg border border-zinc-800 bg-zinc-900/50 flex items-center justify-between gap-2"
              >
                <span className="text-zinc-200">
                  {rel.subject_name}{" "}
                  <span className="text-emerald-400">
                    → {rel.predicate_label} →
                  </span>{" "}
                  {rel.object_name}
                </span>
                <button
                  type="button"
                  onClick={() => onWithdrawRelation(rel.id)}
                  className="text-[11px] text-zinc-500 hover:text-rose-300"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Sourced Quotes from Chats */}
        {evidence && evidence.mentions.length > 0 && (
          <div className="space-y-2">
            <h4 className="font-medium text-zinc-300">
              From Your Conversations ({evidence.mentions.length})
            </h4>
            {evidence.mentions.map((m) => (
              <div
                key={m.id}
                className="p-3 rounded-lg border border-zinc-800/80 bg-zinc-900/40 space-y-1.5"
              >
                <p className="text-zinc-200 line-clamp-3">"{m.quote}"</p>
                {m.conversation_id && (
                  <button
                    type="button"
                    onClick={() => onJumpToConversation(m.conversation_id!)}
                    className="text-indigo-400 hover:underline text-[11px]"
                  >
                    Open chat →
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Collapsed Manual Link / Merge Tools */}
        {otherConcepts.length > 0 && (
          <details className="border-t border-zinc-800/80 pt-3">
            <summary className="cursor-pointer text-zinc-400 hover:text-zinc-200 font-medium">
              Manual link or merge duplicate...
            </summary>
            <div className="pt-3 space-y-3">
              <div className="space-y-2">
                <div className="flex gap-2">
                  <select
                    aria-label="Relation predicate"
                    value={predicate}
                    onChange={(e) => setPredicate(e.target.value)}
                    className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-zinc-200"
                  >
                    <option value="contrasts_with">contrasts with</option>
                    <option value="depends_on">depends on</option>
                    <option value="uses">uses</option>
                    <option value="analogous_to">is analogous to</option>
                    <option value="part_of">is part of</option>
                    <option value="related_to">relates to</option>
                  </select>
                  <select
                    aria-label="Target concept for relation"
                    value={targetConceptId}
                    onChange={(e) => setTargetConceptId(e.target.value)}
                    className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-zinc-200"
                  >
                    <option value="">Choose concept...</option>
                    {otherConcepts.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>
                <input
                  type="text"
                  placeholder="Optional note..."
                  value={explanation}
                  onChange={(e) => setExplanation(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-zinc-200"
                />
                <button
                  type="button"
                  disabled={!targetConceptId}
                  onClick={() => {
                    if (targetConceptId) {
                      onCreateRelation(
                        concept.id,
                        targetConceptId,
                        predicate,
                        explanation,
                      );
                      setExplanation("");
                    }
                  }}
                  className="px-2.5 py-1 rounded bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 text-white"
                >
                  Save Connection
                </button>
              </div>

              <div className="pt-2 border-t border-zinc-800/60 flex items-center gap-2">
                <select
                  aria-label="Merge duplicate into concept"
                  value={mergeTargetId}
                  onChange={(e) => setMergeTargetId(e.target.value)}
                  className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-zinc-200"
                >
                  <option value="">Merge duplicate into...</option>
                  {otherConcepts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={!mergeTargetId}
                  onClick={() => {
                    if (mergeTargetId) {
                      onMergeConcept(concept.id, mergeTargetId);
                    }
                  }}
                  className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 text-zinc-200"
                >
                  Merge
                </button>
              </div>
            </div>
          </details>
        )}
      </div>
    </aside>
  );
};
