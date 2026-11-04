/** AI Provider configuration, privacy boundary disclosures, and full open-format export. */

import React, { useState } from "react";
import type { AISettingsDTO, ExportResultResponse } from "../api/types";

interface SettingsAndOwnershipViewProps {
  settings: AISettingsDTO | undefined;
  onUpdateSettings: (payload: Partial<AISettingsDTO>) => void;
  onValidateProvider: (
    provider: string,
    localUrl: string,
  ) => Promise<{ valid: boolean; message: string; is_remote: boolean }>;
  onExportWorkspace: () => Promise<ExportResultResponse>;
  onReturnToChat: () => void;
}

export const SettingsAndOwnershipView: React.FC<
  SettingsAndOwnershipViewProps
> = ({
  settings,
  onUpdateSettings,
  onValidateProvider,
  onExportWorkspace,
  onReturnToChat,
}) => {
  const [validationMessage, setValidationMessage] = useState<string | null>(
    null,
  );
  const [exportResult, setExportResult] = useState<ExportResultResponse | null>(
    null,
  );

  if (!settings) {
    return (
      <div className="text-xs text-slate-400 p-4">Loading AI settings...</div>
    );
  }

  return (
    <section
      aria-label="Provider Settings and Data Ownership"
      className="space-y-6 max-w-4xl mx-auto"
    >
      <div className="flex items-center justify-between bg-slate-900 border border-slate-800 rounded-lg p-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-100">
            AI Providers, Privacy Boundary & Data Ownership
          </h2>
          <p className="text-xs text-slate-400">
            Your SQLite database is the local source of truth. Hosted model
            calls are strictly opt-in.
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

      {/* Data Transfer Status Banner */}
      <div
        className={`p-3 rounded-lg border text-xs ${
          settings.remote_transfer_active
            ? "bg-amber-950/40 border-amber-700 text-amber-200"
            : "bg-emerald-950/30 border-emerald-800 text-emerald-200"
        }`}
      >
        <div className="font-semibold">
          {settings.remote_transfer_active
            ? "Remote Provider Selected: Selected turn context will be sent to the configured hosted API when consent is enabled."
            : "Local-Only Mode Active: No conversation or knowledge content leaves your machine."}
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-4 text-xs">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
          Task-to-Provider Configuration
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <label className="space-y-1 block">
            <span className="text-slate-400">Conversation Provider</span>
            <select
              value={settings.conversation_provider}
              onChange={(e) =>
                onUpdateSettings({ conversation_provider: e.target.value })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100"
            >
              {settings.providers.map((p) => (
                <option key={p.provider} value={p.provider}>
                  {p.display_name}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1 block">
            <span className="text-slate-400">Extraction Provider</span>
            <select
              value={settings.extraction_provider}
              onChange={(e) =>
                onUpdateSettings({ extraction_provider: e.target.value })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100"
            >
              {settings.providers.map((p) => (
                <option key={p.provider} value={p.provider}>
                  {p.display_name}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1 block">
            <span className="text-slate-400">Embedding Provider</span>
            <select
              value={settings.embedding_provider}
              onChange={(e) =>
                onUpdateSettings({ embedding_provider: e.target.value })
              }
              className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100"
            >
              {settings.providers
                .filter((p) => p.supports_embeddings)
                .map((p) => (
                  <option key={p.provider} value={p.provider}>
                    {p.display_name}
                  </option>
                ))}
            </select>
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-4 pt-2">
          <label className="flex items-center gap-2 text-slate-200">
            <input
              type="checkbox"
              checked={settings.hosted_data_consent}
              onChange={(e) =>
                onUpdateSettings({ hosted_data_consent: e.target.checked })
              }
            />
            <span>
              Allow sending selected prompt & retrieved context to hosted AI
              providers
            </span>
          </label>

          <button
            type="button"
            onClick={async () => {
              const res = await onValidateProvider(
                settings.conversation_provider,
                settings.local_endpoint_url,
              );
              setValidationMessage(res.message);
            }}
            className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200"
          >
            Validate Active Provider
          </button>
        </div>

        {validationMessage && (
          <div className="p-2 rounded bg-slate-950 border border-slate-800 text-slate-300">
            {validationMessage}
          </div>
        )}
      </div>

      {/* Data Portability & Export */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3 text-xs">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
          Open Format Export & Backup
        </h3>
        <p className="text-slate-400">
          Export all conversations, immutable messages, concepts, aliases,
          mentions, explicit annotations, personal states, world claims, user
          relations, suggestions, hypotheses, evidence, and timeline events as a
          portable JSON archive with stable UUIDs.
        </p>
        <button
          type="button"
          onClick={async () => {
            const res = await onExportWorkspace();
            setExportResult(res);
          }}
          className="px-3 py-1.5 rounded bg-emerald-700 hover:bg-emerald-600 text-white font-medium"
        >
          Export Full Workspace JSON
        </button>

        {exportResult && (
          <div className="p-3 rounded bg-slate-950 border border-emerald-800/80 space-y-1 text-slate-200">
            <div className="font-semibold text-emerald-300">
              Export Completed: {exportResult.file_path}
            </div>
            <div className="text-slate-400">
              Exported {exportResult.counts.conversations ?? 0} conversations,{" "}
              {exportResult.counts.messages ?? 0} messages,{" "}
              {exportResult.counts.concepts ?? 0} concepts, and{" "}
              {exportResult.counts.knowledge_events ?? 0} knowledge events.
            </div>
          </div>
        )}
      </div>
    </section>
  );
};
