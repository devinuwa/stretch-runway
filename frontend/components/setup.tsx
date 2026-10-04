"use client";

/**
 * Setup screen (API_CONTRACT.md §3, ARCHITECTURE.md §14.1):
 * paste-text box (POST /api/setup/extract), "or enter manually" form
 * (POST /api/setup/manual), and — demo profile only — "Load sample data"
 * (POST /api/situation/demo).
 */
import { useState } from "react";
import { api } from "@/lib/api/client";
import type {
  ExtractResponse,
  HealthResponse,
  ManualSetupRequest,
  Situation,
  DateExpr,
  EssentialsPeriod,
} from "@/lib/api/types";

function apiMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

const inputCls =
  "w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-emerald-600 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100";
const labelCls = "mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400";
const btnPrimary =
  "rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50";
const btnGhost =
  "rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800";

type InflowRow = { label: string; amount: string; date: string };
type CommitRow = { label: string; amount: string; date: string; mustPay: boolean };

export function SetupScreen({
  health,
  onDraft,
  onSituationLoaded,
  onError,
}: {
  health: HealthResponse | null;
  onDraft: (draft: ExtractResponse) => void;
  onSituationLoaded: (situation: Situation) => void;
  onError: (msg: string | null) => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<"" | "extract" | "demo">("");
  const [showManual, setShowManual] = useState(false);

  const demoProfile = health?.mode.profile === "demo";

  async function extract() {
    if (!text.trim()) return;
    setBusy("extract");
    onError(null);
    try {
      onDraft(await api.extract(text));
    } catch (e) {
      onError(apiMessage(e));
    } finally {
      setBusy("");
    }
  }

  async function loadDemo() {
    setBusy("demo");
    onError(null);
    try {
      onSituationLoaded(await api.loadDemo());
    } catch (e) {
      onError(apiMessage(e));
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="w-full max-w-2xl space-y-6">
      <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="text-lg font-semibold">Describe your situation</h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Plain words are fine — money you have, money that might come in, things you must pay.
        </p>
        <textarea
          className={`${inputCls} mt-3 min-h-32`}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste your situation here…"
        />
        <div className="mt-3 flex items-center gap-3">
          <button className={btnPrimary} onClick={extract} disabled={busy !== "" || !text.trim()}>
            {busy === "extract" ? "Reading…" : "Read my situation"}
          </button>
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            A small local model turns this into fields you can check.
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button className="text-sm font-medium text-emerald-700 hover:underline dark:text-emerald-400" onClick={() => setShowManual((v) => !v)}>
          {showManual ? "Hide manual entry" : "or enter manually"}
        </button>
        {demoProfile && (
          <button className={`${btnGhost} ml-auto`} onClick={loadDemo} disabled={busy !== ""}>
            {busy === "demo" ? "Loading…" : "Load sample data"}
          </button>
        )}
      </div>

      {showManual && (
        <ManualForm
          onDraft={(d) => {
            setShowManual(false);
            onDraft(d);
          }}
          onError={onError}
        />
      )}
    </section>
  );
}

function ManualForm({
  onDraft,
  onError,
}: {
  onDraft: (d: ExtractResponse) => void;
  onError: (msg: string | null) => void;
}) {
  const [asOf, setAsOf] = useState("");
  const [balance, setBalance] = useState("");
  const [essAmount, setEssAmount] = useState("");
  const [essPeriod, setEssPeriod] = useState<EssentialsPeriod>("day");
  const [inflows, setInflows] = useState<InflowRow[]>([{ label: "", amount: "", date: "" }]);
  const [commits, setCommits] = useState<CommitRow[]>([{ label: "", amount: "", date: "", mustPay: false }]);
  const [busy, setBusy] = useState(false);

  const num = (s: string): number | null => {
    const t = s.trim().replace(/,/g, "");
    if (!/^\d+(\.\d+)?$/.test(t)) return null;
    return Math.floor(Number(t));
  };

  async function submit() {
    onError(null);
    const bal = num(balance);
    const ess = num(essAmount);
    if (bal === null || bal < 0 || ess === null || ess <= 0) {
      onError("Balance must be ≥ 0 and essentials must be a positive amount.");
      return;
    }
    const cleanInflows = inflows
      .filter((r) => r.label.trim() && num(r.amount) !== null && /^\d{4}-\d{2}-\d{2}$/.test(r.date))
      .map((r) => ({
        label: r.label.trim(),
        expected_amount: num(r.amount) as number,
        date_expr: { kind: "iso", value: r.date } as DateExpr,
        uncertainty_note: null,
      }));
    const cleanCommits = commits
      .filter((r) => r.label.trim() && num(r.amount) !== null && /^\d{4}-\d{2}-\d{2}$/.test(r.date))
      .map((r) => ({
        label: r.label.trim(),
        amount: num(r.amount) as number,
        date_expr: { kind: "iso", value: r.date } as DateExpr,
        flexible: !r.mustPay,
      }));
    if (!bal && bal !== 0) return;
    const body: ManualSetupRequest = {
      ...(asOf ? { as_of: asOf } : {}),
      balance: bal,
      essentials: { amount: ess, period: essPeriod },
      inflows: cleanInflows,
      commitments: cleanCommits,
    };
    setBusy(true);
    try {
      onDraft(await api.manual(body));
    } catch (e) {
      onError(apiMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h3 className="font-semibold">Enter manually</h3>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <label className={labelCls}>Money I have now</label>
          <input className={inputCls} value={balance} onChange={(e) => setBalance(e.target.value)} inputMode="numeric" placeholder="e.g. 26000" />
        </div>
        <div>
          <label className={labelCls}>Essentials</label>
          <div className="flex gap-2">
            <input className={inputCls} value={essAmount} onChange={(e) => setEssAmount(e.target.value)} inputMode="numeric" placeholder="amount" />
            <select className={inputCls} value={essPeriod} onChange={(e) => setEssPeriod(e.target.value as EssentialsPeriod)}>
              <option value="day">/day</option>
              <option value="week">/week</option>
              <option value="month">/month</option>
            </select>
          </div>
        </div>
        <div>
          <label className={labelCls}>Today&apos;s date (optional)</label>
          <input type="date" className={inputCls} value={asOf} onChange={(e) => setAsOf(e.target.value)} />
        </div>
      </div>

      <fieldset>
        <legend className={labelCls}>Money that might come in</legend>
        <div className="space-y-2">
          {inflows.map((row, i) => (
            <div key={i} className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_120px_150px_40px]">
              <input className={inputCls} placeholder="who / what" value={row.label} onChange={(e) => setInflows(upd(inflows, i, { label: e.target.value }))} />
              <input className={inputCls} placeholder="amount" inputMode="numeric" value={row.amount} onChange={(e) => setInflows(upd(inflows, i, { amount: e.target.value }))} />
              <input type="date" className={inputCls} value={row.date} onChange={(e) => setInflows(upd(inflows, i, { date: e.target.value }))} />
              <button aria-label="remove" className="text-zinc-400 hover:text-red-600" onClick={() => setInflows(inflows.filter((_, j) => j !== i))}>
                ✕
              </button>
            </div>
          ))}
          <button className="text-xs font-medium text-emerald-700 hover:underline dark:text-emerald-400" onClick={() => setInflows([...inflows, { label: "", amount: "", date: "" }])}>
            + add inflow
          </button>
        </div>
      </fieldset>

      <fieldset>
        <legend className={labelCls}>Things to pay</legend>
        <div className="space-y-2">
          {commits.map((row, i) => (
            <div key={i} className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_120px_150px_auto_40px] sm:items-center">
              <input className={inputCls} placeholder="what for" value={row.label} onChange={(e) => setCommits(upd(commits, i, { label: e.target.value }))} />
              <input className={inputCls} placeholder="amount" inputMode="numeric" value={row.amount} onChange={(e) => setCommits(upd(commits, i, { amount: e.target.value }))} />
              <input type="date" className={inputCls} value={row.date} onChange={(e) => setCommits(upd(commits, i, { date: e.target.value }))} />
              <label className="flex items-center gap-1 text-xs text-zinc-600 dark:text-zinc-400">
                <input type="checkbox" checked={row.mustPay} onChange={(e) => setCommits(upd(commits, i, { mustPay: e.target.checked }))} />
                must pay
              </label>
              <button aria-label="remove" className="text-zinc-400 hover:text-red-600" onClick={() => setCommits(commits.filter((_, j) => j !== i))}>
                ✕
              </button>
            </div>
          ))}
          <button className="text-xs font-medium text-emerald-700 hover:underline dark:text-emerald-400" onClick={() => setCommits([...commits, { label: "", amount: "", date: "", mustPay: false }])}>
            + add commitment
          </button>
        </div>
      </fieldset>

      <button className={btnPrimary} onClick={submit} disabled={busy}>
        {busy ? "Checking…" : "Review these numbers"}
      </button>
    </div>
  );
}

function upd<T>(arr: T[], i: number, patch: Partial<T>): T[] {
  return arr.map((row, j) => (j === i ? { ...row, ...patch } : row));
}
