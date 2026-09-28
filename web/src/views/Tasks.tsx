import { ApiState, useApi } from "../components/ApiState";
import type { TaskRow } from "../api/types";

const RISK_STYLE: Record<string, string> = {
  low: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  medium: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  high: "bg-red-500/15 text-red-600 dark:text-red-400",
};

export default function Tasks() {
  const q = useApi<TaskRow[]>(["tasks"], "/tasks");
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Tasks</h1>
        <button className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900" disabled title="New-task drawer lands in P3">
          + New task
        </button>
      </div>
      <ApiState
        q={q}
        render={(rows) => (
          <div className="grid gap-3 sm:grid-cols-2">
            {rows.map((t) => (
              <div key={t.name} className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
                <div className="flex items-center justify-between">
                  <p className="font-semibold">{t.name}</p>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${RISK_STYLE[t.risk] ?? ""}`}>{t.risk}</span>
                </div>
                <p className="mt-1 font-mono text-xs text-zinc-500">{t.branch}</p>
                <p className="mt-2 text-sm">
                  {t.verdict === "PASS" ? (
                    <span className="font-semibold text-emerald-600 dark:text-emerald-400">PASS</span>
                  ) : t.verdict === "FAIL" ? (
                    <span className="font-semibold text-red-600 dark:text-red-400">FAIL</span>
                  ) : (
                    <span className="text-zinc-500">{t.verdict}</span>
                  )}
                </p>
              </div>
            ))}
            {rows.length === 0 && <p className="text-sm text-zinc-500">No contracts yet — start one with `harness task start`.</p>}
          </div>
        )}
      />
    </div>
  );
}
