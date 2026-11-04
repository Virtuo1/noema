/** Clean in-UI API connection, two-model setup (Main Chat + Small Background Organizer), and open data export. */

import React, { useEffect, useState } from "react";
import type {
  AISettingsDTO,
  ExportResultResponse,
  UpdateAISettingsPayload,
} from "../api/types";

interface SettingsAndOwnershipViewProps {
  settings: AISettingsDTO | undefined;
  onUpdateSettings: (payload: UpdateAISettingsPayload) => Promise<void>;
  onValidateProvider: (
    provider: string,
    localUrl: string,
    apiKey?: string,
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
  const [selectedProvider, setSelectedProvider] =
    useState<string>("local_heuristic");
  const [chatModel, setChatModel] = useState<string>("");
  const [organizerProvider, setOrganizerProvider] =
    useState<string>("local_heuristic");
  const [organizerModel, setOrganizerModel] = useState<string>("");
  const [localUrl, setLocalUrl] = useState<string>("http://127.0.0.1:11434/v1");
  const [apiKeyInput, setApiKeyInput] = useState<string>("");
  const [hostedConsent, setHostedConsent] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{
    tone: "ok" | "warn";
    text: string;
  } | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [exportResult, setExportResult] = useState<ExportResultResponse | null>(
    null,
  );

  useEffect(() => {
    if (!settings) return;
    setSelectedProvider(settings.conversation_provider);
    setChatModel(settings.conversation_model);
    setOrganizerProvider(settings.extraction_provider);
    setOrganizerModel(settings.extraction_model);
    setLocalUrl(settings.local_endpoint_url);
    setHostedConsent(settings.hosted_data_consent);
  }, [settings]);

  if (!settings) {
    return (
      <div className="text-sm text-zinc-400 p-8 max-w-2xl mx-auto">
        Loading settings...
      </div>
    );
  }

  const activeProviderInfo = settings.providers.find(
    (p) => p.provider === selectedProvider,
  );
  const organizerProviderInfo = settings.providers.find(
    (p) => p.provider === organizerProvider,
  );

  const handleSelectProvider = (providerId: string) => {
    setSelectedProvider(providerId);
    setOrganizerProvider(providerId);
    const info = settings.providers.find((p) => p.provider === providerId);
    if (info) {
      if (info.recommended_chat_models.length > 0) {
        setChatModel(info.recommended_chat_models[0]);
      }
      if (info.recommended_small_models.length > 0) {
        setOrganizerModel(info.recommended_small_models[0]);
      }
      if (info.is_remote) {
        setHostedConsent(true);
      }
    }
    setApiKeyInput("");
    setFeedback(null);
  };

  const handleSaveAndTest = async () => {
    setIsSaving(true);
    setFeedback(null);
    try {
      const apiKeysPayload: Record<string, string> = {};
      if (apiKeyInput.trim() && activeProviderInfo?.is_remote) {
        apiKeysPayload[selectedProvider] = apiKeyInput.trim();
      }

      const nextConsent = activeProviderInfo?.is_remote ? true : hostedConsent;

      await onUpdateSettings({
        conversation_provider: selectedProvider,
        conversation_model: chatModel.trim(),
        extraction_provider: organizerProvider,
        extraction_model: organizerModel.trim(),
        local_endpoint_url: localUrl.trim(),
        hosted_data_consent: nextConsent,
        ...(Object.keys(apiKeysPayload).length > 0
          ? { api_keys: apiKeysPayload }
          : {}),
      });

      const validation = await onValidateProvider(
        selectedProvider,
        localUrl.trim(),
        apiKeyInput.trim() || undefined,
      );

      setApiKeyInput("");
      setFeedback({
        tone: validation.valid ? "ok" : "warn",
        text: validation.valid
          ? `Saved! ${validation.message}`
          : `Saved settings, but check connection: ${validation.message}`,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section
      aria-label="Provider Settings and Data Ownership"
      className="max-w-2xl mx-auto py-6 px-4 space-y-8"
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">
            AI Models & API Keys
          </h2>
          <p className="text-sm text-zinc-400 mt-0.5">
            Connect an API or local server, and choose your main chat model +
            small background organizer.
          </p>
        </div>
        <button
          type="button"
          onClick={onReturnToChat}
          className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200 transition"
        >
          ← Back to Chat
        </button>
      </div>

      {/* Step 1: Choose Provider & Connect Key */}
      <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 space-y-5">
        <div>
          <h3 className="text-sm font-medium text-zinc-100">
            1. Choose AI Provider
          </h3>
          <p className="text-xs text-zinc-400 mt-0.5">
            Keys are saved locally on your machine with strict file permissions
            and never stored in plaintext database rows.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {settings.providers.map((p) => {
            const isSelected = selectedProvider === p.provider;
            return (
              <button
                key={p.provider}
                type="button"
                onClick={() => handleSelectProvider(p.provider)}
                className={`text-left p-3 rounded-lg border transition flex items-center justify-between ${
                  isSelected
                    ? "bg-indigo-950/40 border-indigo-500 text-zinc-100"
                    : "bg-zinc-950/60 border-zinc-800/80 text-zinc-300 hover:border-zinc-700"
                }`}
              >
                <div>
                  <div className="text-xs font-medium">{p.display_name}</div>
                  <div className="text-[11px] text-zinc-400 mt-0.5">
                    {p.is_remote ? "Cloud API" : "100% On-Device"}
                  </div>
                </div>
                {p.is_remote && p.has_configured_secret && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800">
                    Key saved
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Direct API Key Input inside UI */}
        {activeProviderInfo?.is_remote && (
          <div className="space-y-2 pt-1">
            <div className="flex items-center justify-between text-xs">
              <label
                htmlFor="provider-api-key-input"
                className="font-medium text-zinc-200"
              >
                {activeProviderInfo.display_name} API Key
              </label>
              {activeProviderInfo.has_configured_secret && (
                <span className="text-emerald-400">
                  Configured ({activeProviderInfo.masked_secret_hint})
                </span>
              )}
            </div>
            <input
              id="provider-api-key-input"
              type="password"
              placeholder={
                activeProviderInfo.has_configured_secret
                  ? "Enter a new key to replace saved key..."
                  : `Paste your ${activeProviderInfo.display_name} API key...`
              }
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-700 focus:border-indigo-500 focus:outline-none rounded-lg px-3 py-2 text-sm text-zinc-100"
            />
          </div>
        )}

        {/* Local Endpoint Input for Ollama / llama.cpp */}
        {selectedProvider === "local_openai" && (
          <div className="space-y-1.5 pt-1">
            <label
              htmlFor="local-endpoint-input"
              className="text-xs font-medium text-zinc-200 block"
            >
              Local OpenAI-Compatible Endpoint (Ollama / llama.cpp / vLLM)
            </label>
            <input
              id="local-endpoint-input"
              type="text"
              value={localUrl}
              onChange={(e) => setLocalUrl(e.target.value)}
              placeholder="http://127.0.0.1:11434/v1"
              className="w-full bg-zinc-950 border border-zinc-700 focus:border-indigo-500 focus:outline-none rounded-lg px-3 py-2 text-sm text-zinc-100"
            />
          </div>
        )}
      </div>

      {/* Step 2: Big Chat Model + Small Background Organizer */}
      <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 space-y-5">
        <div>
          <h3 className="text-sm font-medium text-zinc-100">
            2. Main Model & Small Background Organizer
          </h3>
          <p className="text-xs text-zinc-400 mt-0.5">
            Your main model answers you in chat. A smaller, faster model quietly
            organizes concepts and links in the background.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Main Chat Model */}
          <div className="space-y-2 bg-zinc-950/60 border border-zinc-800/80 rounded-lg p-3.5">
            <label
              htmlFor="main-chat-model-input"
              className="text-xs font-medium text-zinc-200 block"
            >
              Main Chat Model (Big LLM)
            </label>
            <input
              id="main-chat-model-input"
              type="text"
              value={chatModel}
              onChange={(e) => setChatModel(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-md px-2.5 py-1.5 text-xs text-zinc-100"
            />
            {activeProviderInfo &&
              activeProviderInfo.recommended_chat_models.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {activeProviderInfo.recommended_chat_models.map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setChatModel(m)}
                      className={`text-[11px] px-2 py-0.5 rounded border ${
                        chatModel === m
                          ? "bg-indigo-950/60 border-indigo-500 text-indigo-200"
                          : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200"
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              )}
          </div>

          {/* Small Background Organizer Model */}
          <div className="space-y-2 bg-zinc-950/60 border border-zinc-800/80 rounded-lg p-3.5">
            <div className="flex items-center justify-between">
              <label
                htmlFor="small-organizer-model-input"
                className="text-xs font-medium text-zinc-200"
              >
                Background Organizer (Small LLM)
              </label>
              <select
                aria-label="Background Organizer Provider"
                value={organizerProvider}
                onChange={(e) => {
                  const nextProv = e.target.value;
                  setOrganizerProvider(nextProv);
                  const info = settings.providers.find(
                    (p) => p.provider === nextProv,
                  );
                  if (info && info.recommended_small_models.length > 0) {
                    setOrganizerModel(info.recommended_small_models[0]);
                  }
                }}
                className="bg-zinc-900 border border-zinc-800 rounded px-1.5 py-0.5 text-[11px] text-zinc-300"
              >
                {settings.providers.map((p) => (
                  <option key={p.provider} value={p.provider}>
                    {p.display_name}
                  </option>
                ))}
              </select>
            </div>
            <input
              id="small-organizer-model-input"
              type="text"
              value={organizerModel}
              onChange={(e) => setOrganizerModel(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-md px-2.5 py-1.5 text-xs text-zinc-100"
            />
            {organizerProviderInfo &&
              organizerProviderInfo.recommended_small_models.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {organizerProviderInfo.recommended_small_models.map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setOrganizerModel(m)}
                      className={`text-[11px] px-2 py-0.5 rounded border ${
                        organizerModel === m
                          ? "bg-emerald-950/60 border-emerald-600 text-emerald-200"
                          : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200"
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              )}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-zinc-800/80">
          <span className="text-xs text-zinc-400">
            {activeProviderInfo?.is_remote
              ? "Saving will enable sending active turn context to your selected provider."
              : "Local mode: your notes and messages stay 100% on this machine."}
          </span>
          <button
            type="button"
            disabled={isSaving}
            onClick={handleSaveAndTest}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-medium text-white transition"
          >
            {isSaving ? "Saving..." : "Save & Test Connection"}
          </button>
        </div>

        {feedback && (
          <div
            className={`p-3 rounded-lg border text-xs ${
              feedback.tone === "ok"
                ? "bg-emerald-950/40 border-emerald-800 text-emerald-200"
                : "bg-amber-950/40 border-amber-800 text-amber-200"
            }`}
          >
            {feedback.text}
          </div>
        )}
      </div>

      {/* Step 3: Simple Data Export */}
      <div className="bg-zinc-900/70 border border-zinc-800/90 rounded-xl p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-sm font-medium text-zinc-100">
            Your Data Ownership
          </h3>
          <p className="text-xs text-zinc-400 mt-0.5">
            Download all conversations, concepts, and connections as a portable
            JSON file at any time.
          </p>
          {exportResult && (
            <p className="text-xs text-emerald-400 mt-1.5">
              Saved to {exportResult.file_path} (
              {exportResult.counts.conversations ?? 0} chats,{" "}
              {exportResult.counts.concepts ?? 0} concepts)
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={async () => {
            const res = await onExportWorkspace();
            setExportResult(res);
          }}
          className="px-3.5 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-100 shrink-0 transition"
        >
          Export Data (JSON)
        </button>
      </div>
    </section>
  );
};
