"use client";

/**
 * Basic trace panel (P0-8): collapsible JSON per TraceStep.
 */
import { useState } from "react";
import type { TraceStep } from "@/lib/api/types";

export function TracePanel({
  steps,
  title = "Trace",
}: {
  steps: TraceStep[];
  title?: string;
}) {
  if (steps.length === 0) return null;
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="text-sm font-semibold">{title}</h2>
      <div className="mt-2 space-y-2">
        {steps.map((s, i) => (
          <TraceRow key={`${s.step}-${i}`} step={s} index={i} />
        ))}
      </div>
    </div>
  );
}

function TraceRow({ step, index }: { step: TraceStep; index: number }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800">
      <button
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="font-mono text-zinc-400">{index + 1}.</span>
        <span className="font-semibold">{step.step}</span>
        <span className="text-zinc-600 dark:text-zinc-400">{step.label}</span>
        <span className="ml-auto font-mono text-zinc-400">{step.ms}ms</span>
        <span aria-hidden className="text-zinc-400">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <pre className="max-h-72 overflow-auto border-t border-zinc-200 bg-zinc-100 px-3 py-2 font-mono text-[10px] leading-4 dark:border-zinc-800 dark:bg-zinc-800">
          {JSON.stringify(step.payload, null, 2)}
        </pre>
      )}
    </div>
  );
}
