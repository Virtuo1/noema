/** Evidence-linked concept side panel separating mentions, explicit annotations, candidate signals, world claims, user relations, and pending suggestions. */

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

  return (
    <aside
      aria-label={`Concept Evidence: ${concept.canonical_name}`}
      className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-4 overflow-y-auto max-h-[82vh]"
    >
      <div className="flex items-start justify-between gap-2 border-b border-slate-800 pb-3">
        <div>
          <span className="text-[11px] uppercase tracking-wider text-indigo-400 font-semibold">
            Concept Evidence Ledger
          </span>
          <h3 className="text-lg font-semibold text-slate-100">
            {concept.canonical_name}
          </h3>
          {concept.description && (
            <p className="text-xs text-slate-400 mt-1">{concept.description}</p>
          )}
          {concept.aliases.length > 1 && (
            <p className="text-[11px] text-slate-400 mt-1">
              Aliases: {concept.aliases.join(", ")}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-xs px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
        >
          Close
        </button>
      </div>

      {/* Four Independent Personal Dimensions (No numeric mastery score!) */}
      <div className="bg-slate-950/70 border border-slate-800 rounded p-3 space-y-1.5 text-xs">
        <div className="font-semibold text-slate-300">
          Your Personal Signals (Evidence-Backed)
        </div>
        <div className="grid grid-cols-2 gap-2 pt-1">
          <div className="p-2 rounded bg-slate-900 border border-slate-800">
            <div className="text-slate-400 text-[11px]">Self-Report</div>
            <div className="text-slate-100 font-medium mt-0.5">
              {formatSelfAssessmentLabel(concept.signals)}
            </div>
          </div>
          <div className="p-2 rounded bg-slate-900 border border-slate-800">
            <div className="text-slate-400 text-[11px]">
              Demonstrated Evidence
            </div>
            <div className="text-slate-100 font-medium mt-0.5">
              {formatDemonstrationLabel(concept.signals)}
            </div>
          </div>
        </div>
        <div className="pt-2 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onStartGroundedChat(concept.canonical_name)}
            className="px-2.5 py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-xs"
          >
            Explore "{concept.canonical_name}" in Chat
          </button>
        </div>
      </div>

      {evidence && (
        <>
          {/* Pending AI Suggestions */}
          {evidence.suggestions.filter((s) => s.status === "pending").length >
            0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-amber-400">
                Pending AI Connection Suggestions (Not Yet in Your Map)
              </h4>
              {evidence.suggestions
                .filter((s) => s.status === "pending")
                .map((s) => (
                  <div
                    key={s.id}
                    className="p-3 rounded border border-amber-800/70 bg-amber-950/20 space-y-2 text-xs"
                  >
                    <div className="font-medium text-amber-200">
                      {s.subject_name} —[{s.predicate_label}]→ {s.object_name}
                    </div>
                    <p className="text-slate-300">{s.explanation}</p>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => onAcceptSuggestion(s.id)}
                        className="px-2.5 py-1 rounded bg-emerald-700 hover:bg-emerald-600 text-white"
                      >
                        Accept Connection
                      </button>
                      <button
                        type="button"
                        onClick={() => onRejectSuggestion(s.id)}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200"
                      >
                        Reject
                      </button>
                      <button
                        type="button"
                        onClick={() => onDismissSuggestion(s.id)}
                        className="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-400"
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                ))}
            </div>
          )}

          {/* User-Established Relations */}
          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
              Your Established Connections ({evidence.user_relations.length})
            </h4>
            {evidence.user_relations.length === 0 ? (
              <p className="text-xs text-slate-400">
                No user-established relations yet.
              </p>
            ) : (
              evidence.user_relations.map((rel) => (
                <div
                  key={rel.id}
                  className="p-2.5 rounded border border-emerald-900/60 bg-emerald-950/20 text-xs space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-emerald-200">
                      {rel.subject_name} —[{rel.predicate_label}]→{" "}
                      {rel.object_name}
                    </span>
                    <button
                      type="button"
                      onClick={() => onWithdrawRelation(rel.id)}
                      className="text-[11px] text-slate-400 hover:text-rose-300"
                    >
                      Withdraw
                    </button>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Origin: {rel.origin.replace(/_/g, " ")}
                  </div>
                  {rel.explanation && (
                    <p className="text-slate-300">{rel.explanation}</p>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Provisional World Claims */}
          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-sky-400">
              Sourced World Claims ({evidence.world_claims.length})
            </h4>
            {evidence.world_claims.length === 0 ? (
              <p className="text-xs text-slate-400">
                No domain claims recorded for this concept.
              </p>
            ) : (
              evidence.world_claims.map((wc) => (
                <div
                  key={wc.id}
                  className="p-2.5 rounded border border-sky-900/60 bg-sky-950/20 text-xs space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sky-200">
                      {wc.subject_name} —[{wc.predicate_label}]→{" "}
                      {wc.object_name}
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-800 text-[10px]">
                      {wc.status} ({wc.source_kind.replace(/_/g, " ")})
                    </span>
                  </div>
                  <p className="text-slate-300">{wc.claim_text}</p>
                </div>
              ))
            )}
          </div>

          {/* Candidate Inferred Signals */}
          {evidence.state_signals.filter((s) => s.review_status === "candidate")
            .length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-purple-300">
                Candidate Inferred Evidence (Low Authority Until Confirmed)
              </h4>
              {evidence.state_signals
                .filter((s) => s.review_status === "candidate")
                .map((sig) => (
                  <div
                    key={sig.evidence_id}
                    className="p-2.5 rounded border border-purple-900/60 bg-purple-950/20 text-xs space-y-1.5"
                  >
                    <div className="font-medium text-purple-200">
                      Possible {sig.signal_kind.replace(/_/g, " ")}
                    </div>
                    <blockquote className="text-slate-300 italic border-l-2 border-purple-700 pl-2">
                      "{sig.quote}"
                    </blockquote>
                    {sig.rationale && (
                      <p className="text-[11px] text-slate-400">
                        {sig.rationale}
                      </p>
                    )}
                    <div className="flex gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() =>
                          onReviewSignal(concept.id, sig.evidence_id, "confirm")
                        }
                        className="px-2 py-0.5 rounded bg-purple-700 hover:bg-purple-600 text-white"
                      >
                        Confirm as Evidence
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          onReviewSignal(concept.id, sig.evidence_id, "dismiss")
                        }
                        className="px-2 py-0.5 rounded bg-slate-800 text-slate-300"
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                ))}
            </div>
          )}

          {/* Source Mentions */}
          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Source Message Mentions ({evidence.mentions.length})
            </h4>
            {evidence.mentions.map((m) => (
              <div
                key={m.id}
                className="p-2.5 rounded border border-slate-800 bg-slate-950/80 text-xs space-y-1"
              >
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span>Role: {m.source_role}</span>
                  {m.extraction_model && (
                    <span>Extractor: {m.extraction_model}</span>
                  )}
                </div>
                <p className="text-slate-200 line-clamp-3">"{m.quote}"</p>
                {m.conversation_id && (
                  <button
                    type="button"
                    onClick={() => onJumpToConversation(m.conversation_id!)}
                    className="text-indigo-400 hover:underline text-[11px]"
                  >
                    Open Source Conversation →
                  </button>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {/* Model Correction & Direct User Relation Tools */}
      {otherConcepts.length > 0 && (
        <div className="border-t border-slate-800 pt-3 space-y-3 text-xs">
          <div className="font-semibold text-slate-300">
            Add Direct Personal Connection or Merge Duplicate
          </div>
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <select
                aria-label="Relation predicate"
                value={predicate}
                onChange={(e) => setPredicate(e.target.value)}
                className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200"
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
                className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200"
              >
                <option value="">Select concept...</option>
                {otherConcepts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
            <input
              type="text"
              placeholder="Optional note on why you connect these concepts..."
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200"
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
              Establish Personal Relation
            </button>
          </div>

          <div className="pt-2 border-t border-slate-800/80 flex items-center gap-2">
            <select
              aria-label="Merge duplicate into concept"
              value={mergeTargetId}
              onChange={(e) => setMergeTargetId(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-slate-200"
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
              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200"
            >
              Merge Concept
            </button>
          </div>
        </div>
      )}
    </aside>
  );
};
