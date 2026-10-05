"use client";

/**
 * App shell / state machine (ARCHITECTURE.md §14): setup -> confirmation ->
 * dashboard (+ ask bar, trace panel, banners). All state lives in React
 * memory only — no localStorage/IndexedDB anywhere.
 */
import { useCallback, useEffect, useState } from "react";
import { api, MOCK } from "@/lib/api/client";
import { API_BASE } from "@/lib/api/http";
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
  const [handoverUrl, setHandoverUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const startedAt = Date.now();
    const HEALTH_TIMEOUT_MS = 90_000;
    const HEALTH_RETRY_MS = 3_000;

    const load = () => {
      api
        .health()
        .then((h) => {
          if (cancelled) return;
          setHealth(h);
          // ?handover=1 toggle is wired from the server health response
          // (STRETCH_HANDOVER=1 forces demo->user, in-memory only, metadata-only traces).
          if (typeof window !== "undefined") {
            const params = new URLSearchParams(window.location.search);
            if (params.get("handover") === "1" && h.mode.handover) {
              setHandoverUrl(window.location.pathname + "?handover=1");
            }
          }
        })
        .catch((e: unknown) => {
          if (cancelled) return;
          // A free hosted server may be cold-starting. Keep retrying for 90s
          // instead of failing on the first timeout.
          if (Date.now() - startedAt < HEALTH_TIMEOUT_MS) {
            setTimeout(load, HEALTH_RETRY_MS);
          } else {
            setError(e instanceof Error ? e.message : String(e));
          }
        });
    };

    load();
    return () => {
      cancelled = true;
    };
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

  const waking = health === null && error === null;

  const backToSetup = useCallback(() => {
    setStage("setup");
    setDraft(null);
    // Drop ?handover=1 from the URL so the banner is only shown while it is set.
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", window.location.pathname);
    }
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

      <Banners
        health={health}
        onClearSession={backToSetup}
        handoverUrl={handoverUrl}
      />

      <main className="flex-1">
        {stage === "setup" && waking && (
          <div
            data-testid="waking-server"
            className="rounded-xl border border-zinc-200 bg-white p-6 text-sm text-zinc-600 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300"
          >
            Waking the free server, this can take about a minute…
          </div>
        )}
        {stage === "setup" && !waking && (
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
        {MOCK ? "mock data layer — fixtures only, no backend" : `backend: ${API_BASE}`} ·
        nothing is stored in your browser · scenarios, not forecasts ·{" "}
        <a
          href="https://github.com/devinuwa/stretch-runway"
          target="_blank"
          rel="noreferrer"
          className="underline hover:text-zinc-700 dark:hover:text-zinc-200"
        >
          source on GitHub
        </a>
      </footer>
    </div>
  );
}
