"use client";

/**
 * Banners (ARCHITECTURE.md §14.6, §9):
 * - LLM not "up": hide the ask bar (parent handles this), show preset buttons
 *   + a "Can I afford X?" form calling /api/ask/direct (handled in AskBar/Dashboard).
 * - Session mode (mode.handover): "Session mode: nothing is saved" + "Clear
 *   session" button calling DELETE /api/data.
 */
import { useState } from "react";
import { api } from "@/lib/api/client";
import type { HealthResponse } from "@/lib/api/types";

export function Banners({
  health,
  onClearSession,
}: {
  health: HealthResponse | null;
  onClearSession: () => void;
}) {
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

  if (!health) return null;

  return (
    <div className="mb-4 space-y-2">
      {health.mode.handover && (
        <div className="flex items-center justify-between rounded-md border border-sky-300 bg-sky-50 px-4 py-2 text-sm text-sky-900 dark:border-sky-700 dark:bg-sky-950 dark:text-sky-200">
          <span>Session mode: nothing is saved.</span>
          <button
            className="rounded border border-sky-400 px-2 py-1 text-xs font-medium hover:bg-sky-100 dark:border-sky-600 dark:hover:bg-sky-900"
            onClick={clearSession}
            disabled={clearing}
          >
            {clearing ? "Clearing…" : "Clear session"}
          </button>
        </div>
      )}
    </div>
  );
}
