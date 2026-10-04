"use client";

/**
 * Confirmation card (ARCHITECTURE.md §14.2, ACCEPTANCE_CRITERIA P0-4):
 * every extracted field editable; ungrounded or missing fields visibly
 * highlighted; resolved dates shown; per-commitment "must pay?" toggle;
 * nothing reaches the engine until Confirm (PUT /api/situation).
 */
import { useMemo, useState } from "react";
import { api } from "@/lib/api/client";
import { dayLabel, exprToText, plainMoney } from "@/lib/format";
import type { ExtractResponse, Situation, TraceStep } from "@/lib/api/types";

const inputCls =
  "w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-900 focus:border-emerald-600 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100";
const flagCls = "border-amber-400 bg-amber-50 dark:border-amber-600 dark:bg-amber-950/40";
const okCls = "border-zinc-300 dark:border-zinc-700";
const btnPrimary =
  "rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50";
const btnGhost =
  "rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800";
const flagPill =
  "ml-2 rounded border border-amber-400 bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-amber-800 dark:border-amber-600 dark:bg-amber-900 dark:text-amber-200";

function Flag({ children }: { children: React.ReactNode }) {
  return <span className={flagPill}>{children}</span>;
}

function rowSet<T>(arr: T[], i: number, patch: Partial<T>): T[] {
  return arr.map((row, j) => (j === i ? { ...row, ...patch } : row));
}

