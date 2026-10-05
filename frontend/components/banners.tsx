"use client";

/**
 * Banners (ARCHITECTURE.md §14.6, §9):
 * - LLM not "up": hide the ask bar (parent handles this), show preset buttons
 *   + a "Can I afford X?" form calling /api/ask/direct (handled in AskBar/Dashboard).
 * - Session mode (mode.handover): "Session mode: nothing is saved" + "Clear
 *   session" button calling DELETE /api/data.
 * - ?handover=1 toggle (handoverUrl): explicit session-mode entry point.
 */
import { useState } from "react";
import { api } from "@/lib/api/client";
import type { HealthResponse } from "@/lib/api/types";

export function Banners({
  health,
  onClearSession,
  handoverUrl,
}: {
  health: HealthResponse | null;
  onClearSession: () => void;
  handoverUrl: string | null;
}) {
  const isHandover = Boolean(health?.mode.handover || handoverUrl);
  const [clearing, setClearing] = useState(false);

  async function clearSession() {
    setClearing(true);
    try {
      await api.deleteData();
    } finally {
      setClearing(false);
      onClearSession();
    }
  }

  function jumpToHandover() {
    // Explicit ?handover=1 toggle. In session mode the server drops the
    // situation to in-memory only; leaving the page shows the banner.
    if (typeof window === "undefined") return;
    window.location.search = "?handover=1";
  }

  const banner = (
    <div className="mb-4 space-y-2">
      {health?.hosted && (
        <div
          data-testid="hosted-banner"
          className="rounded-md border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100"
        >
          Hosted preview: sample data only. The local model is switched off here, so nothing you
          see is AI-generated. Do not enter real numbers. Run it locally for the full private
          version.
        </div>
      )}
      {isHandover && (
        <div className="flex items-center justify-between rounded-md border border-sky-300 bg-sky-50 px-4 py-2 text-sm text-sky-900 dark:border-sky-700 dark:bg-sky-950 dark:text-sky-200">
          <span>Session mode: nothing is saved.</span>
          <span className="flex gap-2">
            {handoverUrl ? (
              <button
                className="rounded border border-sky-400 px-2 py-1 text-xs font-medium hover:bg-sky-100 dark:border-sky-600 dark:hover:bg-sky-900"
                onClick={jumpToHandover}
              >
                ?handover=1
              </button>
            ) : null}
            <button
              className="rounded border border-sky-400 px-2 py-1 text-xs font-medium hover:bg-sky-100 dark:border-sky-600 dark:hover:bg-sky-900"
              onClick={() => {
                setClearing(true);
                api
                  .deleteData()
                  .finally(() => {
                    setClearing(false);
                    onClearSession();
                  });
              }}
              disabled={clearing}
            >
              Clear session
            </button>
          </span>
        </div>
      )}
    </div>
  );

  return banner;
}
