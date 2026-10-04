"use client";

/**
 * App shell / state machine (ARCHITECTURE.md §14): setup -> confirmation ->
 * dashboard (+ ask bar, trace panel, banners). All state lives in React
 * memory only — no localStorage/IndexedDB anywhere.
 */
import { useCallback, useEffect, useState } from "react";
import { api, MOCK } from "@/lib/api/client";
import { SetupScreen } from "@/components/setup";
import { ConfirmationCard } from "@/components/confirmation";
import { Dashboard } from "@/components/dashboard";
import { AskBar } from "@/components/ask-bar";
import { TracePanel } from "@/components/trace-panel";
import { Banners } from "@/components/banners";
import type {
  ExtractResponse,
  HealthResponse,
  Situation,
} from "@/lib/api/types";

type Stage = "setup" | "confirm" | "dashboard";

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [stage, setStage] = useState<Stage>("setup");
  const [draft, setDraft] = useState<ExtractResponse | null>(null);
  const [situation, setSituation] = useState<Situation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const onDraft = useCallback((d: ExtractResponse) => {
    setDraft(d);
    setStage("confirm");
  }, []);

  const onConfirmed = useCallback((s: Situation) => {
    setSituation(s);
    setStage("dashboard");
  }, []);

  const onDemoLoaded = useCallback((s: Situation) => {
    setSituation(s);
    setStage("dashboard");
  }, []);

  const backToSetup = useCallback(() => {
    setStage("setup");
    setDraft(null);
  }, []);

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-5xl flex-col px-4 py-8">
      <header className="mb-8 flex items-baseline justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Stretch</h1>
        {situation?.synthetic && (
          <span
            data-testid="sample-data-badge"
            className="rounded-full border border-amber-300 bg-amber-100 px-3 py-1 text-xs font-bold tracking-wide text-amber-800 uppercase dark:border-amber-700 dark:bg-amber-950 dark:text-amber-300"
          >
            Sample data
          </span>
        )}
      </header>

      <Banners health={health} onClearSession={backToSetup} />

      <main className="flex-1">
        {stage === "setup" && (
          <SetupScreen health={health} onDraft={onDraft} onSituationLoaded={onDemoLoaded} onError={setError} />
        )}
        {stage === "confirm" && draft && (
          <ConfirmationCard draft={draft} onConfirm={onConfirmed} onCancel={backToSetup} />
        )}
        {stage === "dashboard" && situation && (
          <>
            <Dashboard situation={situation} />
            <div className="mt-6">
              <AskBar health={health} llmUp={health?.llm.state === "up"} />
            </div>
          </>
        )}
      </main>

      {error && (
        <div className="mt-6 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      )}

      <footer className="mt-10 text-xs text-zinc-500 dark:text-zinc-400">
        {MOCK ? "mock data layer — fixtures only, no backend" : "backend: http://127.0.0.1:8000"} ·
        nothing is stored in your browser · scenarios, not forecasts
      </footer>
    </div>
  );
}