export function ConfirmationCard({
  draft,
  onConfirm,
  onCancel,
}: {
  draft: ExtractResponse;
  onConfirm: (s: Situation) => void;
  onCancel: () => void;
}) {
  const [asOf, setAsOf] = useState(draft.as_of);
  const [balance, setBalance] = useState(draft.balance.value?.toString() ?? "");
  const [essentials, setEssentials] = useState(draft.essentials_per_day.value?.toString() ?? "");
  const [inflows, setInflows] = useState(
    draft.inflows.map((i) => ({
      id: i.id,
      label: i.label,
      amount: i.expected_amount.value?.toString() ?? "",
      date: i.expected_date.value ?? "",
    })),
  );
  const [commits, setCommits] = useState(
    draft.commitments.map((c) => ({
      id: c.id,
      label: c.label,
      amount: c.amount.value?.toString() ?? "",
      date: c.due_date.value ?? "",
      flexible: c.flexible ?? true,
    })),
  );
  const [horizon, setHorizon] = useState("60");
  const [buffer, setBuffer] = useState("3");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trace: TraceStep[] = Array.isArray(draft.trace) ? draft.trace : [];

  const missingNow = useMemo(() => {
    const m: string[] = [];
    if (balance === "") m.push("balance");
    if (essentials === "") m.push("essentials");
    inflows.forEach((r, i) => {
      if (r.amount === "") m.push(`inflow[${i}].amount`);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(r.date)) m.push(`inflow[${i}].date`);
    });
    commits.forEach((r, i) => {
      if (r.amount === "") m.push(`commitment[${i}].amount`);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(r.date)) m.push(`commitment[${i}].date`);
    });
    return m;
  }, [balance, essentials, inflows, commits]);

  const blocked = missingNow.length > 0;

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      const situation: Situation = {
        as_of: asOf,
        currency: "NGN",
        balance: Math.floor(Number(balance)),
        essentials_per_day: Math.ceil(Number(essentials)),
        inflows: inflows.map((r, i) => ({
          id: r.id,
          label: r.label,
          expected_amount: Math.floor(Number(r.amount)),
          expected_date: r.date,
          uncertainty_note: draft.inflows[i].uncertainty_note,
        })),
        commitments: commits.map((r, i) => ({
          id: r.id,
          label: r.label,
          amount: Math.floor(Number(r.amount)),
          due_date: r.date,
          flexible: r.flexible,
        })),
        horizon_days: Math.max(1, Math.floor(Number(horizon) || 60)),
        buffer_days: Math.max(0, Math.floor(Number(buffer) || 3)),
      };
      onConfirm(await api.putSituation(situation));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="w-full max-w-3xl space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Check what was understood</h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Edit anything that is wrong. Amber means a value the model could not ground in your words,
          or a field that is still missing. Nothing is calculated until you confirm.
        </p>
      </div>

      <div className="space-y-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <div>
            <span className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Balance</span>
            <input
              className={`${inputCls} ${draft.balance.grounded ? okCls : flagCls}`}
              value={balance}
              onChange={(e) => setBalance(e.target.value)}
              inputMode="numeric"
            />
            {!draft.balance.grounded && <Flag>not grounded</Flag>}
            {missingNow.includes("balance") && <Flag>missing</Flag>}
          </div>
          <div>
            <span className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Essentials / day</span>
            <input
              className={`${inputCls} ${draft.essentials_per_day.grounded ? okCls : flagCls}`}
              value={essentials}
              onChange={(e) => setEssentials(e.target.value)}
              inputMode="numeric"
            />
            {!draft.essentials_per_day.grounded && <Flag>not grounded</Flag>}
            {missingNow.includes("essentials") && <Flag>missing</Flag>}
            {draft.essentials_per_day.converted_from && (
              <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
                converted from {plainMoney(draft.essentials_per_day.converted_from.amount)} per{" "}
                {draft.essentials_per_day.converted_from.period}
              </p>
            )}
          </div>
          <div>
            <span className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Starts (as of)</span>
            <input type="date" className={inputCls} value={asOf} onChange={(e) => setAsOf(e.target.value)} />
          </div>
          <div>
            <span className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Horizon / buffer (days)</span>
            <div className="flex gap-2">
              <input
                className={inputCls}
                value={horizon}
                onChange={(e) => setHorizon(e.target.value)}
                inputMode="numeric"
                aria-label="horizon days"
              />
              <input
                className={inputCls}
                value={buffer}
                onChange={(e) => setBuffer(e.target.value)}
                inputMode="numeric"
                aria-label="buffer days"
              />
            </div>
          </div>
        </div>

        <div>
          <h3 className="text-sm font-semibold">Money that might come in</h3>
          {inflows.map((r, i) => (
            <div key={r.id} className="mt-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_120px_170px]">
                <input
                  className={inputCls}
                  value={r.label}
                  onChange={(e) => setInflows(rowSet(inflows, i, { label: e.target.value }))}
                  placeholder="who / what"
                  aria-label="inflow label"
                />
                <input
                  className={`${inputCls} ${draft.inflows[i].expected_amount.grounded ? okCls : flagCls}`}
                  value={r.amount}
                  onChange={(e) => setInflows(rowSet(inflows, i, { amount: e.target.value }))}
                  inputMode="numeric"
                  placeholder="amount"
                  aria-label="inflow amount"
                />
                <input
                  type="date"
                  className={`${inputCls} ${draft.inflows[i].expected_date.grounded ? okCls : flagCls}`}
                  value={r.date}
                  onChange={(e) => setInflows(rowSet(inflows, i, { date: e.target.value }))}
                  aria-label="inflow date"
                />
              </div>
              <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
                {r.id} · resolved: {dayLabel(r.date)}
                {draft.inflows[i].expected_date.date_expr &&
                  ` · from ${exprToText(draft.inflows[i].expected_date.date_expr)}`}
              </p>
              <div className="mt-1">
                {!draft.inflows[i].expected_amount.grounded && <Flag>not grounded</Flag>}
                {!draft.inflows[i].expected_date.grounded && <Flag>date not grounded</Flag>}
                {missingNow.includes(`inflow[${i}].amount`) && <Flag>missing amount</Flag>}
                {missingNow.includes(`inflow[${i}].date`) && <Flag>missing date</Flag>}
              </div>
              {draft.inflows[i].uncertainty_note && (
                <p className="mt-1 text-[11px] italic text-zinc-500 dark:text-zinc-400">
                  “{draft.inflows[i].uncertainty_note}”
                </p>
              )}
            </div>
          ))}
        </div>

        <div>
          <h3 className="text-sm font-semibold">Things to pay</h3>
          {commits.map((r, i) => (
            <div key={r.id} className="mt-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_120px_170px_auto] sm:items-center">
                <input
                  className={inputCls}
                  value={r.label}
                  onChange={(e) => setCommits(rowSet(commits, i, { label: e.target.value }))}
                  placeholder="what for"
                  aria-label="commitment label"
                />
                <input
                  className={`${inputCls} ${draft.commitments[i].amount.grounded ? okCls : flagCls}`}
                  value={r.amount}
                  onChange={(e) => setCommits(rowSet(commits, i, { amount: e.target.value }))}
                  inputMode="numeric"
                  placeholder="amount"
                  aria-label="commitment amount"
                />
                <input
                  type="date"
                  className={`${inputCls} ${draft.commitments[i].due_date.grounded ? okCls : flagCls}`}
                  value={r.date}
                  onChange={(e) => setCommits(rowSet(commits, i, { date: e.target.value }))}
                  aria-label="commitment date"
                />
                <label className="flex items-center gap-1 text-xs whitespace-nowrap text-zinc-600 dark:text-zinc-400">
                  <input
                    type="checkbox"
                    checked={!r.flexible}
                    onChange={(e) => setCommits(rowSet(commits, i, { flexible: !e.target.checked }))}
                  />
                  must pay?
                </label>
              </div>
              <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
                {r.id} · resolved: {dayLabel(r.date)}
                {draft.commitments[i].due_date.date_expr &&
                  ` · from ${exprToText(draft.commitments[i].due_date.date_expr)}`}
              </p>
              <div className="mt-1">
                {!draft.commitments[i].amount.grounded && <Flag>not grounded</Flag>}
                {!draft.commitments[i].due_date.grounded && <Flag>date not grounded</Flag>}
                {draft.commitments[i].flexible === null && <Flag>must-pay not stated</Flag>}
                {missingNow.includes(`commitment[${i}].amount`) && <Flag>missing amount</Flag>}
                {missingNow.includes(`commitment[${i}].date`) && <Flag>missing date</Flag>}
              </div>
            </div>
          ))}
        </div>

        {trace.length > 0 && (
          <details>
            <summary className="cursor-pointer text-[11px] text-zinc-500 dark:text-zinc-400">
              extraction trace
            </summary>
            <pre className="mt-1 max-h-64 overflow-auto rounded bg-zinc-100 p-2 font-mono text-[10px] leading-4 dark:bg-zinc-800">
              {JSON.stringify(trace, null, 2)}
            </pre>
          </details>
        )}
      </div>

      {error && (
        <p className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
        </p>
      )}
      {blocked && (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          Fill the missing fields to continue — empty values are never sent to the engine.
        </p>
      )}

      <div className="flex items-center gap-3">
        <button className={btnPrimary} onClick={confirm} disabled={busy || blocked}>
          {busy ? "Saving…" : "Confirm — show my scenarios"}
        </button>
        <button className={btnGhost} onClick={onCancel}>
          Back
        </button>
      </div>
    </section>
  );
}
