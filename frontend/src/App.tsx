import React from "react";

export default function App(): React.ReactElement {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <header className="border-b border-slate-800 pb-4 mb-6">
        <h1 className="text-xl font-semibold tracking-tight">Noema</h1>
        <p className="text-sm text-slate-400">
          Local-first personal knowledge environment
        </p>
      </header>
    </div>
  );
}
