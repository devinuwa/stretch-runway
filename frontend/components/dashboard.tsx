"use client";

/**
 * Dashboard (ARCHITECTURE.md §14.3, ACCEPTANCE_CRITERIA P0-6): one recharts
 * line chart (balance series per scenario, a marker where the balance first
 * goes below zero), five preset scenario cards (runs out on / days / gap),
 * a safe-spend card and a reserve card. Everything from engine output; never
 * phrased as a prediction.
 */
import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api/client";
import { addDays } from "@/lib/api/engine";
import { dayLabel, money } from "@/lib/format";
import type {
  RunwayResult,
  ScenarioRun,
  ScenariosResponse,
  Situation,
} from "@/lib/api/types";

const cardCls =
  "rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900";
const COLORS = ["#047857", "#b45309", "#1d4ed8", "#9333ea", "#dc2626"];

type TooltipEntry = { name?: string | number; value?: number | string; color?: string };

function SeriesTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-zinc-200 bg-white px-2 py-1 text-xs shadow dark:border-zinc-700 dark:bg-zinc-800">
      <div className="font-medium">day {String(label)}</div>
      {payload.map((p) => (
        <div key={String(p.name)} style={{ color: p.color }}>
          {String(p.name)}: {typeof p.value === "number" ? p.value.toLocaleString("en-US") : String(p.value)}
        </div>
      ))}
    </div>
  );
}

export function Dashboard({ situation }: { situation: Situation }) {
  const [data, setData] = useState<ScenariosResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .scenarios()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [situation]);

  if (error) return <p className="text-sm text-red-700 dark:text-red-300">{error}</p>;
  if (!data) return <p className="text-sm text-zinc-500">Calculating scenarios…</p>;

  const currency = situation.currency;
  const asOf = situation.as_of;

  // One chart row per day with each scenario's series value.
  const rows = data.results[0].result.series.map((_, day) => {
    const row: Record<string, number | string> = { day };
    for (const run of data.results) {
      row[run.scenario.label] = run.result.series[day];
    }
    return row;
  });

  // Shortfall markers: where each series first goes below zero.
  const markers = data.results
    .map((run, idx) => {
      const below = run.result.series.findIndex((v) => v < 0);
      return below === -1
        ? null
        : { x: below, label: run.scenario.label, color: COLORS[idx % COLORS.length] };
    })
    .filter((m): m is NonNullable<typeof m> => m !== null);

  return (
    <div className="space-y-6">
      <div className={cardCls}>
        <h2 className="mb-2 text-sm font-semibold">Balance by day under each preset</h2>
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="day"
                tick={{ fontSize: 11 }}
                tickFormatter={(d: number) => dayLabel(addDays(asOf, Number(d)))}
              />
              <YAxis
                tick={{ fontSize: 11 }}
                width={72}
                tickFormatter={(v: number) => v.toLocaleString("en-US")}
              />
              <Tooltip content={<SeriesTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <ReferenceLine y={0} stroke="#111827" strokeDasharray="4 4" />
              {data.results.map((run, idx) => (
                <Line
                  key={run.scenario.label}
                  type="monotone"
                  dataKey={run.scenario.label}
                  stroke={COLORS[idx % COLORS.length]}
                  dot={false}
                  strokeWidth={2}
                  isAnimationActive={false}
                />
              ))}
              {markers.map((m) => (
                <ReferenceLine
                  key={m.label}
                  x={m.x}
                  stroke={m.color}
                  strokeDasharray="2 2"
                  label={{ value: "runs out", position: "insideTopLeft", fill: m.color, fontSize: 10 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {data.results.map((run) => (
          <ScenarioCard key={run.scenario.label} run={run} currency={currency} />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className={cardCls}>
          <h3 className="text-sm font-semibold">Safe daily spend</h3>
          {data.safe_spend.inflow_today ? (
            <p className="mt-2 text-sm">
              Money is expected today, so this tool sets no daily limit today.
            </p>
          ) : (
            <>
              <p className="mt-2 text-2xl font-bold">{money(data.safe_spend.max_daily_total, currency)}</p>
              <p className="text-xs text-zinc-600 dark:text-zinc-400">
                per day until {dayLabel(data.safe_spend.target_date)} ({data.safe_spend.days_to_cover} days)
              </p>
              <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
                {data.safe_spend.covers_essentials
                  ? "This covers your essentials."
                  : "This does not cover your essentials."}
                {data.safe_spend.already_short && " Already short before any spending."}
              </p>
              <p className="mt-2 text-[11px] text-zinc-500 dark:text-zinc-400">
                It protects only the time until the next money arrives.
              </p>
            </>
          )}
        </div>

        <div className={cardCls}>
          <h3 className="text-sm font-semibold">Essentials reserve</h3>
          <p className="mt-2 text-2xl font-bold">
            {data.reserve.covered ? "covered" : `short ${money(Math.abs(data.reserve.surplus_or_gap), currency)}`}
          </p>
          <p className="text-xs text-zinc-600 dark:text-zinc-400">
            {data.reserve.covered
              ? `with ${money(data.reserve.surplus_or_gap, currency)} to spare`
              : "for essentials and must-pay items before the next money arrives"}
          </p>
          <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-zinc-600 dark:text-zinc-400">
            <dt>Reserve needed</dt>
            <dd className="text-right font-medium text-zinc-900 dark:text-zinc-100">
              {money(data.reserve.reserve, currency)}
            </dd>
            <dt>Essentials part</dt>
            <dd className="text-right">{money(data.reserve.essentials_part, currency)}</dd>
            <dt>Must-pay part</dt>
            <dd className="text-right">{money(data.reserve.must_pay_part, currency)}</dd>
            <dt>Buffer days</dt>
            <dd className="text-right">{data.reserve.buffer_days}</dd>
          </dl>
        </div>
      </div>
    </div>
  );
}

function ScenarioCard({ run, currency }: { run: ScenarioRun; currency: string }) {
  const r: RunwayResult = run.result;
  return (
    <div className={cardCls}>
      <h3 className="text-xs font-semibold text-zinc-600 dark:text-zinc-400">
        If the money arrives {run.scenario.label}
      </h3>
      {r.runs_out_on === null ? (
        <p className="mt-2 text-sm font-bold">all {r.horizon_days} days covered</p>
      ) : (
        <>
          <p className="mt-2 text-sm font-bold">runs out {dayLabel(r.runs_out_on)}</p>
          <p className="text-xs text-zinc-600 dark:text-zinc-400">after {r.runway_days} days</p>
        </>
      )}
      {r.gap_days !== null && r.next_money_after_shortfall !== null && (
        <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
          {r.gap_days}-day gap before {dayLabel(r.next_money_after_shortfall)}
        </p>
      )}
      {r.shortfall_amount !== null && (
        <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
          short {money(r.shortfall_amount, currency)} that day
        </p>
      )}
    </div>
  );
}
